import httpx

from app.config import Settings
from app.services.llm import LLMMessage, LLMRequest
from app.services.llm.factory import get_llm_provider
from app.services.llm.providers import OpenAICompatibleProvider, ProviderConfig


def test_glm_coding_factory_uses_default_endpoint_and_key_env(monkeypatch) -> None:
    monkeypatch.setenv("ZAI_API_KEY", "test-key")
    settings = Settings(
        llm_provider="glm_coding",
        llm_model="glm-test",
        llm_api_key_env="ZAI_API_KEY",
    )

    provider = get_llm_provider(settings)

    assert isinstance(provider, OpenAICompatibleProvider)
    assert provider.config.base_url == "https://open.bigmodel.cn/api/coding/paas/v4"
    assert provider.config.model == "glm-test"
    assert provider.config.api_key == "test-key"


def test_openai_compatible_provider_posts_chat_completions(monkeypatch) -> None:
    calls = []

    class FakeClient:
        def __init__(self, timeout: float) -> None:
            self.timeout = timeout

        def __enter__(self):
            return self

        def __exit__(self, exc_type, exc, tb) -> None:
            return None

        def post(self, url: str, *, json: dict, headers: dict):
            calls.append({"url": url, "json": json, "headers": headers, "timeout": self.timeout})
            return httpx.Response(
                200,
                request=httpx.Request("POST", url),
                json={
                    "model": "glm-test",
                    "choices": [{"message": {"content": "{\"ok\": true}"}}],
                    "usage": {
                        "prompt_tokens": 12,
                        "completion_tokens": 5,
                        "total_tokens": 17,
                        "prompt_tokens_details": {"cached_tokens": 3},
                        "completion_tokens_details": {"reasoning_tokens": 2},
                        "cost_usd": 0.0012,
                    },
                },
            )

    monkeypatch.setattr("app.services.llm.providers.httpx.Client", FakeClient)
    provider = OpenAICompatibleProvider(
        ProviderConfig(
            provider_name="glm_coding",
            model="glm-test",
            api_key="test-key",
            base_url="https://open.bigmodel.cn/api/coding/paas/v4/",
            json_mode=True,
        )
    )

    result = provider.generate(
        LLMRequest(
            messages=[LLMMessage(role="user", content="Return JSON.")],
            expect_json=True,
        )
    )

    assert result.content == "{\"ok\": true}"
    assert result.provider == "glm_coding"
    assert result.usage["prompt_tokens"] == 12
    assert result.usage["completion_tokens"] == 5
    assert result.usage["total_tokens"] == 17
    assert result.usage["cached_tokens"] == 3
    assert result.usage["reasoning_tokens"] == 2
    assert result.cost_usd == 0.0012
    assert calls[0]["url"] == "https://open.bigmodel.cn/api/coding/paas/v4/chat/completions"
    assert calls[0]["headers"]["Authorization"] == "Bearer test-key"
    assert calls[0]["json"]["model"] == "glm-test"
    assert calls[0]["json"]["response_format"] == {"type": "json_object"}
