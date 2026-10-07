import sys
sys.path.insert(0, ".")
from parity.cli import main

sys.argv = ["parity", "compare", "--corpus", "corpora/prod100.jsonl",
            "--reference-url", "https://spark-fceb.tail391339.ts.net/v1",
            "--reference-model", "qwen3.8-flash-next",
            "--candidate-url", "https://spark-fceb.tail391339.ts.net/v1",
            "--candidate-model", "qwen3.8-flash-next",
            "--out", "reports/prod100-selfcheck.json"]
import re
_cfg = open("/Users/areesmanesia/.hermes/config.yaml").read()
key = re.search(r"api_key:\s*(\S+)", _cfg).group(1)
sys.argv += ["--reference-key", key, "--candidate-key", key]
sys.exit(main())
