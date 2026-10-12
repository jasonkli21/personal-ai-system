// @vitest-environment node
import { NextRequest } from "next/server";
import { afterEach, expect, it, vi } from "vitest";
import { GET, POST } from "../../src/app/api/mutations/[...segments]/route";

const proposal = "d8fe8085-c86f-4898-a5fc-d52f2d09c452";
afterEach(() => { vi.unstubAllEnvs(); vi.unstubAllGlobals(); });
it("forwards exact confirmation and separate user identity through the API proxy", async () => {
  vi.stubEnv("API_IAM_AUTH_ENABLED", "false");
  const fetch = vi.fn().mockResolvedValue(new Response("{}", { headers: { "Content-Type": "application/json" } }));
  vi.stubGlobal("fetch", fetch);
  const body = JSON.stringify({ confirmation_id: "confirmation", binding: "a".repeat(64) });
  await POST(new NextRequest(`http://localhost/api/mutations/${proposal}/apply`, {
    method: "POST", body, headers: { Authorization: "Bearer user", "X-Application-ID": "synthetic", "X-Workspace-ID": "space" },
  }), { params: Promise.resolve({ segments: [proposal, "apply"] }) });
  expect(fetch).toHaveBeenCalledWith(`http://localhost:8000/v1/mutations/${proposal}/apply`, expect.objectContaining({ method: "POST", body }));
  const headers = fetch.mock.calls[0][1].headers as Headers;
  expect(headers.get("Authorization")).toBe("Bearer user");
  expect(headers.get("X-Application-ID")).toBe("synthetic");
  expect(headers.get("X-Workspace-ID")).toBe("space");
});
it("rejects arbitrary mutation paths before upstream access", async () => {
  const fetch = vi.fn();
  vi.stubGlobal("fetch", fetch);
  for (const segments of [["..", "write"], [proposal, "delete"], [proposal, "apply", "another"]]) {
    const response = await POST(new NextRequest("http://localhost/api/mutations/bad", { method: "POST" }), { params: Promise.resolve({ segments }) });
    expect(response.status).toBe(404);
  }
  const response = await GET(new NextRequest("http://localhost/api/mutations/bad"), { params: Promise.resolve({ segments: [proposal, "apply"] }) });
  expect(response.status).toBe(404);
  expect(fetch).not.toHaveBeenCalled();
});
