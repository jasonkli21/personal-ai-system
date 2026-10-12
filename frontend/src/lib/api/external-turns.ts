import { request } from "./client";
import type { ApplicationScopeRequest } from "./common";
import type { Message } from "./conversations";

export type ContextSourceClass = "global_profile" | "domain_profile" | "domain_current" | "domain_history" | "ai_memory" | "conversation" | "external_research" | "tool_result" | "client_context";
export type ContextEntityReference = {
  entity_type: string;
  entity_id: string;
  application_id: string;
  workspace_id: string | null;
};
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
  mutation_operations?: { operation_id: string; version: number }[];
  connected_provider_disclosure: ExternalDisclosureOptions;
  manual_external_disclosure: ExternalDisclosureOptions;
  manual_import_reuse: {
    allowed: boolean;
    maximum_sensitivity: "public" | "personal" | "sensitive" | "restricted";
  };
  copy_allowed: boolean;
  draft_insert_target_ids: string[];
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
  federation_choice_ids?: string[];
};
/** Destination-scoped opaque selector; canonical grant data stays on the server. */
export type FederationChoiceOption = {
  id: string;
  categoryLabel: string;
};
export type ContextPackage = {
  schema_version: "context-package-v2";
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
export type SignedDispatchGrant = { claims: Record<string, unknown>; signature: string };
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

export const externalTurnEndpoints = {
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
