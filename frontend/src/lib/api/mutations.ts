import { request } from "./client";
import type { ApplicationScopeRequest } from "./common";
import type { ContextEntityReference } from "./external-turns";

export type MutationView = {
  binding: string;
  apply_available: boolean;
  proposal: {
    schema_version: "mutation-proposal-view-v1";
    proposal_id: string;
    revision: number;
    state: "proposed" | "validated" | "confirmed" | "executing" | "reconciling" | "applied" | "rejected" | "uncertain" | "expired";
    intent: {
      target: ContextEntityReference;
      operation: { operation_id: string; version: number };
      payload: Record<string, unknown> | null;
      expected_domain_version: string;
      expires_at: string;
    };
    validation: { valid: boolean; preview: string | null; expires_at: string; code: string } | null;
    confirmation: { confirmation_id: string; binding: string } | null;
    outcome: {
      state: "applied" | "rejected" | "uncertain";
      code: string;
      post_state: { target: ContextEntityReference; domain_version: string; reference_id: string } | null;
    } | null;
    terminal_code: string | null;
  };
};
export type MutationConfirmation = { confirmation_id: string; binding: string };
export type MutationOperationRef = { operation_id: string; version: number };
export type MutationCandidateRequest = {
  idempotency_key: string;
  output: { conversation_id: string; message_id: string };
  operation: MutationOperationRef;
};
export function createMutationCandidate(candidate: MutationCandidateRequest, scope: ApplicationScopeRequest) {
  return request<MutationView>("/mutations/candidates", {
    method: "POST", body: JSON.stringify(candidate),
  }, scope);
}
export function readMutation(id: string, scope: ApplicationScopeRequest) {
  return request<MutationView>(`/mutations/${encodeURIComponent(id)}`, undefined, scope);
}
export function mutationAction(id: string, action: "validate" | "confirm" | "apply" | "reconcile", scope: ApplicationScopeRequest, confirmation?: MutationConfirmation) {
  return request<MutationView>(`/mutations/${encodeURIComponent(id)}/${action}`, {
    method: "POST", body: JSON.stringify(confirmation ?? {}),
  }, scope);
}
