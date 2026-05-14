from mynovel.domain.models import (
    Book,
    BookStatus,
    Canon,
    CanonProposalRevision,
    CanonProposalRevisionStatus,
    Chapter,
    ChapterStatus,
)
from mynovel.product_views import render_trusted_state_page


def test_trusted_state_page_shows_full_state_sections_without_raw_keys() -> None:
    book = Book(
        id=1,
        title="长夜图书馆",
        genre="奇幻连载",
        audience="成长冒险读者",
        status=BookStatus.PRODUCING,
    )
    canon = Canon(
        id=1,
        book_id=1,
        version=3,
        content={
            "world_rules": [{"name": "街尾蛇城", "rules": "历史守恒"}],
            "characters": [
                {
                    "name": "林墨",
                    "identity": "纸质档案修复师",
                    "role": "档案修复师",
                    "trait": "触觉共感",
                },
                {
                    "name": "莉拉",
                    "detail": "能读懂古代符号",
                    "chapter_title": "离开的召唤",
                    "updated_at": "2026-05-11T18:00:00+00:00",
                },
                {"name": "待确认", "detail": "人物", "type": "状态变化", "chapter": 2},
            ],
            "locations": [{"name": "幽谷", "detail": "旧王朝遗迹"}],
            "relationships": [
                {
                    "subjects": ["苏清月", "萧烈"],
                    "relation": "契约盟友/恋人",
                    "detail": "名义上的叔侄，实际上的医患与灵魂伴侣，强强联手。",
                },
                {"from": "莉拉", "to": "罗文", "detail": "临时同盟"},
            ],
            "foreshadowing": [
                {
                    "trigger": "苏清月检查原主遗物",
                    "description": "苏清月发现原主并非死于意外，而是被长期投喂慢性毒药。",
                },
                "第二枚符号仍未解释",
                {"name": "待确认", "detail": "真实线索被照片证明。", "type": "信息暴露"},
            ],
            "chapter_summaries": [{"chapter": 1, "title": "离开的召唤", "summary": "离村"}],
            "state_history": [
                {
                    "type": "canon_proposal_revision",
                    "target_section": "characters",
                    "changed_sections": [
                        "chapter_summaries",
                        "characters",
                        "foreshadowing",
                        "locations",
                        "relationships",
                    ],
                    "blocked_sections": [{"section": "world_rules", "reason": "已锁定"}],
                    "instruction": "补全开书定盘缺失的信息。",
                    "summary": "已补全人物、地点和关系。",
                    "risks": [],
                    "updated_at": "2026-05-13T12:21:02.019054+00:00",
                },
                {"chapter": 1, "changes": [{"type": "人物状态", "target": "莉拉"}]},
            ],
        },
    )

    page = render_trusted_state_page(book, canon, [])

    assert "可信设定" in page
    assert "人物" in page
    assert "规则：历史守恒" in page
    assert "身份：纸质档案修复师" in page
    assert "定位：档案修复师" in page
    assert "特质：触觉共感" in page
    assert "地点" in page
    assert "关系" in page
    assert "伏笔账本" in page
    assert "真实线索被照片证明" in page
    assert "章节摘要" in page
    assert "变化历史" in page
    assert "莉拉" in page
    assert "幽谷" in page
    relationship_section = page.split('id="relationships"', 1)[1].split('id="foreshadowing"', 1)[0]
    foreshadowing_section = page.split('id="foreshadowing"', 1)[1].split(
        'id="chapter-summaries"',
        1,
    )[0]
    assert "苏清月、萧烈：契约盟友/恋人。名义上的叔侄" in page
    assert relationship_section.count("苏清月、萧烈：契约盟友/恋人") == 1
    assert "苏清月检查原主遗物：苏清月发现原主并非死于意外" in page
    assert foreshadowing_section.count("苏清月检查原主遗物") == 1
    state_history_section = page.split('id="state-history"', 1)[1]
    assert "AI 定盘修订：人物" in state_history_section
    assert "更新分区：章节摘要、人物、伏笔账本、地点、关系" in state_history_section
    assert "说明：补全开书定盘缺失的信息。" in state_history_section
    assert "锁定未改：世界规则（已锁定）" in state_history_section
    assert "名称：待确认；内容：人物" not in page
    assert "名称：待确认" not in page
    assert "relationships：" not in page
    assert "subjects：" not in page
    assert "relation：" not in page
    assert "trigger：" not in page
    assert "state_history：" not in page
    assert "canon_proposal_revision" not in state_history_section
    assert "target_section" not in state_history_section
    assert "changed_sections" not in state_history_section
    assert "blocked_sections" not in state_history_section
    assert "rules：" not in page
    assert "identity：" not in page
    assert "role：" not in page
    assert "trait：" not in page
    assert "chapter_title" not in page
    assert "updated_at" not in page


def test_trusted_state_page_exposes_canon_lock_gate() -> None:
    book = Book(
        id=1,
        title="长夜图书馆",
        genre="奇幻连载",
        audience="成长冒险读者",
        status=BookStatus.CANON_LOCKED,
    )
    canon = Canon(
        id=1,
        book_id=1,
        version=1,
        content={
            "world_rules": [{"name": "雾墙规则", "detail": "幽谷边界危险。"}],
            "characters": [{"name": "罗斯", "detail": "石匠学徒。"}],
            "locations": [{"name": "幽谷", "detail": "旧王朝遗迹。"}],
            "relationships": [{"from": "罗斯", "to": "莉拉", "detail": "临时同盟"}],
            "foreshadowing": ["第二枚符号尚未解释"],
            "chapter_summaries": [{"chapter": 1, "title": "召唤", "summary": "进入幽谷"}],
        },
    )

    page = render_trusted_state_page(book, canon, [])

    assert "canon-gate-layout" in page
    assert "审计风险" in page
    assert "章节生产已解锁" in page
    assert "前 10 章节奏" in page
    assert "可信设定已锁定" in page
    assert "当前进度：<strong>已完成定盘</strong>" in page
    assert "当前为可信设定提案（未锁定）" not in page
    assert "可信设定提案 · 待确认" not in page
    assert "锁定可信设定并开始生产" not in page


def test_trusted_state_page_renders_clickable_canon_sections_with_locks() -> None:
    book = Book(
        id=1,
        title="长夜图书馆",
        genre="奇幻",
        audience="连载读者",
        status=BookStatus.DRAFT,
        constraints={
            "_canon_proposal": {
                "last_revision": {
                    "target_section": "characters",
                    "summary": "已调整人物和关系。",
                }
            }
        },
    )
    canon = Canon(
        id=1,
        book_id=1,
        version=1,
        content={
            "world_rules": [{"name": "雾墙规则", "detail": "幽谷边界危险"}],
            "characters": [{"name": "林烬"}, {"name": "闻舟"}, {"name": "许澜"}],
            "factions": [{"name": "旧石会"}],
            "locations": [{"name": "幽谷"}, {"name": "雾门"}],
            "relationships": [
                {"from": "林烬", "to": "闻舟", "detail": "同盟"},
                {"from": "林烬", "to": "旧石会", "detail": "对抗"},
            ],
            "foreshadowing": ["残页", "雾门", "旧王朝"],
            "chapter_summaries": [
                {"chapter": 1, "title": "召唤"},
                {"chapter": 2, "title": "雾门"},
                {"chapter": 3, "title": "旧石会"},
            ],
        },
    )

    page = render_trusted_state_page(book, canon, [])

    assert 'href="#world"' in page
    assert 'id="world"' in page
    assert 'action="/canon-proposal-lock"' in page
    assert 'name="section" value="world_rules"' in page
    assert "让 AI 修改这部分" in page
    assert "最近一次 AI 修订" in page
    assert "已调整人物和关系" in page


def test_trusted_state_page_summarizes_world_rules_without_raw_json() -> None:
    book = Book(
        id=1,
        title="长夜图书馆",
        genre="奇幻",
        audience="连载读者",
        status=BookStatus.DRAFT,
    )
    canon = Canon(
        id=1,
        book_id=1,
        version=1,
        content={"world_rules": [{"premise": "书籍可以封印神明"}]},
    )

    page = render_trusted_state_page(book, canon, [])

    assert "前提：书籍可以封印神明" in page
    assert "&#x27;premise&#x27;" not in page
    assert "{&#x27;" not in page


def test_trusted_state_page_renders_ai_revision_preview_actions() -> None:
    book = Book(
        id=1,
        title="长夜图书馆",
        genre="奇幻",
        audience="连载读者",
        status=BookStatus.DRAFT,
    )
    canon = Canon(id=1, book_id=1, version=1, content={"characters": []})
    revision = CanonProposalRevision(
        id=9,
        book_id=1,
        base_canon_version=1,
        base_content_hash="content",
        base_locks_hash="locks",
        target_section="characters",
        instruction="主角改成外冷内热",
        allowed_sections=["characters"],
        locked_sections=["world_rules"],
        changed_sections={"characters": [{"name": "林烬"}]},
        blocked_sections=[{"section": "world_rules", "reason": "已锁定"}],
        summary="已调整人物。",
        risks=["需要同步章节动机。"],
    )

    page = render_trusted_state_page(book, canon, [], proposal_revision=revision)

    assert "修订预览" in page
    assert 'action="/canon-proposal-apply"' in page
    assert 'name="revision_id" value="9"' in page
    assert "世界规则" in page
    assert "已锁定" in page


def test_trusted_state_page_presents_ai_revision_as_reviewable_decision() -> None:
    book = Book(
        id=1,
        title="长夜图书馆",
        genre="奇幻",
        audience="连载读者",
        status=BookStatus.DRAFT,
    )
    canon = Canon(id=1, book_id=1, version=1, content={"characters": []})
    revision = CanonProposalRevision(
        id=9,
        book_id=1,
        base_canon_version=1,
        base_content_hash="content",
        base_locks_hash="locks",
        target_section="characters",
        instruction="补全定盘",
        allowed_sections=["characters", "chapter_summaries"],
        locked_sections=["world_rules"],
        changed_sections={
            "characters": [{"name": "林烬", "description": "档案修复师", "skills": ["纸页封印"]}],
            "chapter_summaries": [
                {"title": "魂穿将门，死而复生", "content": "现代医生醒来后自救。"}
            ],
        },
        blocked_sections=[{"section": "world_rules", "reason": "已锁定"}],
        summary="已补全人物和前三章摘要。",
        risks=[],
    )

    page = render_trusted_state_page(book, canon, [], proposal_revision=revision)

    assert "AI 已生成定盘补全预览" in page
    assert "尚未写入可信设定提案" in page
    assert "本次将更新" in page
    assert "应用到定盘提案" in page
    assert "放弃这次预览" in page
    assert "定盘信息不足" not in page
    assert "预览待确认" in page
    assert "先审核左侧 AI 修订预览" in page
    assert 'href="#canon-revision-job"' in page
    assert "魂穿将门，死而复生" in page
    assert "技能：纸页封印" in page
    assert "skills" not in page
    assert "内容：现代医生醒来后自救" not in page
    assert "description：" not in page


def test_trusted_state_page_renders_running_ai_revision_with_auto_refresh() -> None:
    book = Book(
        id=1,
        title="长夜图书馆",
        genre="奇幻",
        audience="连载读者",
        status=BookStatus.DRAFT,
    )
    canon = Canon(id=1, book_id=1, version=1, content={"characters": []})
    revision = CanonProposalRevision(
        id=9,
        book_id=1,
        base_canon_version=1,
        base_content_hash="content",
        base_locks_hash="locks",
        target_section="characters",
        instruction="补全人物设定",
        status=CanonProposalRevisionStatus.RUNNING,
    )

    page = render_trusted_state_page(book, canon, [], proposal_revision=revision)

    assert "AI 正在补全定盘" in page
    assert "自动刷新中" in page
    assert "setTimeout(() => window.location.reload(), 3000)" in page
    assert "#canon-revision-job" in page
    assert 'action="/canon-proposal-apply"' not in page


def test_trusted_state_page_hides_ai_form_for_locked_section() -> None:
    book = Book(
        id=1,
        title="长夜图书馆",
        genre="奇幻",
        audience="连载读者",
        status=BookStatus.DRAFT,
        constraints={"_canon_proposal": {"section_locks": {"world_rules": True}}},
    )
    canon = Canon(
        id=1,
        book_id=1,
        version=1,
        content={"world_rules": [{"name": "雾墙规则"}], "characters": [{"name": "林烬"}]},
    )

    page = render_trusted_state_page(book, canon, [])
    world_section = page.split('id="world"', 1)[1].split('id="characters"', 1)[0]

    assert "此部分已锁定" in world_section
    assert 'name="target_section" value="world_rules"' not in world_section
    assert 'name="target_section" value="characters"' in page


def test_trusted_state_page_hides_revision_forms_when_globally_locked() -> None:
    book = Book(
        id=1,
        title="长夜图书馆",
        genre="奇幻",
        audience="连载读者",
        status=BookStatus.CANON_LOCKED,
    )
    canon = Canon(
        id=1,
        book_id=1,
        version=1,
        content={"world_rules": [{"name": "雾墙规则"}]},
    )

    page = render_trusted_state_page(book, canon, [])

    assert 'action="/canon-proposal-revise"' not in page
    assert 'action="/canon-proposal-lock"' not in page
    assert "让 AI 修改这部分" not in page


def test_trusted_state_page_hides_regenerate_form_when_globally_locked() -> None:
    book = Book(
        id=1,
        title="长夜图书馆",
        genre="奇幻",
        audience="连载读者",
        status=BookStatus.CANON_LOCKED,
    )
    canon = Canon(id=1, book_id=1, version=1, content={"characters": []})
    revision = CanonProposalRevision(
        id=9,
        book_id=1,
        base_canon_version=1,
        base_content_hash="content",
        base_locks_hash="locks",
        target_section="characters",
        instruction="主角改成外冷内热",
        allowed_sections=["characters"],
        changed_sections={"characters": [{"name": "林烬"}]},
        summary="已调整人物。",
    )

    page = render_trusted_state_page(book, canon, [], proposal_revision=revision)

    assert "修订预览" in page
    assert 'action="/canon-proposal-apply"' not in page
    assert 'action="/canon-proposal-discard"' not in page
    assert 'action="/canon-proposal-revise"' not in page
    assert "重新生成预览" not in page


def test_trusted_state_page_renders_full_untruncated_section_values() -> None:
    long_detail = "这是一条很长的世界规则说明，用来确认可信设定详情不会被截断。" * 4
    book = Book(
        id=1,
        title="长夜图书馆",
        genre="奇幻",
        audience="连载读者",
        status=BookStatus.DRAFT,
    )
    canon = Canon(
        id=1,
        book_id=1,
        version=1,
        content={
            "world_rules": [
                {"name": f"规则 {index}", "detail": long_detail} for index in range(1, 8)
            ],
        },
    )

    page = render_trusted_state_page(book, canon, [])

    assert "规则 7" in page
    assert long_detail in page


def test_trusted_state_page_translates_nested_change_keys() -> None:
    book = Book(
        id=1,
        title="长夜图书馆",
        genre="奇幻",
        audience="连载读者",
        status=BookStatus.PRODUCING,
    )
    canon = Canon(
        id=1,
        book_id=1,
        version=1,
        content={
            "state_history": [{"chapter": 1, "changes": [{"target": "莉拉", "change": "离村"}]}],
        },
    )

    page = render_trusted_state_page(book, canon, [])

    assert "内容：离村" in page
    assert "change：" not in page


def test_trusted_state_page_keeps_unlocked_foundation_as_review_gate() -> None:
    book = Book(
        id=1,
        title="长夜图书馆",
        genre="奇幻连载",
        audience="成长冒险读者",
        status=BookStatus.DRAFT,
    )
    canon = Canon(
        id=1,
        book_id=1,
        version=1,
        content={"world_rules": [{"name": "雾墙规则", "detail": "幽谷边界危险。"}]},
    )

    page = render_trusted_state_page(book, canon, [])

    assert "可信设定提案 · 待确认" in page
    assert "定盘信息不足" in page
    assert "让 AI 补全定盘" in page
    assert 'action="/canon-proposal-revise"' in page
    assert 'name="target_section" value="characters"' in page
    assert "需要先补齐什么" in page
    assert "还不能进入下一步" in page
    assert "当前进度：<strong>需要补全定盘</strong>" in page
    assert "强制关卡" not in page
    assert "锁定可信设定并开始生产" not in page
    assert 'action="/lock-canon"' not in page
    assert 'action="/canon-proposal-lock"' not in page
    assert "锁定此部分" not in page
    assert "解除锁定" not in page
    assert "让 AI 修改这部分" not in page
    assert "查看全部分区" not in page
    assert "定盘信息不足，先补全" not in page
    assert "放弃设定，重开一本" in page
    assert page.index("还不能进入下一步") < page.index("审计风险")
    assert "锁定可信设定并开始生产" not in page
    assert "<strong>定盘</strong><em>当前阶段</em>" in page
    assert "规划本章" not in page


def test_trusted_state_page_keeps_lock_action_for_complete_unlocked_foundation() -> None:
    book = Book(
        id=1,
        title="长夜图书馆",
        genre="奇幻连载",
        audience="成长冒险读者",
        status=BookStatus.DRAFT,
    )
    canon = Canon(
        id=1,
        book_id=1,
        version=1,
        content={
            "world_rules": [{"name": "雾墙规则"}],
            "characters": [{"name": "莉拉"}, {"name": "罗文"}, {"name": "伊芙"}],
            "factions": [{"name": "旧石会"}],
            "locations": [{"name": "幽谷"}, {"name": "雾门"}],
            "relationships": [
                {"from": "莉拉", "to": "罗文", "detail": "同盟"},
                {"from": "莉拉", "to": "旧石会", "detail": "被追踪"},
            ],
            "foreshadowing": ["石符", "雾门", "旧王朝"],
            "chapter_summaries": [
                {"chapter": 1, "title": "召唤"},
                {"chapter": 2, "title": "雾门"},
                {"chapter": 3, "title": "旧石会"},
            ],
        },
    )

    page = render_trusted_state_page(book, canon, [])

    assert "下一步：开始章节生产" in page
    assert "当前进度：<strong>可以进入章节生产</strong>" in page
    assert "点击下一步后" in page
    assert "当前设定会成为后续章节的写作依据" in page
    assert "强制关卡" not in page
    assert "尚未锁定" not in page
    right_panel = page.split('class="right-panel audit-risk-panel"', 1)[1]
    assert "事实源" not in right_panel
    assert "锁定前确认" not in page
    assert 'action="/lock-canon"' in page
    assert 'name="book_id" value="1"' in page
    assert "下一步" in page
    assert "锁定可信设定并开始生产" not in page
    assert "让 AI 修复" not in page
    assert "返回修改" not in page
    assert "放弃设定，重开一本" in page
    assert 'action="/abandon-book"' in page
    assert 'name="book_id" value="1"' in page
    assert "定盘信息不足" not in page


def test_trusted_state_page_uses_current_book_audit_risks() -> None:
    book = Book(
        id=1,
        title="长夜图书馆",
        genre="奇幻连载",
        audience="成长冒险读者",
        status=BookStatus.PRODUCING,
    )
    canon = Canon(id=1, book_id=1, version=1, content={})
    chapters = [
        Chapter(
            id=7,
            book_id=1,
            number=1,
            title="离开的召唤",
            status=ChapterStatus.AWAITING_REVIEW,
            audit_report={
                "risk_level": "medium",
                "issues": [
                    {
                        "severity": "medium",
                        "title": "钩子偏弱",
                        "detail": "结尾问题不足以推动下一章。",
                        "resolved": False,
                    }
                ],
            },
        )
    ]

    page = render_trusted_state_page(book, canon, chapters)

    assert "中 1" in page
    assert "钩子偏弱" in page
    assert "第 01 章《离开的召唤》" in page
    assert "世界规则边界模糊" not in page
