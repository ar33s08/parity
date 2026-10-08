"""parity offline test suite: statistics, certificates, judge, migrate, corpus."""
import hashlib
import json
import os
import re
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from parity.core import build_certificate, parity_verdict, two_proportion_z, wilson_interval
from parity.judge import grade_deterministic, grade_run
from parity.migrate import apply_plan, build_plan, scan_repo


class FakeEP:
    def __init__(self, good=True):
        self.good = good
        self.n = 0

    def complete(self, prompt, max_tokens=400):
        self.n += 1
        good_text = ('391 8.0 km Paris hashlib.sha256(b"parity").hexdigest() '
                     '{"name":"a","age":1}')
        return {"text": good_text if self.good else "banana", "seconds": 0.5,
                "prompt_tokens": 10, "completion_tokens": 5}


def test_wilson_interval():
    lo, hi = wilson_interval(97, 100)
    assert 0.90 < lo < 0.99 and hi > 0.985
    assert wilson_interval(0, 0) == (0.0, 0.0)


def test_significance():
    _, p = two_proportion_z(90, 100, 50, 100)
    assert p < 0.001
    _, p2 = two_proportion_z(90, 100, 89, 100)
    assert p2 > 0.5


def test_verdicts():
    assert parity_verdict(90, 90, 100)["verdict"] == "PASS"
    assert parity_verdict(90, 50, 100)["verdict"] == "FAIL"
    assert parity_verdict(50, 90, 100)["verdict"] == "PASS"  # better is fine


def test_certificate_tamper_evident():
    v = parity_verdict(90, 90, 100)
    cert = build_certificate("aa" * 32, {"model_id": "r", "sha": "x", "endpoint": "u",
                                         "pass_count": 90},
                             {"model_id": "c", "sha": "y", "endpoint": "v",
                              "pass_count": 90},
                             {"n": 100, **v}, 3.1, 0.12)
    body = {k: x for k, x in cert.items() if k != "cert_sha256"}
    assert hashlib.sha256(json.dumps(body, sort_keys=True).encode()).hexdigest() \
        == cert["cert_sha256"]
    cert["verdict"] = "tampered"
    h = hashlib.sha256(json.dumps({k: x for k, x in cert.items()
                                   if k != "cert_sha256"}, sort_keys=True).encode()).hexdigest()
    assert h != cert["cert_sha256"]


def test_deterministic_grading():
    assert grade_deterministic({"text": "answer 391", "seconds": 1},
                               {"must_contain": ["391"]})[0]
    assert grade_deterministic({"text": "x", "seconds": 1},
                               {"must_contain": ["391"]}) == (False, "missing:391")
    assert not grade_deterministic({"text": "Paris and London", "seconds": 1},
                                   {"must_contain": ["Paris"],
                                    "must_not_contain": ["London"]})[0]
    assert not grade_deterministic({"text": "x", "seconds": 9},
                                   {"max_seconds": 5})[0]


def test_migrate_full_cycle(tmp_path=None):
    import tempfile
    d = tempfile.mkdtemp()
    open(os.path.join(d, "app.py"), "w").write(
        'import openai\nclient = openai.OpenAI(base_url="https://api.openai.com/v1",'
        ' api_key="k")\nr = client.chat.completions.create(model="gpt-4.1", messages=[])\n')
    open(os.path.join(d, "tell.py"), "w").write(
        'import anthropic\nb = anthropic.Anthropic(api_key="k2")\n')
    open(os.path.join(d, "notify.ts"), "w").write(
        'const Anthropic = require("@anthropic-ai/sdk");\n'
        'const a = new Anthropic({ baseURL: "https://api.anthropic.com/v1",'
        ' apiKey: process.env.K });\n')
    pre = scan_repo(d)
    assert len(pre) >= 4
    apply_plan(build_plan(pre, "https://local.example/v1", "local-m"))
    post = scan_repo(d)
    assert post == []
    import py_compile
    py_compile.compile(os.path.join(d, "app.py"), doraise=True)
    py_compile.compile(os.path.join(d, "tell.py"), doraise=True)


def test_corpus_selftest():
    path = os.path.join(os.path.dirname(__file__), "..", "corpora", "prod100.jsonl")
    if not os.path.exists(path):
        return
    rows = [json.loads(l) for l in open(path)]
    assert len(rows) == 100
    for r_ in rows:
        if "regex" in r_:
            keys = re.findall(r'"(\w+)"', r_["prompt"])
            ans = json.dumps({k: 1 for k in keys})
            assert re.search(r_["regex"], ans), r_["id"]


def test_report_artifact_if_present():
    path = os.path.join(os.path.dirname(__file__), "..", "reports",
                        "prod100-selfcheck.json")
    if not os.path.exists(path):
        return
    rep = json.load(open(path))
    c = rep["certificate"]
    body = {k: v for k, v in c.items() if k != "cert_sha256"}
    assert hashlib.sha256(json.dumps(body, sort_keys=True).encode()).hexdigest() \
        == c["cert_sha256"]
