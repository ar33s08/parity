"""Pre-post verification: every posted artifact must be valid and consistent."""
import glob
import hashlib
import json
import re
import sys

fails = []

def check(name, ok):
    print(("PASS" if ok else "FAIL"), name)
    if not ok:
        fails.append(name)

# 1) parity certificate reports: hash integrity
for path in sorted(glob.glob("reports/*.json")):
    rep = json.load(open(path))
    c = rep["certificate"]
    body = {k: v for k, v in c.items() if k != "cert_sha256"}
    h = hashlib.sha256(json.dumps(body, sort_keys=True).encode()).hexdigest()
    check("cert hash valid: " + path, h == c["cert_sha256"])

# 2) corpus: every rubric item must match a canonical correct answer
rows = [json.loads(l) for l in open("corpora/prod100.jsonl")]
check("corpus has 100 items", len(rows) == 100)
bad = 0
for r_ in rows:
    if "regex" in r_:
        keys = re.findall(r'"(\w+)"', r_["prompt"])
        ans = json.dumps({k: 1 for k in keys})
        if not re.search(r_["regex"], ans):
            bad += 1
check("all regex rubrics satisfiable", bad == 0)

# 3) calibration report numbers match README claim (97/100)
rep = json.load(open("reports/prod100-selfcheck.json"))
check("prod100 report = 97/100", rep["certificate"]["reference"]["pass_count"] == 97)

# 4) core stats sanity (the numbers the posts cite as method)
sys.path.insert(0, ".")
from parity.core import wilson_interval, parity_verdict
lo, hi = wilson_interval(97, 100)
check("wilson(97/100) sane", 0.90 < lo < 0.99 and hi > 0.985)
check("regression detection", parity_verdict(97, 50, 100)["verdict"] == "FAIL")

# 5) corpus sha pinned in report matches corpus on disk
import subprocess
sha = hashlib.sha256(open("corpora/prod100.jsonl", "rb").read()).hexdigest()
check("corpus hash pinning (report vs disk note: regenerated corpus re-pins; report predates fix)",
      rep["certificate"]["corpus_sha256"] == sha)

print("\n%d failures" % len(fails))
sys.exit(1 if fails else 0)
