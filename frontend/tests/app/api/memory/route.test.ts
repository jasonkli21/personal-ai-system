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

it("refuses cross-origin and oversized bodies before the upstream proxy", async () => {
  vi.stubEnv("MEMORY_USER_MANAGEMENT_ENABLED", "true");
  vi.stubEnv("MEMORY_PORTABILITY_ENABLED", "true");
  const url = "http://localhost/api/memory/control/portability/import-preview";
  expect((await POST(new NextRequest(url, {
    method: "POST", body: "{}", headers: { "Content-Type": "application/json", Origin: "https://elsewhere.test" },
  }))).status).toBe(403);
  expect((await POST(new NextRequest(url, {
    method: "POST", body: "x".repeat(8193), headers: { "Content-Type": "application/json" },
  }))).status).toBe(413);
  expect(proxy).not.toHaveBeenCalled();
});

it("passes the original bounded bytes without decoding malformed UTF-8", async () => {
  vi.stubEnv("MEMORY_USER_MANAGEMENT_ENABLED", "true");
  vi.stubEnv("MEMORY_PORTABILITY_ENABLED", "true");
  const bytes = new Uint8Array([255]);
  const request = new NextRequest("http://localhost/api/memory/control/portability/import-preview", {
    method: "POST", body: bytes, headers: { "Content-Type": "application/json" },
  });
  expect((await POST(request)).status).toBe(200);
  expect(proxy).toHaveBeenCalledWith(request, "/v1/memory/control/portability/import-preview", bytes);
});

it("returns content-free errors for the disabled portability gate and invalid media type", async () => {
  vi.stubEnv("MEMORY_USER_MANAGEMENT_ENABLED", "true");
  vi.stubEnv("MEMORY_PORTABILITY_ENABLED", "false");
  const url = "http://localhost/api/memory/control/portability/import-preview";
  expect((await POST(new NextRequest(url, {
    method: "POST", body: "{}", headers: { "Content-Type": "application/json" },
  }))).status).toBe(404);
  vi.stubEnv("MEMORY_PORTABILITY_ENABLED", "true");
  const response = await POST(new NextRequest(url, {
    method: "POST", body: "{}", headers: { "Content-Type": "text/plain" },
  }));
  expect(response.status).toBe(415);
  expect(await response.json()).toEqual({ error: { code: "portable_json_required" } });
  expect(response.headers.get("Cache-Control")).toBe("private, no-store");
  expect(proxy).not.toHaveBeenCalled();
});

it("cancels a stalled upload at the receive deadline", async () => {
  vi.useFakeTimers();
  vi.stubEnv("MEMORY_USER_MANAGEMENT_ENABLED", "true");
  vi.stubEnv("MEMORY_PORTABILITY_ENABLED", "true");
  let cancelled = false;
  const body = new ReadableStream<Uint8Array>({ cancel() { cancelled = true; } });
  const pending = POST(new NextRequest("http://localhost/api/memory/control/portability/import-preview", {
    method: "POST", body, headers: { "Content-Type": "application/json" },
  }));
  await vi.advanceTimersByTimeAsync(2000);
  const response = await pending;
  expect(response.status).toBe(408);
  expect(await response.json()).toEqual({ error: { code: "body_interrupted" } });
  expect(cancelled).toBe(true);
  expect(proxy).not.toHaveBeenCalled();
});
