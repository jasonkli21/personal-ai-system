import assert from "node:assert/strict";
import test from "node:test";
import { BUILD, MAX_BYTES, MAX_SELECTORS, PROTOCOL, SELECTOR_TTL_MS, toolResult } from "../src/contract.js";
import { createWorker } from "../src/index.js";
import { createSyntheticReader } from "../src/synthetic-reader.js";

const origin = "https://example.invalid";
const rejected = { isError: true, content: [{ type: "text", text: "Context unavailable." }] };

function harness(env = {}) {
  let timestamp = Date.UTC(2026, 10, 25);
  const worker = createWorker(createSyntheticReader(() => timestamp));
  const request = (path, init) => worker.fetch(new Request(origin + path, init), env);
  const post = (body, headers = {}) => request("/mcp", {
    method: "POST",
    headers: { "Content-Type": "application/json", ...headers },
    body,
  });
  const rpc = async (method, params, headers) => {
    const response = await post(JSON.stringify({ jsonrpc: "2.0", id: 1, method, params }), headers);
    assert.equal(response.status, 200);
    assert.equal(response.headers.get("cache-control"), "no-store");
    return response.json();
  };
  return {
    request,
    post,
    rpc,
    search: async (query) => (await rpc("tools/call", { name: "search", arguments: { query } })).result,
    fetch: async (id) => (await rpc("tools/call", { name: "fetch", arguments: { id } })).result,
    advance: (ms) => { timestamp += ms; },
  };
}

test("Sites discovery advertises the modern protocol and exactly two read-only tools", async () => {
  const api = harness();
  assert.deepEqual((await api.rpc("server/discover")).result, {
    supportedVersions: [PROTOCOL], capabilities: { tools: {} },
  });
  const { tools } = (await api.rpc("tools/list", {}, { "MCP-Protocol-Version": PROTOCOL })).result;
  assert.deepEqual(tools.map((tool) => tool.name), ["search", "fetch"]);
  for (const tool of tools) {
    assert.equal(tool.annotations.readOnlyHint, true);
    assert.equal(tool.annotations.destructiveHint, false);
    assert.equal(tool.annotations.openWorldHint, false);
    assert.equal(tool.inputSchema.additionalProperties, false);
    assert.equal(tool.outputSchema.additionalProperties, false);
  }
  assert.equal(tools[0].outputSchema.properties.results.maxItems, 10);
  assert.deepEqual(tools[1].outputSchema.required, ["id", "title", "text", "source", "revision", "observed_at", "fresh_until"]);
  assert.equal((await api.rpc("initialize")).error.code, -32601);
  assert.equal((await api.rpc("tools/list", {}, { "MCP-Protocol-Version": "2025-11-25" })).error.code, -32600);
});

test("Harbor search and fetch return the exact URL-free projection in both MCP representations", async () => {
  const api = harness();
  const found = await api.search("  HaRBor  ");
  assert.deepEqual(JSON.parse(found.content[0].text), found.structuredContent);
  const [{ id, title }] = found.structuredContent.results;
  assert.match(id, /^[a-f0-9]{32}$/u);
  assert.equal(title, "Demo trip — Harbor City");

  const fetched = await api.fetch(id);
  const projection = fetched.structuredContent;
  assert.deepEqual(JSON.parse(fetched.content[0].text), projection);
  assert.equal(projection.id, id);
  assert.equal(projection.source, "travel-demo");
  assert.equal(projection.revision, "demo-rev-1");
  assert.equal(projection.observed_at, "2026-11-25T00:00:00.000Z");
  assert.equal(projection.fresh_until, "2026-11-25T00:05:00.000Z");
  assert.deepEqual(JSON.parse(projection.text).days, [
    { day: 1, activity: "Museum", time: "10:00" },
    { day: 2, activity: "Park walk", time: "14:00" },
  ]);
  assert.ok(!Object.hasOwn(projection, "url"));
  assert.ok(Buffer.byteLength(JSON.stringify(fetched)) <= MAX_BYTES);
});

test("nonmatching and excluded sources yield an empty result", async () => {
  const api = harness();
  for (const query of ["no match", "Health", "another owner's trip"]) {
    assert.deepEqual((await api.search(query)).structuredContent, { results: [] });
  }
});

test("query validation uses UTF-8 bytes and denies malformed strings", async () => {
  const api = harness();
  for (const query of ["", " \t\n", "x".repeat(257), "é".repeat(129), "\ud800", 4, [], null]) {
    assert.deepEqual(await api.search(query), rejected);
  }
  assert.deepEqual((await api.search("é".repeat(128))).structuredContent, { results: [] });
});

test("fetch rejects malformed, unknown and foreign selectors without context bytes", async () => {
  const api = harness();
  const foreign = (await harness().search("harbor")).structuredContent.results[0].id;
  for (const selector of ["", "é", "../secret", "abc\n", "x".repeat(201), "unknown", foreign, null]) {
    assert.deepEqual(await api.fetch(selector), rejected);
  }
});

test("selector expires at 60 seconds and cannot survive an isolate restart", async () => {
  const api = harness();
  const id = (await api.search("harbor")).structuredContent.results[0].id;
  api.advance(SELECTOR_TTL_MS - 1);
  assert.equal((await api.fetch(id)).structuredContent.id, id);
  assert.deepEqual(await harness().fetch(id), rejected);
  api.advance(1);
  assert.deepEqual(await api.fetch(id), rejected);
});

test("selector storage stays capped and an evicted selector fails closed", () => {
  const reader = createSyntheticReader(() => 0);
  const oldest = reader.search("harbor").results[0].id;
  let newest;
  for (let index = 0; index < MAX_SELECTORS; index += 1) newest = reader.search("harbor").results[0].id;
  assert.equal(reader.fetch(oldest), null);
  assert.equal(reader.fetch(newest).id, newest);
});

test("unsupported modes fail closed with no fixture fallback", async () => {
  for (const mode of ["PAS_STAGING", "UNAVAILABLE", "other"]) {
    const api = harness({ PAS_CONTEXT_MODE: mode });
    assert.deepEqual(await api.search("harbor"), rejected);
    assert.deepEqual(await api.fetch("valid_selector"), rejected);
    const page = await (await api.request("/")).text();
    assert.match(page, /UNAVAILABLE/u);
    assert.doesNotMatch(page, /Harbor City/u);
  }
});

test("tool parameters reject owner, URL and other unrecognized properties", async () => {
  const api = harness();
  for (const args of [{ query: "harbor", owner_id: "owner" }, { query: "harbor", url: origin }, [], undefined]) {
    const result = (await api.rpc("tools/call", { name: "search", arguments: args })).result;
    assert.deepEqual(result, rejected);
  }
});

test("invalid readers and oversized result envelopes yield the same sanitized failure", async () => {
  const worker = createWorker({ search() { throw new Error("hidden diagnostic"); } });
  const response = await worker.fetch(new Request(origin + "/mcp", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ jsonrpc: "2.0", id: 1, method: "tools/call", params: { name: "search", arguments: { query: "harbor" } } }),
  }));
  assert.deepEqual((await response.json()).result, rejected);
  assert.deepEqual(toolResult({ text: "é".repeat(MAX_BYTES / 2) }), rejected);
});

test("invalid wire frames and disallowed HTTP methods are rejected", async () => {
  const api = harness();
  assert.equal((await (await api.post("{")).json()).error.code, -32700);
  assert.equal((await (await api.post(JSON.stringify([]))).json()).error.code, -32600);
  assert.equal((await api.post("x".repeat(MAX_BYTES + 1))).status, 413);
  assert.equal((await api.post("{}", { "Content-Type": "text/plain" })).status, 415);
  assert.equal((await api.request("/mcp")).status, 405);
  assert.equal((await api.request("/", { method: "POST" })).status, 405);
  assert.equal((await api.request("/citations/v1/sample")).status, 404);
  assert.deepEqual((await api.rpc("tools/call", { name: "propose_itinerary_change", arguments: {} })).result, rejected);
});

test("status page reports diagnostics without echoing request authority or requiring a client runtime", async () => {
  const api = harness();
  const result = await api.request("/?token=hidden", { headers: { Authorization: "Bearer hidden" } });
  const page = await result.text();
  assert.equal(result.status, 200);
  assert.match(result.headers.get("content-security-policy"), /default-src 'none'/u);
  assert.match(page, /SYNTHETIC_LOCAL/u);
  assert.match(page, /Disconnected/u);
  assert.ok(page.includes(BUILD));
  assert.ok(page.includes(PROTOCOL));
  assert.doesNotMatch(page, /hidden|<script/u);
  assert.equal(await (await api.request("/", { method: "HEAD" })).text(), "");
});
