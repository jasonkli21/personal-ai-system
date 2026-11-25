import { harborCity } from "../fixtures/harbor-city.js";
import { MAX_SELECTORS, SELECTOR_TTL_MS } from "./contract.js";

const FIXTURE_FRESHNESS_MS = 300_000;

export function createSyntheticReader(now = Date.now) {
  // Each isolate retains only ephemeral demo selector timestamps, never query text or records.
  const selectors = new Map();

  return {
    search(query) {
      const term = query.trim().toLowerCase();
      if (!harborCity.title.toLowerCase().includes(term)) return { results: [] };

      const observedAt = now();
      for (const [id, issuedAt] of selectors) {
        if (observedAt - issuedAt >= SELECTOR_TTL_MS) selectors.delete(id);
      }
      if (selectors.size >= MAX_SELECTORS) selectors.delete(selectors.keys().next().value);
      const id = crypto.randomUUID().replaceAll("-", "");
      selectors.set(id, observedAt);
      return { results: [{ id, title: harborCity.title }] };
    },

    fetch(id) {
      const observedAt = selectors.get(id);
      const elapsed = now() - observedAt;
      if (observedAt === undefined || elapsed < 0 || elapsed >= SELECTOR_TTL_MS) return null;

      return {
        id,
        ...harborCity,
        observed_at: new Date(observedAt).toISOString(),
        fresh_until: new Date(observedAt + FIXTURE_FRESHNESS_MS).toISOString(),
      };
    },
  };
}
