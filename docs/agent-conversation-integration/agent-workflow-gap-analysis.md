# AutoGEO 后台 Agent 工作流现状对比与优化方案

## 1. 目标

我们要实现的不是一个普通聊天框，而是一个可以自动调用 AutoGEO 内部能力的后台 Agent。

目标用户指令示例：

```text
帮我给小爱科技生成一篇智慧物流文章，发布到知乎
```

理想情况下，Agent 应该自动完成：

```text
识别用户意图
-> 读取/更新会话记忆
-> 确认项目
-> 确认主题/关键词
-> 确认发布平台
-> 查询当前用户的知乎授权账号
-> 生成文章
-> 质检
-> 创建发布任务
-> 按策略执行或等待确认
-> 返回进度和结果
```

本文档用于回答三个问题：

1. 这个完整流程在项目里目前有哪些基础已经实现？
2. 还有哪些环节没有实现或没有接到 Agent？
3. 代码应该如何优化，才能实现完整自动执行流程？

## 2. 目标工作流拆解

完整后台 Agent 工作流可以拆成 10 个环节。

```text
1. 对话入口
2. 用户身份确认
3. 会话记忆管理
4. 意图识别
5. 槽位抽取与补全
6. 权限和业务校验
7. 执行计划生成
8. 调用 AutoGEO 内部服务
9. 任务状态追踪
10. 结果返回与继续对话
```

下面逐项对比当前实现状态。

## 3. 当前代码现状对比

### 3.1 对话入口

目标：

```text
前端对话框 -> POST /api/conversation/message -> 后端 Agent
```

当前实现：

```text
backend/api/conversation.py
frontend/src/views/agent/AgentChat.vue
frontend/src/services/api/index.ts
frontend/src/router/index.ts
```

状态：已实现第一版。

当前能力：

- 后台页面有对话窗口。
- 前端可以调用 `POST /api/conversation/message`。
- 后端可以从登录态拿当前用户。
- 前端可以展示回复、追问、短期记忆。

不足：

- 还没有持久化会话。
- 刷新页面后前端消息历史会丢。
- 后端重启后短期记忆会丢。

结论：

```text
入口已搭好，但还只是原型级。
```

### 3.2 用户身份确认

目标：

```text
后台 Agent 必须使用当前登录用户 system_user_id
不能由前端传 system_user_id
```

当前实现：

```text
backend/api/conversation.py
current_user: User = Depends(get_current_active_user)
```

状态：已实现。

当前能力：

- 后台对话接口受 JWT 登录态保护。
- `system_user_id` 来自后端认证。

不足：

- 后续业务执行时，还需要所有项目、文章、账号查询继续按 `system_user_id` 过滤。
- 当前已有部分 API 例如 `/api/geo/articles`、`/api/auto-publish/tasks` 仍存在没有强制用户隔离或隔离不完整的风险，需要逐项收紧。

结论：

```text
入口身份安全是对的，但后续工具调用仍需统一权限过滤。
```

### 3.3 会话记忆管理

目标：

正式 Agent 需要两类记忆：

```text
message history：完整对话历史
slots：结构化任务状态
```

当前实现：

```text
backend/services/conversation_state_service.py
```

状态：实现了进程内短期 slots 记忆。

当前能力：

- 根据 `conversation_id` 保存 slots。
- 可以记住：
  - intent
  - topic
  - project_hint
  - platforms
  - quantity
  - publish_strategy
  - waiting_for
- 60 分钟过期。

不足：

- 没有保存完整 message history。
- 没有数据库持久化。
- 后端重启后丢失。
- 多进程部署时不共享。
- 无法给 LLM 提供完整上下文。

结论：

```text
当前记忆只能支持原型多轮追问，不足以支撑正式 Agent。
```

### 3.4 意图识别

目标：

Agent 应该识别：

```text
generate_article
generate_and_publish
publish_existing_article
query_task_status
confirm_task
cancel_task
set_default_project
unknown
```

当前实现：

```text
backend/services/conversation_orchestrator.py
```

状态：本地规则识别第一版。

当前能力：

- 可识别生成、发布、生成并发布、查询状态等基础意图。
- 可抽取部分平台，例如知乎、小红书、头条。
- 可抽取简单主题和项目线索。
- 已预留 `AUTOGEO_CONVERSATION_USE_LLM` 开关。
- 可复用现有 `backend/services/feishu_intent_parser.py` 的 GLM / DeepSeek 解析。

不足：

- 默认不接大模型。
- 本地规则无法理解复杂表达。
- 没有标准化 `IntentRecognizer` 模块。
- 意图类型还不够完整。
- 没有 confidence。
- 没有 missing_slots 标准输出。

结论：

```text
当前只适合 demo，不足以承担正式自动任务编排。
```

### 3.5 槽位抽取与补全

目标：

Agent 应该把对话转成结构化任务：

```json
{
  "intent": "generate_and_publish",
  "topic": "智慧物流",
  "project_id": 12,
  "platforms": ["zhihu"],
  "account_ids": [3],
  "quantity": 1,
  "publish_strategy": "review_first"
}
```

当前实现：

```text
conversation_orchestrator._merge_slots
conversation_orchestrator._extract_topic
conversation_orchestrator._extract_project_hint
conversation_orchestrator._extract_platforms
```

状态：基础实现。

当前能力：

- 能保存 topic、project_hint、platforms、quantity 等。
- 能在多轮对话中合并历史 slots。

不足：

- 还不能把 `project_hint` 解析成 `project_id`。
- 还不能把 `platforms` 解析成具体 `account_ids`。
- 还不能处理文章 ID、定时发布时间、多账号选择。
- slots 没有数据库持久化。
- 还没有标准 `missing_slots` 计算器。

结论：

```text
槽位记忆已起步，但离可执行任务参数还差项目解析和账号解析。
```

### 3.6 权限和业务校验

目标：

执行前必须校验：

```text
项目属于当前用户或用户是项目成员
文章属于当前用户可访问项目
账号属于当前用户
平台账号状态正常
质检通过才能发布
```

当前实现：

- `backend/api/conversation.py` 入口能拿当前用户。
- `backend/services/feishu_task_handler.py` 中发布账号查询已经按 `Account.user_id == system_user_id` 过滤。
- `backend/api/account.py` 部分接口已按当前用户过滤。
- `auto_publish_tasks` 有 `triggered_by_user_id` 字段。

不足：

- 后台 Agent 还没有统一的 `PolicyGuard`。
- `backend/api/auto_publish.py` 创建任务时直接按 `article_ids/account_ids` 查询，没有在接口层强制校验账号属于当前用户。
- `backend/api/geo.py` 的文章生成和文章列表也需要加强用户作用域。
- 项目权限模型需要统一使用 `ProjectMember` 或明确项目 owner。

结论：

```text
权限校验能力分散存在，但 Agent 执行链路还没有统一安全网。
```

### 3.7 执行计划生成

目标：

Agent 识别完整信息后，应生成执行计划：

```json
{
  "intent": "generate_and_publish",
  "steps": [
    "resolve_project",
    "prepare_keywords",
    "generate_article",
    "check_quality",
    "create_publish_task",
    "wait_confirmation",
    "execute_publish"
  ]
}
```

当前实现：

暂无独立 `TaskPlanner`。

当前能力：

- `conversation_orchestrator.py` 会返回 `need_clarification`、`accepted`、`confirm_required`。

不足：

- 没有可持久化执行计划。
- 没有步骤状态。
- 没有 plan -> executor 的清晰接口。

结论：

```text
执行计划模块尚未实现。
```

### 3.8 调用 AutoGEO 内部服务

目标：

Agent 应该调用通用执行器：

```text
AgentTaskExecutor
  -> KeywordService
  -> GeoArticleService
  -> check_quality
  -> AutoPublishTask
  -> execute_auto_publish_task
```

当前已有可复用能力：

#### 关键词蒸馏

```text
backend/services/keyword_service.py
backend/api/keywords.py
```

已有：

- `KeywordService.distill`
- `/api/keywords/distill`

#### 文章生成

```text
backend/services/geo_article_service.py
backend/api/geo.py
```

已有：

- `GeoArticleService.generate`
- `/api/geo/generate`

#### 质检

```text
backend/services/geo_article_service.py
backend/api/geo.py
```

已有：

- `GeoArticleService.check_quality`
- `/api/geo/articles/{article_id}/check-quality`

#### 自动发布任务

```text
backend/api/auto_publish.py
backend/database/models.py
```

已有：

- `AutoPublishTask`
- `AutoPublishRecord`
- `execute_auto_publish_task`
- `/api/auto-publish/tasks`

#### 飞书任务编排

```text
backend/services/feishu_task_handler.py
```

已有大量可复用逻辑：

- 准备关键词
- 调用蒸馏
- 质检
- 查用户授权账号
- 创建并执行发布任务

不足：

- 这些逻辑绑定在 `FeishuTaskHandler` 里，包含飞书回复逻辑，后台 Agent 不能直接干净复用。
- 自动发布创建逻辑在 API 文件 `backend/api/auto_publish.py` 中，不适合作为服务层被长期复用。
- 文章生成接口是异步后台任务，Agent 很难拿到生成完成后的 article_id，除非改造返回任务/文章 ID 或通过回调/轮询追踪。

结论：

```text
业务能力基本有，但没有抽成 Agent 可调用的统一服务层。
```

### 3.9 任务状态追踪

目标：

Agent 应该能返回：

```text
文章生成中
质检中
等待确认
发布中
发布成功
发布失败
```

当前实现：

- `GeoArticle.publish_status`
- `GeoArticle.quality_status`
- `AutoPublishTask.status`
- `AutoPublishRecord.status`
- WebSocket 已存在。

不足：

- Conversation session 没有关联 `article_id/task_id`。
- Agent 无法基于 conversation_id 追踪当前任务。
- 前端对话窗口还没有订阅任务进度。

结论：

```text
业务表有状态，但 Agent 还没有把状态串进对话。
```

### 3.10 结果返回与继续对话

目标：

Agent 应该把任务结果写回对话：

```text
文章已生成
质检未通过
发布任务等待确认
知乎发布成功
```

当前实现：

- 前端能展示一次 HTTP 响应。
- WebSocket 能广播一些系统日志和任务事件。

不足：

- Agent 还没有 conversation message 持久化。
- 任务完成后不会自动追加一条 assistant message。
- 外部平台回传还没接。

结论：

```text
还缺 Agent 任务结果回写机制。
```

## 4. 总体差距总结

| 环节 | 当前状态 | 差距 |
|---|---|---|
| 后台对话入口 | 已有 | 需要持久化会话 |
| 登录用户识别 | 已有 | 后续工具调用需继续过滤权限 |
| 短期记忆 | 有 slots 原型 | 缺 message history 和数据库 |
| 意图识别 | 本地规则 + LLM 开关 | 需要正式 IntentRecognizer |
| 槽位抽取 | 基础实现 | 缺 project_id、account_id、article_id 解析 |
| 项目解析 | 未接入 Agent | 需要 resolve_project |
| 账号解析 | 未接入 Agent | 需要 resolve_accounts |
| 关键词准备 | 现有能力在 FeishuTaskHandler/KeywordService | 需要抽成通用工具 |
| 文章生成 | 现有 GeoArticleService | 需要 Agent 调用并追踪 article_id |
| 质检 | 现有 GeoArticleService.check_quality | 需要串入 Agent 流程 |
| 创建发布任务 | 现有 AutoPublishTask | 需要服务层封装和权限校验 |
| 自动执行发布 | 现有 execute_auto_publish_task | 需要确认策略和 Agent 调用 |
| 任务进度 | 业务表已有 | 缺 conversation 关联和前端展示 |

## 5. 推荐代码优化方向

### 5.1 新建 Agent 服务目录

建议把当前散落的 Agent 逻辑重构到：

```text
backend/services/agent/
  __init__.py
  orchestrator.py
  memory.py
  intent_recognizer.py
  slot_extractor.py
  policy_guard.py
  task_planner.py
  task_executor.py
  tools.py
  schemas.py
```

当前文件迁移关系：

```text
conversation_orchestrator.py -> agent/orchestrator.py
conversation_state_service.py -> agent/memory.py
```

### 5.2 新增数据库模型

需要新增：

```text
ConversationSession
ConversationMessage
UserAgentPreference
```

建议表结构见：

```text
docs/agent-conversation-integration/backend-agent-design.md
```

关键字段：

```text
conversation_sessions.slots
conversation_sessions.status
conversation_sessions.current_intent
conversation_messages.role
conversation_messages.content
conversation_messages.metadata
```

### 5.3 抽出通用 AgentTaskExecutor

新增：

```text
backend/services/agent/task_executor.py
```

职责：

```text
execute_generate_article_plan
execute_generate_and_publish_plan
execute_query_status_plan
confirm_publish_task
```

它调用内部服务，不调用前端 API。

### 5.4 从 FeishuTaskHandler 抽通用逻辑

`FeishuTaskHandler` 里已经有很多好东西，但它混合了飞书回复。

建议抽出：

```text
prepare_keywords
resolve_publish_accounts
create_publish_task
run_quality_check
```

变成：

```text
backend/services/agent/tools.py
```

`FeishuTaskHandler` 后续只负责：

```text
飞书事件解析
飞书消息回复
调用同一个 Agent Orchestrator
```

### 5.5 把 AutoPublishTask 创建逻辑下沉为服务

当前创建发布任务主要在：

```text
backend/api/auto_publish.py
```

建议新增：

```text
backend/services/auto_publish_task_service.py
```

提供：

```python
create_auto_publish_task(
    db,
    system_user_id,
    article_ids,
    account_ids,
    exec_type,
    source,
    wait_confirmation=True,
)
```

API 和 Agent 都调用这个服务。

这样可以统一：

- 文章存在校验
- 账号存在校验
- 用户权限校验
- 任务记录创建
- 子任务记录创建
- 是否立即执行

### 5.6 文章生成服务需要返回可追踪 ID

当前 `/api/geo/generate` 是 BackgroundTasks，返回：

```text
生成任务已提交
```

Agent 需要更明确：

```json
{
  "article_id": 123,
  "status": "generating"
}
```

建议改造 `GeoArticleService.generate` 的调用方式：

- Agent 直接调用 service。
- 先创建 `GeoArticle` 占位记录。
- 立即拿到 `article_id`。
- 后续生成完成后更新文章。

如果当前 `generate` 已经会创建占位文章，则可以让它返回 `article_id`，不要只返回文本消息。

### 5.7 新增确认机制

新增意图：

```text
confirm_task
cancel_task
```

当 Agent 创建待确认发布任务后：

```json
{
  "status": "confirm_required",
  "task_id": 991,
  "reply": "文章已生成并通过质检，是否确认发布到知乎？"
}
```

用户说：

```text
确认发布
```

Agent 校验：

```text
task.triggered_by_user_id == current_user.id
task.status == waiting_confirmation 或 pending
```

然后执行：

```text
execute_auto_publish_task(task.id)
```

## 6. 推荐实施阶段

### 阶段 1：补齐正式会话记忆

目标：

```text
Agent 能保存完整 message history 和 slots。
```

改动：

- 新增数据库表：
  - `conversation_sessions`
  - `conversation_messages`
- 替换当前内存 `ConversationStateService`
- 前端刷新后能恢复历史对话

验收：

```text
用户第一句说主题
刷新页面
第二句补平台
Agent 仍能继续任务
```

### 阶段 2：接入 LLM 意图识别

目标：

```text
Agent 能准确理解复杂自然语言。
```

改动：

- 新增 `IntentRecognizer`
- 使用 GLM / DeepSeek / OpenAI 兼容接口
- 输出结构化 JSON
- 增加 confidence 和 missing_slots

验收：

```text
用户说“给小爱科技来一篇智慧物流的稿子，直接安排到知乎”
Agent 识别 generate_and_publish + topic + project_hint + zhihu
```

### 阶段 3：实现项目和账号解析工具

目标：

```text
Agent 能把自然语言线索变成可执行 ID。
```

新增：

```text
resolve_project(system_user_id, project_hint)
resolve_accounts(system_user_id, platforms)
```

验收：

```text
project_hint=小爱科技 -> project_id=12
platforms=[zhihu] -> account_ids=[3]
```

### 阶段 4：实现 AgentTaskExecutor 生成文章

目标：

```text
Agent 能自动生成文章草稿。
```

改动：

- 新增 `AgentTaskExecutor.execute_generate_article`
- 调用关键词选择/蒸馏
- 调用 `GeoArticleService.generate`
- 记录 article_id 到 slots

验收：

```text
用户说“给小爱科技写一篇智慧物流文章”
Agent 创建文章生成任务，并返回 article_id
```

### 阶段 5：接入质检和待确认发布任务

目标：

```text
Agent 能生成文章、质检、创建待确认发布任务。
```

改动：

- 调用 `check_quality`
- 质检失败返回 `review_required`
- 质检通过创建 `AutoPublishTask`
- 默认不立即发布，进入 `confirm_required`

验收：

```text
用户说“生成并发布到知乎”
Agent 生成文章，通过质检后返回“是否确认发布”
```

### 阶段 6：确认后自动发布

目标：

```text
用户确认后 Agent 自动执行发布。
```

改动：

- 支持 `confirm_task`
- 调用 `execute_auto_publish_task`
- 任务状态回写 conversation

验收：

```text
用户说“确认发布”
Agent 执行知乎发布，并返回结果
```

### 阶段 7：进度回传和前端展示

目标：

```text
前端对话窗口能看到任务执行进度。
```

改动：

- conversation 关联 `article_id/task_id`
- WebSocket 或轮询获取任务状态
- 任务完成后自动追加 assistant message

验收：

```text
对话中出现：
正在生成文章
质检中
等待确认
发布中
发布成功
```

## 7. 推荐的第一版真实闭环

不要一开始就做完全自动发布。

推荐第一版：

```text
用户说：帮我生成文章并发布到知乎
Agent：
1. 自动识别意图
2. 自动补齐项目/平台/账号
3. 自动生成文章
4. 自动质检
5. 自动创建待确认发布任务
6. 等用户说“确认发布”
7. 再执行真正发布
```

这样安全，也能验证完整链路。

## 8. 关键代码改造清单

### 必做

```text
1. 新增 conversation_sessions / conversation_messages
2. 新增 backend/services/agent/ 目录
3. 新增 IntentRecognizer
4. 新增 AgentTaskExecutor
5. 新增 resolve_project / resolve_accounts 工具
6. 抽出 AutoPublishTaskService
7. 改造 GeoArticleService.generate 返回 article_id
8. 前端 AgentChat 支持恢复历史和显示任务进度
```

### 应改

```text
1. FeishuTaskHandler 只保留飞书适配，业务逻辑抽出
2. auto_publish.py 中任务创建逻辑下沉到服务层
3. geo.py 中生成逻辑下沉或统一返回可追踪任务
4. 所有文章、项目、账号查询统一按 system_user_id 校验
```

### 暂缓

```text
1. 飞书/OpenClaw 共用 conversation session
2. 用户长期偏好记忆
3. 全自动无需确认发布
4. 多模型路由
```

## 9. 需要你确认的内容

### 模型 API

需要确认使用：

```text
GLM
DeepSeek
OpenAI 兼容接口
其他
```

### 发布策略

建议默认：

```text
生成文章：自动
质检：自动
创建发布任务：自动
真正发布：需要确认
```

如果你确定要全自动发布，需要确认：

```text
是否允许 publish_strategy=immediate 直接执行？
哪些平台允许？
是否必须质检通过？
多账号时如何选择默认账号？
```

### 权限模型

需要确认：

```text
项目归属如何判断？
ProjectMember 是否是正式权限依据？
没有 ProjectMember 时是否允许所有项目可见？
```

## 10. 结论

当前项目已经具备很多底层能力：

```text
关键词蒸馏
文章生成
质检
自动发布任务
Playwright 发布
飞书任务编排
后台对话入口
短期 slots 记忆
```

但还没有形成完整后台 Agent，因为缺少：

```text
持久会话记忆
LLM 结构化意图识别
项目解析工具
账号解析工具
统一 AgentTaskExecutor
统一 AutoPublishTaskService
任务进度回写对话
确认后执行发布
```

所以后续重点不是“再做一个聊天框”，而是把已有业务能力抽成 Agent 可调用的工具链。

最终目标：

```text
用户一句自然语言
-> Agent 自动补齐任务参数
-> 调用内部服务完成生成、质检、发布任务
-> 必要时追问或请求确认
-> 全程可追踪、可恢复、可审计
```
