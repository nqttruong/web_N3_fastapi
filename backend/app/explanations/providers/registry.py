"""Which generator is active. Tests install a fake with ``set_generator_for_tests``."""

from dataclasses import dataclass

from app.core.config import Settings
from app.explanations.interfaces import ExplanationGenerator

_override: ExplanationGenerator | None = None


@dataclass(frozen=True)
class ProviderStatus:
    available: bool
    provider: str | None
    model: str | None
    reason: str | None


def set_generator_for_tests(generator: ExplanationGenerator | None) -> None:
    global _override
    _override = generator


def status(settings: Settings) -> ProviderStatus:
    if _override is not None:
        return ProviderStatus(True, _override.provider, _override.model, None)
    if settings.ai_provider == "none":
        return ProviderStatus(False, None, None, "AI_PROVIDER=none: chỉ dùng chế độ thủ công.")
    if settings.openai_api_key is None:
        return ProviderStatus(
            False,
            "openai",
            settings.openai_model,
            "Chưa cấu hình OPENAI_API_KEY. Bạn vẫn có thể xuất prompt sang ChatGPT và nhập JSON.",
        )
    return ProviderStatus(True, "openai", settings.openai_model, None)


def get_generator(settings: Settings) -> ExplanationGenerator | None:
    if _override is not None:
        return _override
    if not status(settings).available:
        return None
    from app.explanations.providers.openai_provider import OpenAIExplanationGenerator

    return OpenAIExplanationGenerator(settings)
