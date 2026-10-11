import type { ContextPackage } from "../../../lib/api";
import styles from "./continuation-sidecar.module.css";

export function ContextPackageSummary({ packageValue }: { packageValue: ContextPackage }) {
  return <section className={styles.context} aria-labelledby="context-package-heading">
    <h3 id="context-package-heading">Prepared context</h3>
    <p>
      Estimated {packageValue.input_tokens.toLocaleString()} tokens · {packageValue.selected_message_count} direct conversation messages · {packageValue.summarized_source_message_count ?? 0} messages represented by summaries · {packageValue.effective_sensitivity} sensitivity
    </p>
    <p>Policy {packageValue.policy_version} · expires {new Date(packageValue.expires_at).toLocaleString()}</p>
    <ul className={styles.sources}>
      {packageValue.included_sources.map(source => <li key={`${source.category}-${source.sensitivity.join("-")}-${source.authority.join("-")}`}>
        {source.category}: {source.item_count} included · {source.sensitivity.join(", ")} · {source.authority.join(", ")}
      </li>)}
      {packageValue.excluded_sources.map(source => <li key={`${source.category}-${source.reason}`}>
        {source.category}: {source.item_count} omitted ({source.reason})
      </li>)}
    </ul>
    <details>
      <summary>Inspect bounded prepared messages</summary>
      <div className={styles.preview}>
        {packageValue.messages.map((message, index) => <article key={`${index}-${message.role}`}>
          <strong>{message.role}</strong><pre>{message.content}</pre>
        </article>)}
      </div>
    </details>
  </section>;
}
