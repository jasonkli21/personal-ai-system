export const PROTOCOL = "2026-07-28";
export const PROFILE = "pas-context/default";
export const BUILD = "0.1.0";
export const MAX_BYTES = 8192;
export const MAX_QUERY_BYTES = 256;
export const MAX_ID_BYTES = 200;
export const MAX_HITS = 10;
export const SELECTOR_TTL_MS = 60_000;
export const MAX_SELECTORS = 1024;

const encoder = new TextEncoder();
export const byteLength = (value) => encoder.encode(value).byteLength;
export const isObject = (value) => value !== null && typeof value === "object" && !Array.isArray(value);
const selectorPattern = /^[A-Za-z0-9_-]+$/u;
const hasOnly = (value, key) => isObject(value) && Object.keys(value).length === 1 && Object.hasOwn(value, key);

export function validArguments(tool, args) {
  if (tool === "search") {
    return hasOnly(args, "query") && typeof args.query === "string" &&
      args.query.isWellFormed() && args.query.trim().length > 0 && byteLength(args.query) <= MAX_QUERY_BYTES;
  }
  return tool === "fetch" && hasOnly(args, "id") && typeof args.id === "string" &&
    args.id.length <= MAX_ID_BYTES && selectorPattern.test(args.id);
}

const string = { type: "string" };
const timestamp = { ...string, format: "date-time" };
const selector = { ...string, minLength: 1, maxLength: MAX_ID_BYTES, pattern: "^[A-Za-z0-9_-]+$" };
const object = (properties) => ({
  type: "object",
  properties,
  required: Object.keys(properties),
  additionalProperties: false,
});
const annotations = { readOnlyHint: true, destructiveHint: false, idempotentHint: true, openWorldHint: false };

export const TOOLS = [
  {
    name: "search",
    description: "Find the fabricated Harbor City itinerary by title in the synthetic demo. Returns opaque IDs for fetch.",
    inputSchema: object({ query: { ...string, minLength: 1, maxLength: MAX_QUERY_BYTES, pattern: "\\S" } }),
    outputSchema: object({ results: { type: "array", maxItems: MAX_HITS, items: object({ id: selector, title: string }) } }),
    annotations,
  },
  {
    name: "fetch",
    description: "Read a fabricated itinerary from this plugin's recent search result. Pass its opaque ID unchanged.",
    inputSchema: object({ id: selector }),
    outputSchema: object({ id: selector, title: string, text: string, source: string, revision: string, observed_at: timestamp, fresh_until: timestamp }),
    annotations,
  },
];

export const wasDenied = () => ({
  isError: true,
  content: [{ type: "text", text: "Context unavailable." }],
});

export function toolResult(projection) {
  if (projection === null) return wasDenied();
  const result = {
    structuredContent: projection,
    content: [{ type: "text", text: JSON.stringify(projection) }],
  };
  return byteLength(JSON.stringify(result)) <= MAX_BYTES ? result : wasDenied();
}
