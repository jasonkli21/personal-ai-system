import { NextRequest, NextResponse } from "next/server";

import { proxyApi } from "../../../../../lib/conversation-proxy";

function memoryPath(request: NextRequest) {
  if (process.env.MEMORY_USER_MANAGEMENT_ENABLED !== "true") {
    return NextResponse.json({ error: { code: "not_found", message: "Memory controls are unavailable." } }, { status: 404 });
  }
  return proxyApi(request, `/v1/memory/control${request.nextUrl.pathname.slice("/api/memory/control".length)}${request.nextUrl.search}`);
}

export const GET = memoryPath;
export const POST = memoryPath;
