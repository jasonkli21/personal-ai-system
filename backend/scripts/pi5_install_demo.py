"""Create a new synthetic operator corpus; explicit scope, no user-data ingestion."""

import argparse
from datetime import UTC, datetime, timedelta
from hashlib import sha256
from pathlib import Path
from uuid import uuid4

from personal_ai.retrieval.installation import Access, Installation, LocalDocument

parser = argparse.ArgumentParser(description=__doc__)
parser.add_argument("output", type=Path)
for name in ("owner", "actor", "application"):
    parser.add_argument("--" + name, required=True)
parser.add_argument("--workspace")
args = parser.parse_args()
if not args.output.is_absolute():
    parser.error("output must be an absolute operator path")
access = Access(
    owner_id=args.owner,
    acting_user_id=args.actor,
    application_id=args.application,
    workspace_id=args.workspace,
)
now = datetime.now(UTC)
text = "Atlas is a synthetic catalog entry for demonstrating authorized local retrieval."
value = Installation(
    schema_version="retrieval-installation-v2",
    issuer_id=uuid4(),
    enabled=True,
    tool_enabled=True,
    access=(access,),
    documents=(
        LocalDocument(
            source_id="demo-atlas",
            revision="1",
            rights_epoch="1",
            rights_reference="operator-demo-v1",
            license="CC0-synthetic-demo",
            title="Synthetic catalog",
            text=text,
            content_sha256=sha256(text.encode()).hexdigest(),
            sensitivity="public",
            observed_at=now,
            expires_at=now + timedelta(hours=24),
            quote_allowed=True,
            access=(access,),
        ),
    ),
)
with args.output.open("x") as stream:
    stream.write(value.model_dump_json(indent=2) + "\n")
print("PI5_DEMO_CREATED: synthetic local corpus only; external query disclosure is disabled")
