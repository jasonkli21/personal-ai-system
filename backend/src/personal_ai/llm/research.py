"""Research synthesis composition, independent of search adapter selection."""

from personal_ai.llm.execution import compose_pair
from personal_ai.settings import Settings


def compose_research_inference(settings: Settings, usage_factory):
    """Use the same operator policy; retain literal-excerpt offline research."""
    if settings.inference_profile.startswith("offline_fake"):
        # Resolve first: paid modes and invalid selections must not bypass policy.
        compose_pair(settings)
        from personal_ai.context.tokens import EstimatedTokenCounter
        from personal_ai.llm.fake import FakeResearchLLMClient

        return EstimatedTokenCounter(), FakeResearchLLMClient()
    pair = compose_pair(settings, usage_factory())
    return pair.counter, pair.generator
