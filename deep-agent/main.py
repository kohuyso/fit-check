import os
import sys
from pathlib import Path
from dotenv import load_dotenv

# 1. Load environment variables
env_path = Path(__file__).parent / ".env"
if env_path.exists():
    load_dotenv(dotenv_path=env_path)
else:
    load_dotenv()  # Fallback to current working directory

# 2. Configure LangSmith Observability for "fit-check-agent" project
langsmith_api_key = os.getenv("LANGSMITH_API_KEY") or os.getenv("LANGCHAIN_API_KEY")
if langsmith_api_key is not None and "your_" not in langsmith_api_key and langsmith_api_key.strip():
    os.environ["LANGSMITH_TRACING"] = "true"
    os.environ["LANGCHAIN_TRACING_V2"] = "true"
    os.environ["LANGSMITH_PROJECT"] = os.getenv("LANGSMITH_PROJECT", "fit-check-agent")
    os.environ["LANGCHAIN_API_KEY"] = langsmith_api_key
    os.environ["LANGSMITH_API_KEY"] = langsmith_api_key
else:
    os.environ["LANGSMITH_TRACING"] = "false"
    os.environ["LANGCHAIN_TRACING_V2"] = "false"
    os.environ["LANGSMITH_PROJECT"] = "fit-check-agent"



from deepagents import create_deep_agent
from langchain_core.tools import tool

# 3. Define Tools
@tool
def calculate_expression(expression: str) -> str:
    """Safely evaluates basic mathematical expressions."""
    try:
        # Simple safe evaluation for math expressions
        allowed = set("0123456789+-*/(). %")
        if not all(c in allowed for c in expression):
            return "Error: Unsupported characters in mathematical expression."
        result = eval(expression, {"__builtins__": None}, {})
        return str(result)
    except Exception as e:
        return f"Calculation error: {e}"

@tool
def get_system_overview(topic: str) -> str:
    """Returns an architectural summary of modern AI agent architectures."""
    summaries = {
        "deepagents": "Deep Agents provide an opinionated harness built on LangChain/LangGraph with built-in task planning, filesystem context, memory, and sub-agent orchestration.",
        "langgraph": "LangGraph is a library for building stateful, multi-actor applications with LLMs using graph-based control flows.",
        "langsmith": "LangSmith is an all-in-one platform for LLM application development, debugging, testing, evaluating, and monitoring."
    }
    key = topic.lower().strip()
    return summaries.get(key, f"Summary available for topic: {topic}. Deep Agents enable multi-step reasoning and sub-agent coordination.")

# 4. Agent Factory Function
def build_research_agent(model_name: str | None = None):
    """
    Constructs a Deep Agent configured for the 'fit-check-agent' LangSmith project.
    Model is model-agnostic (Google GenAI, OpenAI, Anthropic, etc.).
    """
    # Pick model from argument, env, or default
    active_model = model_name or os.getenv("MODEL_NAME", "google_genai:gemini-3.1-flash-lite")
    
    agent = create_deep_agent(
        model=active_model,
        tools=[calculate_expression, get_system_overview],
        system_prompt=(
            "You are a helpful research assistant built with LangChain and DeepAgents. "
            "Use available tools when necessary to provide accurate, structured responses."
        ),
        name="my-first-deep-agent"
    )
    return agent

# 5. Execution Demo
if __name__ == "__main__":
    print("=" * 65)
    print("🚀 Deep Agents Python Quickstart")
    print(f"📊 LangSmith Project : {os.environ.get('LANGSMITH_PROJECT')}")
    print(f"📡 Tracing Enabled   : {os.environ.get('LANGCHAIN_TRACING_V2')}")
    print("=" * 65)

    # Check for available LLM API keys
    has_key = any([
        os.getenv("GEMINI_API_KEY"),
        os.getenv("OPENAI_API_KEY"),
        os.getenv("ANTHROPIC_API_KEY")
    ])

    if not has_key:
        print("\n⚠️  No LLM API Key detected in deep-agent/.env.")
        print("👉 Please add your GEMINI_API_KEY, OPENAI_API_KEY, or ANTHROPIC_API_KEY into deep-agent/.env")
        print("   to execute live queries.\n")
        sys.exit(0)

    try:
        agent = build_research_agent()
        query = "What is the difference between LangGraph and Deep Agents, and calculate 25 * 14 + 180?"
        print(f"\n💬 Query: {query}\n")
        print("⏳ Invoking Deep Agent...")
        
        config = {"configurable": {"thread_id": "quickstart-thread-01"}}
        response = agent.invoke({
            "messages": [{"role": "user", "content": query}]
        }, config=config)

        last_message = response["messages"][-1]
        print("\n" + "=" * 65)
        print("✨ Deep Agent Response:")
        print("=" * 65)
        print(last_message.content)
        print("\n✅ Execution finished. Traces recorded to LangSmith project: 'fit-check-agent'.")

    except Exception as err:
        print(f"\n❌ Execution note: {err}")
        print("Ensure the chosen provider package and API key match your MODEL_NAME configuration.")
