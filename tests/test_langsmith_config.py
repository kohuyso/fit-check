import os
import pytest
from app.core.config import Settings, setup_langsmith_environment

def test_langsmith_environment_disabled_by_default():
    custom_settings = Settings(
        LANGCHAIN_TRACING_V2=False,
        LANGCHAIN_API_KEY=None
    )
    result = setup_langsmith_environment(custom_settings)
    assert result is False
    assert os.environ.get("LANGCHAIN_TRACING_V2") == "false"

def test_langsmith_environment_enabled_with_valid_key():
    custom_settings = Settings(
        LANGCHAIN_TRACING_V2=True,
        LANGCHAIN_API_KEY="lsv2_pt_test_secret_key_12345678",
        LANGCHAIN_PROJECT="fitcheck-test-project",
        LANGCHAIN_ENDPOINT="https://api.smith.langchain.com"
    )
    result = setup_langsmith_environment(custom_settings)
    assert result is True
    assert os.environ.get("LANGCHAIN_TRACING_V2") == "true"
    assert os.environ.get("LANGCHAIN_API_KEY") == "lsv2_pt_test_secret_key_12345678"
    assert os.environ.get("LANGCHAIN_PROJECT") == "fitcheck-test-project"
    assert os.environ.get("LANGCHAIN_ENDPOINT") == "https://api.smith.langchain.com"

def test_langsmith_environment_rejects_dummy_placeholder_key():
    custom_settings = Settings(
        LANGCHAIN_TRACING_V2=True,
        LANGCHAIN_API_KEY="your_langsmith_api_key_here",
        LANGCHAIN_PROJECT="fitcheck-ai-backend"
    )
    result = setup_langsmith_environment(custom_settings)
    assert result is False
