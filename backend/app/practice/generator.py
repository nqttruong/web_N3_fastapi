"""Practice generators: OpenAI (shared PR3 infrastructure) or a test fake."""

from dataclasses import dataclass
from typing import Protocol

from app.core.config import Settings
from app.explanations import prompts
from app.explanations.interfaces import Usage
from app.explanations.providers import registry
from app.practice.context import PracticeContext
from app.practice.payload import PracticeSet


@dataclass(frozen=True)
class PracticeResult:
    payload: PracticeSet
    usage: Usage
    model: str


class PracticeGenerator(Protocol):
    provider: str
    model: str

    def generate(
        self, ctx: PracticeContext, *, feedback: list[str] | None = None
    ) -> PracticeResult: ...


class OpenAIPracticeGenerator:
    provider = "openai"

    def __init__(self, settings: Settings) -> None:
        from app.explanations.providers.openai_provider import OpenAIStructuredClient

        self.client = OpenAIStructuredClient(settings)
        self.model = self.client.model

    def generate(
        self, ctx: PracticeContext, *, feedback: list[str] | None = None
    ) -> PracticeResult:
        prompt = prompts.render_practice(ctx, feedback=feedback)
        payload, usage, model = self.client.parse(
            instructions=prompt.instructions,
            input=prompt.input,
            text_format=PracticeSet,
            cache_key=prompt.version,
        )
        return PracticeResult(payload, usage, model)


_override: PracticeGenerator | None = None


def set_practice_generator_for_tests(generator: PracticeGenerator | None) -> None:
    global _override
    _override = generator


def get_practice_generator(settings: Settings) -> PracticeGenerator | None:
    if _override is not None:
        return _override
    if not registry.status(settings).available:
        return None
    return OpenAIPracticeGenerator(settings)
