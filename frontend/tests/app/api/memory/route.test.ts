// @vitest-environment node
import { NextRequest } from "next/server";
import { afterEach, expect, it, vi } from "vitest";
import { GET, POST } from "../../../../src/app/api/memory/control/[...segments]/route";

const proxy = vi.hoisted(() => vi.fn(() => new Response("{}")));
vi.mock("../../../../src/lib/conversation-proxy", () => ({ proxyApi: proxy }));
afterEach(() => { vi.unstubAllEnvs(); proxy.mockClear(); });

it("keeps read and mutation proxies disabled by default", async () => {
  vi.stubEnv("MEMORY_USER_MANAGEMENT_ENABLED", "false");
  expect((await GET(new NextRequest("http://localhost/api/memory/control/knowledge"))).status).toBe(404);
  expect((await POST(new NextRequest("http://localhost/api/memory/control/knowledge/id/forget", { method: "POST" }))).status).toBe(404);
  expect(proxy).not.toHaveBeenCalled();
});

it("forwards scoped requests and bounded query parameters through the existing proxy", async () => {
  vi.stubEnv("MEMORY_USER_MANAGEMENT_ENABLED", "true");
  const request = new NextRequest("http://localhost/api/memory/control/knowledge?query=layout&limit=8");
  expect((await GET(request)).status).toBe(200);
  expect(proxy).toHaveBeenCalledWith(request, "/v1/memory/control/knowledge?query=layout&limit=8");
});
