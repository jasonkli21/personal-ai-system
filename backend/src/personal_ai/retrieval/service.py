"""Standalone bounded use case. No persistence of passages or model integration."""

import asyncio
from datetime import UTC, datetime, timedelta
from threading import BoundedSemaphore
from time import monotonic

import anyio

from personal_ai.auth.application_clients import require_current_client_authority
from personal_ai.retrieval.contracts import RetrievalOutcome
from personal_ai.retrieval.external import ExternalBridge
from personal_ai.retrieval.installation import LexicalIndex, legacy_issuer_id, load_snapshot
from personal_ai.retrieval.journal import AttemptJournal, IntentConflict
from personal_ai.search.contracts import SearchDispatch

# Process bound, independent of application service instances/event loops.
_SLOTS = BoundedSemaphore(2)


class RetrievalService:
    def __init__(
        self,
        settings,
        scope,
        usage_factory,
        *,
        registrations=None,
        current_settings=None,
        request_authority=None,
    ):
        self.settings, self.scope = settings, scope
        self.usage_factory, self.registrations = usage_factory, registrations
        self.current_settings = current_settings or (lambda: settings)
        self.request_authority = request_authority

    def guard(self, snapshot, bridge=None, *, tool=False, tool_guard=None, deadline_at=None):
        require_current_client_authority()
        if self.request_authority is not None:
            self.request_authority()
        current_settings = self.current_settings()
        if (
            not current_settings.retrieval_enabled
            or current_settings.retrieval_installation_file
            != self.settings.retrieval_installation_file
            or current_settings.research_search_adapter != self.settings.research_search_adapter
            or current_settings.external_providers_kill_switch_enabled
            and bridge is not None
        ):
            raise ValueError("source_authority_changed")
        current = load_snapshot(self.settings.retrieval_installation_file)
        if (
            current.digest != snapshot.digest
            or not current.installation.allows(self.scope)
            or tool
            and not current.installation.tool_enabled
            or bridge is not None
            and (
                not current_settings.retrieval_external_enabled
                or not bridge.current(current_settings)
            )
        ):
            raise ValueError("source_authority_changed")
        if tool_guard:
            tool_guard()
        if deadline_at is not None and monotonic() >= deadline_at:
            raise TimeoutError("retrieval_deadline")

    async def query(self, query, *, tool=False, tool_guard=None):
        if not _SLOTS.acquire(blocking=False):
            return self.outcome(query, (), ("busy",))
        try:
            try:
                async with asyncio.timeout(self.settings.retrieval_timeout_seconds):
                    return await self._query(query, tool=tool, tool_guard=tool_guard)
            except IntentConflict:
                raise
            except TimeoutError:
                return self.outcome(query, (), ("timeout",))
            except Exception:  # noqa: BLE001 - never expose operator paths or source exceptions
                return self.outcome(query, (), ("source_unavailable",))
        finally:
            _SLOTS.release()

    async def _query(self, query, *, tool, tool_guard):
        deadline_at = monotonic() + self.settings.retrieval_timeout_seconds
        snapshot = await anyio.to_thread.run_sync(
            load_snapshot, self.settings.retrieval_installation_file
        )
        if not snapshot.installation.allows(self.scope):
            return self.outcome(query, (), ("source_unavailable",))
        guard = lambda: self.guard(
            snapshot, tool=tool, tool_guard=tool_guard, deadline_at=deadline_at
        )
        guard()
        now = datetime.now(UTC)
        items, reasons, dispatch, bridge = [], [], None, None
        if "local" in query.sources:
            # Access filtering happens before building index statistics or examining text.
            docs = tuple(d for d in snapshot.installation.documents if d.allows(self.scope, now))
            issuer_id = snapshot.installation.issuer_id or legacy_issuer_id(
                self.settings.retrieval_installation_file
            )
            found, excluded = LexicalIndex(docs, issuer_id=str(issuer_id)).search(
                query, self.scope, now
            )
            items.extend(found)
            reasons.extend(excluded)
        if "external" in query.sources:
            if (
                not self.settings.retrieval_external_enabled
                or self.settings.external_providers_kill_switch_enabled
                or self.settings.research_kill_switch_enabled
                or self.settings.app_environment not in {"local", "test"}
                or not any(
                    g.allows(self.scope) for g in snapshot.installation.external_query_access
                )
            ):
                reasons.append("external_not_admitted")
            elif not self.settings.retrieval_attempt_journal_file:
                reasons.append("external_unconfigured")
            else:
                try:
                    bridge = ExternalBridge(
                        self.settings, self.usage_factory, registrations=self.registrations
                    )
                    guard()
                    journal = AttemptJournal(self.settings.retrieval_attempt_journal_file)
                    deadline = now + timedelta(seconds=self.settings.retrieval_timeout_seconds)
                    operation = bridge.prepare(query, deadline)
                    if operation is not None:
                        denial = journal.reserve(self.scope, query)
                    else:
                        # A contradictory deterministic domain filter cannot dispatch.
                        denial = None
                    if denial:
                        reasons.append(denial)
                    elif operation is not None:
                        final_guard = lambda: self.guard(
                            snapshot,
                            bridge,
                            tool=tool,
                            tool_guard=tool_guard,
                            deadline_at=deadline_at,
                        )
                        found, excluded, dispatch = await bridge.search(
                            query,
                            deadline,
                            final_guard,
                            journal.scope_key(self.scope),
                            operation=operation,
                        )
                        final_guard()
                        items.extend(found)
                        reasons.extend(excluded)
                        # Completion is observation only, never permission to replay bodies.
                        journal.complete(self.scope, query)
                except IntentConflict:
                    raise
                except Exception as error:  # noqa: BLE001 - closed safe reason vocabulary
                    code = getattr(error, "code", "")
                    invocation_id = getattr(error, "usage_invocation_id", None)
                    attempt_id = getattr(error, "usage_attempt_id", None)
                    if invocation_id is not None:
                        dispatch = SearchDispatch((), invocation_id, attempt_id)
                    reasons.append(
                        {
                            "search_quota": "quota",
                            "search_timeout": "timeout",
                            "search_invalid_response": "invalid_source",
                            "search_constraint_unsupported": "freshness_unverified",
                            "search_unavailable": "external_outcome_unknown",
                        }.get(code, "external_not_admitted")
                    )
        try:
            self.guard(snapshot, bridge, tool=tool, tool_guard=tool_guard, deadline_at=deadline_at)
            now = datetime.now(UTC)
            if any(item.expires_at <= now for item in items):
                raise ValueError("source_expired")
        except TimeoutError:
            raise
        except Exception:  # noqa: BLE001 - remove all bodies after any final authority failure
            return self.outcome(query, (), ("source_authority_changed",))
        outcome = self.outcome(query, items, reasons, dispatch)
        self.guard(snapshot, bridge, tool=tool, tool_guard=tool_guard, deadline_at=deadline_at)
        return outcome

    @staticmethod
    def outcome(query, items, reasons, dispatch=None):
        selected, quote_bytes, token_bound = [], 0, 0
        reasons = list(reasons)
        seen = set()
        for item in items:
            if item.citation_id in seen:
                continue
            seen.add(item.citation_id)
            size = len(item.quote.encode())
            # Conservative UTF-8 byte ceiling for all serialized evidence metadata + quotes.
            tokens = len(item.model_dump_json().encode())
            if (
                len(selected) >= query.max_items
                or quote_bytes + size > query.max_quote_bytes
                or token_bound + tokens > query.max_tokens
            ):
                reasons.append("budget")
                continue
            selected.append(item)
            quote_bytes += size
            token_bound += tokens
        reasons = tuple(dict.fromkeys(reasons))
        state = (
            "partial"
            if selected and reasons
            else "complete"
            if selected or not reasons
            else "unavailable"
        )
        if not selected and not reasons:
            reasons = ("no_matches",)
        return RetrievalOutcome(
            idempotency_key=query.idempotency_key,
            state=state,
            reasons=reasons,
            items=tuple(selected),
            quote_bytes=quote_bytes,
            token_upper_bound=token_bound,
            usage_invocation_id=dispatch.usage_invocation_id if dispatch else None,
            usage_attempt_id=dispatch.usage_attempt_id if dispatch else None,
        )
