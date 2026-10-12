import { NextRequest, NextResponse } from "next/server";
import { proxyApi } from "../../../../lib/conversation-proxy";

export const dynamic = "force-dynamic";
type Context = { params: Promise<{ segments: string[] }> };
const uuid = /^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$/i;
async function proxy(request: NextRequest, context: Context) {
  const { segments } = await context.params;
  if (!uuid.test(segments[0] ?? "") || !(
    (request.method === "GET" && segments.length === 1) ||
    (request.method === "POST" && segments.length === 2 &&
      ["validate", "confirm", "apply", "reconcile"].includes(segments[1]))
  )) return NextResponse.json({ error: { message: "Not found." } }, { status: 404 });
  return proxyApi(request, `/v1/mutations/${segments.join("/")}`);
}
export const GET = proxy;
export const POST = proxy;
