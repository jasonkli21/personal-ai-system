"""Regenerate/check the public OpenAPI subset. No provider/storage calls."""

import argparse
from pathlib import Path

from personal_ai.api.consumer_contract import serialized_contract

parser = argparse.ArgumentParser()
parser.add_argument("--check", action="store_true")
args = parser.parse_args()
path = Path(__file__).resolve().parents[2] / "docs/platform-independence/consumer-v1.openapi.json"
value = serialized_contract()
if args.check:
    assert path.read_text() == value, "regenerate with backend/scripts/pi2_contract.py"
else:
    path.write_text(value)
print("PI2_CONSUMER_CONTRACT=PASS")
