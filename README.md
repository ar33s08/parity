# parity

**Is your local model good enough to replace the cloud one?**

parity replays *your* prompt corpus against a reference endpoint (the cloud
model you're leaving) and a candidate endpoint (your local/quantized stack),
grades both with deterministic rubrics (judge model only for open-ended items),
and issues a hash-pinned, tamper-evident **equivalence certificate**:

```json
{"schema": "parity/cert/0.1",
 "corpus_sha256": "75287f5a…", "verdict": "PASS",
 "task": {"reference_pass": 1.0, "candidate_pass": 1.0, "p_value": 1.0},
 "mean_latency_ratio": 3.1, "cost_ratio": 0.12,
 "cert_sha256": "2027bad3…"}
```

## Usage
```bash
python -m parity.cli compare \
  --corpus my-prompts.jsonl \
  --reference-url https://api.openai.com/v1 --reference-model gpt-4.1 --reference-key *** \
  --candidate-url https://dgx.tailnet.ts.net/v1 --candidate-model qwen3-coder-q4 --candidate-key *** \
  --out report.json
```
Corpus format: JSONL, `{"id","prompt", optional "must_contain","must_not_contain","regex","max_seconds"}`.
Exit code 1 = statistically significant regression (CI gate for automation).

## Honest limits (v0.1)
- n=5 smoke corpus; statistical power needs >=100 prompts (README contract).
- Judge-model grading is only as fair as the judge; deterministic rubrics preferred.
- Latency ratios are single-run wall-clock, not p95 yet.
- Certificates are content-hashed, not yet signed by a hosted authority.

## parity migrate — the agent that fires your cloud vendor

```bash
# find every cloud LLM call site in a repo (Python + JS/TS)
python -m parity.cli migrate scan ./myrepo

# migrate + gate + certify in ONE command
python -m parity.cli migrate certify ./myrepo \
  --url https://dgx.tailnet.ts.net/v1 --model qwen3-coder-q4 --key *** \
  --reference-url https://api.openai.com/v1 --reference-model gpt-4.1 --reference-key *** \
  --corpus prod-prompts.jsonl --out cert.json
```

The certificate embeds the migration record (sites migrated, hosts before,
files changed) pinned by content hash. Exit code 1 = regression detected —
wire it into CI: **no certificate, no merge.**

v0.1 verified cycle: 5 cloud sites → 0 across explicit URLs, pinned models,
implicit SDK defaults, and attribute-style constructors; all files compile;
corpus gate PASS with valid cert_sha256.
