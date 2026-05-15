from __future__ import annotations

import argparse
from pathlib import Path

from sqlmodel import Session

from mynovel.db import create_db_and_tables, create_engine_for_path
from mynovel.domain.models import ProviderConfig, ProviderConfigValidation
from mynovel.provider_config_validation import provider_model_fingerprint


def main() -> None:
    parser = argparse.ArgumentParser(description="Prepare Playwright database fixtures.")
    parser.add_argument("--db", type=Path, required=True)
    parser.add_argument("--profile", choices=["configured", "unconfigured"], required=True)
    args = parser.parse_args()

    if args.db.exists():
        args.db.unlink()
    args.db.parent.mkdir(parents=True, exist_ok=True)
    engine = create_engine_for_path(args.db)
    create_db_and_tables(engine)
    if args.profile == "configured":
        _save_validated_provider_config(engine)


def _save_validated_provider_config(engine) -> None:
    config = ProviderConfig(
        llm_base_url="https://api.example.test/v1",
        llm_api_key="test-key",
        llm_model="gpt-test",
        embedding_use_llm_credentials=True,
        embedding_base_url="https://api.example.test/v1",
        embedding_model="text-embedding-test",
        rerank_use_llm_credentials=True,
        rerank_base_url="https://api.example.test/v1",
        rerank_model="rerank-test",
    )
    validation = ProviderConfigValidation(
        llm_fingerprint=provider_model_fingerprint(config, "llm"),
        embedding_fingerprint=provider_model_fingerprint(config, "embedding"),
        rerank_fingerprint=provider_model_fingerprint(config, "rerank"),
    )
    with Session(engine) as session:
        session.add(config)
        session.add(validation)
        session.commit()


if __name__ == "__main__":
    main()
