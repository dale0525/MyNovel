import pytest

from mynovel.workflows.embedding import parse_embedding_response


def test_parse_embedding_response_returns_first_vector() -> None:
    assert parse_embedding_response({"data": [{"embedding": [0.1, 0.2]}]}) == [0.1, 0.2]


def test_parse_embedding_response_rejects_missing_vector() -> None:
    with pytest.raises(ValueError, match="Embedding response has no usable vector"):
        parse_embedding_response({"data": []})
