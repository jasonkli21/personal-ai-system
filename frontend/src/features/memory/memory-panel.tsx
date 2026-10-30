"use client";

import { useEffect, useState } from "react";

import { authenticatedFetch, getAuthIdentityKey, subscribeAuth } from "../../lib/auth";

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
type StoredIntent = { version: 1; actor: string; intent: Intent };
const PENDING_INTENT_KEY = "memory-control.pending-operation.v1";

function validIntent(value: unknown): value is Intent {
  if (!value || typeof value !== "object") return false;
  const intent = value as Partial<Intent>;
  if (typeof intent.path !== "string" || !intent.body || typeof intent.body !== "object") return false;
  const { operation_id, expected_version, confirm, decision } = intent.body;
  const target = "[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}";
  const pathIsSafe = new RegExp(`^(knowledge/${target}/forget|proposals/${target}/decision)$`, "i")
    .test(intent.path);
  return pathIsSafe
    && /^[0-9a-f-]{36}$/i.test(operation_id)
    && Number.isSafeInteger(expected_version)
    && expected_version >= 0
    && confirm === true
    && (decision === undefined || decision === "reviewed" || decision === "rejected");
}

function readStoredIntent(): StoredIntent | null {
  try {
    const raw = sessionStorage.getItem(PENDING_INTENT_KEY);
    if (!raw) return null;
    const stored = JSON.parse(raw) as Partial<StoredIntent>;
    return stored.version === 1 && typeof stored.actor === "string" && validIntent(stored.intent)
      ? stored as StoredIntent
      : null;
  } catch {
    return null;
  }
}

function removeStoredIntent() {
  try {
    sessionStorage.removeItem(PENDING_INTENT_KEY);
  } catch {
    // Storage is optional; it contains no durable application data.
  }
}

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

  useEffect(() => {
    function restorePendingIntent() {
      const stored = readStoredIntent();
      if (!stored) {
        removeStoredIntent();
        return;
      }
      const actor = getAuthIdentityKey();
      if (!actor) return;
      if (stored.actor !== actor) {
        removeStoredIntent();
        setUncertain(null);
        return;
      }
      setUncertain(stored.intent);
      setMessage(
        "A previous operation has an unknown outcome. Reconcile this same operation before another action.",
      );
    }
    restorePendingIntent();
    const unsubscribe = subscribeAuth(restorePendingIntent);
    return () => {
      unsubscribe();
    };
  }, []);

  function keepPendingIntent(intent: Intent) {
    setUncertain(intent);
    const actor = getAuthIdentityKey();
    if (!actor) return;
    try {
      const stored: StoredIntent = { version: 1, actor, intent };
      sessionStorage.setItem(PENDING_INTENT_KEY, JSON.stringify(stored));
    } catch {
      // Keep the in-memory handle; browser storage can be unavailable in private modes.
    }
  }

  function clearPendingIntent() {
    setUncertain(null);
    removeStoredIntent();
  }

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
        setMessage(knowledge.truncated
          ? "Results are incomplete: only a bounded set of recent records was checked."
          : "Inspection refreshed.");
      }
    } catch (error) { setMessage((error as Error).message); }
    finally { setBusy(false); }
  }

  async function apply(intent: Intent) {
    setBusy(true); setItems([]); setProposals([]); setConfirmed(null);
    // Keep the exact intent until a durable result is known; transport failure is uncertain.
    keepPendingIntent(intent);
    try {
      const result = await request<Outcome>(intent.path, intent.body);
      setMessage(result.status === "applied"
        ? "Forgotten for future use. Input already sent to a provider cannot be recalled."
        : `Memory operation: ${result.status}${result.replayed ? " (reconciled)" : ""}.`);
      if (result.status !== "unknown_commit" && result.status !== "temporarily_unavailable") {
        clearPendingIntent();
      }
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
