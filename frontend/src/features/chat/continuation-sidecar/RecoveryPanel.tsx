import type { ExternalTurnReconciliation } from "../../../lib/api/external-turns";
import styles from "./continuation-sidecar.module.css";

export function RecoveryPanel({
  result,
  onAbandon,
  busy,
}: {
  result: ExternalTurnReconciliation;
  onAbandon: () => void;
  busy: boolean;
}) {
  return <section className={styles.context} aria-labelledby="recovery-heading">
    <h3 id="recovery-heading">Earlier preparation status</h3>
    <p>A previous prepare request may have committed before its response reached this browser. The prompt body is not reconstructed.</p>
    <p>Canonical state: {result.state}{result.stale_reason ? ` · ${result.stale_reason}` : ""}</p>
    {result.state === "prepared" || result.state === "prepared_stale"
      ? <button type="button" disabled={busy} onClick={onAbandon}>Cancel this prepared reservation and start fresh</button>
      : <p>Inspect or reopen the canonical conversation before retrying.</p>}
  </section>;
}
