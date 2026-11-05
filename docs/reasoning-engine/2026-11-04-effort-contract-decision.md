# Continuation effort contract decision

Baseline `cac6549c47323ababb2c1d2ba3f1f871d3bc43de`. The checkout already
contains a PRD move and planning drafts. The implementation preserves the
offline seals and uses the existing continuation identity and send lifecycle.

Adopt the frozen request validator on automatic continuation only. Omitted
budget dimensions stay zero. A future defaulting scheme needs a different
version. Freeze the direct policy version for this request schema so replay
keeps the original policy identity. Changes in request ceilings or effort
under the same key conflict. Existing completed turns replay through the
same disclosure checks. Incomplete attempts stay bound to their original
key and canonical records.

The opt-in direct lane uses only the current message and shared system
context. The assembler uses the matched counter, with source planning,
summary refresh and memory lifecycle work excluded. This makes the zero
source/tool bounds enforceable and avoids auxiliary generation. Preserve
the existing ledger and authority checks for any physical send. The hosted
lane needs independent proof that even its plain generation bounds all
billable or hidden output before it can enter this envelope.

A capability is an immutable proof for a specific installed profile,
runtime, operation and bounded wire mapping. Synthetic proof applies only
to the offline fake. Installed real adapters start with zero native mappings.
Publish a versioned, explicitly negotiated terminal observation containing
only bounded policy and resource facts. Preserve the no-field stream and
durable identity.
