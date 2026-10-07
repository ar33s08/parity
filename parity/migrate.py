"""parity.migrate: the cloud->local migration agent, certified.

v0.1 scope (deterministic, no LLM in the loop yet):
  scan  -> AST/regex find of cloud LLM call sites in a repo
  plan  -> migration plan JSON (which files, what changes, candidate endpoints)
  apply -> rewrite call sites to point at the local endpoint
  gate  -> run parity compare on the repo's own corpus before/after; refuse to
           certify a migration that regresses (exit 1 = rollback instruction)

The point: a migration you cannot prove is a rewrite you will regret.
"""

import ast
import json
import os
import re
import sys

CLOUD_HOSTS = {
    "api.openai.com": "openai",
    "api.anthropic.com": "anthropic",
    "api.cohere.ai": "cohere",
    "generativelanguage.googleapis.com": "google",
    "api.deepseek.com": "deepseek",
}


def scan_repo(root):
    """Returns list of findings: {file, line, host, kind, snippet}."""
    findings = []
    skip_dirs = {".git", "node_modules", ".venv", "venv", "__pycache__", "dist", "build"}
    for dirpath, dirnames, filenames in os.walk(root):
        dirnames[:] = [d for d in dirnames if d not in skip_dirs]
        for fn in filenames:
            path = os.path.join(dirpath, fn)
            if fn.endswith(".py"):
                findings += _scan_py(path)
            elif fn.endswith((".js", ".ts", ".mjs", ".cjs", ".jsx", ".tsx")):
                findings += _scan_js(path)
    return findings


def _scan_py(path):
    out = []
    try:
        src = open(path, encoding="utf-8", errors="ignore").read()
    except OSError:
        return out
    for i, line in enumerate(src.splitlines(), 1):
        low = line.lower()
        for host in CLOUD_HOSTS:
            if host in low:
                out.append({"file": path, "line": i, "host": host,
                            "kind": "literal-url", "snippet": line.strip()[:160]})
    # SDK client constructions without explicit URL (implicit cloud default)
    try:
        tree = ast.parse(src)
    except SyntaxError:
        return out
    shimmed = "parity-migrate" in src
    for node in ast.walk(tree):
        if isinstance(node, ast.Call) and isinstance(node.func, ast.Name):
            if node.func.id in ("OpenAI", "AsyncOpenAI", "Anthropic", "AsyncAnthropic"):
                has_base = any(k.arg in ("base_url", "api_base") for k in node.keywords)
                if not has_base and not shimmed:
                    out.append({"file": path, "line": node.lineno,
                                "host": "implicit:" + node.func.id,
                                "kind": "implicit-sdk",
                                "snippet": ast.unparse(node)[:160]})
    return out


_JS_URL_RE = re.compile(r"https?://([\w.-]+)")
_JS_CTOR_RE = re.compile(r"new\s+(OpenAI|Anthropic)\s*\(")


def _scan_js(path):
    out = []
    try:
        src = open(path, encoding="utf-8", errors="ignore").read()
    except OSError:
        return out
    for i, line in enumerate(src.splitlines(), 1):
        for m in _JS_URL_RE.finditer(line):
            host = m.group(1)
            if host in CLOUD_HOSTS:
                out.append({"file": path, "line": i, "host": host,
                            "kind": "literal-url", "snippet": line.strip()[:160]})
        if _JS_CTOR_RE.search(line) and "parity-migrate" not in src:
            out.append({"file": path, "line": i, "host": "implicit-js",
                        "kind": "implicit-sdk", "snippet": line.strip()[:160]})
    return out


def build_plan(findings, local_url, local_model):
    hosts = sorted({f["host"] for f in findings})
    files = sorted({f["file"] for f in findings})
    return {
        "schema": "parity/plan/0.1",
        "n_findings": len(findings),
        "hosts": hosts,
        "files": files,
        "target": {"url": local_url, "model": local_model},
        "actions": ["rewrite base_url/api_base -> %s" % local_url,
                    "pin model -> %s" % local_model,
                    "run parity corpus gate",
                    "attach equivalence certificate to PR"],
        "findings": findings,
    }


_LOCAL_URL_RE = re.compile(r"""(base_url\s*=\s*)(["'])https?://(api\.openai\.com|api\.anthropic\.com|api\.cohere\.ai|generativelanguage\.googleapis\.com|api\.deepseek\.com)[^"']*\2""")
_JS_LOCAL_URL_RE = re.compile(r"""(baseURL\s*:\s*)(["'])https?://(api\.openai\.com|api\.anthropic\.com|api\.cohere\.ai|generativelanguage\.googleapis\.com|api\.deepseek\.com)[^"']*\2""")
_MODEL_RE = re.compile(r"""(model\s*=\s*)(["'])[\w.:/-]+\2""")
_JS_MODEL_RE = re.compile(r"""(model\s*:\s*)(["'])[\w.:/-]+\2""")


def rewrite_file(path, local_url, local_model):
    src = open(path, encoding="utf-8", errors="ignore").read()
    n = 0

    def sub_base(m):
        nonlocal n; n += 1
        return m.group(1) + m.group(2) + local_url + m.group(2)
    def sub_base_js(m):
        nonlocal n; n += 1
        return m.group(1) + m.group(2) + local_url + m.group(2)
    def sub_model(m):
        nonlocal n; n += 1
        return m.group(1) + m.group(2) + local_model + m.group(2)

    new = _LOCAL_URL_RE.sub(sub_base, src)
    new = _JS_LOCAL_URL_RE.sub(sub_base_js, new)
    # only rewrite model= when the same file pointed at a cloud host
    if any(h in src for h in CLOUD_HOSTS):
        new = _MODEL_RE.sub(sub_model, new)
        new = _JS_MODEL_RE.sub(sub_model, new)
    if new != src:
        open(path, "w", encoding="utf-8").write(new)
    return n


def apply_plan(plan):
    changed = {}
    for f in plan["files"]:
        changed[f] = rewrite_file(f, plan["target"]["url"], plan["target"]["model"])
    # implicit SDK sites (no base_url anywhere): inject env shim. Both SDKs honor
    # OPENAI_BASE_URL / ANTHROPIC_BASE_URL at construction time.
    implicit_files = sorted({f["file"] for f in plan["findings"]
                             if f["host"].startswith("implicit")})
    for f in implicit_files:
        src = open(f, encoding="utf-8", errors="ignore").read()
        if "OPENAI_BASE_URL" in src:
            continue
        py = f.endswith(".py")
        if py:
            shim = ('import os\n'
                    'os.environ.setdefault("OPENAI_BASE_URL", "%s")  # parity-migrate\n'
                    'os.environ.setdefault("ANTHROPIC_BASE_URL", "%s")  # parity-migrate\n'
                    % (plan["target"]["url"], plan["target"]["url"]))
        else:
            shim = ('process.env.OPENAI_BASE_URL ||= "%s"; // parity-migrate\n'
                    'process.env.ANTHROPIC_BASE_URL ||= "%s"; // parity-migrate\n'
                    % (plan["target"]["url"], plan["target"]["url"]))
        open(f, "w", encoding="utf-8").write(shim + src)
        changed[f] = changed.get(f, 0) + 1
    return changed
