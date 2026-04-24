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
    assert calls[0]["url"] == "https://open.bigmodel.cn/api/coding/paas/v4/chat/completions"
    assert calls[0]["headers"]["Authorization"] == "Bearer test-key"
    assert calls[0]["json"]["model"] == "glm-test"
    assert calls[0]["json"]["response_format"] == {"type": "json_object"}
