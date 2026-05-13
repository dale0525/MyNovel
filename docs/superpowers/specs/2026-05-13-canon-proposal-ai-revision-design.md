# MyNovel 可信设定提案 AI 修订设计

日期：2026-05-13

相关资料：

- 产品计划：[MyNovel 产品计划与产品心态设计](2026-05-10-product-plan-design.md)
- 设计图：[开书定盘 / Canon 锁定关卡](../../assets/mynovel-flow-06-canon-lock-gate.png)

## 1. 背景

当前 `可信设定提案 · 待确认` 页面已经展示世界规则、人物、势力、地点、关系、伏笔账本、章节摘要和变化历史，但这些入口只具备视觉卡片效果，不能进入详情，也不能修改。

产品方向要求 MyNovel 保持“全 AI 化 + 人工审核”：作者不应该手动维护复杂设定字段，而应该用一两句自然语言提出修改意见，由 AI 完成一致性修订，作者负责审核、应用和锁定。

## 2. 目标

- 让设定分区可点击查看完整内容。
- 在全局 canon 未锁定前，允许用户对任意分区提出自然语言修改意见。
- AI 可以联动修改其他未锁定分区。
- 每个分区可以独立锁定和解锁。
- 已锁定分区只能作为约束上下文，AI 不得修改。
- AI 修订必须先进入预览，由用户确认后才应用到提案。
- 全局锁定后，整份可信设定成为生产线事实源，不再走自由修订入口。

## 3. 非目标

- 不做重型字段编辑器。
- 不做复杂提案版本树或分支管理。
- 不做锁定后直接改 canon 的自由入口。
- 不在本阶段实现逐字段 diff 可视化。
- 不做长期修订版本树；但修订预览必须服务端持久化，保证应用时不可被前端篡改。

## 4. 核心概念

### 4.1 设定分区

第一阶段用固定 section registry 管理分区，未知分区一律拒绝：

| Canon key | URL anchor | 中文标签 | 可 AI 修订 | 默认值 | 说明 |
| --- | --- | --- | --- | --- | --- |
| `world_rules` | `world` | 世界规则 | 是 | `[]` | 兼容现有“世界观”入口。 |
| `characters` | `characters` | 人物 | 是 | `[]` | 主角、配角、NPC。 |
| `factions` | `factions` | 势力 | 是 | `[]` | 现有开书流程需要补默认空数组。 |
| `locations` | `locations` | 地点 | 是 | `[]` | 城市、区域、地标。 |
| `relationships` | `relationships` | 关系 | 是 | `[]` | 人物、势力、地点之间的关系。 |
| `foreshadowing` | `foreshadowing` | 伏笔账本 | 是 | `[]` | 伏笔、线索、回收计划。 |
| `chapter_summaries` | `chapter-summaries` | 章节摘要 | 是 | `[]` | 前 10 章节奏和摘要。 |
| `state_history` | `state-history` | 变化历史 | 否 | `[]` | 只读展示已应用修订摘要。 |

服务端返回分区页时使用 registry 中的 URL anchor，而不是直接把 Canon key 当作锚点。

### 4.2 分区锁

每个分区都有独立锁定状态：

- 未锁定：AI 可以修改。
- 已锁定：AI 只能读取，不能修改。

分区锁是可逆的。用户可以显式解锁某个分区，然后再次让 AI 修订。解锁动作需要在 UI 上明确触发，避免误改。

### 4.3 全局锁定

全局“锁定可信设定并开始生产”之后，书籍状态进入 `CANON_LOCKED`。此后当前页面以只读为主，后续状态变化只能通过章节审核流程写入新 canon 版本。

### 4.4 提案与事实源生命周期

现有实现会在开书方案确认后创建 `Canon(version=1)`。在 `BookStatus.DRAFT` 阶段，这份 `Canon.content` 是“可信设定提案正文”，还不是生产事实源；章节生产已有状态门禁，必须等全局锁定后才能消费。

为了避免污染后续 canon、导出和上下文编译，`Canon.content` 不保存任何内部提案元数据。分区锁、最近修订摘要和待应用预览都放在 `Book.constraints` 或专门的预览记录中。

全局锁定时，服务端执行转换：

- 校验 book 仍为 `DRAFT` 且存在提案正文。
- 用 section registry 规范化 `Canon.content`，未知内部键不进入事实源。
- 清除 `Book.constraints["_canon_proposal"]` 中的草稿锁和最近预览状态。
- 将该书所有 `pending` 的 `CanonProposalRevision` 标记为 `stale`。
- 记录一条锁定轨迹，说明提案成为 canon v1 事实源。
- 将 book 状态改为 `CANON_LOCKED`。

## 5. 用户体验

### 5.1 分区总览

开书定盘页的分区卡片从静态卡片变成入口：

- 点击卡片进入该分区详情。
- 卡片显示条目数、锁定状态和最近修改状态。
- 卡片右上角提供锁定/解锁操作。

已锁定分区用清晰的锁图标和状态文案表示。未锁定分区显示“可由 AI 修订”。

### 5.2 分区详情

详情区域展示完整条目，而不是只截断前几条。每个条目以普通作者能理解的中文标签展示，不暴露原始 JSON key。

详情区包含：

- 分区标题和锁定状态。
- 当前内容列表。
- 最近一次 AI 修订摘要。
- “让 AI 修改这部分”的输入框。

如果分区已锁定，输入框不可提交，并提示用户先解锁。

### 5.3 AI 修订输入

用户输入自然语言意见，例如：

- “主角不要这么冷，改成外冷内热，并和旧王朝有一点血缘牵连。”
- “世界观里魔法代价太轻，改成每次使用都会损耗记忆。”
- “势力关系太散，把旧石会和王室遗民绑得更紧。”

提交时，系统传给 AI：

- 当前完整可信设定提案。
- 当前目标分区。
- 用户意见。
- 分区锁定状态。
- 已锁定分区的不可修改约束。
- 输出 JSON schema 要求。

### 5.4 修订预览

AI 返回后不直接覆盖提案，而是展示修订预览：

- 将修改哪些分区。
- 每个分区的修改摘要。
- 修改后的内容预览。
- 因锁定而未修改的分区。
- 与用户意见相关的冲突或风险。

用户可以选择：

- 应用到提案。
- 重新生成。
- 放弃。

### 5.5 应用修订

用户点击“应用到提案”后，系统只更新未锁定分区。即使 AI 响应包含已锁定分区，服务端也必须原子拒绝本次应用，并显示违规分区；不能静默剔除部分修改后继续应用。

应用成功后：

- 当前 canon 提案内容更新。
- `state_history` 增加一条“开书提案修订”记录。
- 页面回到对应分区详情。
- 全局状态仍然是 `DRAFT`，不会进入生产线。

`state_history` 不能出现在 AI 的 `changed_sections` 中。它是系统审计记录，由服务端在修订成功应用后追加，不受 AI 修订分区锁控制。

## 6. 数据设计

沿用当前 `Canon.content` 作为提案正文，但不把提案元数据写入 `Canon.content`。分区锁和最近修订摘要存入 `Book.constraints["_canon_proposal"]`：

```json
{
  "_canon_proposal": {
    "section_locks": {
      "characters": false,
      "chapter_summaries": false,
      "factions": false,
      "foreshadowing": false,
      "locations": false,
      "relationships": false,
      "world_rules": true,
      "state_history": true
    },
    "last_revision": {
      "target_section": "characters",
      "instruction": "主角改成外冷内热",
      "changed_sections": ["characters", "relationships", "foreshadowing"],
      "blocked_sections": ["world_rules"],
      "summary": "已调整主角性格，并增加相关关系和伏笔。",
      "updated_at": "2026-05-13T12:00:00+00:00"
    }
  }
}
```

`section_locks` 必须包含 registry 中所有分区。缺失时按默认值补齐：可修订分区默认为 `false`，只读分区默认为 `true`。未知 section 一律拒绝。

修订预览新增服务端持久化记录 `CanonProposalRevision`：

| 字段 | 说明 |
| --- | --- |
| `id` | 预览 ID，应用时只提交这个 ID。 |
| `book_id` | 所属书籍。 |
| `base_canon_version` | 生成预览时的 canon version。 |
| `base_content_hash` | 生成预览时的规范化 `Canon.content` hash。 |
| `base_locks_hash` | 生成预览时的分区锁 hash。 |
| `target_section` | 用户正在修改的分区。 |
| `instruction` | 用户自然语言意见。 |
| `allowed_sections` | 生成时允许 AI 修改的分区集合。 |
| `locked_sections` | 生成时锁定的分区集合。 |
| `changed_sections` | AI 返回的整分区替换内容。 |
| `blocked_sections` | 因锁定或冲突未修改的分区说明。 |
| `summary` | AI 修订摘要。 |
| `risks` | 风险提示。 |
| `status` | `pending`、`applied`、`discarded`、`stale`。 |
| `created_at` / `applied_at` | 生命周期时间。 |

应用修订时，前端不回传 AI payload，只回传 `revision_preview_id`。服务端从数据库读取预览内容。

`state_history` 继续作为用户可见的变更历史，记录已应用修订，而不是记录每次预览。

## 7. 服务端流程

### 7.1 切换分区锁

新增 POST 行为：

- 输入：`book_id`、`section`、`locked`。
- 校验：book 必须存在，状态仍为 `DRAFT`，section 存在于 registry 且可修订。
- 效果：更新 `Book.constraints["_canon_proposal"]["section_locks"]`。
- 返回：重定向到 `/book/{book_id}/state#{anchor}`。

### 7.2 请求 AI 修订

新增 POST 行为：

- 输入：`book_id`、`target_section`、`revision_instruction`。
- 校验：book 为 `DRAFT`，目标分区存在且未锁定。
- 调用模型生成结构化修订。
- 校验 AI 输出只能包含允许修改的分区。
- 保存 `CanonProposalRevision(status="pending")`，包含 base content hash 和 base locks hash。
- 返回修订预览页面，只暴露 `revision_preview_id`。

如果模型不可用或输出无法解析，页面显示失败原因，并保留用户输入。

### 7.3 应用 AI 修订

新增 POST 行为：

- 输入：`book_id`、`revision_preview_id`。
- 重新加载当前 canon 和分区锁。
- 校验 book 当前仍为 `DRAFT`；否则拒绝应用，并将 pending 预览标记为 `stale`。
- 校验预览记录存在、属于该 book、状态为 `pending`。
- 校验当前 canon version、content hash、locks hash 与预览生成时一致；不一致则标记为 `stale`，要求重新生成。
- 再次校验 `changed_sections` 只包含当前未锁定且 registry 允许修订的分区。
- 原子替换 `changed_sections` 中的完整分区内容，并写入可见变更历史。
- 将预览状态改为 `applied`。
- 返回分区详情。

服务端不能只依赖前端隐藏字段判断锁定状态，必须以数据库中的当前锁为准。

## 8. AI 输出契约

AI 必须返回结构化 JSON：

```json
{
  "target_section": "characters",
  "changed_sections": {
    "characters": [],
    "relationships": [],
    "foreshadowing": []
  },
  "blocked_sections": [
    {
      "section": "world_rules",
      "reason": "世界规则已锁定，不能引入复活机制。"
    }
  ],
  "summary": "已按意见调整人物，并保持世界规则不变。",
  "risks": [
    "人物血缘牵连会影响第 3-5 章动机，需要后续章节计划同步关注。"
  ]
}
```

`changed_sections` 只能包含未锁定分区。已锁定分区如有相关影响，必须放入 `blocked_sections` 或 `risks`。

MVP 的合并策略是“整分区替换”：

- `changed_sections.characters` 如果存在，必须是修改后的完整人物数组，而不是 patch 或 append。
- 其他可修订分区同理，均以完整数组替换。
- 未出现在 `changed_sections` 的分区保持不变。
- 服务端按 section registry 校验每个值必须是数组。
- 人物改名、势力改名等引用同步由 AI 在同一次响应里联动更新相关未锁定分区。
- 条目级 patch、稳定条目 ID 和逐字段 diff 放到第二阶段。

## 9. 错误处理

- 目标分区已锁定：提示用户先解锁。
- AI 请求失败：保留输入，允许重试。
- AI 输出不是合法 JSON：提示“AI 返回格式异常”，不更新提案。
- AI 尝试修改已锁定分区：原子拒绝应用，并展示违规分区。
- 预览生成后内容或锁状态变化：标记预览过期，要求重新生成。
- 前端提交未知 section 或不属于当前 book 的预览 ID：拒绝请求。
- 当前书已全局锁定：隐藏自由修订入口，只读展示。
- 没有 canon 提案：提示先完成开书方案选择。

## 10. 测试策略

### 10.1 UI 测试

- 待确认页面的分区卡片可点击，并指向对应详情锚点。
- 每个分区显示锁定/解锁状态。
- 未锁定分区显示 AI 修订输入框。
- 已锁定分区隐藏或禁用 AI 修订入口。
- 修订预览展示 changed、blocked、risks 和操作按钮。

### 10.2 工作流测试

- `DRAFT` 状态下可以切换分区锁。
- `CANON_LOCKED` 状态下不能切换分区锁。
- AI 修订可更新多个未锁定分区。
- AI 修订包含已锁定分区时，应用原子失败且 canon 不变。
- 应用修订会写入 `state_history`。
- AI 输出解析失败时不修改 canon。
- 预览后锁状态变化，应用时标记 stale 且不修改 canon。
- 预览后 canon 内容变化，应用时标记 stale 且不修改 canon。
- 预览生成后执行全局锁定，再提交预览应用，必须失败且 canon 不变。
- 全局锁定时，该书所有 pending 预览都会标记 stale。
- 未知 section、缺失 section、不可修订 section 均被拒绝。
- 稀疏锁状态会补默认值，只读分区默认锁定。

### 10.3 回归测试

- 原有全局锁定流程仍可用。
- 章节审核写入 canon 的流程不受影响。
- 导出 JSON 时不会破坏已有 trusted_state 内容。
- 渲染详情时不暴露 proposal 内部元数据。
- 全局锁定时不会把 proposal metadata 写入 `Canon.content`。
- 章节生产上下文不包含 proposal metadata。
- 导出和导入不会泄漏 `_canon_proposal` 或待应用预览。

## 11. 分阶段实现

### 第一阶段

- 分区详情锚点和完整展示。
- 分区锁定/解锁。
- AI 修订请求和预览。
- 应用修订到未锁定分区。

### 第二阶段

- 更细的条目级修订入口。
- 更清晰的 before/after 差异展示。
- 最近多次修订记录。

### 第三阶段

- 提案版本树、回滚和对比。
- 锁定后受控变更申请。
