"""migrate subcommand for parity.cli (appended handlers)."""

import json
import subprocess
import sys

from .migrate import scan_repo, build_plan, apply_plan


def _certify(repo, url, model, key, ref_url, ref_model, ref_key, corpus, out):
    """apply + gate + certificate, one command. Certificate is pinned to the
    repo diff and corpus hash. Migration without a PASS verdict = exit 1 so CI
    blocks the merge."""
    from .cli import main as compare_main
    pre = scan_repo(repo)
    plan = build_plan(pre, url, model)
    changed = apply_plan(plan)
    print("migrated %d call sites across %d files" % (
        len(pre), len(changed)), file=sys.stderr, flush=True)
    if not corpus:
        print("no --corpus given: refusing to certify blind. Run `parity compare` "
              "manually. Migration applied, NO certificate.", file=sys.stderr)
        return 1
    argv = ["compare", "--corpus", corpus,
            "--reference-url", ref_url, "--reference-model", ref_model,
            "--reference-key", ref_key or "",
            "--candidate-url", url, "--candidate-model", model,
            "--candidate-key", key or "", "--out", out + ".compare.json"]
    rc = compare_main(argv)
    rep = json.load(open(out + ".compare.json"))
    cert = rep["certificate"]
    cert["migration"] = {
        "repo": repo,
        "call_sites_migrated": len(pre),
        "hosts_before": sorted({f["host"] for f in pre}),
        "files": changed,
    }
    # restick cert hash over the extended body
    import hashlib
    cert.pop("cert_sha256", None)
    cert["cert_sha256"] = hashlib.sha256(
        json.dumps(cert, sort_keys=True).encode()).hexdigest()
    with open(out, "w") as f:
        json.dump(cert, f, indent=2)
    print(json.dumps(cert, indent=2))
    if cert["verdict"] == "FAIL":
        print("\nGATE FAILED: regression detected. Roll back (git checkout .) "
              "before merging.", file=sys.stderr)
        return 1
    print("\ncertificate written to %s" % out, file=sys.stderr)
    return rc


def cmd_migrate(argv):
    """parity migrate scan|plan|apply|certify <repo> [options]"""
    if len(argv) < 2:
        print("usage: parity migrate <scan|plan|apply|certify> <repo> "
              "[--url URL] [--model M] [--key K] "
              "[--reference-url U --reference-model M --reference-key K] "
              "[--corpus C.jsonl] [--out cert.json]", file=sys.stderr)
        return 2
    action, repo = argv[0], argv[1]
    url, model, plan_path = "http://127.0.0.1:8000/v1", "local-model", None
    opts = {}
    args = argv[2:]
    i = 0
    while i < len(args):
        if args[i] == "--url": url = args[i + 1]; i += 2
        elif args[i] == "--model": model = args[i + 1]; i += 2
        elif args[i] == "--plan": plan_path = args[i + 1]; i += 2
        elif args[i].startswith("--") and i + 1 < len(args):
            opts[args[i][2:]] = args[i + 1]; i += 2
        else: i += 1

    if action == "scan":
        findings = scan_repo(repo)
        print(json.dumps(findings, indent=2))
        hosts = sorted({f["host"] for f in findings})
        print("\n%d cloud call sites; hosts: %s" % (len(findings), ", ".join(hosts) or "-"),
              file=sys.stderr)
        return 0
    if action == "plan":
        plan = build_plan(scan_repo(repo), url, model)
        print(json.dumps(plan, indent=2))
        return 0
    if action == "apply":
        if plan_path:
            plan = json.load(open(plan_path))
        else:
            plan = build_plan(scan_repo(repo), url, model)
        changed = apply_plan(plan)
        print(json.dumps({"changed": changed}, indent=2))
        print("\nNow GATE it: run `parity compare` on this repo's corpus before "
              "opening the PR. No certificate, no merge.", file=sys.stderr)
        return 0
    if action == "certify":
        return _certify(repo, url, model, opts.get("key", ""),
                        opts.get("reference-url", url),
                        opts.get("reference-model", model),
                        opts.get("reference-key", ""),
                        opts.get("corpus"), opts.get("out", "parity-cert.json"))
    print("unknown action", file=sys.stderr)
    return 2
