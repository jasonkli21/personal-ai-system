import { NextRequest, NextResponse } from "next/server";

import { proxyApi } from "../../../../../lib/conversation-proxy";

const MAX_BYTES = 8192;
const memoryRoute = /^(knowledge(?:\/[0-9a-f-]{36}(?:\/(?:forget|revise))?)?|topics|proposals(?:\/[0-9a-f-]{36}\/decision)?|portability\/(?:capabilities|profile|export|import-preview))$/i;

function error(status: number, code: string) {
  return NextResponse.json({ error: { code } }, { status, headers: { "Cache-Control": "private, no-store" } });
}

async function memoryPath(request: NextRequest) {
  const path = request.nextUrl.pathname.slice("/api/memory/control/".length);
  if (process.env.MEMORY_USER_MANAGEMENT_ENABLED !== "true" || !memoryRoute.test(path)
      || (path.startsWith("portability/") && process.env.MEMORY_PORTABILITY_ENABLED !== "true")) {
    return error(404, "not_found");
  }
  const origin = request.headers.get("origin");
  if ((origin && origin !== request.nextUrl.origin)
      || request.headers.get("sec-fetch-site") === "cross-site") {
    return error(403, "origin_denied");
  }
  const upstream = `/v1/memory/control/${path}${request.nextUrl.search}`;
  if (request.method === "GET") return proxyApi(request, upstream);
  if (request.headers.get("content-type")?.split(";")[0] !== "application/json" || !request.body) {
    return error(415, "portable_json_required");
  }
  const reader = request.body.getReader();
  const buffer = new Uint8Array(MAX_BYTES);
  let size = 0;
  let timedOut = false;
  const timer = setTimeout(() => {
    timedOut = true;
    void reader.cancel().catch(() => undefined);
  }, 2000);
  try {
    while (true) {
      const { done, value } = await reader.read();
      if (timedOut) return error(408, "body_interrupted");
      if (done) break;
      if (value.length > MAX_BYTES - size) {
        void reader.cancel().catch(() => undefined);
        return error(413, "body_too_large");
      }
      buffer.set(value, size);
      size += value.length;
    }
  } catch {
    return error(408, "body_interrupted");
  } finally {
    clearTimeout(timer);
    reader.releaseLock();
  }
  return proxyApi(request, upstream, buffer.subarray(0, size));
}

export const GET = memoryPath;
export const POST = memoryPath;
