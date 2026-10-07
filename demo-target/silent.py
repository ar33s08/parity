import os
os.environ.setdefault("OPENAI_BASE_URL", "https://dgx.tail391339.ts.net/v1")  # parity-migrate
os.environ.setdefault("ANTHROPIC_BASE_URL", "https://dgx.tail391339.ts.net/v1")  # parity-migrate
from openai import OpenAI
c = OpenAI(api_key="sk-other")
