"""Single registry of immutable historical bytes for verification checks.

``source_contract_check`` and ``naming_policy_check`` both attest these exact
bytes so neither standalone gate depends on the other to notice a mutation.
Keys are repository-relative paths.
"""

from __future__ import annotations

HISTORICAL_PLANNING_LOCKS = {
    "backend/src/personal_ai/evaluation/fixtures/context/planning-baseline-v35.json": (
        "d344dbbe8c7a8dc5d53b8b61c12212a034451bd68cc2cc64f02b26c3f1104fe9"
    ),
    "backend/src/personal_ai/evaluation/fixtures/context/planning-baseline-v36.json": (
        "d6e0c9a6abc936eb2d9e64564ccf4f6009876b10901129d5067423fff0fc8fdc"
    ),
    "backend/src/personal_ai/evaluation/fixtures/context/planning-baseline-v37.json": (
        "1e4e9a635947f3a668a69a183542bb0b4833a9b166f9d205ae58f8ca7585d83b"
    ),
    "backend/src/personal_ai/evaluation/fixtures/context/planning-baseline-v38.json": (
        "222882f4256dbe19c4c68855792c3180e304a5218530056975bd019c11b77fb6"
    ),
}

HISTORICAL_OFFLINE_MANIFESTS = {
    "backend/src/personal_ai/evaluation/fixtures/offline_information_handling/manifest-v1.json": (
        "8480771c464c353a8899a36a4c510fe08a3665ff97a0cde7c0b867f5ff0d99bf"
    ),
    "backend/src/personal_ai/evaluation/fixtures/offline_information_handling/manifest-v2.json": (
        "ad69387bca873df3e9b3522ff15d222122d49ed572d8a113423cae5fd0af336c"
    ),
    "backend/src/personal_ai/evaluation/fixtures/offline_information_handling/source-manifest-v2-generation-2.json": (
        "322dd2f2e6bf7a66a9065bdbf36c8fa50fd37c3537a5ab82279d7139ba54a53f"
    ),
    "backend/src/personal_ai/evaluation/fixtures/offline_information_handling/source-manifest-v2-generation-3.json": (
        "431667748921a5a2cc05a19538172830effc3a8a144cfc4645fbb3b2038fb93c"
    ),
    "backend/src/personal_ai/evaluation/fixtures/offline_information_handling/source-manifest-v2-generation-4.json": (
        "ccee9fd1fcf6dad10c12d27ebc4dbec64995f5063e80a4313229a0121248ab42"
    ),
    "backend/src/personal_ai/evaluation/fixtures/offline_information_handling/source-manifest-v2-generation-5.json": (
        "c37407024e50c801e794b2b88a3341f598a7d1736d8c9e1f4221f07c2c8496a2"
    ),
    "backend/src/personal_ai/evaluation/fixtures/offline_information_handling/source-manifest-v2-generation-6.json": (
        "35b42c70c19aac0f44dc7f9a118e0f360472a9077c3a0b3da22d70abe8938bc6"
    ),
    "backend/src/personal_ai/evaluation/fixtures/offline_information_handling/source-manifest-v2-generation-7.json": (
        "587a4d2530e428ce32c3dc273c38c3734ad183466e47fc17cb3278800bcc1614"
    ),
    "backend/src/personal_ai/evaluation/fixtures/offline_information_handling/source-manifest-v2-generation-8.json": (
        "f28f367c8a884801bb7bb0463929bb98426a57af46090fbd094b5402ac948869"
    ),
    "backend/src/personal_ai/evaluation/fixtures/offline_information_handling/source-manifest-v2-generation-9.json": (
        "a00a8faf9f8a8f7dc17efbc81e07a8053c80415a7735eae362ed43ad95bc6a3e"
    ),
    "backend/src/personal_ai/evaluation/fixtures/offline_information_handling/source-manifest-v2-generation-10.json": (
        "de316118c1eaa556a9110b9807a9c288dfc992bbb3215978b5ece8b4852e56c7"
    ),
    "backend/src/personal_ai/evaluation/fixtures/offline_information_handling/source-manifest-v2-generation-11.json": (
        "324a6a6df4f6c56aea7aa1f832d601c714d773623aa8b71ee5aabf9d6c80cd52"
    ),
    "backend/src/personal_ai/evaluation/fixtures/offline_information_handling/source-manifest-v2-generation-12.json": (
        "36b4f14e03cb5acecee64b541d26903458e77a4243eb8dc73b79fb351c1c8634"
    ),
}

HISTORICAL_FROZEN_CASES = {
    "backend/src/personal_ai/evaluation/fixtures/offline_information_handling/cases-v1.json": (
        "84c0e5a1e990ac5b282a24348e4319406d3ec4188d179099777ab5aa4b5651bf"
    ),
    "backend/src/personal_ai/evaluation/fixtures/offline_information_handling/cases-v2.json": (
        "25df654eda27040c3b52695fd6ec695b53238a7cf76b82e1ed4e5d442b55205d"
    ),
}

HISTORICAL_FIXTURES = {
    "backend/src/personal_ai/evaluation/fixtures/decisions/decision-fixtures.json": (
        "221e9a3b42945b33363720b67a6d50e8204b3e01cae582fc81f24d1f2c870cb2"
    ),
    "backend/src/personal_ai/evaluation/fixtures/iterative_research/iterative-research-fixtures.json": (
        "6db4b06c7d371c2a54fec37886c4b9df4ff555b671689a1c96cf9c4935ff4ef1"
    ),
    "backend/src/personal_ai/evaluation/fixtures/iterative_research/iterative-research-fixtures-v2.json": (
        "b65ee153b020ae44dbefab33fb21ff268585ca08b0a490af98d0aa5d87ecc129"
    ),
    "backend/src/personal_ai/evaluation/fixtures/memory/memory-control-v1.json": (
        "7d2e93b33904ddb81bef6e4f8f3ffff89a51b7d63b85b5e88c21877c4b6c2a9d"
    ),
    "backend/src/personal_ai/evaluation/fixtures/memory/memory-knowledge-consumer-v1.json": (
        "ff94f67f8889f13887128003d21e5f1b89078e806c12a1d148c4ac7d1d347066"
    ),
    "backend/src/personal_ai/evaluation/fixtures/memory/memory-knowledge-pairs-v1.json": (
        "587e87f11422719e8ad2f512ede7020c0bae937cb555b1035cd8eb386866756e"
    ),
    "backend/src/personal_ai/evaluation/fixtures/memory/memory-task-cases-v1.json": (
        "043edaae3461286b49bcb4fda4f73bdc5059e528361bad3fa670a3b1c4e58b18"
    ),
    "backend/src/personal_ai/evaluation/fixtures/memory/memory-task-cases-v2.json": (
        "592a0e3799aeafc32ebf7cba0c7e162ff0af98d0049af2cf683de653e5fc02e1"
    ),
}

HISTORICAL_MIGRATIONS = {
    "backend/src/personal_ai/persistence/migrations/008_storage_migration_control.sql": (
        "85b2431c757e14c830fa1debdbb2edb367d0a6e32d420b33543ad49300bf0fad"
    ),
    "backend/src/personal_ai/persistence/migrations/009_derived_source_migration_metadata.sql": (
        "3048dbe3fb767e3c26240456014bbdb9f8664de4890db379d5de91efd1a9bffd"
    ),
    "backend/src/personal_ai/persistence/migrations/011_effect_receipt_migration_payload.sql": (
        "96c8809151a86eaf63dc0f7e962b564f01681ef5ab41b444261a6aba0c98ff7e"
    ),
    "backend/src/personal_ai/persistence/migrations/012_provider_rate_limit_source_payload.sql": (
        "4cf0223fd84b1235695c5b63cec176cbab4798f46a9fb8133522f76ef77f4299"
    ),
    "backend/src/personal_ai/persistence/migrations/027_memory_dependency_epochs.sql": (
        "3591c9d2ea669d66f994e3fb5492484fd7c5ea9c8321b66fea0fda1014543009"
    ),
    "backend/src/personal_ai/persistence/migrations/028_verified_memory_knowledge.sql": (
        "652c92c1251ede51ae0697d72a74e1bcc61ebbdf9b101d3cbf00ac312ced067c"
    ),
    "backend/src/personal_ai/persistence/migrations/030_memory_control.sql": (
        "0690004c83086e1dce8539f9311fb24a1d0f1afba6666e6b5077d0618d56a058"
    ),
    "backend/src/personal_ai/persistence/migrations/032_profile_consents.sql": (
        "18551d07e8ac2f494d9da8bdae7f15dfdef41040e65611740b0bed0ddbbd1f0b"
    ),
    "backend/src/personal_ai/persistence/migrations_py/022_routing_authorities.py": (
        "003787e63cf27e4552f2505a9de189d738e8fafce6b94ab7edf1c46252f19b35"
    ),
}


def immutable_history() -> dict[str, str]:
    """Return every pinned historical path and its exact SHA-256."""
    return {
        **HISTORICAL_PLANNING_LOCKS,
        **HISTORICAL_OFFLINE_MANIFESTS,
        **HISTORICAL_FROZEN_CASES,
        **HISTORICAL_FIXTURES,
        **HISTORICAL_MIGRATIONS,
    }
