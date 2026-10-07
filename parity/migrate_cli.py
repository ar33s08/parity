"""migrate subcommand for parity.cli (appended handlers)."""

import json
import sys

from .migrate import scan_repo, build_plan, apply_plan


def cmd_migrate(argv):
    """parity migrate scan|plan|apply <repo> [--url ...] [--model ...]"""
    if len(argv) < 2:
        print("usage: parity migrate <scan|plan|apply> <repo> [--url URL] [--model M]",
              file=sys.stderr)
        return 2
    action, repo = argv[0], argv[1]
    url, model, plan_path = "http://127.0.0.1:8000/v1", "local-model", None
    args = argv[2:]
    i = 0
    while i < len(args):
        if args[i] == "--url": url = args[i + 1]; i += 2
        elif args[i] == "--model": model = args[i + 1]; i += 2
        elif args[i] == "--plan": plan_path = args[i + 1]; i += 2
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
    print("unknown action", file=sys.stderr)
    return 2
