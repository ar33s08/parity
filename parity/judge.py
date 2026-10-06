"""parity judge: deterministic rubric checks first; optional judge model for the rest.

A rubric item looks like: {"id": "...", "prompt": "...", "must_contain": [...],
"must_not_contain": [...], "regex": "...", "max_seconds": optional}
Items with rubric fields are graded deterministically (no judge call).
Items without are graded by the judge endpoint (same for A and B -> fair).
"""


def grade_deterministic(rec, item):
    text = rec["text"]
    for s in item.get("must_contain", []):
        if s not in text:
            return False, "missing:" + s
    for s in item.get("must_not_contain", []):
        if s.lower() in text.lower():
            return False, "forbidden:" + s
    if "regex" in item:
        import re
        if not re.search(item["regex"], text):
            return False, "regex"
    if "max_seconds" in item and rec["seconds"] > item["max_seconds"]:
        return False, "latency"
    return True, "rubric"


JUDGE_PROMPT = ("You are a strict equivalence judge. A task is PASS if the answer "
                "correctly fulfills the request. Grade ONLY the answer. "
                "Reply with exactly PASS or FAIL.\n\nRequest: %s\n\nAnswer: %s")


def grade_judged(rec, judge_endpoint):
    out = judge_endpoint.complete(JUDGE_PROMPT % (rec["prompt"], rec["text"][:2000]),
                                 max_tokens=10)
    return ("PASS" in out["text"].upper()[:20]), "judge"


def grade_run(rows, corpus, judge_endpoint=None):
    results = []
    for row, item in zip(rows, corpus):
        det = any(k in item for k in ("must_contain", "must_not_contain", "regex", "max_seconds"))
        if det:
            ok, how = grade_deterministic(row, item)
        elif judge_endpoint is not None:
            ok, how = grade_judged(row, judge_endpoint)
        else:
            ok, how = True, "unjudged"
        results.append({"idx": row["idx"], "id": row["id"], "pass": ok, "how": how})
    return results
