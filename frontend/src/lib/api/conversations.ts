import { request, streamRequest } from "./client";
import type { ApplicationScopeRequest } from "./common";
import type { ContinuationRequest } from "./external-turns";

export type Conversation = {
  id: string;
  owner_id: string;
  application_id: string;
  workspace_id: string | null;
  title: string | null;
  created_at: string;
  updated_at: string;
};

export type TurnAttribution = {
  fact_source: "server_observed" | "client_reported" | "user_declared";
  execution_origin: "automatic_managed" | "connected_local" | "manual_import";
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
  execution?: { effective_sensitivity: "public" | "personal" | "sensitive" | "restricted" } | null;
};

export type ConversationDetail = { conversation: Conversation; messages: Message[] };
export type ResponseErrorEvent = { message_id: string; code: string; message: string };
export type StreamHandlers = {
  onMessageCreated: (message: Message) => void;
  onDelta: (messageId: string, delta: string) => void;
  onCompleted: (message: Message) => void;
  onError: (event: ResponseErrorEvent) => void;
};

export const conversationEndpoints = {
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
};
