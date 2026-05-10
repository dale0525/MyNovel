from sqlmodel import Session

from mynovel.domain.models import Book, ProviderConfig, utc_now


def add_book(session: Session, book: Book) -> Book:
    session.add(book)
    session.commit()
    session.refresh(book)
    return book


def get_provider_config(session: Session) -> ProviderConfig | None:
    return session.get(ProviderConfig, 1)


def save_provider_config(session: Session, config: ProviderConfig) -> ProviderConfig:
    existing = get_provider_config(session)
    if existing is None:
        config.id = 1
        session.add(config)
        session.commit()
        session.refresh(config)
        return config

    existing.llm_base_url = config.llm_base_url
    existing.llm_api_key = config.llm_api_key
    existing.llm_model = config.llm_model
    existing.embedding_base_url = config.embedding_base_url
    existing.embedding_api_key = config.embedding_api_key
    existing.embedding_model = config.embedding_model
    existing.rerank_base_url = config.rerank_base_url
    existing.rerank_api_key = config.rerank_api_key
    existing.rerank_model = config.rerank_model
    existing.updated_at = utc_now()
    session.add(existing)
    session.commit()
    session.refresh(existing)
    return existing
