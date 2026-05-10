from mynovel.llm.openai_compatible import ChatRequest


def test_chat_request_payload() -> None:
    request = ChatRequest(model="test-model", messages=[{"role": "user", "content": "hi"}])

    assert request.to_payload()["model"] == "test-model"
