"use client";

import { useEffect, useRef, useState } from "react";
import type { ApplicationScopeRequest } from "../../../lib/api/common";
import { mutationAction, readMutation, type MutationConfirmation, type MutationView } from "../../../lib/api/mutations";

export function MutationProposalPanel({ proposalId, scope }: { proposalId: string; scope: ApplicationScopeRequest }) {
  const [view, setView] = useState<MutationView | null>(null);
  const [reviewed, setReviewed] = useState(false);
  const [busy, setBusy] = useState(false);
  const inFlight = useRef(false);
  const [recoveryRequired, setRecoveryRequired] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const confirmation = useRef<MutationConfirmation | null>(null);
  useEffect(() => {
    let active = true;
    readMutation(proposalId, scope).then(value => {
      if (active) setView(value);
    }).catch(() => { if (active) { setView(null); setError("This proposal is unavailable. Refresh to check its status."); } });
    return () => { active = false; };
  }, [proposalId, scope]);

  async function act(action: "validate" | "confirm" | "apply" | "reconcile" | "refresh") {
    if (inFlight.current) return;
    inFlight.current = true;
    setBusy(true);
    setError(null);
    try {
      if (action === "confirm" && view && !confirmation.current) {
        confirmation.current = { confirmation_id: crypto.randomUUID(), binding: view.binding };
      }
      const choice = view?.proposal.confirmation ?? confirmation.current ?? undefined;
      const value = action === "refresh" ? await readMutation(proposalId, scope)
        : await mutationAction(proposalId, action, scope, choice);
      setView(value);
      setRecoveryRequired(false);
      setReviewed(false);
    } catch {
      if (action === "apply" || action === "confirm") setRecoveryRequired(true);
      if (action === "refresh") setView(null);
      setError("The request could not be completed. Refresh or reconcile to check its status.");
    } finally {
      inFlight.current = false;
      setBusy(false);
    }
  }
  const scoped = view?.proposal.intent.target.application_id === (scope.applicationId ?? "personal_ai")
    && view?.proposal.intent.target.workspace_id === (scope.workspaceId ?? null);
  const proposal = scoped ? view?.proposal : undefined;
  const expired = !!proposal && Math.min(
    Date.parse(proposal.intent.expires_at), Date.parse(proposal.validation?.expires_at ?? proposal.intent.expires_at),
  ) <= Date.now();
  const uncertain = proposal && ["executing", "reconciling", "uncertain"].includes(proposal.state);
  return <section aria-label="Domain mutation proposal">
    <h3>Proposed domain change</h3>
    {error && <p role="alert">{error}</p>}
    {proposal && <>
      <p>{proposal.intent.operation.operation_id} v{proposal.intent.operation.version} · {proposal.intent.target.entity_type} {proposal.intent.target.entity_id}</p>
      <p role="status">Status: {proposal.state}</p>
      {proposal.intent.payload && <details><summary>Exact proposed patch</summary><pre style={{ whiteSpace: "pre-wrap" }}>{JSON.stringify(proposal.intent.payload, null, 2)}</pre></details>}
      {proposal.validation?.preview && <pre style={{ whiteSpace: "pre-wrap" }}>{proposal.validation.preview}</pre>}
      {proposal.state === "proposed" && <button disabled={busy} onClick={() => void act("validate")}>Validate proposal</button>}
      {view?.apply_available && !expired && !recoveryRequired && proposal.state === "validated" && <>
        <label><input type="checkbox" checked={reviewed} disabled={busy} onChange={event => setReviewed(event.target.checked)} /> I reviewed this exact change</label>
        <button disabled={busy || !reviewed} onClick={() => void act("confirm")}>Confirm change</button>
      </>}
      {view?.apply_available && !expired && !recoveryRequired && proposal.state === "confirmed" && <button disabled={busy} onClick={() => void act("apply")}>Apply confirmed change</button>}
      {(uncertain || recoveryRequired) && <button disabled={busy} onClick={() => void act("reconcile")}>Reconcile outcome</button>}
      {proposal.outcome?.post_state && <p>Authoritative result: {proposal.outcome.post_state.reference_id} · revision {proposal.outcome.post_state.domain_version}</p>}
      {proposal.terminal_code && <p>{proposal.terminal_code}</p>}
      {expired && !uncertain && proposal.state !== "applied" && <p>This proposal has expired.</p>}
    </>}
    <button disabled={busy} onClick={() => void act("refresh")}>Refresh proposal status</button>
  </section>;
}
