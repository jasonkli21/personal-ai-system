# PI-8 implementation and verification

2026-11-03. Baseline `9b4b0f4db358ac97c156a615831dbb81a0a636a9`.
The [pre-code record](pi-8-plan-hardening.md) inventories the three original
untracked files and the attached prompt. The [ledger](pi-8-verification.json)
binds the observed source, contracts, tests, fixtures, lockfile and static
infrastructure by SHA-256. It reports scope per case. `make pi8-check` validates
dated evidence and includes negative tests. It neither launches app commands
nor generates acceptance. No application behavior changed.

## Reproduction and observed attempts

Run from repo root with prepared backend Python 3.11.15 and uv 0.11.13.
Observed platform macOS 27.0.1 arm64, managed Codex sandbox. For the make
commands, use `env -i PATH="$PWD/backend/.venv/bin:/opt/homebrew/bin:/usr/bin:/bin" TMPDIR=/tmp`.
This excludes ambient credentials. The reviewed synthetic suites use injected
transports and the repository Python audit hook. That hook observes Python
socket operations in its process. Native kernel enforcement remains blocked.

| Command | Exit and result | Wall seconds |
| --- | --- | --- |
| `sandbox-exec -p '(version 1)(allow default)(deny network*)' /usr/bin/true` | 1, `sandbox_apply: Operation not permitted` | Under 1 |
| `make pi7-local-smoke PI7_SMOKE_FLAGS=--require-native` | 2, `sandbox_launcher_rejected` before build/dispatch | 0.14 |
| `make pi7-consumer-smoke PI7_SMOKE_FLAGS=--require-native` | 2, same native gate | 0.09 |
| `make pi7-cloud-plan` | 0, static policy only. Plan digest `912051145eb28c95ead41108927e2a0e094294e8bab440f010977165626aba80` | 0.06 |
| `bash -n infrastructure/gcp/deploy.sh` | 0, static syntax | Under 1 |
| `bash infrastructure/gcp/deploy.sh apply` | 2, `apply_blocked_unverified`. Source review verified the branch only prints fixed text and exits | Under 1 |
| `backend/.venv/bin/python -I backend/scripts/pi2_contract.py --check` | 0, generated OpenAPI matches, two dependency warnings | 2.04 |
| Focused suite below | 0, 326 passed, no failures/skips, four warnings, zero forbidden network attempts observed by hook | 10.54 |
| `make pi7-check` | 0, 221 passed, no failures/skips, four warnings, zero forbidden network attempts observed by hook | 32.94 |
| Client/API suite below | 0, 24 passed, no failures/skips, three warnings, zero forbidden network attempts observed by hook | 2.44 |
| Offline core archive recipe below | 0, two archives inspected. Earlier build/inspection attempts retained below | 1.19 build |
| `make backend-lint` | First run exit 2, Ruff C413. Final run exit 0 | 0.12 each |
| `make pi8-check` | 0, 36 cases and input hashes valid, five standard-library tests passed | See ledger |
| `git diff --check` and `git diff --cached --check` | 0, whitespace checks | Under 1 |

The focused runs overlap with `pi7-check`. Counts describe commands and
cannot be summed as unique coverage.

```sh
env -i PATH="$PWD/backend/.venv/bin:/usr/bin:/bin" TMPDIR=/tmp LITELLM_LOCAL_MODEL_COST_MAP=True \
  backend/.venv/bin/python -E -s backend/scripts/pi2_http_checks.py -q \
  backend/tests/test_inference_execution.py backend/tests/test_litellm_gateway.py \
  backend/tests/test_provider_usage.py backend/tests/test_profile_consent.py \
  backend/tests/test_pi5_context.py backend/tests/test_pi5_retrieval.py \
  backend/tests/test_memory_control.py backend/tests/test_memory_control_context.py

env -i PATH="$PWD/backend/.venv/bin:/usr/bin:/bin" TMPDIR=/tmp LITELLM_LOCAL_MODEL_COST_MAP=True \
  backend/.venv/bin/python -E -s backend/scripts/pi2_http_checks.py -q \
  backend/tests/test_pi2_client.py backend/tests/test_memory_control_api.py
```

No `make pi5-check`, `make pi6-check`, `make platform-independence-check`
or full `make backend-test-offline` run. Those paths combine native/loopback
prerequisites, broader application execution, or builds without explicit
offline flags. PI-7 also records the historical planning revision guard
failure. Historical suites and their limits stay in their owning reports.
The native smoke refusal was respected. Docker was absent and no daemon
was contacted. No live accounts, providers, search, hosted deployment,
personal data, actual deletion or restore were used.

## Offline archive reproduction

No installation or archive extraction. The local build uses prepared Hatchling
without build isolation. Set an explicit empty cache and disable downloads.

```sh
audit_tmp=$(mktemp -d /tmp/pi8-build.XXXXXXXX)
trap 'rm -rf -- "$audit_tmp"' EXIT
env -i PATH="/opt/homebrew/bin:/usr/bin:/bin" TMPDIR="$audit_tmp" \
  UV_CACHE_DIR="$audit_tmp/cache" UV_PYTHON_DOWNLOADS=never SOURCE_DATE_EPOCH=1793664000 \
  uv --no-config --offline build backend --no-build-isolation \
  --python "$PWD/backend/.venv/bin/python" --out-dir "$audit_tmp/dist"
backend/.venv/bin/python -I - "$audit_tmp/dist" <<'PY'
import hashlib, sys, tarfile, zipfile
from pathlib import Path

dist = Path(sys.argv[1])
wheel, = dist.glob("*.whl")
source, = dist.glob("*.tar.gz")
with zipfile.ZipFile(wheel) as archive:
    names = archive.namelist()
    assert all(n.startswith(("personal_ai/", "personal_ai_backend-0.1.0.dist-info/")) for n in names)
    assert not any(n.endswith("/entry_points.txt") for n in names)
    assert b"personal-ai-reference" not in archive.read(next(n for n in names if n.endswith("/METADATA")))
    print(wheel.name, len(names), hashlib.sha256(wheel.read_bytes()).hexdigest())
with tarfile.open(source) as archive:
    names = archive.getnames()
    assert all(n.split("/")[1] in {"src", "pyproject.toml", "uv.lock", "PKG-INFO", ".gitignore"} for n in names)
    assert all(n.split("/")[2] == "personal_ai" for n in names if n.split("/")[1] == "src")
    assert b"personal-ai-reference" not in archive.extractfile(next(n for n in names if n.endswith("/PKG-INFO"))).read()
    print(source.name, len(names), hashlib.sha256(source.read_bytes()).hexdigest())
PY
```

| Distribution | Entries | SHA-256 |
| --- | --- | --- |
| Core wheel, offline checkout build | 450 | `e72093fd67cba0966e75858b11e38747de2de714659520462f3881788ecc7b5a` |
| Core sdist, offline checkout build | 451 | `498996b786c37005ea14fefe3c3928c62b8ccfad5cd04a6fe18d06d052756867` |

Earlier attempt A built both archives in 1.54 s. Inspection exited 1 when
the output directory included an extra entry. Attempt B built both in
1.20 s. Inspection exited 1 in 0.06 s because its sdist allowlist omitted
the inherited `.gitignore`. Attempt C used the corrected layout and passed.
These are static packaging observations. The trusted installed gate stays blocked.

## Self-review and artifact handling

Reviewed the exact diff and trace from source authority to provider, replay,
export, storage, and the no-apply branch. Runtime canary coverage is partial.
Only command metadata, numeric results, bounded error labels and input digests
enter the ledger. Review the staged patch, run `git diff --cached --check`
and scan staged added lines for credential-shaped patterns and raw fixture
payloads. Original test fixture files and historical results stay in place.
The [readiness assessment](pi-8-readiness-assessment.md) distinguishes inherited
P1 gaps from the export coverage hypothesis and audit defects. Use the
[fresh-session review prompt](pi-8-independent-review-handoff.md) for independent
acceptance.
