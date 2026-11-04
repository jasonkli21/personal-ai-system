"""Deterministic bounded derivative navigation; every read resolves fresh authority."""

import re
import unicodedata
from collections import defaultdict
from hashlib import sha256
from math import log

from personal_ai.memory.research.contracts import (
    MAX_BYTES,
    MAX_TOPICS,
    PAGE_SIZE,
    IndexEntry,
    ResearchFailure,
    ResearchIndex,
    ResearchScope,
    Topic,
    digest,
)

STOP = frozenset(
    (
        "a",
        "an",
        "the",
        "for",
        "of",
        "is",
        "to",
        "and",
        "or",
        "use",
        "what",
        "how",
        "before",
        "after",
        "session",
    )
)


def terms(text):
    normalized = unicodedata.normalize("NFKC", text).casefold()
    normalized = re.sub(r"[\u2010-\u2015\u2212\ufe58\ufe63\uff0d]", "-", normalized)
    words = re.findall(r"[^\W_]+(?:-[^\W_]+)*", normalized, flags=re.UNICODE)
    # Treat common letter-plus-number identifiers consistently across a hyphen
    # or whitespace boundary, while retaining exact full-token matching.
    folded = []
    position = 0
    while position < len(words):
        current = words[position]
        if (
            position + 1 < len(words)
            and re.fullmatch(r"[a-z]+", current)
            and re.fullmatch(r"\d+", words[position + 1])
        ):
            folded.append(f"{current}-{words[position + 1]}")
            position += 2
        else:
            folded.append(current)
            position += 1
    values = tuple(sorted(set(folded) - STOP))
    if len(values) > 128 or any(len(v) > 64 for v in values):
        raise ResearchFailure("incomplete", "term_cap")
    return values


def label(text):
    # Never turn path syntax, control characters or instructions into navigation.
    if not re.fullmatch(r"[A-Za-z][A-Za-z0-9 -]{0,79}", text) or any(
        t in text.casefold() for t in ("ignore", "instruction", "prompt", "override")
    ):
        return "Topic"
    return text


def build_index(source, query, *, cancelled=lambda: False):
    with source.lease(query, cancelled=cancelled):
        records = source.universe(query)
        generation = source.generation(query)
        entries, groups = [], {}
        for record in records:
            source.check(query, cancelled=cancelled)
            parent = None
            for depth in range(1, len(record.topic) + 1):
                path = record.topic[:depth]
                topic_id = digest([generation, path])
                groups.setdefault(topic_id, (parent, label(path[-1]), depth, []))[3].append(
                    record.id
                )
                parent = topic_id
            entries.append(
                IndexEntry(
                    record_id=record.id,
                    fingerprint=digest(record),
                    content_fingerprint=sha256(record.content.encode()).hexdigest(),
                    dependency_version=source.dependency(record).version,
                    terms=terms(record.content + " " + " ".join(record.topic)),
                    topic_id=parent,
                )
            )
        if len(groups) > MAX_TOPICS:
            raise ResearchFailure("incomplete", "topic_cap")
        index = ResearchIndex(
            generation=generation,
            query_identity=source.query_identity(query),
            scope=ResearchScope.from_request(query.canonical.scope),
            project=query.project,
            entries=tuple(entries),
            topics=tuple(
                Topic(
                    id=key,
                    parent_id=value[0],
                    label=value[1],
                    depth=value[2],
                    leaf_ids=tuple(sorted(value[3])),
                )
                for key, value in sorted(groups.items())
            ),
        )
        if len(index.model_dump_json().encode()) > MAX_BYTES:
            raise ResearchFailure("incomplete", "index_bytes_cap")
        return index


def validate_index(source, index, query):
    if (
        index.scope != ResearchScope.from_request(query.canonical.scope)
        or index.project != query.project
        or index.query_identity != source.query_identity(query)
        or index.generation != source.generation(query)
    ):
        raise ResearchFailure("denied", "generation_changed")
    # Restored/tampered snapshots cannot silently omit an eligible record or
    # change terms/topic edges under a copied generation label.
    if index != build_index(source, query):
        raise ResearchFailure("denied", "index_integrity")


def browse(source, index, query, *, parent_id=None, cancelled=lambda: False):
    with source.lease(query, cancelled=cancelled):
        validate_index(source, index, query)
        if parent_id is not None and not any(t.id == parent_id for t in index.topics):
            raise ResearchFailure("denied", "unknown_topic")
        return tuple(t for t in index.topics if t.parent_id == parent_id)


def fetch_topic(source, index, query, topic_id, *, page=0, cancelled=lambda: False):
    if page not in (0, 1):
        raise ResearchFailure("incomplete", "expansion_cap")
    with source.lease(query, cancelled=cancelled):
        validate_index(source, index, query)
        topic = next((t for t in index.topics if t.id == topic_id), None)
        if topic is None:
            raise ResearchFailure("denied", "unknown_topic")
        if len(topic.leaf_ids) > 2 * PAGE_SIZE:
            raise ResearchFailure("incomplete", "topic_page_cap")
        ids = topic.leaf_ids[page * PAGE_SIZE : (page + 1) * PAGE_SIZE]
        return source.fetch(index, query, ids)


def lexical_ranks(index, text):
    query_terms = set(terms(text))
    postings = defaultdict(list)
    for entry in index.entries:
        for term in entry.terms:
            postings[term].append(entry.record_id)
    scores = defaultdict(float)
    for term in sorted(query_terms):
        ids = postings[term]
        for identifier in ids:
            scores[identifier] += log(1 + (len(index.entries) + 1) / (len(ids) + 1))
    return tuple(sorted(scores, key=lambda i: (-scores[i], i)))


def fuse(lexical, semantic):
    scores = defaultdict(float)
    for ranking in (lexical, semantic):
        for position, identifier in enumerate(ranking, 1):
            scores[identifier] += 1 / (60 + position)
    return tuple(sorted(scores, key=lambda i: (-scores[i], i)))
