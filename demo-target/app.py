import openai

client = openai.OpenAI(base_url="https://dgx.tail391339.ts.net/v1", api_key="sk-test")

resp = client.chat.completions.create(model="qwen3.8-flash-next", messages=[])
