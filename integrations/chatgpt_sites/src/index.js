import { MAX_BYTES, PROTOCOL, TOOLS, isObject, toolResult, validArguments, wasDenied } from "./contract.js";
import { createSyntheticReader } from "./synthetic-reader.js";
import { SYNTHETIC_LOCAL, resolveMode, statusPage } from "./status.js";

const headers = {
  "Cache-Control": "no-store",
  "Referrer-Policy": "no-referrer",
  "X-Content-Type-Options": "nosniff",
};
const plain = (status, extra = {}) => new Response(null, { status, headers: { ...headers, ...extra } });
const json = (id, body) => Response.json({ jsonrpc: "2.0", id, ...body }, { headers });
const error = (id, code, message) => json(id, { error: { code, message } });

async function readFrame(request) {
  const stream = request.body?.getReader();
  if (!stream) throw new SyntaxError();
  const bytes = new Uint8Array(MAX_BYTES);
  let offset = 0;

  try {
    for (;;) {
      const { done, value } = await stream.read();
      if (done) break;
      if (offset + value.byteLength > MAX_BYTES) {
        void stream.cancel().catch(() => {});
        return null;
      }
      bytes.set(value, offset);
      offset += value.byteLength;
    }
  } finally {
    stream.releaseLock();
  }

  return { body: JSON.parse(new TextDecoder("utf-8", { fatal: true }).decode(bytes.subarray(0, offset))) };
}

async function mcp(request, mode, reader) {
  if (request.method !== "POST") return plain(405, { Allow: "POST" });
  const type = request.headers.get("Content-Type")?.split(";")[0].trim().toLowerCase();
  if (type !== "application/json") return plain(415);

  let frame;
  try {
    frame = await readFrame(request);
  } catch {
    return error(null, -32700, "Parse error");
  }
  if (frame === null) return plain(413);

  const { body } = frame;
  if (!isObject(body) || body.jsonrpc !== "2.0" || typeof body.method !== "string" ||
    !(Number.isSafeInteger(body.id) || (typeof body.id === "string" && body.id.length <= 128))) {
    return error(null, -32600, "Invalid request");
  }
  const { id, method, params } = body;
  const version = request.headers.get("MCP-Protocol-Version");
  if (version !== null && version !== PROTOCOL) return error(id, -32600, "Unsupported MCP protocol version");

  switch (method) {
    case "server/discover":
      return json(id, { result: { supportedVersions: [PROTOCOL], capabilities: { tools: {} } } });
    case "tools/list":
      return json(id, { result: { tools: TOOLS } });
    case "tools/call": {
      if (!isObject(params) || typeof params.name !== "string") return error(id, -32602, "Invalid params");
      const { name, arguments: args } = params;
      if (mode !== SYNTHETIC_LOCAL || !validArguments(name, args)) return json(id, { result: wasDenied() });
      try {
        const projection = name === "search" ? reader.search(args.query) : reader.fetch(args.id);
        return json(id, { result: toolResult(projection) });
      } catch {
        return json(id, { result: wasDenied() });
      }
    }
    default:
      return error(id, -32601, "Method not found");
  }
}

export function createWorker(reader = createSyntheticReader()) {
  // Hosted browser and MCP access are checked by Sites before forwarding.
  // This Worker uses no caller identity. The only reachable reader is fabricated.
  return {
    async fetch(request, env = {}) {
      const { pathname } = new URL(request.url);
      const mode = resolveMode(env);
      if (pathname === "/mcp") return mcp(request, mode, reader);
      if (pathname !== "/") return plain(404);
      if (request.method !== "GET" && request.method !== "HEAD") return plain(405, { Allow: "GET, HEAD" });

      return new Response(request.method === "HEAD" ? null : statusPage(mode), {
        headers: {
          ...headers,
          "Content-Type": "text/html; charset=utf-8",
          "Content-Security-Policy": "default-src 'none'; style-src 'unsafe-inline'; base-uri 'none'; form-action 'none'",
        },
      });
    },
  };
}

export default createWorker();
