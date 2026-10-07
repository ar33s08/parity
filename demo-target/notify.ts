process.env.OPENAI_BASE_URL ||= "https://dgx.tail391339.ts.net/v1"; // parity-migrate
process.env.ANTHROPIC_BASE_URL ||= "https://dgx.tail391339.ts.net/v1"; // parity-migrate
const Anthropic = require("@anthropic-ai/sdk");
const a = new Anthropic({ baseURL: "https://dgx.tail391339.ts.net/v1", apiKey: process.env.K });
