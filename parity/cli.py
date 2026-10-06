"""parity CLI: `parity compare --corpus c.jsonl --reference ... --candidate ...`"""

import argparse
import json
import sys

from .core import parity_verdict, model_id_sha, build_certificate
from .runner import Endpoint, run_corpus, corpus_sha
from .judge import grade_run


def load_jsonl(path):
    with open(path) as f:
        return [json.loads(l) for l in f if l.strip()]


def main(argv=None):
    p = argparse.ArgumentParser(prog="parity")
    sub = p.add_subparsers(dest="cmd", required=True)
    c = sub.add_parser("compare")
    c.add_argument("--corpus", required=True)
    c.add_argument("--reference-url", required=True)
    c.add_argument("--reference-model", required=True)
    c.add_argument("--reference-key", default="")
    c.add_argument("--candidate-url", required=True)
    c.add_argument("--candidate-model", required=True)
    c.add_argument("--candidate-key", default="")
    c.add_argument("--judge-url"); c.add_argument("--judge-model")
    c.add_argument("--judge-key", default="")
    c.add_argument("--out", default="parity-report.json")
    c.add_argument("--max-tokens", type=int, default=400)
    a = p.parse_args(argv)

    corpus = load_jsonl(a.corpus)
    ref_ep = Endpoint(a.reference_url, a.reference_key, a.reference_model, "reference:" + a.reference_model)
    cand_ep = Endpoint(a.candidate_url, a.candidate_key, a.candidate_model, "candidate:" + a.candidate_model)
    judge_ep = Endpoint(a.judge_url, a.judge_key, a.judge_model, "judge") if a.judge_url else None

    rows_ref = run_corpus(a.corpus, ref_ep)
    print("reference done (%d prompts)" % len(rows_ref), file=sys.stderr, flush=True)
    rows_cand = run_corpus(a.corpus, cand_ep)
    print("candidate done", file=sys.stderr, flush=True)
    g_ref = grade_run(rows_ref, corpus, judge_ep)
    g_cand = grade_run(rows_cand, corpus, judge_ep)

    n = len(corpus)
    s_ref = sum(1 for g in g_ref if g["pass"])
    s_cand = sum(1 for g in g_cand if g["pass"])
    task = parity_verdict(s_ref, s_cand, n)
    lr = (sum(r["seconds"] for r in rows_cand) / max(1e-9, sum(r["seconds"] for r in rows_ref)))
    cr = (sum(r["prompt_tokens"] + r["completion_tokens"] for r in rows_cand)
          / max(1, sum(r["prompt_tokens"] + r["completion_tokens"] for r in rows_ref)))
    cert = build_certificate(corpus_sha(a.corpus),
        {"model_id": a.reference_model, "sha": model_id_sha(a.reference_model),
         "endpoint": a.reference_url, "pass_count": s_ref},
        {"model_id": a.candidate_model, "sha": model_id_sha(a.candidate_model),
         "endpoint": a.candidate_url, "pass_count": s_cand},
        {"n": n, **task}, lr, cr)
    report = {"certificate": cert,
              "per_prompt": [{"idx": g["idx"], "id": g["id"], "reference": g["pass"],
                             "candidate": gc["pass"], "how": g["how"]}
                            for g, gc in zip(g_ref, g_cand)]}
    with open(a.out, "w") as f:
        json.dump(report, f, indent=2)
    print(json.dumps(cert, indent=2))
    return 0 if cert["verdict"] != "FAIL" else 1


if __name__ == "__main__":
    sys.exit(main())
