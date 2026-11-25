# PAS Personal Context

This ChatGPT Sites Worker exposes a connection-status page and the read-only MCP tools `search` and `fetch`. In the first release the only source is one fabricated Harbor City itinerary. PAS is disconnected. `PAS_STAGING` is reserved. Selecting it or any unsupported mode reports `UNAVAILABLE` and disables reads.

The port uses Sites' Worker ESM deployment format. `src/index.js` handles the Sites transport and page route. `src/contract.js` describes and bounds the default, URL-free tool profile. `src/synthetic-reader.js` implements the demo, and `fixtures/` holds its fabricated source. The production artifact bundles one self-contained Worker. esbuild is a locked build dependency. The hosted Worker has no third-party runtime dependencies.

## Develop

Use Node 22 or newer and the pnpm version pinned in `package.json`.

```sh
CI=true pnpm install --frozen-lockfile --ignore-scripts
pnpm test
pnpm build
pnpm dev
```

The preview listens only on `127.0.0.1:4173`. It exercises the same handler without the hosted Sites access policy. The deployed Site relies on Sites for owner-private access. This release does not consume Sites identity headers. The only runtime variable is documented in `.env.example`. The local preview reads its environment from the shell.

`search` accepts a nonblank query of at most 256 UTF-8 bytes. It returns up to ten opaque selectors and titles. `fetch` accepts an opaque ASCII selector of at most 200 bytes. It returns the ID, title, text, source, revision and UTC observation and freshness times. UTF-8 tool results are capped at 8,192 bytes, including both MCP representations. The fixture issues selectors valid for 60 seconds within one isolate, up to 1,024 selectors. The next call can safely fail after expiry, eviction, restart, or cross-isolate routing. Selectors in this demo have no PAS owner or consent meaning.

The only hosted operation that changes in-memory state is issuance or eviction of temporary demo selectors. There is no domain record write, persistent storage, model invocation, external request, or application connection. Real Travel and all Health sources are excluded from this component. PAS will own authenticated staging authority and selector lifetime once that integration has been independently verified.

See [Deployment and operations](DEPLOYMENT.md) for versioning, review and recovery. See the [release evidence template](RELEASES.md) for the exact observations to retain.
