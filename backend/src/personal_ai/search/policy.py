"""Conservative URL, literal-snippet extraction and transparent planning policy."""

import ipaddress
import re
from hashlib import sha256
from html import unescape
from html.parser import HTMLParser
from urllib.parse import parse_qsl, urlencode, urlsplit, urlunsplit

from personal_ai.agents.research.contracts import ResearchError


def canonical_url(value: str) -> str:
    if len(value) > 2048 or re.search(r"[\x00-\x20\x7f\\]", value):
        raise ValueError("unsafe URL")
    parsed = urlsplit(value)
    host = (parsed.hostname or "").lower().rstrip(".")
    if (
        parsed.scheme not in {"http", "https"}
        or parsed.username
        or parsed.password
        or not host
        or parsed.port not in {None, 80, 443}
        or "%" in host
    ):
        raise ValueError("unsafe URL")
    try:
        address = ipaddress.ip_address(host)
    except ValueError:
        if (
            "." not in host
            or host.endswith((".local", ".localhost", ".internal", ".invalid"))
            or re.fullmatch(r"[0-9.xa-f]+", host)
            or not re.fullmatch(r"[a-z0-9.-]+", host)
            or any(
                not part or part.startswith("-") or part.endswith("-") for part in host.split(".")
            )
        ):
            raise ValueError("unsafe URL")
    else:
        if not address.is_global:
            raise ValueError("unsafe URL")
        host = f"[{host}]" if address.version == 6 else host
    port = (
        f":{parsed.port}"
        if parsed.port and parsed.port != (443 if parsed.scheme == "https" else 80)
        else ""
    )
    query = [
        (k, v)
        for k, v in parse_qsl(parsed.query, keep_blank_values=True)
        if not k.lower().startswith("utm_") and k.lower() not in {"fbclid", "gclid"}
    ]
    return urlunsplit((parsed.scheme, host + port, parsed.path or "/", urlencode(query), ""))


class _TextParser(HTMLParser):
    def __init__(self):
        super().__init__(convert_charrefs=True)
        self.parts = []
        self.hidden = 0

    def handle_starttag(self, tag, attrs):
        if tag in {"script", "style"}:
            self.hidden += 1

    def handle_endtag(self, tag):
        if tag in {"script", "style"}:
            self.hidden = max(0, self.hidden - 1)
        self.parts.append(" ")

    def handle_data(self, data):
        if not self.hidden:
            self.parts.append(data)


class SnippetExtractor:
    def extract(self, text: str) -> str:
        if len(text) > 10000:
            raise ResearchError("extraction_oversized")
        parser = _TextParser()
        parser.feed(text)
        passage = " ".join(unescape(" ".join(parser.parts)).split())
        if len(passage) > 1200 or any(ord(c) < 32 for c in passage):
            raise ResearchError("extraction_oversized")
        return passage


def content_fingerprint(passage: str) -> str:
    # Preserve case, punctuation, numbers and negation; only whitespace is normalized.
    return sha256(" ".join(passage.split()).encode()).hexdigest()


class DeterministicPlanner:
    strategy_id = "literal-snippet"
    strategy_version = 1

    def plan(self, question: str, max_queries: int):
        return (" ".join(question.split()),) if question.strip() and max_queries else ()


class BoundedQualifierPlanner:
    """Small non-promoted query probe; no inference, source expansion or recursion."""

    strategy_version = 1

    def __init__(self, *, expansion=False):
        self.expansion = expansion
        self.strategy_id = "bounded-expansion" if expansion else "bounded-qualifier"

    def plan(self, question, max_queries):
        return ((question, question + " specification")[:max_queries] if self.expansion
                else (question + " specification",))


def configured_query_planner(settings):
    if not settings.research_retrieval_experiments_enabled:
        return DeterministicPlanner()
    factories = {
        "literal-snippet-v1": DeterministicPlanner,
        "qualifier-v1": BoundedQualifierPlanner,
        "expansion-v1": lambda: BoundedQualifierPlanner(expansion=True),
    }
    return factories.get(settings.research_query_strategy, DeterministicPlanner)()


def planned_queries(planner, question: str, max_queries: int, *, with_reason=False):
    try:
        if not re.fullmatch(r"[a-z][a-z0-9_-]{0,79}", getattr(planner, "strategy_id", "")) or not (
            isinstance(getattr(planner, "strategy_version", None), int)
            and 1 <= planner.strategy_version <= 2147483647
        ):
            raise ValueError("unversioned query strategy")
        values = planner.plan(question, max_queries)
        if not isinstance(values, (list, tuple)) or len(values) > max_queries:
            raise ValueError("invalid plan")
        result = []
        for value in values:
            if not isinstance(value, str) or len(value) > 500 or not value.strip():
                raise ValueError("invalid query")
            value = " ".join(value.split())
            # Custom planners must preserve all explicit question terms; no tool syntax.
            from personal_ai.search.planning import preserves_question

            if not preserves_question(question, value):
                raise ValueError("query dropped constraints")
            if value not in result:
                result.append(value)
        queries = tuple(result)
        return (queries, "accepted") if with_reason else queries
    except Exception:  # noqa: BLE001 - optional planners fail to the deterministic baseline
        queries = tuple(DeterministicPlanner().plan(question, max_queries))
        return (queries, "invalid_strategy_fallback") if with_reason else queries
