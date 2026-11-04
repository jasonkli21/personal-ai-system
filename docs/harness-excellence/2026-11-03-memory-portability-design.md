# Memory portability implementation decision

2026-11-03. Base `51cfda1c9ad7c610364454e405cbfe5769a8e11e`. Development scope.

- **Now.** Keep the private owner API outside the external consumer contract. Require
  recent verified Google authentication, builtin audience and authorized party,
  exact server-resolved actor, and standalone scope for profile operations.
  Keep the browser on its same-origin bearer-token proxy.
- **Now.** Reuse the bounded project reader, source lease, canonical lifecycle CAS
  and exact-key receipts for inspection and forget. The operator account export is
  a separate audience and its inventory is too broad for this surface. The workflow
  attempt evidence establishes local dispatch history, which supplies no knowledge
  correction issuer or transferable evidence.
- **Now.** Correct explicit preferences using the existing profile writer with
  caller revision checked under its existing locks. Export only the four possible
  user-set fields, with owner and source revision, observation time, scope and
  restrictions. The closed canonical JSON format uses SHA-256 for integrity.
  Prepare bytes under the profile and owner fence and release one bounded response.
  Preview reads at most 8 KiB and retains no file, grants, receipts or writes.
- **Before enablement.** Prove deployed owner identity, transport release ordering,
  native concurrency and restore against post-backup owner fences, profile changes,
  forget and revocation. Disable the adapter by flag, keeping canonical state and
  replay evidence. Treat previously delivered bytes as outside managed revocation.
- **Defer.** Verified knowledge replacement, external or project knowledge export,
  import commit, full roundtrip and distributed send fences require independent
  issuer authority and atomic lineage. Keep grant management on the existing owner
  API and use the existing consent boundary for the synthetic two-consumer check.

Static and hermetic evidence cover this development slice. Native, external,
deployed recovery and actual utility have separate acceptance criteria.
