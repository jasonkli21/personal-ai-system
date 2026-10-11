import type { BridgeConnection, BridgePairing } from "../../../lib/api";
import type { DraftTarget } from "./ManualExternalPanel";
import styles from "./continuation-sidecar.module.css";

export type SavedCompletion = {
  text: string;
  latencyMs: number;
  inputTokens?: number;
  outputTokens?: number;
};

export function ConnectedProviderPanel({
  savedCompletion,
  busy,
  pairing,
  finalPackageReviewed,
  bridgeConnection,
  draftTargets,
  onInsertDraft,
  onRetrySave,
  onSend,
  canCancelExecution,
  onCancelExecution,
}: {
  savedCompletion: SavedCompletion | null;
  busy: boolean;
  pairing: BridgePairing | null;
  finalPackageReviewed: boolean;
  bridgeConnection: BridgeConnection | null;
  draftTargets: readonly DraftTarget[];
  onInsertDraft?: (targetId: string, text: string) => void;
  onRetrySave: () => void;
  onSend: () => void;
  canCancelExecution: boolean;
  onCancelExecution: () => void;
}) {
  return <section className={styles.manual} aria-labelledby="connected-heading">
    <h3 id="connected-heading">Connected provider response</h3>
    <p>Connected deltas appear on the pending assistant turn in the shared conversation view. They remain transient until completion.</p>
    {savedCompletion && <>
      <p>The bridge completed. Retry saves the same response and does not send it again.</p>
      {onInsertDraft && draftTargets.map(draftTarget => <button
        key={draftTarget.id}
        type="button"
        disabled={busy}
        onClick={() => onInsertDraft(draftTarget.id, savedCompletion.text)}
      >Insert response into {draftTarget.label} draft</button>)}
      <button type="button" disabled={busy} onClick={onRetrySave}>Retry saving response</button>
    </>}
    {!savedCompletion && <button type="button" disabled={busy || !pairing || !finalPackageReviewed || bridgeConnection?.usage?.state === "limit"} onClick={onSend}>
      {busy ? "Sending…" : "Send through local bridge"}
    </button>}
    {canCancelExecution && <button type="button" onClick={onCancelExecution}>Cancel connected execution</button>}
  </section>;
}
