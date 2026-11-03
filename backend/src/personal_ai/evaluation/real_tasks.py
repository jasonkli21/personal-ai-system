"""Paired synthetic chat tasks, with explicit separation of plumbing and model evidence."""

import argparse
import json
import platform
import subprocess
from datetime import UTC, datetime
from hashlib import sha256
from importlib.resources import files
from time import monotonic
from uuid import uuid4

import anyio

from personal_ai.applications.contracts import ApplicationContextRequest
from personal_ai.applications.registry import default_application_registry
from personal_ai.auth.scope import RequestScope
from personal_ai.context import ContextAssembler
from personal_ai.context.providers import ContextPreparationError
from personal_ai.contracts.execution import ContinuationRequest
from personal_ai.entities import Conversation, Message
from personal_ai.llm.errors import LLMError
from personal_ai.llm.execution import compose_pair
from personal_ai.services import ChatTurnService
from personal_ai.services.chat.events import TurnCompleted, TurnFailed
from personal_ai.settings import Settings
from personal_ai.storage import InMemoryConversationRepository, InMemoryMessageRepository
from personal_ai.usage.context import bind_usage_task
from personal_ai.usage.trace import Trace


def load_manifest():
    data = files(__package__).joinpath("fixtures/real_tasks/v1.json").read_bytes()
    return json.loads(data), sha256(data).hexdigest()


async def run_case(settings, pair, case, arm, run_id):
    conversations = InMemoryConversationRepository()
    messages = InMemoryMessageRepository(conversations)
    now = datetime.now(UTC)
    conversation = conversations.create(Conversation(
        id=uuid4(), owner_id="local", title="Synthetic task", created_at=now, updated_at=now,
    ))
    source_ids = []
    parent = None
    for source in (case["source"], case["distractor"]):
        for role, content in (("user", "Record this evidence card."), ("assistant", source)):
            message = messages.create(Message(
                id=uuid4(), conversation_id=conversation.id, owner_id="local",
                role=role, content=content, status="completed",
                parent_message_id=parent, created_at=now,
            ))
            parent = message.id
        source_ids.append(parent)
    # Explicit selection is a narrowing request. A fresh UUID exercises the
    # canonical cross-branch deny before any provider receives the turn.
    selected = {"direct": (), "selected": (source_ids[0],), "eligible": None}[arm]
    if case["require_scope_denial"]:
        selected = (uuid4(),)
    request_id = uuid4()
    registration = default_application_registry().registration("personal_ai")
    scope = ApplicationContextRequest(
        scope=RequestScope(
            owner_id="local", acting_user_id="local", application_id="personal_ai",
            request_id=str(request_id),
        ),
        definition=registration.definition,
    )
    service = ChatTurnService(
        conversations, messages, pair.generator, owner_id="local",
        application_context=scope, model=pair.generator.identity.model_id,
        context_assembler=ContextAssembler(settings, pair.counter),
    )
    request = ContinuationRequest(
        content=case["prompt"], idempotency_key=request_id, candidate_message_ids=selected,
    )
    start = monotonic()
    result = None
    status = "no_terminal"
    with bind_usage_task("chat_generation", request_id=str(request_id), run_id=str(run_id)):
        try:
            stream = await anyio.to_thread.run_sync(service.continue_turn, conversation.id, request)
            async for event in stream:
                if isinstance(event, TurnCompleted):
                    result, status = event.message, "completed"
                elif isinstance(event, TurnFailed):
                    status = "generation_failed"
        except ContextPreparationError as error:
            status = (
                "scope_denied" if error.code == "continuation_source_not_active_completed"
                else "preparation_failed"
            )
        except LLMError as error:
            status = error.code
    denied = status == "scope_denied"
    text = result.content.casefold() if result else ""
    leaked = any(marker.casefold() in text for marker in case["forbidden"])
    success = bool(result) and not leaked and all(item.casefold() in text for item in case["required"])
    if case["family"] == "safe_denial":
        # A deny phrase is a literal proxy, with separate leakage accounting.
        success = success and any(phrase in text for phrase in ("decline", "cannot", "can't", "won't"))
    if case["require_scope_denial"]:
        success = denied
        leaked = leaked or result is not None
    attribution = result.attribution if result else None
    return {
        "id": case["id"], "family": case["family"], "split": case["split"], "arm": arm,
        "case_digest": sha256(json.dumps(case, sort_keys=True).encode()).hexdigest(),
        "request_id": request_id, "status": status,
        "completed": result is not None, "scope_denied": denied,
        "rubric_pass": success, "forbidden_output": leaked,
        "source_selected": bool(attribution and source_ids[0] in attribution.source_message_ids),
        "distractor_selected": bool(attribution and source_ids[1] in attribution.source_message_ids),
        "input_tokens": attribution.input_tokens if attribution else None,
        "output_tokens": attribution.output_tokens if attribution else None,
        "usage_confidence": attribution.usage_confidence if attribution else None,
        "elapsed_ms": int((monotonic() - start) * 1000),
    }


async def run(settings, pair, manifest, trace, run_id, cases):
    rows = []
    with trace.capture():
        for case in cases:
            for arm in manifest["arms"]:
                row = await run_case(settings, pair, case, arm, run_id)
                row["request"] = trace.request_ref(row.pop("request_id"))
                rows.append(row)
    return rows


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--trace", help="New JSONL basename in the current directory")
    parser.add_argument("--local-case", help="Explicitly run one development case on configured local inference")
    args = parser.parse_args()
    manifest, corpus_digest = load_manifest()
    bounds = {
        "max_context_tokens": manifest["context_tokens"],
        "max_response_tokens": manifest["output_tokens"],
        "request_timeout_seconds": manifest["deadline_seconds"],
        "summary_trigger_tokens": 2048,
    }
    if args.local_case:
        cases = [case for case in manifest["cases"] if case["id"] == args.local_case
                 and case["split"] == "development" and case["family"] != "safe_denial"]
        if not cases or not args.trace:
            parser.error("a positive development case and --trace are required for local runs")
        settings = Settings(**bounds)
        if settings.inference_profile != "local_llama" or settings.inference_cost_mode != "local_only":
            parser.error("local runs require the explicitly configured local-only profile")
        from personal_ai.persistence.factory import persistence_factory

        usage = persistence_factory(settings).provider_usage_accounting(settings)
        tier = "E2_attempt"
    else:
        settings = Settings(
            _env_file=None, ai_provider="fake", ai_model="unused", app_environment="test",
            inference_profile="offline_fake", inference_cost_mode="offline_fake", **bounds,
        )
        usage = None
        cases = manifest["cases"]
        tier = "E1_scripted"
    pair = compose_pair(settings, usage)
    # Git identity binds the receipt; no source paths, env values or Git remote are recorded.
    commit = subprocess.check_output(["git", "rev-parse", "HEAD"], text=True).strip()
    dirty = bool(subprocess.check_output(
        ["git", "status", "--porcelain", "--untracked-files=normal"],
    ))
    run_id, trace = uuid4(), Trace()
    configuration = {
        "workspace_dirty": dirty,
        "corpus": corpus_digest, "profile": settings.inference_profile,
        "model": pair.generator.identity.model_id, "serializer": pair.generator.identity.serializer_id,
        "runtime": settings.local_llama_build if args.local_case else "synthetic",
        "policy": manifest["policy"], "seed": manifest["seed"], "temperature": manifest["temperature"],
        "bounds": bounds, "os": platform.system(), "machine": platform.machine(),
        "python": platform.python_version(),
    }
    if args.local_case:
        profile = pair.generator.admission.profile
        configuration["registry_ref"] = profile.ref.model_dump(mode="json")
        configuration["endpoint_identity"] = profile.endpoint_id
    configuration_digest = sha256(json.dumps(configuration, sort_keys=True).encode()).hexdigest()
    rows = anyio.run(run, settings, pair, manifest, trace, run_id, cases)
    summary = None
    if args.trace:
        summary = trace.export(
            args.trace, commit=commit, configuration=configuration_digest, run_id=run_id,
        )
    print(json.dumps({
        "version": 1, "tier": tier, "commit": commit, "run_id": str(run_id),
        "configuration": configuration, "configuration_digest": configuration_digest,
        "trace_summary": summary, "results": rows,
    }, sort_keys=True))
    if any(row["forbidden_output"] or row["id"] == "denial-scope" and not row["scope_denied"] for row in rows):
        return 1
    if args.local_case:
        return 0 if any(row["arm"] == "selected" and row["rubric_pass"] for row in rows) else 1
    return 0 if all(row["completed"] for row in rows if row["id"] != "denial-scope") else 1


if __name__ == "__main__":
    raise SystemExit(main())
