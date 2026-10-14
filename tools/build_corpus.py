"""Build a parity corpus from your OWN production LLM request logs.

Input: JSONL where each line is a logged request, one of:
  {"messages": [...]}                      # chat-completions request body
  {"prompt": "..."}                        # plain prompt
  {"request": {...}} or {"body": {...}}    # wrapped proxy log formats
Lines may also carry response/output fields; they are ignored here (the
certificate compares live runs, not recorded outputs).

Output: parity corpus JSONL ({"id", "messages"|"prompt"}), deterministically
sampled so re-runs on the same logs yield the SAME corpus hash.

Privacy: reads local logs only; never sends anything anywhere. Redacts
common secret shapes from prompts before writing them to the corpus.

Usage:
  python tools/build_corpus.py --in proxy-logs.jsonl --n 100 --out corpus.jsonl
"""
import argparse
import hashlib
import json
import re

SECRET_RES = [
    (re.compile(r"(sk-[A-Za-z0-9_\-]{16,})"), "[REDACTED_KEY]"),
    (re.compile(r"(AKIA[0-9A-Z]{16})"), "[REDACTED_AWS]"),
    (re.compile(r"(Bearer\s+[A-Za-z0-9._\-]{16,})"), "Bearer [REDACTED]"),
    (re.compile(r"([A-Za-z0-9+/_]{32,}={0,2})"), lambda m:
     "[REDACTED_B64]" if not _is_wordy(m.group(1)) else m.group(0)),
]


def _is_wordy(s):
    return len(set(s)) < 3 or s.isalnum() and s.islower()


def redact(text):
    if not isinstance(text, str):
        return text
    for rx, rep in SECRET_RES:
        text = rx.sub(rep, text)
    return text


def extract_request(obj):
    """Returns {'messages': [...]} or {'prompt': '...'} or None."""
    for key in ("messages", "prompt"):
        if key in obj:
            val = obj[key]
            if key == "messages" and isinstance(val, list) and val:
                return {"messages": [
                    {"role": m.get("role", "user"),
                     "content": redact(m.get("content", ""))}
                    for m in val if isinstance(m, dict)]}
            if key == "prompt" and isinstance(val, str) and val.strip():
                return {"prompt": redact(val)}
    for wrapper in ("request", "body", "payload"):
        if isinstance(obj.get(wrapper), dict):
            got = extract_request(obj[wrapper])
            if got:
                return got
    return None


def build(input_path, n, seed=0):
    seen = set()
    records = []
    with open(input_path) as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            try:
                obj = json.loads(line)
            except json.JSONDecodeError:
                continue
            req = extract_request(obj)
            if not req:
                continue
            h = hashlib.sha256(json.dumps(req, sort_keys=True).encode()).hexdigest()
            if h in seen:
                continue
            seen.add(h)
            records.append((h, req))
    # deterministic sample: stable sort by hash(seed+hash)
    keyed = sorted(records,
                   key=lambda t: hashlib.sha256(
                       (str(seed) + t[0]).encode()).hexdigest())
    return [dict(id="log%04d" % i, **req)
            for i, (_, req) in enumerate(keyed[:n])]


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--in", dest="inp", required=True)
    ap.add_argument("--n", type=int, default=100)
    ap.add_argument("--out", default="corpus.jsonl")
    ap.add_argument("--seed", type=int, default=0)
    a = ap.parse_args()
    rows = build(a.inp, a.n, a.seed)
    with open(a.out, "w") as f:
        for r in rows:
            f.write(json.dumps(r) + "\n")
    print("wrote %d corpus rows to %s" % (len(rows), a.out))


if __name__ == "__main__":
    main()
