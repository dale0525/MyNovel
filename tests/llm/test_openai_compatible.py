from mynovel.llm.openai_compatible import ChatRequest, EmbeddingRequest, RerankRequest


def test_chat_request_payload() -> None:
    request = ChatRequest(model="test-model", messages=[{"role": "user", "content": "hi"}])

    assert request.to_payload()["model"] == "test-model"


def test_embedding_request_payload() -> None:
    request = EmbeddingRequest(model="embedding-model", input=["章节摘要", "伏笔"])

    assert request.to_payload() == {"model": "embedding-model", "input": ["章节摘要", "伏笔"]}


def test_rerank_request_payload() -> None:
    request = RerankRequest(
        model="rerank-model",
        query="符号发热",
        documents=["莉拉掌心符号发热", "普通集市"],
        top_n=1,
    )

    assert request.to_payload() == {
        "model": "rerank-model",
        "query": "符号发热",
        "documents": ["莉拉掌心符号发热", "普通集市"],
        "top_n": 1,
    }
