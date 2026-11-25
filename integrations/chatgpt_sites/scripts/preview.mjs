import { createServer } from "node:http";
import { Readable } from "node:stream";
import worker from "../src/index.js";

const host = "127.0.0.1";
const port = Number(process.env.PAS_PREVIEW_PORT ?? "4173");
const env = { PAS_CONTEXT_MODE: process.env.PAS_CONTEXT_MODE };
const server = createServer(async (incoming, outgoing) => {
  try {
    const { method, headers } = incoming;
    const url = new URL(`http://${host}:${port}`);
    // Parsing an incoming URL as a path keeps the preview bound to its own origin.
    const target = new URL(incoming.url, url);
    if (target.origin !== url.origin) {
      outgoing.writeHead(400).end();
      return;
    }

    const init = { method, headers };
    if (method !== "GET" && method !== "HEAD") {
      init.body = Readable.toWeb(incoming);
      init.duplex = "half";
    }
    const result = await worker.fetch(new Request(target, init), env);
    outgoing.writeHead(result.status, Object.fromEntries(result.headers));
    if (result.body) Readable.fromWeb(result.body).pipe(outgoing);
    else outgoing.end();
  } catch {
    if (!outgoing.headersSent) outgoing.writeHead(500);
    outgoing.end();
  }
});
server.requestTimeout = 10_000;
server.listen(port, host, () => console.log(`Local: http://${host}:${server.address().port}`));
