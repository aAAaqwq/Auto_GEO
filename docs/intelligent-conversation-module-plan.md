# AutoGEO 智能对话模块研究与实施思路

## 1. 核心判断

新增“智能对话模块”与当前已经规划的 `Agent Command API` 不冲突，反而是上下游关系。

当前的指令入口：

```text
飞书 / OpenClaw / 其他平台
        |
        v
/api/integrations/agent-command
```

它的职责是：

- 校验外部来源是否可信
- 接收外部用户身份
- 把自然语言消息传进 AutoGEO
- 不直接操作数据库
- 不直接指定系统用户、项目或发布账号

智能对话模块的职责应该是：

- 理解用户意图
- 维护多轮对话上下文
- 判断缺失信息
- 调用关键词蒸馏、文章生成、质检、发布任务等内部能力
- 把执行进度和结果整理成用户能理解的回复

所以推荐架构是：

```text
飞书 / OpenClaw / Web 对话框 / 其他平台
        |
        v
统一指令入口 Agent Command API
        |
        v
智能对话模块 Conversation Orchestrator
        |
        v
AutoGEO 标准业务服务
关键词蒸馏 -> 文章生成 -> 质量检查 -> 自动发布 -> 结果回传
```

一句话概括：

> 指令入口负责“谁在说、从哪里来”；智能对话模块负责“他说的是什么意思、下一步该做什么”。

## 2. 目标场景

用户在 AutoGEO 内部对话框、飞书、OpenClaw 或其他外部平台中输入：

```text
帮我在绑定的平台上发布一篇关于智慧物流的文章
```

系统应完成：

1. 识别用户身份
2. 找到该用户绑定的 AutoGEO 系统账号
3. 确认可访问项目
4. 确认默认项目或追问项目
5. 蒸馏关键词
6. 生成文章
7. 执行质量检查
8. 查找该用户绑定的平台发布账号
9. 创建自动发布任务
10. 执行发布
11. 返回进度和结果

## 3. 与现有模块的关系

### 3.1 当前指令入口

当前新增的接口：

```text
POST /api/integrations/agent-command
```

适合作为所有外部平台进入 AutoGEO 的统一入口。

它不应该承担复杂业务编排，否则后续会变成一个臃肿的“大接口”。它应该继续保持薄层：

- token 校验
- 外部身份解析
- 请求格式标准化
- 调用智能对话模块
- 返回标准响应

### 3.2 新增智能对话模块

建议新增：

```text
backend/services/conversation_orchestrator.py
backend/services/conversation_state_service.py
backend/api/conversation.py
```

职责划分：

- `conversation_orchestrator.py`
  - 智能对话主编排器
  - 负责理解用户意图、判断缺失信息、调用业务流程

- `conversation_state_service.py`
  - 管理多轮对话状态
  - 记录用户当前正在确认哪个项目、哪个平台、哪篇文章

- `api/conversation.py`
  - AutoGEO 后台页面里的直接对话接口
  - 例如 `POST /api/conversation/message`

外部入口和内部页面都可以调用同一个对话编排器：

```text
/api/integrations/agent-command
        |
        v
ConversationOrchestrator

/api/conversation/message
        |
        v
ConversationOrchestrator
```

这样飞书、OpenClaw、后台网页都共享同一套对话能力。

## 4. 推荐架构

```text
用户消息
  |
  v
入口适配层
  - Web 对话框
  - Agent Command API
  - 飞书 Webhook
  - OpenClaw Skill
  |
  v
身份解析层
  - system_user_id
  - external_user_id
  - channel
  - chat_id
  |
  v
智能对话层
  - 意图识别
  - 槽位抽取
  - 多轮追问
  - 风险判断
  |
  v
业务编排层
  - 项目解析
  - 关键词蒸馏
  - 文章生成
  - 质量检查
  - 账号选择
  - 发布任务创建
  |
  v
执行层
  - n8n / AI 生成
  - Playwright 发布
  - 任务状态追踪
  |
  v
结果回复
```

## 5. 对话模块的标准输入输出

### 5.1 输入

建议定义统一输入模型：

```json
{
  "source": "web | openclaw | feishu",
  "channel": "web | feishu | other",
  "system_user_id": 1,
  "external_user_id": "ou_xxx",
  "external_chat_id": "oc_xxx",
  "message": "帮我在绑定的平台上发布一篇关于智慧物流的文章",
  "session_id": "conv_xxx",
  "raw_event": {}
}
```

注意：

- `system_user_id` 只能由后端身份解析得到
- 外部平台不能直接传 `system_user_id`
- Web 后台可以从登录态得到 `system_user_id`
- 飞书/OpenClaw 可以从绑定表得到 `system_user_id`

### 5.2 输出

建议定义统一输出模型：

```json
{
  "success": true,
  "status": "accepted",
  "reply": "收到，正在为你生成文章并准备发布。",
  "conversation_id": "conv_xxx",
  "trace_id": "trace_xxx",
  "intent": "generate_and_publish",
  "need_user_input": false,
  "task_id": 123,
  "next_questions": []
}
```

常见状态：

- `accepted`：已接收并开始处理
- `need_clarification`：需要用户补充信息
- `binding_required`：外部账号未绑定
- `project_required`：无法确定项目
- `account_required`：没有可用发布账号
- `review_required`：生成内容需要人工审核
- `running`：任务执行中
- `completed`：任务完成
- `failed`：任务失败

## 6. 核心业务流程

### 6.1 生成并发布

用户：

```text
帮我在绑定的平台上发布一篇关于智慧物流的文章
```

标准流程：

```text
1. 解析意图：generate_and_publish
2. 解析主题：智慧物流
3. 解析平台：未指定
4. 查询用户绑定的平台账号
5. 如果只有一个可用平台，默认使用该平台
6. 如果多个平台，追问用户要发布到哪些平台
7. 查询用户默认项目
8. 如果没有默认项目，追问项目或公司名称
9. 对项目进行关键词蒸馏
10. 选择合适关键词
11. 调用文章生成服务
12. 等待生成完成
13. 执行质量检查
14. 质检通过则创建自动发布任务
15. 执行发布
16. 返回任务 ID、平台、进度和结果
```

### 6.2 信息不足时追问

如果用户没有默认项目：

```text
我还不知道这篇文章属于哪个项目。请告诉我要使用的公司、客户或项目名称。
```

如果用户绑定了多个平台账号，但没有指定平台：

```text
你当前有多个可用发布平台：知乎、小红书、头条。请告诉我要发布到哪些平台。
```

如果没有授权账号：

```text
你还没有可用的平台发布账号，请先在 AutoGEO 后台完成账号授权。
```

### 6.3 质量检查不通过

如果文章生成完成但质量检查未通过：

```text
文章已经生成，但当前质量检查未通过，已为你保留为草稿。建议人工审核后再发布。
```

不要自动发布未通过质检的文章。

## 7. 多轮对话状态

建议新增会话状态表，或者先用内存/缓存过渡。

长期建议表结构：

```text
conversation_sessions(
  id,
  source,
  channel,
  external_user_id,
  external_chat_id,
  system_user_id,
  status,
  current_intent,
  slots,
  last_message,
  created_at,
  updated_at,
  expires_at
)
```

其中 `slots` 可以保存：

```json
{
  "intent": "generate_and_publish",
  "topic": "智慧物流",
  "project_id": null,
  "platforms": [],
  "quantity": 1,
  "publish_strategy": "immediate",
  "waiting_for": "project"
}
```

当用户下一句回复“用小爱科技项目”时，对话模块可以继续补齐 `project_id`，而不是重新开始。

## 8. 与现有服务的复用关系

优先复用现有服务，不重新造一套：

- 意图解析：
  - 当前可先复用 `FeishuIntentParser`
  - 后续建议改名或抽象为 `IntentParser`

- 任务编排：
  - 当前可复用 `FeishuTaskHandler` 内部逻辑
  - 后续建议拆成通用 `AgentTaskHandler`

- 关键词蒸馏：
  - 复用 `KeywordService`

- 文章生成：
  - 复用 `GeoArticleService`

- 发布任务：
  - 复用 `AutoPublishTask`
  - 复用 `execute_auto_publish_task`

- 用户绑定：
  - 第一阶段复用 `feishu_user_bindings`
  - 后续增加 `external_user_bindings`

## 9. 分阶段实施计划

### 阶段 1：内部 Web 对话框

目标：

在 AutoGEO 后台新增一个“智能对话”入口，让登录用户可以直接对话。

任务：

- 新增 `POST /api/conversation/message`
- 根据登录态获取 `system_user_id`
- 调用 `ConversationOrchestrator`
- 返回意图解析结果
- 暂不真实发布，只验证流程

验收：

输入：

```text
帮我写一篇关于智慧物流的文章，发布到知乎
```

返回：

```text
已识别为 generate_and_publish，目标平台 zhihu。
```

### 阶段 2：接入标准业务链路

目标：

智能对话可以真正触发关键词蒸馏、文章生成、质检和发布任务。

任务：

- 接入项目解析
- 接入关键词蒸馏
- 接入文章生成
- 接入质量检查
- 接入账号过滤
- 创建自动发布任务

验收：

用户在后台对话框输入指令，可以创建一条 `auto_publish_task`。

### 阶段 3：接入外部 Agent Command API

目标：

OpenClaw、飞书等外部平台不直接走旧的意图解析，而是统一调用智能对话模块。

任务：

- 修改 `AgentCommandHandler`
- 身份解析后调用 `ConversationOrchestrator`
- 返回统一对话响应

验收：

飞书或 OpenClaw 中发送同一句话，可以触发与后台对话框一致的流程。

### 阶段 4：多轮对话

目标：

支持缺少项目、平台、数量等信息时自动追问。

任务：

- 新增会话状态管理
- 保存 slots
- 支持 `need_clarification`
- 支持用户补充信息后继续执行

验收：

用户：

```text
帮我发一篇文章
```

系统：

```text
请告诉我要使用哪个项目，以及要发布到哪个平台。
```

用户：

```text
小爱科技，发布到知乎
```

系统继续执行原任务。

### 阶段 5：统一多平台入口

目标：

飞书、OpenClaw、企业微信、Web 对话都共享同一个智能对话能力。

任务：

- 新增 `external_user_bindings`
- 迁移或兼容 `feishu_user_bindings`
- 所有外部入口统一调用 Agent Command API

验收：

同一个 AutoGEO 用户可以绑定多个外部身份，但任务权限仍只按 `system_user_id` 控制。

## 10. 风险与控制

### 权限风险

风险：

外部平台冒充用户或指定其他用户身份。

控制：

- 外部请求必须带 `AUTOGEO_AGENT_TOKEN`
- 外部请求不能传 `system_user_id`
- 后端必须通过绑定表解析用户
- 所有项目、文章、账号查询都必须按 `system_user_id` 过滤

### 误发布风险

风险：

用户一句话被误解后直接发布。

控制：

- 高风险情况要求确认
- 质检未通过不发布
- 多平台、多账号时优先追问
- 首期可默认创建草稿或待确认任务

### 对话漂移风险

风险：

多轮对话中模型忘记上下文或错误补全信息。

控制：

- 使用结构化 slots
- 每轮只更新明确字段
- 不让模型直接决定 `system_user_id`、`account_id`
- 关键动作由代码校验

## 11. 推荐当前决策

建议保留现有 `Agent Command API`，不要删除，也不要把所有逻辑写进这个入口。

推荐新增一个独立的智能对话模块：

```text
ConversationOrchestrator
```

然后让不同入口都调用它：

```text
Web 对话框
        |
        v
ConversationOrchestrator

OpenClaw / 飞书
        |
        v
Agent Command API
        |
        v
ConversationOrchestrator
```

这样既能做 AutoGEO 内部的智能对话，也能自然扩展到飞书和其他平台。

## 12. 最小可交付版本

第一版不需要一次性做完整智能体，只需要做到：

```text
1. 后台新增智能对话接口
2. 用户输入自然语言
3. 解析意图
4. 检查绑定项目和账号
5. 能返回缺失信息提示
6. 在信息完整时创建文章生成或发布任务
```

第一版完成后，再逐步补齐：

- 多轮追问
- 任务进度流式返回
- 飞书卡片消息
- 发布结果卡片
- 多平台统一绑定
