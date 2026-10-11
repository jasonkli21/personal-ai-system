import type { FormEventHandler } from "react";

import styles from "./continuation-sidecar.module.css";

export type DraftTarget = { id: string; label: string };

export function ManualExternalPanel({
  portablePrompt,
  finalPackageReviewed,
  copyAllowed,
  copied,
  onCopy,
  importText,
  onImportTextChange,
  providerLabel,
  onProviderLabelChange,
  modelLabel,
  onModelLabelChange,
  busy,
  onImport,
  draftTargets,
  onInsertDraft,
}: {
  portablePrompt: string;
  finalPackageReviewed: boolean;
  copyAllowed: boolean;
  copied: boolean;
  onCopy: () => void;
  importText: string;
  onImportTextChange: (value: string) => void;
  providerLabel: string;
  onProviderLabelChange: (value: string) => void;
  modelLabel: string;
  onModelLabelChange: (value: string) => void;
  busy: boolean;
  onImport: FormEventHandler<HTMLFormElement>;
  draftTargets: readonly DraftTarget[];
  onInsertDraft?: (targetId: string, text: string) => void;
}) {
  return <section className={styles.manual} aria-labelledby="manual-heading">
    <h3 id="manual-heading">Manual external model</h3>
    <p>Personal AI did not open, control, authenticate to, scrape, or verify the external model or session. This prompt is user-mediated and can be used without the local bridge.</p>
    <label htmlFor="portable-prompt">Prepared prompt</label>
    <textarea id="portable-prompt" readOnly value={portablePrompt} />
    <button type="button" onClick={onCopy} disabled={!portablePrompt || !finalPackageReviewed || !copyAllowed}>Copy prepared prompt</button>
    {copied && <span role="status">Copied.</span>}
    <form onSubmit={onImport} className={styles.form}>
      <label htmlFor="manual-response">Paste the external response</label>
      <textarea id="manual-response" value={importText} onChange={event => onImportTextChange(event.target.value)} maxLength={20000} disabled={busy} />
      <label htmlFor="manual-provider">Provider label (optional, user-declared)</label>
      <input id="manual-provider" value={providerLabel} maxLength={200} onChange={event => onProviderLabelChange(event.target.value)} disabled={busy} />
      <label htmlFor="manual-model">Model label (optional, user-declared)</label>
      <input id="manual-model" value={modelLabel} maxLength={200} onChange={event => onModelLabelChange(event.target.value)} disabled={busy} />
      <p className={styles.note}>Provider and model labels are unverified. Imported text returns as a conversation turn and does not apply changes to domain records.</p>
      {onInsertDraft && importText.trim() && draftTargets.map(draftTarget => <button
        key={draftTarget.id}
        type="button"
        disabled={busy}
        onClick={() => onInsertDraft(draftTarget.id, importText)}
      >Insert response into {draftTarget.label} draft</button>)}
      <button type="submit" disabled={busy || !importText.trim() || !finalPackageReviewed}>Import response into conversation</button>
    </form>
  </section>;
}
