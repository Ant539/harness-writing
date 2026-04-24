"""Build LLM providers from Paper Harness settings."""

import os

from app.config import Settings, settings
from app.services.llm.providers import (
    AnthropicProvider,
    GeminiProvider,
    LLMProviderError,
    OpenAICompatibleProvider,
    ProviderConfig,
)
from app.services.llm.types import LLMProvider


OPENAI_COMPATIBLE_PROVIDERS = {
    "openai",
    "openai_compatible",
    "glm",
    "glm_coding",
    "zhipu",
    "deepseek",
    "qwen",
    "openrouter",
    "ollama",
    "vllm",
    "lmstudio",
    "local",
}


DEFAULT_BASE_URLS = {
    "openai": "https://api.openai.com/v1",
    "glm": "https://open.bigmodel.cn/api/paas/v4",
    "zhipu": "https://open.bigmodel.cn/api/paas/v4",
    "glm_coding": "https://open.bigmodel.cn/api/coding/paas/v4",
    "deepseek": "https://api.deepseek.com",
    "qwen": "https://dashscope.aliyuncs.com/compatible-mode/v1",
    "openrouter": "https://openrouter.ai/api/v1",
    "ollama": "http://localhost:11434/v1",
    "vllm": "http://localhost:8000/v1",
    "lmstudio": "http://localhost:1234/v1",
    "local": "http://localhost:8000/v1",
}


DEFAULT_API_KEY_ENVS = {
    "openai": "OPENAI_API_KEY",
    "openai_compatible": "OPENAI_API_KEY",
    "glm": "ZAI_API_KEY",
    "zhipu": "ZAI_API_KEY",
    "glm_coding": "ZAI_API_KEY",
    "deepseek": "DEEPSEEK_API_KEY",
    "qwen": "DASHSCOPE_API_KEY",
    "openrouter": "OPENROUTER_API_KEY",
    "anthropic": "ANTHROPIC_API_KEY",
    "gemini": "GEMINI_API_KEY",
}


DEFAULT_MODELS = {
    "openai": "gpt-5.4-mini",
    "openai_compatible": "gpt-5.4-mini",
    "glm": "glm-5.1",
    "zhipu": "glm-5.1",
    "glm_coding": "glm-5.1",
    "deepseek": "deepseek-chat",
    "qwen": "qwen-plus",
    "openrouter": "openai/gpt-5.4-mini",
    "ollama": "llama3.1",
    "vllm": "local-model",
    "lmstudio": "local-model",
    "local": "local-model",
    "anthropic": "claude-sonnet-4-5",
    "gemini": "gemini-2.5-pro",
}


KEYLESS_PROVIDERS = {"ollama", "vllm", "lmstudio", "local"}


def get_llm_provider(config: Settings = settings) -> LLMProvider | None:
    """Return the configured provider, or None for deterministic local behavior."""
    provider_name = config.llm_provider.strip().lower()
    if provider_name in {"", "none", "mock", "deterministic"}:
        return None

    provider_config = _provider_config(provider_name, config)
    if provider_name in OPENAI_COMPATIBLE_PROVIDERS:
        return OpenAICompatibleProvider(provider_config)
    if provider_name == "anthropic":
        return AnthropicProvider(provider_config)
    if provider_name == "gemini":
        return GeminiProvider(provider_config)
    supported = ", ".join(sorted([*OPENAI_COMPATIBLE_PROVIDERS, "anthropic", "gemini"]))
    raise LLMProviderError(f"Unsupported LLM provider '{provider_name}'. Supported: {supported}.")


def _provider_config(provider_name: str, config: Settings) -> ProviderConfig:
    model = config.llm_model or DEFAULT_MODELS.get(provider_name)
    if not model:
        raise LLMProviderError(f"Provider '{provider_name}' requires PAPER_HARNESS_LLM_MODEL.")
    base_url = config.llm_base_url or DEFAULT_BASE_URLS.get(provider_name)
    api_key = _api_key(provider_name, config)
    if not api_key and provider_name not in KEYLESS_PROVIDERS:
        env_name = config.llm_api_key_env or DEFAULT_API_KEY_ENVS.get(provider_name) or "LLM_API_KEY"
        raise LLMProviderError(
            f"Provider '{provider_name}' requires PAPER_HARNESS_LLM_API_KEY "
            f"or environment variable {env_name}."
        )
    return ProviderConfig(
        provider_name=provider_name,
        model=model,
        api_key=api_key,
        base_url=base_url,
        temperature=config.llm_temperature,
        timeout_seconds=config.llm_timeout_seconds,
        max_tokens=config.llm_max_tokens,
        json_mode=config.llm_json_mode,
    )


def _api_key(provider_name: str, config: Settings) -> str | None:
    if config.llm_api_key:
        return config.llm_api_key
    env_name = config.llm_api_key_env or DEFAULT_API_KEY_ENVS.get(provider_name)
    if not env_name:
        return None
    return os.environ.get(env_name)
