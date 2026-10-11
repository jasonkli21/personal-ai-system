import { NextRequest } from "next/server";

import { proxyConversationApi } from "../../../../../../lib/conversation-proxy";

export const dynamic = "force-dynamic";
type Context = { params: Promise<{ conversationId: string; segments: string[] }> };

export async function POST(request: NextRequest, { params }: Context) {
  const { conversationId, segments } = await params;
  const path = [conversationId, "external-turns", ...segments]
    .map(segment => encodeURIComponent(segment))
    .join("/");
  return proxyConversationApi(request, `/${path}`);
}
