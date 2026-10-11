import { authenticatedFetch } from "./auth";
import { readSseFrames, SseError } from "./sse";

export type Conversation = {
  id: string;
  owner_id: string;
  application_id: string;
  workspace_id: string | null;
  title: string | null;
  created_at: string;
  updated_at: string;
};

export type Message = {
  id: string;
  conversation_id: string;
  owner_id: string;
  application_id: string;
  workspace_id: string | null;
  role: "user" | "assistant";
  content: string;
  status: "pending" | "streaming" | "completed" | "failed" | "superseded";
  created_at: string;
  parent_message_id: string | null;
  supersedes_message_id: string | null;
  model: string | null;
  error_code: string | null;
  attribution?: TurnAttribution | null;
};

export type TurnAttribution = {
  mode: "connected_provider" | "manual_external";
  fact_source: "server_observed" | "client_reported" | "user_declared";
  execution_origin?: "automatic_managed" | "connected_local" | "manual_import" | null;
  provider_id: string | null;
  model_id: string | null;
  recorded_at: string;
  latency_ms?: number | null;
  input_tokens?: number | null;
  output_tokens?: number | null;
  usage_source?: "provider" | "estimated" | null;
  usage_confidence?: "reported" | "estimated" | null;
  model_verified: false;
  package_fingerprint?: string | null;
  connection_id?: string | null;
  connection_revision?: number | null;
};

export type ContextSourceClass = "global_profile" | "domain_profile" | "domain_current" | "domain_history" | "ai_memory" | "conversation" | "external_research" | "tool_result" | "client_context";

export type ContextEntityReference = {
  entity_type: string;
  entity_id: string;
  application_id: string;
  workspace_id: string | null;
};

/** Advisory host metadata. Server identity and authorization remain authoritative. */
export type ApplicationLaunchContext = {
  schema_version: "application-launch-v1";
  application_id: string;
  workspace_id: string | null;
  entity_refs: ContextEntityReference[];
  view_id: string | null;
  conversation_id: string;
  client_context: Record<string, string | number | boolean | null>;
};

export type ExternalDisclosureOptions = {
  allowed: boolean;
  allowed_context_categories: ContextSourceClass[];
  maximum_sensitivity: "public" | "personal" | "sensitive" | "restricted";
};

export type SidecarActionOptions = {
  connected_provider_disclosure: ExternalDisclosureOptions;
  manual_external_disclosure: ExternalDisclosureOptions;
  allow_manual_import_context: boolean;
  copy_allowed: boolean;
  draft_insert_target_ids: string[];
  future_apply_operation_ids: string[];
};

export type ConversationDetail = { conversation: Conversation; messages: Message[] };
type ErrorPayload = { error?: { message?: string } };
type MessageCreatedEvent = { message: Message };
type ResponseDeltaEvent = { message_id: string; delta: string };
type ResponseCompletedEvent = { message: Message };
type ResponseErrorEvent = { message_id: string; code: string; message: string };

export type StreamHandlers = {
  onMessageCreated: (message: Message) => void;
  onDelta: (messageId: string, delta: string) => void;
  onCompleted: (message: Message) => void;
  onError: (event: ResponseErrorEvent) => void;
};

export type ExternalMode = "connected_provider" | "manual_external";
export type ExecutionChoice = {
  mode: "automatic" | ExternalMode;
  endpoint?: { endpoint_profile_id: string; profile_version: number } | null;
  model_id?: string | null;
  connection_id?: string | null;
  connection_revision?: number | null;
  caller_id?: string | null;
  audience?: string | null;
};
export type ContinuationRequest = {
  content: string;
  idempotency_key: string;
  choice: ExecutionChoice;
  candidate_message_ids?: string[] | null;
  launch_context?: ApplicationLaunchContext | null;
  excluded_source_classes?: ContextSourceClass[];
};
export type ContextPackage = {
  schema_version: "context-package-v1";
  messages: { role: "system" | "developer" | "user" | "assistant"; content: string }[];
  included_sources: { category: string; item_count: number; sensitivity: string[]; authority: string[] }[];
  excluded_sources: { category: string; reason: string; item_count: number }[];
  selected_message_count: number;
  summarized_source_message_count?: number;
  input_tokens: number;
  counter_kind: "estimated";
  effective_sensitivity: string;
  maximum_sensitivity: string;
  policy_version: string;
  grant_versions: string[];
  expires_at: string;
  fingerprint: string;
};
export type PreparedExecution = {
  owner_id: string;
  application_id: string;
  workspace_id: string | null;
  conversation_id: string;
  reservation_id: string;
  branch_digest: string;
  source_authority_digest: string;
  provider_id: string;
  model_id: string;
  execution_profile: {
    endpoint: { endpoint_profile_id: string; profile_version: number };
    endpoint_id: string;
    deployment_id: string;
    serializer_id: string;
    runtime_id: string;
    external_transport_id?: string | null;
  };
  connection_id: string;
  connection_revision: number;
  messages: ContextPackage["messages"];
  effective_sensitivity: string;
  maximum_sensitivity: string;
  policy_version: string;
  max_output_bytes: number;
  max_output_chars: number;
  timeout_seconds: number;
};
export type ExplicitProfileOption = {
  endpoint: { endpoint_profile_id: string; profile_version: number };
  provider_id: string;
  capabilities: string[];
  maximum_sensitivity: string;
  external_transport_id: string;
};
export type ExecutionOptions = {
  modes: ("automatic" | ExternalMode)[];
  explicit_profiles: ExplicitProfileOption[];
  sidecar: SidecarActionOptions;
};
export type PreparedExternalTurn = {
  message_id: string;
  reservation_id: string;
  mode: ExternalMode;
  provider_id: string | null;
  model_id: string | null;
  package_fingerprint: string;
  context_package: ContextPackage;
  portable_prompt: string | null;
  connected_execution: PreparedExecution | null;
};
export type ContextPreview = {
  selected_message_count: number;
  planned_sources: { category: string; operation: string; fields: string[]; max_results: number; max_tokens: number | null }[];
  excluded_sources: { category: string; reason: string }[];
};
export type ExternalTurnReconciliation = {
  state: "not_found" | "not_external" | "prepared" | "prepared_stale" | "dispatched" | "completed" | "cancelled" | "unknown";
  message_id: string | null;
  package_fingerprint?: string | null;
  mode?: ExternalMode | null;
  expires_at?: string | null;
  stale_reason?: string | null;
};
export type SignedDispatchGrant = {
  claims: Record<string, unknown>;
  signature: string;
};
export type BridgePairing = {
  caller_id: string;
  audience: string;
  connection_id: string;
  connection_revision: number;
  expires_at: number;
  caller_authorization: string;
};
export type BridgeConnection = {
  connection_id: string;
  state: string;
  plan_permission: boolean;
  revision: number;
  remote_revocation: string;
  account_label: string;
  usage: { state: "available" | "limit" | "unavailable" | "unknown"; observed_at: number | null } | null;
  recovery: {
    reconnect: "local_operator";
    switch_account: "local_operator_new_pairing";
    manage_usage: "provider_account_ui";
  };
};
export type BridgeModel = { slug: string; display_name: string };

export type ApplicationScopeRequest = {
  /** App IDs are extensible; the backend registry remains the authority. */
  applicationId?: string;
  workspaceId?: string | null;
  requestId?: string;
  capabilities?: string[];
  clientContext?: Record<string, string | number | boolean | null>;
};

export function applicationScopeHeaders(scope: ApplicationScopeRequest = {}): Record<string, string> {
  const headers: Record<string, string> = {
    "X-Application-ID": scope.applicationId ?? "personal_ai",
    "X-Request-ID": scope.requestId ?? crypto.randomUUID(),
  };
  if (scope.workspaceId) headers["X-Workspace-ID"] = scope.workspaceId;
  if (scope.capabilities?.length) headers["X-Client-Capabilities"] = scope.capabilities.join(",");
  if (scope.clientContext && Object.keys(scope.clientContext).length) {
    headers["X-Client-Context"] = JSON.stringify(scope.clientContext);
  }
  return headers;
}

export class ApiError extends Error {
  constructor(message: string, readonly status?: number) {
    super(message);
    this.name = "ApiError";
  }
}

async function request<T>(path: string, init?: RequestInit, scope?: ApplicationScopeRequest): Promise<T> {
  let response: Response;
  try {
    response = await authenticatedFetch(`/api${path}`, {
      ...init,
      headers: { "Content-Type": "application/json", ...applicationScopeHeaders(scope), ...init?.headers },
    });
  } catch {
    throw new ApiError("Unable to reach the Personal AI service. Please try again.");
  }
  if (!response.ok) {
    const body = (await response.json().catch(() => ({}))) as ErrorPayload;
    throw new ApiError(body.error?.message ?? "The request could not be completed. Please try again.", response.status);
  }
  return response.json() as Promise<T>;
}

async function streamRequest(path: string, init: RequestInit, handlers: StreamHandlers, scope?: ApplicationScopeRequest): Promise<void> {
  let response: Response;
  try {
    response = await authenticatedFetch(`/api${path}`, {
      ...init,
      headers: { "Content-Type": "application/json", ...applicationScopeHeaders(scope), ...init.headers },
    });
  } catch {
    throw new ApiError("Unable to reach the Personal AI service. Please try again.");
  }
  if (!response.ok) {
    const body = (await response.json().catch(() => ({}))) as ErrorPayload;
    throw new ApiError(body.error?.message ?? "The request could not be completed. Please try again.", response.status);
  }
  if (!response.body) throw new ApiError("The response stream could not be read. Please try again.");

  let terminal = false;
  const consume = (event: string, data: string) => {
    if (!event || !data) return;
    try {
      switch (event) {
        case "message.created": {
          const payload = JSON.parse(data) as MessageCreatedEvent;
          if (!payload.message || typeof payload.message.id !== "string") throw new Error("Invalid message");
          handlers.onMessageCreated(payload.message);
          break;
        }
        case "response.delta": {
          const payload = JSON.parse(data) as ResponseDeltaEvent;
          if (typeof payload.message_id !== "string" || typeof payload.delta !== "string") throw new Error("Invalid delta");
          handlers.onDelta(payload.message_id, payload.delta);
          break;
        }
        case "response.completed": {
          const payload = JSON.parse(data) as ResponseCompletedEvent;
          if (!payload.message || typeof payload.message.id !== "string" || payload.message.role !== "assistant" || payload.message.status !== "completed" || typeof payload.message.content !== "string") throw new Error("Invalid completion");
          handlers.onCompleted(payload.message);
          terminal = true;
          break;
        }
        case "response.error": {
          const payload = JSON.parse(data) as ResponseErrorEvent;
          if (typeof payload.message_id !== "string" || typeof payload.code !== "string" || typeof payload.message !== "string") throw new Error("Invalid error");
          handlers.onError(payload);
          terminal = true;
          break;
        }
      }
    } catch {
      throw new ApiError("The response stream could not be read. Please try again.");
    }
  };

  try {
    for await (const frame of readSseFrames(response, { frameCharacters: 131072, totalBytes: 4 * 1024 * 1024 })) {
      consume(frame.event, frame.data);
      if (terminal) return;
    }
    throw new ApiError("The response was interrupted. Please retry.");
  } catch (error) {
    if (error instanceof SseError && error.kind === "incomplete") {
      throw new ApiError("The response was interrupted. Please retry.");
    }
    throw error instanceof ApiError ? error : new ApiError("The response stream could not be read. Please try again.");
  }
}

export const conversationsApi = {
  create(title?: string, signal?: AbortSignal, scope?: ApplicationScopeRequest) {
    return request<Conversation>("/conversations", { method: "POST", body: JSON.stringify(title ? { title } : {}), signal }, scope);
  },
  async list(signal?: AbortSignal, scope?: ApplicationScopeRequest) {
    return (await request<{ conversations: Conversation[] }>("/conversations", { signal }, scope)).conversations;
  },
  get(conversationId: string, signal?: AbortSignal, scope?: ApplicationScopeRequest) {
    return request<ConversationDetail>(`/conversations/${encodeURIComponent(conversationId)}`, { signal }, scope);
  },
  send(conversationId: string, content: string, handlers: StreamHandlers, signal?: AbortSignal, scope?: ApplicationScopeRequest) {
    return streamRequest(`/conversations/${encodeURIComponent(conversationId)}/messages`, { method: "POST", body: JSON.stringify({ content }), signal }, handlers, scope);
  },
  regenerate(conversationId: string, messageId: string, handlers: StreamHandlers, signal?: AbortSignal, scope?: ApplicationScopeRequest) {
    return streamRequest(`/conversations/${encodeURIComponent(conversationId)}/messages/${encodeURIComponent(messageId)}/regenerate`, { method: "POST", signal }, handlers, scope);
  },
  editAndRetry(conversationId: string, messageId: string, content: string, handlers: StreamHandlers, signal?: AbortSignal, scope?: ApplicationScopeRequest) {
    return streamRequest(`/conversations/${encodeURIComponent(conversationId)}/messages/${encodeURIComponent(messageId)}/edit-and-retry`, { method: "POST", body: JSON.stringify({ content }), signal }, handlers, scope);
  },
  continueTurn(conversationId: string, continuation: ContinuationRequest, handlers: StreamHandlers, signal?: AbortSignal, scope?: ApplicationScopeRequest) {
    return streamRequest(`/conversations/${encodeURIComponent(conversationId)}/continue`, { method: "POST", body: JSON.stringify(continuation), signal }, handlers, scope);
  },
  executionOptions(signal?: AbortSignal, scope?: ApplicationScopeRequest) {
    return request<ExecutionOptions>("/conversations/execution-options", { signal }, scope);
  },
  prepareExternal(conversationId: string, continuation: ContinuationRequest, signal?: AbortSignal, scope?: ApplicationScopeRequest) {
    return request<PreparedExternalTurn>(`/conversations/${encodeURIComponent(conversationId)}/external-turns/prepare`, { method: "POST", body: JSON.stringify(continuation), signal }, scope);
  },
  previewExternal(conversationId: string, continuation: ContinuationRequest, signal?: AbortSignal, scope?: ApplicationScopeRequest) {
    return request<ContextPreview>(`/conversations/${encodeURIComponent(conversationId)}/external-turns/preview`, { method: "POST", body: JSON.stringify(continuation), signal }, scope);
  },
  reconcileExternal(conversationId: string, idempotencyKey: string, signal?: AbortSignal, scope?: ApplicationScopeRequest) {
    return request<ExternalTurnReconciliation>(`/conversations/${encodeURIComponent(conversationId)}/external-turns/requests/${encodeURIComponent(idempotencyKey)}`, { signal }, scope);
  },
  abandonExternalByKey(conversationId: string, idempotencyKey: string, signal?: AbortSignal, scope?: ApplicationScopeRequest) {
    return request<Message>(`/conversations/${encodeURIComponent(conversationId)}/external-turns/requests/${encodeURIComponent(idempotencyKey)}/abandon`, { method: "POST", signal }, scope);
  },
  dispatchExternal(conversationId: string, messageId: string, connectedExecution: PreparedExecution, signal?: AbortSignal, scope?: ApplicationScopeRequest) {
    return request<{ proof: SignedDispatchGrant }>(`/conversations/${encodeURIComponent(conversationId)}/external-turns/${encodeURIComponent(messageId)}/dispatch`, { method: "POST", body: JSON.stringify({ connected_execution: connectedExecution }), signal }, scope);
  },
  importManual(conversationId: string, messageId: string, body: { package_fingerprint: string; text: string; provider_label?: string; model_label?: string }, signal?: AbortSignal, scope?: ApplicationScopeRequest) {
    return request<Message>(`/conversations/${encodeURIComponent(conversationId)}/external-turns/${encodeURIComponent(messageId)}/import`, { method: "POST", body: JSON.stringify(body), signal }, scope);
  },
  completeConnected(conversationId: string, messageId: string, body: { package_fingerprint: string; text: string; latency_ms?: number; input_tokens?: number; output_tokens?: number }, signal?: AbortSignal, scope?: ApplicationScopeRequest) {
    return request<Message>(`/conversations/${encodeURIComponent(conversationId)}/external-turns/${encodeURIComponent(messageId)}/complete`, { method: "POST", body: JSON.stringify(body), signal }, scope);
  },
  failExternal(conversationId: string, messageId: string, packageFingerprint: string, signal?: AbortSignal, scope?: ApplicationScopeRequest) {
    return request<Message>(`/conversations/${encodeURIComponent(conversationId)}/external-turns/${encodeURIComponent(messageId)}/fail`, { method: "POST", body: JSON.stringify({ package_fingerprint: packageFingerprint, code: "bridge_execution_interrupted" }), signal }, scope);
  },
  abandonExternal(conversationId: string, messageId: string, packageFingerprint: string, signal?: AbortSignal, scope?: ApplicationScopeRequest) {
    return request<Message>(`/conversations/${encodeURIComponent(conversationId)}/external-turns/${encodeURIComponent(messageId)}/abandon`, { method: "POST", body: JSON.stringify({ package_fingerprint: packageFingerprint }), signal }, scope);
  },
};
