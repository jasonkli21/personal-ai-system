"""Generate the supported external consumer subset from executable API models."""

import json

from personal_ai.api.schemas import (
    ErrorResponse,
    ExternalCreateConversationRequest,
    SSEMessageCreated,
    SSEResponseCompleted,
    SSEResponseDelta,
    SSEResponseError,
)

CONSUMER_API_VERSION = "1.1.0"
OPERATIONS = {
    "/v1/retrieval/query": ("post",),
    "/v1/tools/retrieval.query.v1/invoke": ("post",),
    "/v1/conversations": ("get", "post"),
    "/v1/conversations/{conversation_id}": ("get",),
    "/v1/conversations/{conversation_id}/context-preview": ("post",),
    "/v1/conversations/{conversation_id}/continue": ("post",),
    "/v1/conversations/{conversation_id}/continuations/{idempotency_key}": ("get",),
}


def consumer_openapi():
    from personal_ai.main import create_app

    full = create_app(selected_contributions=()).openapi()
    schemas = full["components"]["schemas"]
    schemas[ExternalCreateConversationRequest.__name__] = (
        ExternalCreateConversationRequest.model_json_schema()
    )
    events = {}
    for name, model in (
        (None, ErrorResponse),
        ("message.created", SSEMessageCreated),
        ("response.delta", SSEResponseDelta),
        ("response.completed", SSEResponseCompleted),
        ("response.error", SSEResponseError),
    ):
        schema = model.model_json_schema(ref_template="#/components/schemas/{model}")
        schemas.update(schema.pop("$defs", {}))
        schemas[model.__name__] = schema
        if name:
            events[name] = {"$ref": "#/components/schemas/" + model.__name__}
    paths = {
        path: {method: full["paths"][path][method] for method in methods}
        for path, methods in OPERATIONS.items()
    }
    paths["/v1/conversations"]["post"]["requestBody"] = {
        "required": True,
        "content": {
            "application/json": {
                "schema": {
                    "$ref": "#/components/schemas/ExternalCreateConversationRequest"
                }
            }
        },
    }
    for path in paths.values():
        for operation in path.values():
            operation["security"] = [{"GoogleUserIDToken": []}]
            operation["parameters"] = [
                *operation.get("parameters", []),
                {
                    "in": "header",
                    "name": "X-Application-ID",
                    "required": True,
                    "schema": {"type": "string"},
                },
                {
                    "in": "header",
                    "name": "X-Workspace-ID",
                    "required": False,
                    "schema": {"type": "string"},
                    "description": "Required when the installed application requires workspace scope; membership is server-owned.",
                },
            ]
            # FastAPI's default validation schema differs from our safe exception handler.
            for status in ("400", "401", "403", "404", "408", "409", "413", "422", "429", "503"):
                operation["responses"][status] = {
                    "description": "Safe middleware/service error; see consumer-v1.md",
                    "content": {
                        "application/json": {
                            "schema": {"$ref": "#/components/schemas/ErrorResponse"}
                        }
                    },
                }
    needed = set()

    def collect(value):
        if isinstance(value, dict):
            ref = value.get("$ref", "")
            if ref.startswith("#/components/schemas/"):
                name = ref.rsplit("/", 1)[-1]
                if name not in needed:
                    needed.add(name)
                    collect(schemas[name])
            for child in value.values():
                collect(child)
        elif isinstance(value, list):
            for child in value:
                collect(child)

    collect(paths)
    collect(events)
    return {
        "openapi": full["openapi"],
        "info": {"title": "Personal AI external consumer", "version": CONSUMER_API_VERSION},
        "paths": paths,
        "components": {
            "schemas": {name: schemas[name] for name in sorted(needed)},
            "securitySchemes": {
                "GoogleUserIDToken": {
                    "type": "http",
                    "scheme": "bearer",
                    "bearerFormat": "Google OIDC ID token",
                }
            },
        },
        "x-sse-events": events,
        "x-external-request-max-bytes": 131072,
        "x-stream-resume": "unsupported; reconcile the original idempotency_key",
    }


def serialized_contract():
    return json.dumps(consumer_openapi(), indent=2, sort_keys=True) + "\n"
