import { NextRequest } from "next/server";
import { proxyApi } from "../../../lib/conversation-proxy";

export const dynamic = "force-dynamic";
export async function POST(request: NextRequest) {
  return proxyApi(request, "/v1/mutations");
}
