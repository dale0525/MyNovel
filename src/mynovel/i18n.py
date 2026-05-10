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
        "provider.embedding_use_llm": "Embedding 复用 LLM Base URL / API Key",
        "provider.rerank_base_url": "Rerank Base URL（可选）",
        "provider.rerank_api_key": "Rerank API Key（可选）",
        "provider.rerank_model": "Rerank 模型（可选）",
        "provider.rerank_use_llm": "Rerank 复用 LLM Base URL / API Key",
        "provider.save": "保存配置",
        "provider.saved": "模型配置已保存",
        "book.title": "开书流程",
        "book.description": "只输入一个想法，让 AI 补全开书蓝图，再按你的意见多轮修改。",
        "book.idea": "创意",
        "book.idea_placeholder": "一个失意档案员重建禁书图书馆",
        "book.create": "生成开书蓝图",
        "book.created": "已生成开书蓝图 v{version}",
        "book.idea_required": "创意不能为空。",
        "blueprint.title": "开书蓝图 v{version}",
        "blueprint.empty": "还没有开书蓝图。",
        "blueprint.revision_notes": "修改意见",
        "blueprint.revise": "让 AI 修改蓝图",
        "blueprint.revised": "已生成修改版蓝图 v{version}",
        "blueprint.revision_required": "修改意见不能为空。",
        "blueprint.parse_failed": "AI 返回内容不是可用的蓝图 JSON，已保留原文。",
        "blueprint.raw_response": "AI 原始返回",
    }
}


def t(key: str, locale: str = DEFAULT_LOCALE, **kwargs: object) -> str:
    text = TRANSLATIONS.get(locale, TRANSLATIONS[DEFAULT_LOCALE]).get(key, key)
    return text.format(**kwargs)
