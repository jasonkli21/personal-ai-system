"""Research synthesis composition, independent of search adapter selection."""

from personal_ai.llm.errors import LLMInvalidConfigurationError
from personal_ai.settings import Settings


def compose_research_inference(settings: Settings, usage_factory):
    """Build the configured research synthesis client and its matching token counter."""
    from personal_ai.context.tokens import EstimatedTokenCounter
    from personal_ai.llm.context import GeminiTokenCounter
    from personal_ai.llm.fake import FakeResearchLLMClient
    from personal_ai.llm.gemini import GeminiLLMClient

    inference_provider = settings.ai_provider.lower()
    if inference_provider == "fake":
        return EstimatedTokenCounter(), FakeResearchLLMClient()
    if inference_provider == "gemini":
        inference_usage = usage_factory()
        return GeminiTokenCounter(settings, usage_accounting=inference_usage), GeminiLLMClient(
            settings, usage_accounting=inference_usage
        )
    raise LLMInvalidConfigurationError("research inference configuration is unsupported")
