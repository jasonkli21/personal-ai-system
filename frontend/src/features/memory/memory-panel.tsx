"use client";

import { useState } from "react";

import { authenticatedFetch } from "../../lib/auth";

type Memory = {
  application_id: string; workspace_id: string | null;
  id: string; title: string; kind: string; historical_content: string;
  project: { project_id: string; revision: string; branch: string };
  authority: string; verification: string; state_version: number; expires_at: string;
  source_ids: string[];
};
type Proposal = {
  id: string; status: string; version: number; expires_at: string;
  content: { title: string; claim: string } | null;
};
type Outcome = { status: string; replayed?: boolean };
type Intent = { path: string; body: { operation_id: string; expected_version: number; confirm: true; decision?: string } };

async function request<T>(path: string, body?: Intent["body"]): Promise<T> {
  const response = await authenticatedFetch(`/api/memory/control/${path}`, {
    method: body ? "POST" : "GET", cache: "no-store",
    ...(body ? { headers: { "Content-Type": "application/json" }, body: JSON.stringify(body) } : {}),
  });
  if (!response.ok) throw new Error("Memory controls are unavailable or require a recent sign-in.");
  return response.json() as Promise<T>;
}

export function MemoryPanel() {
  const [items, setItems] = useState<Memory[]>([]);
  const [proposals, setProposals] = useState<Proposal[]>([]);
  const [message, setMessage] = useState("");
  const [busy, setBusy] = useState(false);
  const [uncertain, setUncertain] = useState<Intent | null>(null);
  const [confirmed, setConfirmed] = useState<string | null>(null);

  async function refresh() {
    setBusy(true);
    setItems([]); setProposals([]);
    try {
      const [knowledge, pending] = await Promise.all([
        request<{ status: string; items: Memory[]; truncated: boolean }>("knowledge"),
        request<{ status: string; proposals: Proposal[] }>("proposals"),
      ]);
      if (knowledge.status !== "found" || pending.status !== "found") {
        setMessage("Memory inspection is unavailable. Narrowing or current authorization may be required.");
      } else {
        setItems(knowledge.items); setProposals(pending.proposals);
        setMessage(knowledge.truncated ? "Showing the first eight eligible records." : "Inspection refreshed.");
      }
    } catch (error) { setMessage((error as Error).message); }
    finally { setBusy(false); }
  }

  async function apply(intent: Intent) {
    setBusy(true); setItems([]); setProposals([]); setConfirmed(null);
    // Keep the exact intent until a durable result is known; transport failure is uncertain.
    setUncertain(intent);
    try {
      const result = await request<Outcome>(intent.path, intent.body);
      setMessage(result.status === "applied"
        ? "Forgotten for future use. Input already sent to a provider cannot be recalled."
        : `Memory operation: ${result.status}${result.replayed ? " (reconciled)" : ""}.`);
      if (result.status !== "unknown_commit" && result.status !== "temporarily_unavailable") setUncertain(null);
    } catch { setMessage("Outcome unknown. Reconcile this same operation before another action."); }
    finally { setBusy(false); }
  }

  function mutate(path: string, version: number, decision?: string) {
    void apply({ path, body: { operation_id: crypto.randomUUID(), expected_version: version, confirm: true, ...(decision ? { decision } : {}) } });
  }

  return <section aria-label="Memory controls">
    <button disabled={busy} onClick={() => void refresh()}>Inspect memory</button>
    <p role="status">{message}</p>
    {uncertain && <button disabled={busy} onClick={() => void apply(uncertain)}>Reconcile original operation</button>}
    <p>Decision revision is unavailable until a trusted evidence issuer is registered.</p>
    {items.map(item => <article key={item.id}>
      <h2>{item.title}</h2>
      <p>{item.kind} · {item.authority} · {item.verification}</p>
      <p>Scope {item.application_id}/{item.workspace_id ?? "personal"}. Project {item.project.project_id}, revision {item.project.revision}, branch {item.project.branch}; version {item.state_version}; expires {item.expires_at}.</p>
      <pre style={{ whiteSpace: "pre-wrap" }}>{item.historical_content}</pre>
      <p>Sources: {item.source_ids.join(", ")}</p>
      <label><input type="checkbox" checked={confirmed === item.id} onChange={event => setConfirmed(event.target.checked ? item.id : null)} />Forget this record for future use. Previously sent input cannot be recalled.</label>
      <button disabled={busy || !!uncertain || confirmed !== item.id} onClick={() => mutate(`knowledge/${item.id}/forget`, item.state_version)}>Forget</button>
    </article>)}
    {proposals.map(proposal => <article key={proposal.id}>
      <h2>Unverified suggestion: {proposal.content?.title}</h2>
      <p>{proposal.content?.claim}</p>
      <p>{proposal.status}; version {proposal.version}; expires {proposal.expires_at}.</p>
      {proposal.status === "pending" && <>
        <button disabled={busy || !!uncertain} onClick={() => mutate(`proposals/${proposal.id}/decision`, proposal.version, "reviewed")}>Mark reviewed</button>
        <button disabled={busy || !!uncertain} onClick={() => mutate(`proposals/${proposal.id}/decision`, proposal.version, "rejected")}>Reject</button>
      </>}
    </article>)}
  </section>;
}
