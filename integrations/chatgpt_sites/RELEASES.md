# Release evidence

Use one entry per prepared or deployed version. Store opaque project, plugin and deployment IDs, private access URLs, redacted tool traces, approval records and environment revisions in the private operational record. Keep credentials and raw request content out of release evidence.

| Field | Record |
| --- | --- |
| Date and state | Prepared, saved, deployed, rolled back, or disabled |
| PAS GitHub review | Approved commit and path |
| Portable source | SHA-256 of sorted per-file SHA-256 manifest; state any excluded generated files |
| Sites source | Exact Sites-managed Git commit |
| Sites version | Saved version number, private record pointer, deployment result |
| Runtime code | SHA-256 of `dist/server/index.js` |
| Tool contract | Worker build, MCP protocol version and profile |
| Backends | Reviewed PAS, Travel and Health SHAs; actual deployed PAS revision where applicable |
| Controls | Visibility, data tier, auth mode, configuration revision, approvals |
| Verification | Exact commands, results, client/surface/version and sanitized trace references |
| Recovery | Last known safe version, disablement path and revocation owner |
