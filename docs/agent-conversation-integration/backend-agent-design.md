# AutoGEO 后台智能 Agent 设计方案

## 1. 先明确：这个 Agent 到底是什么

AutoGEO 后台 Agent 不应该只是一个聊天框，也不应该只是一个大模型问答入口。

它应该是一个“自然语言任务编排器”：

```text
用户自然语言
  |
  v
理解用户想做什么
  |
  v
记住当前任务上下文
  |
  v
判断缺什么信息
  |
  v
安全地调用 AutoGEO 内部能力
  |
  v
把进度、结果、追问返回给用户
```

一句话：

> Agent 负责把“人说的话”变成“AutoGEO 可以安全执行的结构化任务”。

它不应该直接绕过权限，不应该直接操作数据库写任意 ID，也不应该一识别到发布意图就立刻发布。

## 2. 推荐总体架构

后台 Agent 建议拆成 7 个部分。

```text
前端对话窗口 AgentChat
        |
        v
Conversation API
        |
        v
ConversationOrchestrator
        |
        +--> MemoryManager
        |
        +--> IntentRecognizer
        |
        +--> SlotExtractor
        |
        +--> PolicyGuard
        |
        +--> TaskPlanner
        |
        +--> AgentTaskExecutor
```

### 2.1 前端对话窗口

职责：

- 显示用户和 Agent 的完整对话。
- 发送用户消息。
- 展示当前识别出的意图、槽位、缺失信息。
- 展示任务进度。
- 接收用户确认。

前端不应该：

- 直接调用大模型 API。
- 直接调用发布 API。
- 直接传 `system_user_id`、`account_id`、`project_id` 来让后端执行。

### 2.2 Conversation API

建议接口：

```text
POST /api/conversation/message
GET  /api/conversation/sessions
GET  /api/conversation/sessions/{id}
POST /api/conversation/sessions/{id}/confirm
POST /api/conversation/sessions/{id}/cancel
```

职责：

- 从登录态拿当前 `system_user_id`。
- 接收用户消息。
- 调用 `ConversationOrchestrator`。
- 返回统一响应。

它本身不做复杂业务。

### 2.3 ConversationOrchestrator

这是 Agent 的主控。

职责：

```text
1. 读取当前会话记忆
2. 调用模型或规则识别意图
3. 抽取槽位
4. 合并历史 slots
5. 校验用户权限
6. 判断信息是否完整
7. 生成下一步动作
8. 调用任务执行器或返回追问
9. 更新记忆
10. 返回给前端
```

它是“大脑调度器”，但不是业务服务本身。

### 2.4 IntentRecognizer

职责：识别用户意图。

建议第一批意图：

```text
generate_article          生成文章
generate_and_publish      生成并发布
publish_existing_article  发布已有文章
query_task_status         查询任务状态
query_article             查询文章
query_project             查询项目
bind_external_account     外部平台绑定
set_default_project       设置默认项目
cancel_task               取消任务
unknown                   未识别
```

意图识别可以分三层：

```text
第一层：规则快速识别
第二层：LLM 结构化解析
第三层：业务校验纠偏
```

不要完全相信大模型。大模型只负责提出结构化候选结果，最终能不能执行由代码判断。

### 2.5 SlotExtractor

职责：从用户消息中抽取任务参数。

核心 slots：

```json
{
  "intent": "generate_and_publish",
  "topic": "智慧物流",
  "project_id": null,
  "project_hint": "小爱科技",
  "client_id": null,
  "platforms": ["zhihu"],
  "account_ids": [],
  "article_ids": [],
  "quantity": 1,
  "publish_strategy": "review_first",
  "scheduled_at": null,
  "quality_required": true,
  "waiting_for": ["project"],
  "confirmation_required": true
}
```

注意：

- `project_hint` 可以来自模型。
- `project_id` 必须由代码查库确认。
- `account_ids` 必须由代码按当前用户过滤后得到。
- 大模型不能直接决定 `account_id`。

### 2.6 MemoryManager

职责：管理 Agent 的记忆。

记忆不应该只有一种。至少分三类：

```text
1. message history：完整对话历史
2. task slots：结构化任务状态
3. user preferences：用户长期偏好
```

### 2.7 AgentTaskExecutor

职责：真正调用 AutoGEO 内部业务。

它应该调用已有服务，而不是重新写一套：

```text
ProjectService / Project 查询
KeywordService
GeoArticleService
QualityCheckService
AutoPublishTask
execute_auto_publish_task
```

建议后续从 `FeishuTaskHandler` 里抽出通用执行器：

```text
backend/services/agent_task_executor.py
```

## 3. 记忆应该如何设计

### 3.1 不要只保存完整聊天文本

完整聊天文本有用，但不能只靠它。

如果只保存：

```json
[
  {"role": "user", "content": "帮我写一篇文章"},
  {"role": "assistant", "content": "请告诉我主题"},
  {"role": "user", "content": "智慧物流"}
]
```

问题是：

- 执行时还要重新理解一遍。
- 模型可能误读上下文。
- 不利于权限校验。
- 不利于恢复任务状态。

### 3.2 正确做法：message history + slots

正式版应该同时保存两套东西。

第一套：完整消息历史。

用途：

- 前端回放。
- 审计。
- 给 LLM 做上下文。
- 排查误判。

示例：

```json
[
  {
    "role": "user",
    "content": "帮我写一篇文章",
    "created_at": "2026-06-05T10:00:00"
  },
  {
    "role": "assistant",
    "content": "请告诉我主题和项目",
    "created_at": "2026-06-05T10:00:02"
  }
]
```

第二套：结构化 slots。

用途：

- 判断缺什么。
- 安全执行。
- 恢复任务。
- 不依赖模型猜测。

示例：

```json
{
  "intent": "generate_and_publish",
  "topic": "智慧物流",
  "project_id": 12,
  "platforms": ["zhihu"],
  "quantity": 1,
  "publish_strategy": "review_first",
  "waiting_for": [],
  "confirmation_required": true
}
```

一句话：

> message history 负责“记得聊过什么”，slots 负责“知道该执行什么”。

### 3.3 建议数据库表

#### conversation_sessions

```text
conversation_sessions(
  id,
  source,              -- web / feishu / openclaw
  channel,             -- web / feishu / other
  system_user_id,
  external_user_id,
  external_chat_id,
  status,              -- active / waiting_user / running / completed / failed / cancelled
  current_intent,
  slots,
  summary,
  created_at,
  updated_at,
  expires_at
)
```

#### conversation_messages

```text
conversation_messages(
  id,
  conversation_id,
  role,                -- user / assistant / system / tool
  content,
  metadata,
  created_at
)
```

#### user_agent_preferences

```text
user_agent_preferences(
  id,
  system_user_id,
  default_project_id,
  default_platforms,
  default_publish_strategy,
  require_confirmation_before_publish,
  tone_preference,
  created_at,
  updated_at
)
```

### 3.4 记忆生命周期

建议：

```text
短期会话记忆：1-24 小时
任务会话记忆：直到任务完成后保留 30-90 天
用户偏好记忆：长期保存，可由用户修改
```

## 4. 用户意图如何识别

### 4.1 输入给模型的内容

不能只把用户当前一句话发给模型。应该包含：

```text
1. 系统提示词
2. 当前用户消息
3. 最近 N 条 message history
4. 当前 slots
5. 当前用户可用项目摘要
6. 当前用户可用平台摘要
7. 可用工具/动作定义
```

示例输入上下文：

```json
{
  "current_message": "那就发到知乎",
  "slots": {
    "intent": "generate_and_publish",
    "topic": "智慧物流",
    "project_hint": "小爱科技",
    "platforms": []
  },
  "available_projects": [
    {"id": 12, "name": "小爱科技", "company_name": "小爱科技有限公司"}
  ],
  "available_platforms": ["zhihu", "xiaohongshu"]
}
```

### 4.2 模型输出必须是结构化 JSON

模型不要直接返回一段聊天文本，而是返回：

```json
{
  "intent": "generate_and_publish",
  "slots": {
    "topic": "智慧物流",
    "project_hint": "小爱科技",
    "platforms": ["zhihu"],
    "quantity": 1,
    "publish_strategy": "review_first"
  },
  "missing_slots": [],
  "confidence": 0.91,
  "reply": "好的，我理解为：为小爱科技生成一篇智慧物流文章，并准备发布到知乎。"
}
```

### 4.3 代码二次校验

模型输出后，代码必须做二次校验：

```text
project_hint -> 查 projects
platforms -> 检查是否支持
account_ids -> 按 system_user_id 查 accounts
article_ids -> 按 system_user_id / 项目权限查文章
publish_strategy -> 检查是否允许自动发布
```

如果校验失败，不能执行，必须追问。

## 5. 识别意图之后如何继续执行

### 5.1 总流程

```text
用户消息
  |
  v
读取会话记忆
  |
  v
识别意图 + 抽取 slots
  |
  v
合并旧 slots
  |
  v
业务校验和权限过滤
  |
  v
判断是否缺信息
  |
  +-- 缺信息 -> 保存 slots -> 追问用户
  |
  +-- 信息完整 -> 生成执行计划
                    |
                    v
                风险判断
                    |
                    +-- 需要确认 -> 返回 confirm_required
                    |
                    +-- 可执行 -> 调用 AgentTaskExecutor
```

### 5.2 生成文章流程

```text
intent = generate_article

必需 slots:
  - topic 或 keyword_id
  - project_id
  - quantity

流程:
1. 确认 project_id
2. 如果没有 keyword_id，则基于项目和主题找关键词
3. 如果没有合适关键词，触发关键词蒸馏或追问
4. 调用 GeoArticleService 生成文章
5. 保存 article_id
6. 返回生成状态
```

### 5.3 生成并发布流程

```text
intent = generate_and_publish

必需 slots:
  - topic 或 keyword_id
  - project_id
  - platforms
  - account_ids
  - publish_strategy

流程:
1. 确认项目
2. 确认平台
3. 查询当前用户在这些平台下的账号
4. 多账号时追问选择
5. 生成文章
6. 质检
7. 质检失败 -> review_required
8. 质检通过 -> 创建待确认发布任务
9. 用户确认 -> 执行发布
10. 返回结果
```

### 5.4 查询任务状态流程

```text
intent = query_task_status

流程:
1. 按 system_user_id 查询最近任务
2. 如果用户指定 task_id，则校验任务归属
3. 返回任务状态、文章、平台、失败原因
```

### 5.5 发布已有文章流程

```text
intent = publish_existing_article

必需 slots:
  - article_ids
  - platforms 或 account_ids

流程:
1. 查用户可见文章
2. 如果没指定文章，追问选择
3. 查用户可用发布账号
4. 创建待确认发布任务
5. 用户确认后执行
```

## 6. Agent 响应状态设计

建议统一状态：

```text
understood             已理解，但尚未执行
need_clarification     缺少信息
confirm_required       需要用户确认
planning               正在生成执行计划
running                正在执行
review_required        需要人工审核
completed              已完成
failed                 失败
cancelled              已取消
```

响应示例：

```json
{
  "success": true,
  "status": "need_clarification",
  "reply": "我已经知道你要生成文章，但还不知道使用哪个项目。",
  "conversation_id": "conv_xxx",
  "intent": "generate_article",
  "slots": {
    "topic": "智慧物流",
    "project_id": null
  },
  "missing_slots": ["project_id"],
  "next_questions": [
    "请告诉我要使用哪个项目。"
  ],
  "execution_plan": null
}
```

## 7. 工具调用应该怎么设计

Agent 不应该直接写死业务过程，而应该通过工具/服务调用。

建议工具清单：

```text
search_projects
resolve_project
list_publish_accounts
resolve_platform_accounts
distill_keywords
generate_article
check_article_quality
create_publish_task
confirm_publish_task
query_task_status
cancel_task
```

每个工具都必须接收 `system_user_id`，并在内部做权限过滤。

示例：

```python
resolve_project(system_user_id, project_hint) -> ProjectResolution
list_publish_accounts(system_user_id, platforms) -> List[Account]
create_publish_task(system_user_id, article_ids, account_ids) -> AutoPublishTask
```

## 8. 安全边界

必须遵守：

```text
1. 模型不能决定 system_user_id
2. 模型不能决定 account_id
3. 模型不能绕过项目权限
4. 模型不能直接执行发布
5. 质检未通过不能自动发布
6. 高风险动作必须 confirm_required
7. 所有执行都要有 trace_id
8. 所有任务都要记录 triggered_by_user_id
```

建议默认策略：

```text
生成文章：可以自动创建草稿
生成并发布：先创建待确认任务
发布动作：必须用户确认
多账号：必须用户选择
多项目：必须用户选择
低置信度意图：必须追问
```

## 9. 分阶段落地

### 阶段 1：真正的后台 Agent 对话基础

目标：

```text
后台对话具备 LLM 意图识别、message history、slots 记忆。
```

任务：

- 新增 `conversation_sessions`
- 新增 `conversation_messages`
- 接入 LLM 结构化解析
- 保存完整对话历史
- 保存 slots
- 支持多轮追问

### 阶段 2：接入项目和账号解析

目标：

```text
Agent 能知道当前用户有哪些项目、哪些发布账号。
```

任务：

- `resolve_project`
- `list_publish_accounts`
- 平台别名解析
- 多项目/多账号追问

### 阶段 3：接入文章生成

目标：

```text
Agent 能从对话创建文章生成任务。
```

任务：

- 接关键词蒸馏
- 接文章生成
- 生成后写入 conversation slots
- 返回 article_id 和状态

### 阶段 4：接入质检和待确认发布

目标：

```text
Agent 能创建待确认发布任务，但不直接发布。
```

任务：

- 质检通过才允许进入发布准备
- 创建 `auto_publish_task`
- 返回 `confirm_required`
- 用户确认后执行

### 阶段 5：接外部平台统一入口

目标：

```text
Web、飞书、OpenClaw 使用同一套 Agent。
```

任务：

- 外部身份绑定解析
- 外部入口复用 conversation sessions
- 任务结果回传飞书/OpenClaw

## 10. 现在代码应该调整成什么样

建议目录最终变成：

```text
backend/api/conversation.py

backend/services/agent/
  orchestrator.py
  memory.py
  intent_recognizer.py
  slot_extractor.py
  policy_guard.py
  task_planner.py
  task_executor.py
  tools.py

backend/database/models.py
  ConversationSession
  ConversationMessage
  UserAgentPreference
```

当前已有的：

```text
backend/services/conversation_orchestrator.py
backend/services/conversation_state_service.py
backend/api/conversation.py
```

可以先继续用，但下一步建议重构到 `backend/services/agent/` 目录，职责会更清楚。

## 11. 需要你确认的关键决策

### 11.1 模型选择

需要确认使用哪个：

```text
GLM
DeepSeek
OpenAI 兼容接口
本地模型
```

### 11.2 执行权限

需要确认：

```text
是否允许 Agent 自动生成文章？
是否允许 Agent 自动创建发布任务？
是否允许 Agent 自动发布？
```

建议：

```text
自动生成草稿：允许
自动创建待确认发布任务：允许
自动发布：暂不允许
```

### 11.3 记忆策略

需要确认：

```text
完整对话保存多久？
任务完成后是否保留？
用户偏好是否长期保存？
是否允许用户清除记忆？
```

建议：

```text
message history 保留 90 天
slots 随任务长期保留
用户偏好长期保留
提供清除按钮
```

## 12. 最终目标

最终的 AutoGEO 后台 Agent 应该做到：

```text
用户：帮我给小爱科技写一篇智慧物流文章，发到知乎

Agent：
1. 识别意图 generate_and_publish
2. 找到小爱科技项目
3. 找到该用户知乎账号
4. 生成文章
5. 质检
6. 创建待确认发布任务
7. 询问用户是否发布

用户：确认发布

Agent：
8. 执行发布
9. 返回发布结果
```

这才是完整 Agent，而不是单纯聊天窗口。
