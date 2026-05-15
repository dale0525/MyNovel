# MyNovel React Core Workbench Migration Design

日期：2026-05-15

相关资料：

- 既有 UI/UX 方向：[MyNovel 聚焦创作台 UI/UX 重设计](2026-05-15-focused-creative-workbench-uiux-design.md)
- 模型配置规格：[MyNovel AI API Setup Validation Design](2026-05-15-ai-api-setup-validation-design.md)
- Vite 官方文档：https://vite.dev/guide/
- Vite 后端集成文档：https://vite.dev/guide/backend-integration
- shadcn/ui Vite 安装文档：https://ui.shadcn.com/docs/installation/vite

## 1. 背景

MyNovel 当前用 Python 标准库 HTTP 服务直接渲染 HTML。这个方式已经支撑了开书、定盘、章节生产、章节审核、可信设定和质量中心等流程，但继续做复杂 UI 会遇到三个问题：

- 服务端字符串拼接页面不适合继续扩展高质量交互、异步状态、表单校验和组件复用。
- 页面视觉和交互密度受限，难以稳定达到“聚焦创作台”的目标。
- 模型配置、长任务等待、章节审核等场景需要更清晰的客户端状态管理。

本次迁移将一次性切换到 React 前端。旧服务端页面不再作为用户入口，也不保留一套可并行访问的旧 UI。

## 2. 决策

采用 `React + TypeScript + Vite + shadcn/ui + Tailwind CSS` 重建所有用户主界面。

Python 后端继续负责：

- 本地 HTTP 服务启动。
- SQLite 数据读写。
- AI 调用和后台任务。
- JSON API。
- React SPA 静态文件托管。

React 前端负责：

- 所有用户可见页面。
- 表单、异步状态、错误状态和成功反馈。
- 路由、页面布局、设计系统和 shadcn/ui 组件组合。
- 未配置模型时的唯一启动界面。

旧的 Python HTML render functions 在迁移完成后不再挂到用户路由。能删除的直接删除；短期确实仍被测试或内部逻辑引用的，必须迁移为 API presenter、纯数据 formatter 或测试夹具，不能作为浏览器用户入口存在。

## 3. 目标

- 启动应用且未配置模型时，`/` 只显示模型配置界面，不显示主导航、项目列表或其他主界面元素。
- 模型配置页支持填写 `base url`、`api key`、`model name`、`embedding model name`、`rerank model name`。
- embedding 和 rerank 默认勾选“使用和 LLM 相同的 base url / api key”，取消后可填写独立 base url / api key。
- 保存时自动测试 LLM、embedding、rerank 三个模型；任意一个失败都不能保存和继续。
- 再次保存时只测试上次未通过或本次改动影响到的模型。
- 用 React SPA 覆盖首页、开书、蓝图选择、可信设定、项目工作台、章节生成、章节审核、质量中心、导入、更新和设置等用户主流程。
- 后端 API 明确、可测试，前端不依赖服务端 HTML 字符串。
- 保持桌面入口和 PyInstaller 打包路径可用。

## 4. 非目标

- 不引入 Electron、Tauri 或远程多用户服务。
- 不重写数据库模型、AI 工作流和后台任务调度。
- 不把主交互改成聊天机器人。
- 不保留旧服务端页面作为备用 UI。
- 不做 SSR。前端是浏览器端 SPA，后端只托管静态资源和 API。

## 5. 产品体验

### 5.1 首次启动 / 未配置模型

未配置完整且验证通过的模型时，应用入口是全屏配置界面：

- 页面只有品牌区、配置表单、测试进度、错误说明和保存按钮。
- 不出现侧边栏、项目列表、创作工作台、更新入口或其他分散注意力的元素。
- 表单按三组展示：LLM、Embedding、Rerank。
- Embedding 和 Rerank 的“使用 LLM 相同连接信息”开关默认开启；开启时隐藏或禁用对应 base url / api key 输入，仍保留模型名输入。
- 保存按钮文案体现真实动作，例如 `测试并保存配置`。
- 测试中显示三个模型的独立状态：`等待测试`、`测试中`、`通过`、`失败`。
- 失败时明确说明是哪一个模型失败、失败原因和下一步要改什么。

### 5.2 已配置后的主工作台

已配置且验证通过后，`/` 进入“聚焦创作台”：

- 左侧是稳定导航：工作台、开书、项目、章节、可信设定、质量、设置。
- 主区只突出当前下一步行动。
- 右侧或底部显示最近 AI 结果、运行状态和待用户确认事项。
- 长任务页面显示真实阶段，不伪造百分比。

### 5.3 章节生产和审核

章节页面必须从“正文优先”调整为“结果汇报优先”：

- AI 完成了什么。
- 关键状态变化。
- AI 已自动修复。
- 还需要用户决定什么。
- 正文阅读和手工编辑。

这些区块先由现有数据和 run trace 尽量生成；缺失的结构化信息以清晰空态表达，不用假数据填充。

## 6. 视觉系统

采用 shadcn/ui 作为组件基础，但不直接使用默认黑白后台风格。

设计方向延续“聚焦创作台”：

- 低刺激暖灰绿背景，避免纯白高反差。
- 主强调色使用深鼠尾草绿，过程态使用低饱和琥珀，风险态使用克制砖红。
- 卡片更紧致，减少松散大空白。
- 使用 Lucide 图标或 SVG，不用 emoji 充当功能图标。
- 动效只用于页面进入、状态切换和异步反馈，遵守 `prefers-reduced-motion`。
- 字体方案在前端设计系统中统一定义，避免浏览器默认字体堆栈成为主要视觉语言。

shadcn/ui 组件按需落到 `frontend/src/components/ui/`，业务组件放在 `frontend/src/components/`，设计 tokens 放在 `frontend/src/styles/` 或 Tailwind theme 中。

## 7. 前端架构

新增 `frontend/`：

- `frontend/package.json`：前端脚本和依赖。
- `frontend/index.html`：Vite SPA 入口。
- `frontend/src/main.tsx`：React 挂载入口。
- `frontend/src/app/`：路由、全局 providers、应用壳。
- `frontend/src/pages/`：页面级组件。
- `frontend/src/features/`：模型配置、开书、工作台、章节、可信设定、质量中心等业务模块。
- `frontend/src/components/ui/`：shadcn/ui 生成组件。
- `frontend/src/components/layout/`：应用壳、导航、状态条。
- `frontend/src/lib/api.ts`：fetch wrapper、错误处理、请求取消。
- `frontend/src/lib/types.ts`：API DTO 类型。
- `frontend/src/styles/`：全局 CSS、tokens、字体和动效。

路由由前端统一管理。推荐使用 `react-router`，因为本项目是本地单页应用，路由需求清晰，不需要更重的全栈路由框架。

核心前端路由：

- `/setup`：模型配置。
- `/`：工作台。未配置时由客户端和服务端双重保护，只显示 setup。
- `/books/new`：开书。
- `/books/import`：导入。
- `/books/:bookId`：项目工作台。
- `/books/:bookId/state`：可信设定。
- `/books/:bookId/quality`：质量中心。
- `/blueprints/:blueprintId`：蓝图结果和选择。
- `/chapters/:chapterId`：章节生产和审核。
- `/updates`：更新。
- `/settings/provider`：模型配置。

## 8. 后端架构

`dev_server.py` 已接近 1000 行，迁移时必须拆分，避免继续膨胀。

目标模块边界：

- `dev_server.py`：命令行入口、server 启动、handler 组装。
- `api_server.py` 或 `api_routes.py`：JSON API dispatch。
- `static_server.py`：SPA 静态文件、MIME 类型、index fallback。
- `api_serializers.py`：SQLModel 对象到 JSON DTO。
- `api_errors.py`：统一错误响应。
- 现有 workflow/server 模块继续承载业务动作，例如 provider config、chapter、canon proposal、update。

请求规则：

- `/api/*` 只返回 JSON。
- `/health` 继续返回 JSON，方便健康检查。
- `/assets/*` 和 Vite build 产物由静态服务器返回。
- 非 API 的 GET 路由 fallback 到 `index.html`，让 React Router 接管。
- 旧 POST 表单路由迁移为 `/api/*` JSON POST，不再返回 HTML 或 303 跳转作为用户交互机制。
- Markdown、JSON、纯文本导出接口可保留文件响应，但路径应纳入 API 或 download 命名空间，例如 `/api/books/:id/export.md`。

## 9. API 范围

迁移必须覆盖现有用户流程，不只迁移首页。

模型配置：

- `GET /api/provider-config`
- `POST /api/provider-config/validate`
- `POST /api/provider-config`

工作台和项目：

- `GET /api/app/bootstrap`
- `GET /api/books`
- `GET /api/books/:bookId`
- `POST /api/books/import`
- `POST /api/books/:bookId/word-targets`
- `POST /api/books/:bookId/abandon`

开书和蓝图：

- `POST /api/open-book`
- `POST /api/blueprints/:blueprintId/retry`
- `POST /api/blueprints/:blueprintId/revise`
- `POST /api/blueprints/:blueprintId/accept`
- `GET /api/blueprints/:blueprintId`

可信设定和定盘：

- `GET /api/books/:bookId/state`
- `POST /api/books/:bookId/state/lock`
- canon proposal 相关的现有 POST 行为迁移到 `/api/books/:bookId/canon-proposals/*`。

章节：

- `GET /api/chapters/:chapterId`
- `POST /api/chapters/:chapterId/run`
- `POST /api/books/:bookId/chapters/run-batch`
- `POST /api/chapters/:chapterId/request-revision`
- `POST /api/chapters/:chapterId/repair`
- `POST /api/chapters/:chapterId/edit`
- `POST /api/chapters/:chapterId/approve`
- `GET /api/chapters/:chapterId/export.txt`

质量中心：

- `GET /api/books/:bookId/quality`
- `POST /api/books/:bookId/quality/style-assets`
- `POST /api/books/:bookId/quality/deconstruct-reference`
- `POST /api/books/:bookId/quality/snapshots`

更新：

- `GET /api/updates`
- `POST /api/updates/check`
- `POST /api/updates/stage`

所有 API 错误统一返回：

```json
{
  "error": {
    "code": "provider_validation_failed",
    "message": "模型连接测试未全部通过。",
    "details": {}
  }
}
```

## 10. 模型配置验证数据流

前端提交完整配置草稿，后端负责判断哪些模型需要重新测试：

- 若模型类型上次已通过，且影响该模型的 base url、api key、model name 未变化，则复用通过结果。
- 若模型类型上次失败，必须重新测试。
- 若用户修改影响该模型的字段，必须重新测试。
- LLM、embedding、rerank 三个结果全部通过后，后端保存 provider config 和 validation metadata。
- 任意失败时，后端保存 validation metadata 但不保存新的 provider config。

前端不自行判定“可保存”，只展示后端报告并阻止用户误解状态。

## 11. 打包与开发环境

继续用 pixi 作为项目开发入口，不要求系统级安装工具。

需要新增：

- Node.js 和前端包管理器依赖由 pixi 管理。
- `pixi run frontend-dev`：启动 Vite dev server。
- `pixi run frontend-build`：构建 React SPA。
- `pixi run frontend-typecheck`：TypeScript 检查。
- `pixi run frontend-lint`：前端 lint。
- `pixi run dev`：可选择先构建前端 dist 再启动 Python，或在开发模式下让 Python 指向 Vite dev server。

生产和桌面打包：

- Vite build 输出到 `frontend/dist`。
- `pyproject.toml` 的 package data 纳入前端 dist。
- `desktop-build` 继续使用 PyInstaller，但必须 collect React dist。
- 若 dist 不存在，生产模式启动应给出明确错误；开发模式可以提示运行 `pixi run frontend-build` 或启用 Vite dev server。

## 12. 测试策略

Python：

- 保留现有 workflow 和 repository 测试。
- 将 HTML 断言迁移为 API JSON 断言。
- 增加 SPA fallback、静态资源、API 错误格式测试。
- 增加未配置模型时 `/` 只返回 React shell 且 bootstrap 指向 setup 的测试。

前端：

- TypeScript typecheck。
- Vite production build。
- 组件和 API client 单元测试。
- 浏览器 smoke test，至少覆盖：
  - 未配置模型访问 `/` 只看到模型配置。
  - 模型配置三模型测试失败时不能继续。
  - 已配置后进入工作台。
  - 章节页能展示运行中、失败、待审核、已通过等状态。

验收前必须运行：

- `pixi run test`
- `pixi run lint`
- `pixi run frontend-typecheck`
- `pixi run frontend-build`
- 浏览器 smoke test 命令

## 13. 迁移顺序

1. 建立 `frontend/`、Vite、React、Tailwind、shadcn/ui 和 pixi 任务。
2. 拆分 Python server：静态托管、SPA fallback、JSON API 基础、统一错误。
3. 先迁移模型配置页，并确保未配置模型时无其他主界面元素。
4. 迁移工作台、开书、蓝图、项目页和可信设定主链路。
5. 迁移章节生成、章节审核、修订、批准、导出。
6. 迁移质量中心、导入和更新页。
7. 删除或下线旧 HTML 用户路由和 render functions。
8. 调整打包、测试和文档。

每一步完成时，用户可访问入口仍只有 React，不允许阶段性把旧页面暴露给用户使用。

## 14. 验收标准

- 新项目中不存在可作为用户入口访问的旧服务端 HTML 页面。
- 所有主用户路径都由 React SPA 渲染。
- 未配置模型时，启动页只有模型配置体验。
- 模型配置保存严格受三模型验证结果 gate 控制。
- 再保存只测试失败或受改动影响的模型。
- Python 后端 API 与静态托管职责清晰，`dev_server.py` 低于 1000 行并持续可维护。
- 前端有统一设计 tokens、组件结构和错误/加载/空态模式。
- PyInstaller 桌面包可以包含并启动 React SPA。
- Python 和前端验证命令全部通过。
