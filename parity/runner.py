"""parity runner: replay a prompt corpus against reference and candidate endpoints."""

import hashlib
import json
import time
import urllib.request


def corpus_sha(path):
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(65536), b""):
            h.update(chunk)
    return h.hexdigest()


class Endpoint:
    def __init__(self, base_url, api_key, model, name=None):
        self.base_url = base_url.rstrip("/")
        self.api_key = api_key
        self.model = model
        self.name = name or model

    def complete(self, prompt, max_tokens=400):
        payload = {"model": self.model, "messages": [{"role": "user", "content": prompt}],
                   "max_tokens": max_tokens, "temperature": 0.0}
        req = urllib.request.Request(self.base_url + "/chat/completions",
                                     data=json.dumps(payload).encode(),
                                     headers={"Content-Type": "application/json",
                                              "Authorization": "***" + self.api_key})
        t0 = time.time()
        with urllib.request.urlopen(req, timeout=600) as resp:
            body = json.loads(resp.read().decode())
        dt = time.time() - t0
        msg = body["choices"][0]["message"]
        text = msg.get("content")
        if text is None:
            text = msg.get("reasoning") or msg.get("reasoning_content") or ""
        usage = body.get("usage") or {}
        return {"text": text, "seconds": dt,
                "prompt_tokens": usage.get("prompt_tokens", 0),
                "completion_tokens": usage.get("completion_tokens", 0)}


def run_corpus(path, endpoint):
    """Returns list of {idx, prompt, output, seconds, tokens}."""
    rows = []
    with open(path) as f:
        for i, line in enumerate(f):
            if not line.strip():
                continue
            rec = json.loads(line)
            out = endpoint.complete(rec["prompt"])
            rows.append({"idx": i, "id": rec.get("id", "p%04d" % i),
                         "prompt": rec["prompt"], **out})
    return rows
