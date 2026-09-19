# 🤖 Deep Agents Python Quickstart (`fit-check-agent`)

Minimal Deep Agent prototype built with [LangChain](https://github.com/langchain-ai/langchain) & [DeepAgents](https://github.com/langchain-ai/langchain-skills).

---

## 🚀 Quick Setup

### 1. Configure Environment (`deep-agent/.env`)

Copy `.env.example` to `.env`:

```bash
cp deep-agent/.env.example deep-agent/.env
```

Edit `deep-agent/.env` and fill in your keys:

```env
# LangSmith Observability
LANGSMITH_TRACING=true
LANGSMITH_PROJECT=fit-check-agent
LANGSMITH_API_KEY=your_langsmith_api_key

# Choose your provider and add your API key:
MODEL_NAME=google_genai:gemini-2.5-flash
GEMINI_API_KEY=your_gemini_api_key
# or OPENAI_API_KEY=your_openai_key with MODEL_NAME=openai:gpt-4o-mini
# or ANTHROPIC_API_KEY=your_anthropic_key with MODEL_NAME=anthropic:claude-3-5-sonnet-20241022
```

### 2. Run the Agent

```bash
python deep-agent/main.py
```

### 3. View Traces in LangSmith

Open [smith.langchain.com](https://smith.langchain.com/) and navigate to the project **`fit-check-agent`** to view execution graphs, tool execution timelines, and token consumption metrics.
