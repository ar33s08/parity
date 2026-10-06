"""parity core: statistics and certificate construction. Pure, no I/O."""

import hashlib
import json
import math


def wilson_interval(successes, n, z=1.96):
    """Wilson score interval for a binomial proportion."""
    if n == 0:
        return (0.0, 0.0)
    p = successes / n
    denom = 1 + z * z / n
    center = (p + z * z / (2 * n)) / denom
    margin = (z / denom) * math.sqrt(p * (1 - p) / n + z * z / (4 * n * n))
    return (max(0.0, center - margin), min(1.0, center + margin))


def two_proportion_z(s1, n1, s2, n2):
    """Two-sided z-test for equal pass rates. Returns (z, p_value)."""
    if min(n1, n2) == 0:
        return (0.0, 1.0)
    p1, p2 = s1 / n1, s2 / n2
    p = (s1 + s2) / (n1 + n2)
    se = math.sqrt(p * (1 - p) * (1 / n1 + 1 / n2)) if 0 < p < 1 else 0.0
    if se == 0:
        return (0.0, 1.0)
    z = (p1 - p2) / se
    # two-sided p via erf
    pval = math.erfc(abs(z) / math.sqrt(2))
    return (z, min(1.0, pval))


def parity_verdict(a_pass, b_pass, n, ci=0.95):
    """Compute equivalence verdict between reference (a) and candidate (b).
    Parity = candidate pass-rate Wilson lower bound is within `margin` of
    reference point estimate AND no statistically significant regression."""
    lo_a, hi_a = wilson_interval(a_pass, n)
    lo_b, hi_b = wilson_interval(b_pass, n)
    z, pval = two_proportion_z(a_pass, n, b_pass, n)
    regression = (pval < 0.05) and (b_pass < a_pass)
    return {
        "reference_pass": a_pass / n, "candidate_pass": b_pass / n,
        "reference_ci": [round(lo_a, 4), round(hi_a, 4)],
        "candidate_ci": [round(lo_b, 4), round(hi_b, 4)],
        "z": round(z, 3), "p_value": round(pval, 4),
        "significant_regression": bool(regression),
        "verdict": "FAIL" if regression else ("PASS" if (hi_b >= lo_a or b_pass >= a_pass) else "REVIEW"),
    }


def model_id_sha(model_id, extra=""):
    return hashlib.sha256((model_id + "|" + extra).encode()).hexdigest()[:16]


def build_certificate(corpus_sha, reference, candidate, task_stats, mean_latency_ratio,
                      cost_ratio, verdict="PASS", issued_by="parity-cli/0.1"):
    body = {
        "schema": "parity/cert/0.1",
        "corpus_sha256": corpus_sha,
        "reference": reference,   # {"model_id","sha","endpoint","avg_cost"}
        "candidate": candidate,
        "n_prompts": task_stats["n"],
        "task": task_stats,      # parity_verdict output
        "mean_latency_ratio": round(mean_latency_ratio, 2),
        "cost_ratio": round(cost_ratio, 4),
        "verdict": verdict,
        "issued_by": issued_by,
    }
    body["cert_sha256"] = hashlib.sha256(
        json.dumps(body, sort_keys=True).encode()).hexdigest()
    return body
