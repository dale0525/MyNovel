DEFAULT_LOCALE = "zh-CN"

TRANSLATIONS = {
    "zh-CN": {
        "app.title": "MyNovel 调试台",
        "app.subtitle": "本地 AI 小说生产线调试工作台。",
        "app.sqlite": "SQLite",
        "nav.provider_config": "模型配置",
        "nav.open_book": "开书流程",
        "status.configured": "配置已完成",
        "status.not_configured": "配置完成后才能开书",
        "status.no_books": "还没有草稿书。",
        "provider.title": "模型配置",
        "provider.description": "先配置 OpenAI-compatible 的 LLM 和 Embedding 接口；Rerank 可以稍后补。",
        "provider.llm_base_url": "LLM Base URL",
        "provider.llm_api_key": "LLM API Key",
        "provider.llm_model": "LLM 模型",
        "provider.embedding_base_url": "Embedding Base URL",
        "provider.embedding_api_key": "Embedding API Key",
        "provider.embedding_model": "Embedding 模型",
        "provider.rerank_base_url": "Rerank Base URL（可选）",
        "provider.rerank_api_key": "Rerank API Key（可选）",
        "provider.rerank_model": "Rerank 模型（可选）",
        "provider.save": "保存配置",
        "provider.saved": "模型配置已保存",
        "book.title": "开书流程",
        "book.description": "完成模型配置后，再创建第一本草稿书。",
        "book.idea": "创意",
        "book.idea_placeholder": "一个失意档案员重建禁书图书馆",
        "book.genre": "类型",
        "book.audience": "读者",
        "book.create": "创建草稿",
        "book.created": "已创建草稿书 #{book_id}",
        "book.idea_required": "创意不能为空。",
        "books.title": "草稿书",
        "books.id": "ID",
        "books.premise": "核心创意",
        "books.genre": "类型",
        "books.status": "状态",
    }
}


def t(key: str, locale: str = DEFAULT_LOCALE, **kwargs: object) -> str:
    text = TRANSLATIONS.get(locale, TRANSLATIONS[DEFAULT_LOCALE]).get(key, key)
    return text.format(**kwargs)
