# AI 辅助/主导长篇小说写作工具调研

数据采集日期：2026-05-10。仓库指标来自 GitHub API 与 GitHub 搜索，README/文档来自各项目公开仓库。Star、issue、活跃度会变化，本文仅记录本次调研快照。

## 结论摘要

AI 长篇小说工具已经从“补全文本”明显分化为三条路线：

1. **端到端生产管线**：用 Agent、结构化状态、审稿循环把一本书拆成可执行流程。代表项目是 InkOS、AI_NovelGenerator、Long-Novel-GPT、AI-Novel-Writing-Assistant、NovelForge、autonovel。
2. **写作工作台/前端生态**：提供角色卡、世界书、记忆、模型连接、编辑器与交互体验，但不一定负责完整生产链。代表项目是 SillyTavern、KoboldAI/KoboldCpp、Arboris、Ai-Novel、Narratium。
3. **长文本生成研究方法**：解决超长输出、递归规划、长期/短期记忆、评估与训练。代表项目是 RecurrentGPT、WriteHERE、LongWriter。

对我们的项目最有参考价值的方向不是“一键生成整本书”的宣传口号，而是以下工程共识：

- **用结构化状态托住长篇一致性**：角色、地点、物资、关系、伏笔、章节摘要、情绪弧线应是可校验的数据，而不是仅靠一段 prompt。
- **先编译上下文再写作**：把作者意图、当前焦点、章节目标、检索结果、规则栈和风格指纹编译成可审阅输入，避免全部混在一次模型调用里。
- **章节管线必须有审计和修订闭环**：Draft -> extract state -> audit -> revise -> accept，比单次生成更可控。
- **RAG 是辅助检索，不应成为唯一事实源**：事实源应是数据库/结构化文件，向量库只做召回。
- **人类审核点要前置在关键决策**：书名方向、世界观、角色阵容、卷纲、章节发布、重大冲突等位置需要 gate；普通小修可自动化。
- **要记录每次生成的 trace 和成本**：长篇项目会出现上下文污染、模型幻觉、风格漂移、成本失控，必须可追踪和可回滚。

## 仓库快照

| 项目 | Stars | 主要语言 | License | 最近 pushed | 定位 |
|---|---:|---|---|---|---|
| [SillyTavern/SillyTavern](https://github.com/SillyTavern/SillyTavern) | 27,316 | JavaScript | AGPL-3.0 | 2026-05-05 | 高度可控的 LLM 前端，角色/世界书/提示词生态强 |
| [LostRuins/koboldcpp](https://github.com/LostRuins/koboldcpp) | 10,475 | C++ | AGPL-3.0 | 2026-05-09 | GGUF 本地模型运行器，内置 KoboldAI Lite 写作 UI |
| [Narcooo/inkos](https://github.com/Narcooo/inkos) | 5,942 | TypeScript | AGPL-3.0 | 2026-05-09 | 自主小说写作 Agent，写、审、改与人工门控 |
| [YILING0013/AI_NovelGenerator](https://github.com/YILING0013/AI_NovelGenerator) | 4,809 | Python | AGPL-3.0 | 2026-04-27 | 多章节长篇小说生成器，带 GUI、向量检索和一致性检查 |
| [KoboldAI/KoboldAI-Client](https://github.com/KoboldAI/KoboldAI-Client) | 3,891 | Python | AGPL-3.0 | 2025-01-16 | 经典 AI 写作/冒险前端，Memory、Author's Note、World Info |
| [THUDM/LongWriter](https://github.com/THUDM/LongWriter) | 1,860 | Python | Apache-2.0 | 2025-06-24 | 10,000+ 词长输出模型、数据、评估和 AgentWrite 管线 |
| [t59688/arboris-novel](https://github.com/t59688/arboris-novel) | 1,387 | Python | 未声明 | 2026-02-25 | 面向创作者的写作辅助 Web 工具 |
| [conorbronsdon/avoid-ai-writing](https://github.com/conorbronsdon/avoid-ai-writing) | 1,418 | Skill | MIT | 2026-05-08 | 检测/改写 AI 味的可复用 agent skill |
| [MaoXiaoYuZ/Long-Novel-GPT](https://github.com/MaoXiaoYuZ/Long-Novel-GPT) | 1,104 | Python | 未声明 | 2025-11-05 | 基于 LLM + RAG 的长篇小说 Agent |
| [mind-protocol/terminal-velocity](https://github.com/mind-protocol/terminal-velocity) | 1,099 | Python | 未声明 | 2025-01-06 | 10 个 AI agents 自主完成 100k 词小说的公开案例 |
| [aiwaves-cn/RecurrentGPT](https://github.com/aiwaves-cn/RecurrentGPT) | 1,002 | Python | GPL-3.0 | 2024-05-15 | 用自然语言模拟 RNN/LSTM 的超长文本生成研究 |
| [worldwonderer/oh-story-claudecode](https://github.com/worldwonderer/oh-story-claudecode) | 946 | JavaScript | MIT | 2026-05-10 | 网文创作 skill 包，扫榜、拆文、写作、去 AI 味 |
| [principia-ai/WriteHERE](https://github.com/principia-ai/WriteHERE) | 915 | Python | 未声明 | 2025-11-24 | 异构递归规划的长文写作框架 |
| [NousResearch/autonovel](https://github.com/NousResearch/autonovel) | 893 | Python | 未声明 | 2026-03-20 | 从 seed 到小说、修订、排版、插图、有声书的自动管线 |
| [HappyFox001/AI-Chat](https://github.com/HappyFox001/AI-Chat) | 810 | TypeScript | 未声明 | 2026-03-30 | Narratium.ai，角色、世界、对话与分支记忆平台，已停止开发 |
| [RhythmicWave/NovelForge](https://github.com/RhythmicWave/NovelForge) | 795 | Python | AGPL-3.0 | 2026-04-26 | Schema-first 卡片式长篇创作引擎 |
| [inliver233/Ai-Novel](https://github.com/inliver233/Ai-Novel) | 627 | Python | MIT | 2026-04-19 | 小说创作与项目管理 Web demo |
| [datacrystals/AIStoryWriter](https://github.com/datacrystals/AIStoryWriter) | 237 | Python | AGPL-3.0 | 2025-11-24 | CLI 小说生成器，支持 Ollama/Google/OpenRouter |
| [jackaduma/Recurrent-LLM](https://github.com/jackaduma/Recurrent-LLM) | 205 | Python | MIT | 2023-09-28 | RecurrentGPT 的开源/本地 LLM 实现 |
| [ydsgangge-ux/dramatica-flow](https://github.com/ydsgangge-ux/dramatica-flow) | 135 | Python | 未声明 | 2026-04-29 | 基于 Dramatica 理论的因果链/多线叙事管线 |

## 重点项目分析

### 1. InkOS

来源：[GitHub](https://github.com/Narcooo/inkos)

**方法论**：把每章写作拆成多 Agent 接力：Radar 扫趋势、Planner 生成本章意图、Composer 编译上下文和规则栈、Architect 规划章节结构、Writer 写正文、Observer 抽取事实、Reflector 写 JSON delta、Normalizer 做字数治理、Auditor 做连续性审计、Reviser 修订。若审计不通过，会自动进入“修订 -> 再审计”循环。

**记忆设计**：维护 7 类真相文件/结构化状态：世界状态、资源账本、未闭合伏笔、章节摘要、支线进度、情感弧线、角色交互矩阵。新版把权威状态迁移到 JSON + Zod schema，Markdown 只是人类可读投影；Node 22+ 下启用 SQLite 时序记忆库。

**工具栈**：TypeScript、Node、CLI/TUI/Studio、SQLite、Zod、OpenAI-compatible providers、OpenClaw skill、多模型路由。

**优点**：

- 对长篇小说最核心的问题建模完整：状态、伏笔、角色信息边界、审计、修订、回滚、成本、日志。
- “输入治理”很强，能把作者意图、当前焦点、规则栈、章节上下文拆开审阅。
- 同时提供 CLI、TUI、Web Studio、Agent skill，适合人类和外部 Agent 调用。

**缺点/风险**：

- AGPL-3.0，若复用代码需要谨慎处理开源义务。
- 功能范围非常大，早期项目照搬会导致复杂度过高。
- README 有较强产品宣传色彩，实测效果仍需自己跑样例验证。

**对我们的参考价值**：最值得借鉴的是“结构化真相文件 + 输入编译 trace + 审计修订闭环”。MVP 可以先做 Writer/Observer/Auditor/Reviser 四段，再逐步加入 Radar 和 Studio。

### 2. AI_NovelGenerator

来源：[GitHub](https://github.com/YILING0013/AI_NovelGenerator)

**方法论**：按“生成设定 -> 生成目录 -> 生成章节草稿 -> 定稿章节 -> 更新全局摘要/角色状态/向量库/剧情要点 -> 可选一致性审校”推进。强调多阶段生成、状态追踪、伏笔管理、语义检索和知识库参考。

**工具栈**：Python GUI、LLM adapter、embedding adapter、vectorstore、consistency checker，支持 OpenAI/DeepSeek/Ollama 等 OpenAI-compatible 服务。

**优点**：

- 流程直接、可理解，适合作为 MVP 参考。
- 把“定稿”作为状态更新触发点，避免每次草稿都污染长期记忆。
- 对国内用户友好，配置项贴近网文长篇创作。

**缺点/风险**：

- README 显示项目曾一度暂停维护，2026-03 后重构仍处早期。
- GUI 和核心逻辑可能耦合较重，扩展到多人协作/自动流水线需要改造。
- AGPL-3.0。

**对我们的参考价值**：章节定稿后再更新摘要、角色状态和向量库，这个边界非常重要。MVP 应明确 draft、accepted chapter、canonical state 的生命周期。

### 3. Long-Novel-GPT

来源：[GitHub](https://github.com/MaoXiaoYuZ/Long-Novel-GPT)

**方法论**：基于 LLM + RAG，自上而下采用“大纲 -> 章节 -> 正文”扩写。支持导入现有小说、拆书提取剧情人物关系和剧情纲要、根据用户意见检索相关正文片段/纲要并修改，再同步更新剧情纲要。README 还给出“50 章并行生成 -> 扩剧情 -> 扩正文”的百万字生产思路。

**工具栈**：Python、Docker、Gradio UI、本地或云端 OpenAI-compatible 模型、线程并发、Prompt 库、费用显示。

**优点**：

- 目标非常聚焦：长篇/网文的一键或半自动生成。
- RAG + 已有小说导入 + 局部改写是实际作者很需要的能力。
- Docker 部署降低上手成本。

**缺点/风险**：

- 未声明 license，不宜直接复用代码。
- 多线程扩写能提升速度，但如果状态更新和冲突检测不够强，容易放大前后矛盾。
- “百万字”更多是生成能力表达，质量与一致性仍要靠审计体系补足。

**对我们的参考价值**：可以借鉴“导入已有小说 -> 拆书 -> 结构化纲要 -> 局部重写 -> 同步更新纲要”的续写流程，但不要把并发生成放到第一阶段。

### 4. AI-Novel-Writing-Assistant

来源：[GitHub](https://github.com/ExplosiveCoderflome/AI-Novel-Writing-Assistant)

**方法论**：定位为“AI 导演式长篇小说生产系统”。从一句灵感进入自动导演，生成整本方向、标题组、书级 framing、故事宏观规划、角色准备、卷战略、节奏拆章和章节执行；Creative Hub 统一对话、规划、工具调用、审批节点、状态卡片和中断恢复。

**工具栈**：TypeScript monorepo、React + Vite、Express + Prisma、LangChain/LangGraph、Plate editor、Qdrant、SQLite、桌面版 release。

**优点**：

- 产品化程度高，贴近“新手从灵感到完整小说”的真实路径。
- LangGraph/Tool Registry/Runtime/审批节点是 AI-native 产品工程的好样例。
- 世界观、角色、拆书、知识库、写法资产有较清晰的产品联动。

**缺点/风险**：

- 未声明 license，不能直接复用代码。
- 仓库体量大，包含备份/临时文件痕迹，工程整洁度需要谨慎评估。
- 目标过全，MVP 容易被“自动导演 + 全链路产品”拖大。

**对我们的参考价值**：值得学习产品结构：Creative Hub、审批节点、状态卡片、中断恢复、写法资产。但初期只应选“自动导演开书”和“章节执行”两条最短路径。

### 5. NovelForge

来源：[GitHub](https://github.com/RhythmicWave/NovelForge)

**方法论**：Schema-first 卡片创作，把世界观、角色、章节、审核结果等内容抽象为可校验卡片；用 @DSL 精准引用项目数据；通过知识图谱和动态信息维护一致性；代码式 workflow 与 Workflow Agent 让用户能把常用创作流程自动化。

**工具栈**：Python/FastAPI 后端、卡片 schema、relation graph、workflow agent、prompt workshop、项目初始化/拆书等内置 workflow。

**优点**：

- Schema-first 很适合长篇项目，能降低 LLM 输出结构漂移。
- 卡片模式适合创作者逐步沉淀设定、桥段、人物、伏笔和审核结果。
- @DSL 引用比“全文塞 prompt”更可控。

**缺点/风险**：

- AGPL-3.0。
- 卡片系统对普通用户可能有学习成本。
- 如果 schema 设计过细，早期会降低创作流畅度。

**对我们的参考价值**：可借鉴“卡片 + schema + @引用 + 审核结果卡片”的内容组织方式。我们的 MVP 可以先定义少量核心 schema：Book、Character、Location、PlotHook、Chapter、ChapterAudit。

### 6. autonovel

来源：[GitHub](https://github.com/NousResearch/autonovel)

**方法论**：从 seed concept 自动生成世界、角色、大纲、voice、canon，再逐章写草稿；每章用评分门槛保留/重试；修订阶段使用 adversarial edit、Elo 章节比较、4 persona reader panel、Claude Opus 双人格 review，最后输出 PDF、ePub、封面、插图和有声书脚本。README 称第一本小说 19 章 79,456 词，PIPELINE 记录另一次 75k 词/23 章/5 轮修订经验。

**工具栈**：Python、uv、Anthropic API、27 个脚本、LaTeX、ePub、ElevenLabs、图像生成、git 分支/提交作为实验保留与回滚机制。

**优点**：

- 是少见的“从创意到出版物”的完整自动化工程样例。
- 评估/修订体系强，强调 modify-evaluate-keep/discard。
- 把 voice discovery、canon、anti-slop、anti-pattern 单独建模，值得学习。

**缺点/风险**：

- 更像研究/实验管线，不是稳定产品。
- 对 Claude/外部 API、排版、图像、音频依赖较多，成本和失败点多。
- 未声明 license。

**对我们的参考价值**：非常适合作为离线批处理 pipeline 参考，尤其是“评分门槛 + commit/rollback + reader panel + revision brief”。

### 7. WriteHERE

来源：[GitHub](https://github.com/principia-ai/WriteHERE)

**方法论**：Heterogeneous Recursive Planning。核心不是固定流程，而是递归拆分写作任务，并在 retrieval、reasoning、composition 三类任务之间动态切换。支持 story/report 两种模式，并用可视化界面展示任务图、状态和任务类型。

**工具栈**：Python、Flask backend、React frontend、OpenAI/Anthropic、SerpAPI、递归 planner/executor/memory/cache/task graph。

**优点**：

- 对“写作不是固定流水线”这个问题有研究价值。
- 实时任务图有助于解释 Agent 为什么这么写。
- MIT badge 显示 MIT，但 GitHub API 本次未识别 license，复用前需核对仓库 license 文件。

**缺点/风险**：

- 泛长文框架，小说领域的角色、伏笔、情绪线等专门状态不如 InkOS/NovelForge 细。
- 研究框架到产品还有距离。

**对我们的参考价值**：适合借鉴任务图和异构任务拆分，不建议初期完全采用开放式 planner；先用确定管线，局部引入递归拆分。

### 8. RecurrentGPT / Recurrent-LLM

来源：[RecurrentGPT](https://github.com/aiwaves-cn/RecurrentGPT)、[Recurrent-LLM](https://github.com/jackaduma/Recurrent-LLM)

**方法论**：用自然语言模拟 LSTM/RNN。每个时间步输入上一段文本和下一段计划，生成新段落、下一段计划，并更新短期记忆；长期记忆保存所有历史段落摘要，可用语义搜索召回。

**工具栈**：Python、Prompt engineering、OpenAI API、Gradio demo、语义搜索；Recurrent-LLM 支持开源/本地 LLM。

**优点**：

- 对“任意长文本如何滚动生成”给出了简洁模型。
- 长期/短期记忆分层是长篇小说系统的基础思想。
- 允许人类选择下一步计划，适合人机共写。

**缺点/风险**：

- 偏段落级生成，缺少完整小说工程里的角色/伏笔/审计/修订系统。
- 代码活跃度较低。

**对我们的参考价值**：可作为章节内生成算法：用 short memory 维持近期场景，用 long memory/summary 召回远期事实，但需要叠加结构化状态和审稿。

### 9. LongWriter

来源：[GitHub](https://github.com/THUDM/LongWriter)

**方法论**：不是小说应用，而是长输出能力研究。提供 LongWriter 模型、LongWriter-6k 数据、LongBench-Write/LongWrite-Ruler 评估，以及 AgentWrite 数据构造管线。重点证明模型可生成 10,000+ 词长文本，并评估长度与质量。

**工具栈**：Transformers、vLLM、Hugging Face datasets/models、训练/评估脚本、GPT-4o judge。

**优点**：

- 对“单次长输出”能力有直接参考。
- 提供评估框架，不只看 token 数，也看质量。
- Apache-2.0，复用友好。

**缺点/风险**：

- 单次长输出不等于长篇小说一致性。
- 训练/部署门槛高，不适合作为应用 MVP 起点。

**对我们的参考价值**：不要把所有章节都压进一次超长输出。可以在未来引入长输出模型生成“章节级长草稿”或做评估基线，但长篇一致性仍需状态系统。

### 10. SillyTavern

来源：[GitHub](https://github.com/SillyTavern/SillyTavern)

**方法论**：强控制型 LLM 前端。虽然更偏角色扮演/聊天，但它在角色卡、WorldInfo/lorebook、提示词控制、扩展生态、多后端接入、移动端体验方面非常成熟。

**工具栈**：Node/JavaScript、OpenAI/OpenRouter/Claude/Mistral/Kobold/Ooba/Tabby/NovelAI 等多后端、WorldInfo、Visual Novel Mode、图像生成、TTS、extensions。

**优点**：

- 社区和生态极强，真实用户使用场景多。
- 模型接入、提示词设置、世界书和角色卡体验值得研究。
- 本地安装，不提供 hosted 服务，隐私定位明确。

**缺点/风险**：

- 不是长篇小说生产系统，缺少章节级 project/canon/revision pipeline。
- AGPL-3.0。
- 功能非常多，学习曲线陡。

**对我们的参考价值**：可学习模型 provider 抽象、角色/世界书交互、prompt preset 管理、扩展机制。不要照搬聊天产品形态。

### 11. KoboldAI / KoboldCpp

来源：[KoboldAI-Client](https://github.com/KoboldAI/KoboldAI-Client)、[koboldcpp](https://github.com/LostRuins/koboldcpp)

**方法论**：KoboldAI 是经典 AI-assisted writing/browser frontend，提供 Memory、Author's Note、World Info、Save/Load、Adventure/Novel/Chatbot 模式。KoboldCpp 则把 llama.cpp/GGUF 本地推理和 KoboldAI Lite UI 打包成易运行工具。

**工具栈**：KoboldAI-Client 使用 Python；KoboldCpp 使用 C++/llama.cpp/GGUF，支持 CPU/GPU、OpenAI/Ollama/Kobold API、RAG TextDB、图像、TTS、STT、多模态等。

**优点**：

- 本地模型体验强，适合隐私敏感创作者。
- Memory、Author's Note、World Info 是早期 AI 写作产品的经典三件套。
- KoboldCpp 单文件/零安装策略很适合普通用户。

**缺点/风险**：

- 更偏模型运行和互动前端，不解决完整长篇生产管理。
- 本地小模型质量不稳定，需要模型选择和参数调优。
- AGPL-3.0。

**对我们的参考价值**：可把 OpenAI-compatible、本地 Kobold/Ollama 后端作为第一批 provider；同时借鉴 Memory/Author's Note/World Info 但升级为结构化项目状态。

### 12. Arboris

来源：[GitHub](https://github.com/t59688/arboris-novel)

**方法论**：定位为“能记住你的世界、理解角色、随故事推进的写作伙伴”，不是自动生成器。核心是设定管理、大纲与故事线、写作辅助、多版本对比。

**工具栈**：Python/FastAPI 后端、Docker、SQLite/MySQL、LLM API、角色/地点/派系模型、foreshadowing、review、writer、analytics 等服务。

**优点**：

- 产品目标克制，强调辅助创作者而非完全替代。
- 多版本对比符合写作者真实决策过程。
- 默认 SQLite，Docker 上手简单。

**缺点/风险**：

- 未声明 license。
- 自动化生产链不如 InkOS/Long-Novel-GPT 完整。

**对我们的参考价值**：如果我们的目标偏“AI 辅助写作伙伴”，Arboris 的设定管理、多版本对比、低门槛部署值得借鉴。

### 13. Ai-Novel

来源：[GitHub](https://github.com/inliver233/Ai-Novel)

**方法论**：小说创作与项目管理 Web demo。支持项目向导、世界观/风格/约束配置、大纲/章节 SSE 流式生成、章节分析、批量生成、世界书、角色术语、story memories、open loops、结构化记忆变更集、RAG、Graph、Prompt Presets。

**工具栈**：React + Vite、FastAPI、Docker Compose、Postgres/Redis/rq_worker、Chroma/pgvector、OpenAI/Anthropic/Gemini、多用户与 OIDC。

**优点**：

- 工程化完整：后台任务、可观测性、脱敏、导入导出、多用户。
- Story memories、open loops、结构化记忆变更集很贴近长篇需求。
- MIT。

**缺点/风险**：

- README 标注为 demo，生产成熟度需要验证。
- 系统组件较多，部署复杂度高于单机工具。

**对我们的参考价值**：适合参考项目管理、后台任务、prompt preset、结构化记忆 apply/rollback 的实现方向。

### 14. AIStoryWriter

来源：[GitHub](https://github.com/datacrystals/AIStoryWriter)

**方法论**：CLI 生成中长篇故事，支持为初始大纲、章节大纲、正文等不同阶段配置不同模型。README 自评目前擅长生成较长故事、角色一致性和有趣大纲，仍需改进重复短语、章节衔接、节奏和速度。

**工具栈**：Python CLI、Ollama、Google、OpenRouter、自动下载本地模型、prompt/config 可改。

**优点**：

- 结构简单，适合快速实验模型组合。
- 支持本地模型，适合低成本/隐私实验。
- README 对缺点比较诚实。

**缺点/风险**：

- 功能较轻，缺少强审计与状态管理。
- AGPL-3.0。

**对我们的参考价值**：可作为命令行 batch MVP 的简化参考，尤其是“不同阶段不同模型”的配置格式。

### 15. oh-story-claudecode

来源：[GitHub](https://github.com/worldwonderer/oh-story-claudecode)

**方法论**：不是独立应用，而是 Claude Code/OpenClaw skill 包。覆盖环境部署、长篇/短篇扫榜、拆文学习、写作、精修定稿、去 AI 味、审查、封面。内置 5 个专业 Agent：story-architect、character-designer、narrative-writer、consistency-checker、story-researcher。

**工具栈**：Skills、Claude Code/OpenClaw、browser CDP、hooks、references 写作技法库、Agent 分工。

**优点**：

- 把“市场扫榜 -> 拆文 -> 创作 -> 去 AI 味”串成网文创作方法论。
- 适合和 coding agent/CLI workflow 集成。
- MIT。

**缺点/风险**：

- 强依赖外部 agent 环境，不是独立产品。
- 扫榜/拆文涉及平台数据抓取与版权边界，产品化需谨慎。

**对我们的参考价值**：可借鉴 skill 化能力：把“拆文”“审查”“去 AI 味”“封面生成”做成可插拔工具，而不是硬塞进主流程。

### 16. Terminal Velocity

来源：[GitHub](https://github.com/mind-protocol/terminal-velocity)

**方法论**：10 个 specialized AI agents 自主协作完成约 100,000 词小说。角色包括 SpecificationsAgent、ProductionAgent、ManagementAgent、EvaluationAgent、ResearcherAgent、DeduplicationAgent、IntegrationAgent、WritingAgent 等。

**工具栈**：Python、KinOS、GitHub 公开文档、直播记录、完整 manuscript。

**优点**：

- 是“多 Agent 能否真正完成一部长篇”的公开案例。
- 文件结构清楚地区分 story、characters、world_building。
- 透明记录创作过程，便于复盘。

**缺点/风险**：

- 更像作品/实验记录，不是可复用小说写作框架。
- 未声明 license。
- “100% AI-generated”不等于质量足够商业化。

**对我们的参考价值**：可参考 Agent 职责划分和公开创作日志，但工程上应优先做可复用状态与管线。

### 17. Dramatica-Flow

来源：[GitHub](https://github.com/ydsgangge-ux/dramatica-flow)

**方法论**：把小说抽象为因果链、伏笔生命周期、情感弧线、角色关系网络、多线叙事、信息边界和三层审计机制。强调“让 AI 理解故事，而不是只会写文字”。

**工具栈**：Python、FastAPI、DeepSeek/Ollama、5 层 Agent 管线、世界状态快照、真相文件。

**优点**：

- 叙事理论建模很强，尤其是因果链和信息边界。
- 多线叙事/全局时间轴对长篇有实际价值。

**缺点/风险**：

- star 较低，成熟度和社区验证不足。
- 未声明 license。

**对我们的参考价值**：可以把“事件必须回答 cause/event/effect/decision”做成审计规则，防止章节变成松散事件堆。

### 18. Narratium / AI-Chat

来源：[GitHub](https://github.com/HappyFox001/AI-Chat)

**方法论**：角色、世界、会话与分支记忆平台，兼容 SillyTavern 角色卡和 lore，支持视觉化 session tracing/branching、插件系统、长时对话和本地部署。README 明确项目已停止开发。

**工具栈**：TypeScript、OpenAI/OpenRouter/Ollama/LM Studio、React Flow、桌面构建、插件系统。

**优点**：

- 世界/角色/会话记忆的 UI 方向值得看。
- 分支会话适合探索剧情可能性。

**缺点/风险**：

- 已停止开发。
- 更偏角色扮演和互动世界，不是小说生产链。

**对我们的参考价值**：可借鉴分支记忆/剧情分叉探索，但不应依赖其架构。

## 方法论横向比较

| 方法 | 代表项目 | 解决的问题 | 局限 |
|---|---|---|---|
| 大纲 -> 章节 -> 正文 | Long-Novel-GPT、AI_NovelGenerator | 把长篇拆成层级结构，易上手 | 容易过度依赖最初大纲，后期漂移后修复困难 |
| 真相文件/结构化状态 | InkOS、NovelForge、Dramatica-Flow、Ai-Novel | 防止角色、物资、伏笔、信息边界混乱 | schema 设计难，太细会降低创作速度 |
| RAG/向量检索 | Long-Novel-GPT、AI_NovelGenerator、AI-Novel-Writing-Assistant、Ai-Novel | 长篇上下文召回，支持导入资料/拆书 | 向量召回会漏，不能替代权威事实源 |
| 递归规划 | WriteHERE | 根据任务动态拆解，而非固定 pipeline | 输出难预测，产品层需要更多解释和控制 |
| Recurrent memory | RecurrentGPT | 任意长文本滚动生成，维护短/长期记忆 | 小说工程状态不足，需要结合审计 |
| 多 Agent 协作 | InkOS、autonovel、Terminal Velocity、oh-story | 专业分工，能做规划/写作/评审/修订 | Agent 过多会增加成本和失败点 |
| 评估/修订循环 | autonovel、InkOS、avoid-ai-writing | 提升质量，减少 AI 味和逻辑问题 | 评估本身也可能幻觉，需要结构化规则补充 |
| 市场扫榜/拆文 | oh-story、AI-Novel-Writing-Assistant | 面向网文商业化，提取题材和节奏 | 可能涉及版权/平台抓取边界 |
| 单次超长输出 | LongWriter | 提高章节级长文本生成能力 | 不解决全书一致性和长期状态 |
| 强前端/角色生态 | SillyTavern、KoboldAI、Narratium | 模型连接、角色卡、lorebook、互动体验成熟 | 不等于完整小说项目管理 |

## 工具栈观察

### LLM provider

多数项目都走 OpenAI-compatible 抽象，兼容 OpenAI、Anthropic、Gemini、OpenRouter、DeepSeek、Ollama、LM Studio、本地 Kobold/Ooba/Tabby 等。建议我们第一版就设计 provider interface，不要把某个模型硬编码进业务。

### 存储

- **SQLite**：适合本地单机、桌面应用、MVP，InkOS、Arboris、AI-Novel-Writing-Assistant 都有类似思路。
- **Postgres + Redis**：适合 Web 多用户和后台任务，Ai-Novel 使用这类工程化组合。
- **Markdown/JSON 文件**：适合人类审阅和 git 版本管理。InkOS 的“JSON 为权威、Markdown 为投影”是较好的折中。
- **Vector DB**：Chroma、pgvector、Qdrant、项目内 vectorstore。建议作为 derived index，可重建，不作为唯一事实源。

### 前端形态

- CLI：适合 batch pipeline、agent 调用、可测试。
- TUI：适合本地创作者长时间工作。
- Web Studio：适合可视化编辑、审阅、配置、状态面板。
- 桌面版：降低部署门槛，但会增加发布复杂度。

建议我们的顺序：CLI/core library -> local Web Studio -> desktop package。

### 工作流编排

项目里常见三种方案：

- 固定脚本 pipeline：autonovel、AIStoryWriter，简单可靠。
- Agent/tool registry：InkOS、AI-Novel-Writing-Assistant，灵活但复杂。
- Workflow DSL/code workflow：NovelForge，适合高级用户复用流程。

建议 MVP 用固定 pipeline，并把每步输入输出做成结构化文件/API，为后续 workflow agent 留接口。

### 质量控制

高价值控制点包括：

- 章节前：上下文选择 trace、规则栈、字数预算、章节目标。
- 章节中：分场景/分段生成、局部记忆、风格约束。
- 章节后：事实抽取、状态 delta、schema 校验、连续性审计、AI 味审计、修订 brief。
- 定稿后：摘要、角色状态、伏笔状态、资源账本、向量索引更新。

## 对 MyNovel 的建议架构

### 产品定位

建议初期定位为：**本地优先、长篇项目管理清晰、AI 可主导但人类可审核的小说生产工作台**。

不要第一版就承诺“全自动生成百万字”。更现实的承诺是：从一个创意开始，能稳定生成一卷/若干章，并且每章的事实状态可追踪、可审计、可回滚。

### MVP 核心循环

1. `create book`：输入题材、目标读者、核心卖点、风格参考、禁区。
2. `plan book`：生成 premise、world bible、character set、volume outline。
3. `plan chapter`：根据大纲和当前状态生成章节目标、must-keep、must-avoid、上下文选择 trace。
4. `draft chapter`：生成章节草稿，记录模型、参数、prompt、成本。
5. `extract state`：从草稿抽取角色、地点、物资、关系、伏笔、时间线、情绪变化。
6. `audit chapter`：对照 canonical state 做连续性、因果、信息边界、AI 味、字数和风格审计。
7. `revise chapter`：根据 audit brief 自动修订；严重问题进入人工 gate。
8. `accept chapter`：定稿后才更新 canonical state 和向量索引。

### 建议的数据模型

第一版只需要少量强 schema：

- `Book`: title, genre, audience, premise, style, constraints
- `Character`: identity, desire, fear, relationships, knowledge_scope, current_state
- `Location`: rules, factions, resources, current_state
- `PlotHook`: setup_chapter, promise, status, due_hint, resolution
- `ChapterPlan`: chapter_no, goal, beats, required_context, forbidden_moves
- `ChapterDraft`: text, model, prompt_version, cost, generated_at
- `ChapterAudit`: issues, severity, evidence, suggested_fix
- `StateDelta`: proposed changes after a draft, accepted only after validation

### 技术选择建议

结合仓库现状为空、AGENTS 要求使用 pixi，建议：

- Core 使用 Python + pixi 起步：方便 LLM、RAG、评估、脚本化 pipeline。
- 状态存储先用 SQLite + JSON schema/Pydantic；Markdown 作为投影导出。
- Provider 走 OpenAI-compatible abstraction，预留 Anthropic/Gemini/Ollama。
- 向量检索先用 Chroma 或 SQLite-friendly 方案，后续再接 Qdrant/pgvector。
- CLI 先行，Web Studio 后置。CLI 的每步都输出 JSON，方便未来 agent/workflow 调用。

如果项目更偏桌面/Web 产品，可以第二阶段引入 TypeScript 前端；不要一开始就同时做 monorepo、桌面、workflow agent、多人系统。

### 不建议第一阶段做的事

- 不要先做复杂市场扫榜和平台抓取，版权和稳定性问题较多。
- 不要把多 Agent 数量堆到十几个；先做少数可验证角色。
- 不要把 RAG 当作事实数据库。
- 不要追求一次生成 10,000+ 词；先保证章节级状态闭环。
- 不要让用户只能通过聊天控制项目；长篇创作需要可编辑资产和明确状态面板。

## 可直接复用/借鉴的设计清单

| 设计 | 借鉴来源 | 建议优先级 |
|---|---|---|
| 结构化真相文件 + Markdown 投影 | InkOS | P0 |
| 章节定稿后才更新长期记忆 | AI_NovelGenerator | P0 |
| plan/compose/draft/audit/revise 原子命令 | InkOS | P0 |
| 状态 delta + schema 校验 + apply/rollback | InkOS、Ai-Novel | P0 |
| 章节审计结果作为可保存资产 | NovelForge | P1 |
| 多模型路由：规划/写作/审计不同模型 | InkOS、AIStoryWriter | P1 |
| 风格指纹/写法资产 | InkOS、AI-Novel-Writing-Assistant | P1 |
| reader panel / 多 persona 审稿 | autonovel | P1 |
| 递归任务图可视化 | WriteHERE | P2 |
| 市场扫榜/拆文 workflow | oh-story、AI-Novel-Writing-Assistant | P2 |
| 单次超长输出模型评估 | LongWriter | P2 |

## 推荐下一步

1. 建立项目骨架：pixi、Python package、CLI、SQLite、Pydantic schema、docs。
2. 先实现最短闭环：create book -> plan chapter -> draft -> audit -> accept。
3. 准备 2-3 个固定测试小说项目，用同一套 pipeline 比较模型和 prompt 版本。
4. 每章保存完整 trace，包括输入上下文、模型参数、生成成本、状态 delta、审计结果。
5. 等 CLI 闭环稳定后，再做 Web Studio：状态面板、章节编辑、审计查看、角色/伏笔卡片。

## 来源链接

- [Narcooo/inkos](https://github.com/Narcooo/inkos)
- [YILING0013/AI_NovelGenerator](https://github.com/YILING0013/AI_NovelGenerator)
- [MaoXiaoYuZ/Long-Novel-GPT](https://github.com/MaoXiaoYuZ/Long-Novel-GPT)
- [ExplosiveCoderflome/AI-Novel-Writing-Assistant](https://github.com/ExplosiveCoderflome/AI-Novel-Writing-Assistant)
- [RhythmicWave/NovelForge](https://github.com/RhythmicWave/NovelForge)
- [NousResearch/autonovel](https://github.com/NousResearch/autonovel)
- [principia-ai/WriteHERE](https://github.com/principia-ai/WriteHERE)
- [aiwaves-cn/RecurrentGPT](https://github.com/aiwaves-cn/RecurrentGPT)
- [jackaduma/Recurrent-LLM](https://github.com/jackaduma/Recurrent-LLM)
- [THUDM/LongWriter](https://github.com/THUDM/LongWriter)
- [SillyTavern/SillyTavern](https://github.com/SillyTavern/SillyTavern)
- [KoboldAI/KoboldAI-Client](https://github.com/KoboldAI/KoboldAI-Client)
- [LostRuins/koboldcpp](https://github.com/LostRuins/koboldcpp)
- [t59688/arboris-novel](https://github.com/t59688/arboris-novel)
- [inliver233/Ai-Novel](https://github.com/inliver233/Ai-Novel)
- [datacrystals/AIStoryWriter](https://github.com/datacrystals/AIStoryWriter)
- [worldwonderer/oh-story-claudecode](https://github.com/worldwonderer/oh-story-claudecode)
- [conorbronsdon/avoid-ai-writing](https://github.com/conorbronsdon/avoid-ai-writing)
- [mind-protocol/terminal-velocity](https://github.com/mind-protocol/terminal-velocity)
- [ydsgangge-ux/dramatica-flow](https://github.com/ydsgangge-ux/dramatica-flow)
- [HappyFox001/AI-Chat](https://github.com/HappyFox001/AI-Chat)
