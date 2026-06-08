# AutoGEO 外部平台与智能对话联合接入方案

## 1. 这份方案要解决什么

现有两份文档分别在讲两个环节：

- `openclaw-feishu-integration-plan.md`：飞书、OpenClaw 等外部平台如何安全接入 AutoGEO。
- `intelligent-conversation-module-plan.md`：自然语言进来后，AutoGEO 如何理解意图、补齐信息、编排生成和发布任务。

这两个环节必须合在一起才有完整价值。最终目标是：

```text
用户在飞书 / OpenClaw / AutoGEO 后台说一句自然语言
        |
        v
AutoGEO 验证这个外部用户确实绑定了某个后台用户
        |
        v
智能对话模块理解意图，必要时追问
        |
        v
调用 AutoGEO 现有项目、关键词、文章生成、质检、发布能力
        |
        v
把任务进度和结果返回给原来的会话
```

一句话概括：

> 外部平台负责把话带进来，AutoGEO 负责验证人、理解话、执行任务、返回结果。

## 2. 最终统一架构

推荐把系统拆成五层，不要把所有逻辑塞进一个接口。

```text
飞书 / OpenClaw / Web 后台 / 其他平台
        |
        v
入口适配层
  - /api/feishu/webhook
  - OpenClaw autogeo-publish Skill
  - /api/conversation/message
  - /api/integrations/agent-command
        |
        v
身份验证与绑定解析层
  - 校验来源 token / 签名
  - 解析 external_user_id / chat_id
  - 根据绑定表解析 system_user_id
  - 校验项目、账号、文章都属于该 system_user_id
        |
        v
智能对话层 ConversationOrchestrator
  - 意图识别
  - 槽位抽取
  - 多轮追问
  - 风险确认
  - 标准响应组装
        |
        v
业务编排层 AgentTaskHandler
  - 项目解析
  - 关键词蒸馏
  - 文章生成
  - 质量检查
  - 发布账号选择
  - auto_publish_task 创建
        |
        v
执行与回传层
  - n8n / AI 生成
  - Playwright 发布
  - 任务状态追踪
  - 飞书 / OpenClaw / Web 回复
```

核心原则：

- 外部平台永远不能传 `system_user_id`。
- 外部平台永远不能传 `account_id` 来指定发布账号。
- AutoGEO 后端必须通过绑定表解析用户身份。
- 所有项目、文章、发布账号查询都必须按 `system_user_id` 过滤。
- 智能对话模块只提出意图和候选槽位，关键 ID 由代码查库确认。

## 3. 三条入口如何联合

### 3.1 Web 后台入口

适合 AutoGEO 登录用户直接使用。

```text
AutoGEO Web
-> POST /api/conversation/message
-> 从登录态得到 system_user_id
-> ConversationOrchestrator
-> AgentTaskHandler
```

这个入口最简单，因为用户已经登录。它不需要外部绑定解析，只需要从登录态拿 `system_user_id`。

### 3.2 飞书原生入口

短期保留现有飞书直连能力，保证最小闭环稳定。

```text
飞书机器人
-> POST /api/feishu/webhook
-> 校验飞书事件
-> 解析 open_id / union_id / chat_id
-> 查 feishu_user_bindings
-> ConversationOrchestrator
-> AgentTaskHandler
-> 飞书回复
```

飞书原生入口不应该继续走一套独立业务逻辑，后续应逐步改成调用同一个 `ConversationOrchestrator`。

### 3.3 OpenClaw 统一入口

适合后续多平台扩展。

```text
飞书 / 其他聊天平台
-> OpenClaw Channel
-> autogeo-publish Skill
-> POST /api/integrations/agent-command
-> 校验 X-AutoGEO-Agent-Token
-> 根据 source/channel/external_user_id 查绑定
-> ConversationOrchestrator
-> AgentTaskHandler
-> OpenClaw 回复原会话
```

OpenClaw 只做连接层，不碰数据库，不决定用户权限，不执行发布。

## 4. 飞书用户与 AutoGEO 后台用户如何验证为同一个人

这是整个项目最重要的安全闭环。

### 4.1 正确的绑定逻辑

不要让用户在飞书里直接输入手机号、邮箱或用户 ID 绑定。推荐使用“后台登录态生成一次性绑定码”的方式。

```text
1. 用户先登录 AutoGEO 后台
2. 后台生成一次性绑定码，例如 AG8K2Q
3. 绑定码写入 feishu_binding_codes
   - code = AG8K2Q
   - system_user_id = 当前登录用户 ID
   - status = 0
   - expires_at = 30 分钟后
4. 用户在飞书私聊机器人发送：绑定 AG8K2Q
5. AutoGEO 收到飞书事件，解析发送者 open_id / union_id
6. 后端查找未使用且未过期的绑定码
7. 创建或更新 feishu_user_bindings
   - open_id = 飞书发送者 open_id
   - union_id = 飞书 union_id
   - system_user_id = 绑定码所属后台用户
   - status = 1
8. 标记绑定码已使用
   - status = 1
   - used_by_open_id = 当前飞书 open_id
   - used_at = 当前时间
9. 后续所有飞书命令都通过 open_id 查 system_user_id
```

这能证明两件事：

- 这个人能登录 AutoGEO 后台，所以他拥有后台用户身份。
- 这个人能控制对应飞书账号，所以他拥有飞书外部身份。

两边都成立，才能把 `open_id` 和 `system_user_id` 绑定起来。

### 4.2 OpenClaw 场景下怎么验证

如果 OpenClaw 的 Feishu Channel 能拿到飞书 `open_id`，第一阶段可以继续复用现有飞书绑定表：

```text
OpenClaw external_user_id = 飞书 open_id
AutoGEO 查询 feishu_user_bindings.open_id
```

这时 OpenClaw 不能自己声明用户是谁，只能把飞书通道拿到的 `open_id` 传给 AutoGEO。

长期建议新增通用绑定表 `external_user_bindings`：

```text
external_user_bindings(
  id,
  source,              -- feishu / openclaw / wechat / slack
  channel,             -- feishu / telegram / web
  external_user_id,    -- open_id / platform user id
  external_union_id,
  external_chat_id,
  system_user_id,
  default_client_id,
  default_project_id,
  status,
  bind_method,         -- code / admin / oauth
  verified_at,
  created_at,
  updated_at
)
```

兼容策略：

```text
短期：
  channel=feishu 时查 feishu_user_bindings

中期：
  新建 external_user_bindings
  绑定时同时写 feishu_user_bindings 和 external_user_bindings

长期：
  所有外部入口统一查 external_user_bindings
  feishu_user_bindings 只作为历史兼容表或迁移后废弃
```

### 4.3 每次外部命令都要重新做的校验

绑定成功不代表后续可以放松。每次外部命令都必须校验：

```text
1. 校验请求来源
   - Agent Command API 校验 X-AutoGEO-Agent-Token
   - 飞书原生 Webhook 校验飞书签名或事件来源

2. 校验外部身份
   - source/channel/external_user_id 必须存在
   - external_user_id 只能来自平台事件，不从用户文本里解析

3. 解析系统用户
   - 通过绑定表查 system_user_id
   - status 必须为已绑定

4. 校验系统用户可用
   - users.id 存在
   - 用户未禁用

5. 校验项目权限
   - 项目必须属于该用户
   - 或用户在 project_members 中有权限

6. 校验发布账号权限
   - Account.user_id == system_user_id
   - 不接受外部传入 account_id

7. 校验任务归属
   - auto_publish_tasks.triggered_by_user_id = system_user_id
   - 任务查询只能查该用户可见任务
```

## 5. 统一请求与响应模型

### 5.1 Agent Command API 请求

```json
{
  "source": "openclaw",
  "channel": "feishu",
  "external_user_id": "ou_xxx",
  "external_chat_id": "oc_xxx",
  "message": "帮我写一篇关于智慧物流的文章，发布到知乎",
  "raw_event": {}
}
```

禁止字段：

```text
system_user_id
account_id
project_id
client_id
```

这些 ID 不能由外部平台直接传入。如果未来需要支持候选项目或候选账号，也必须只作为自然语言线索，由 AutoGEO 后端查库确认。

### 5.2 ConversationOrchestrator 标准输入

```json
{
  "source": "openclaw",
  "channel": "feishu",
  "system_user_id": 1,
  "external_user_id": "ou_xxx",
  "external_chat_id": "oc_xxx",
  "message": "帮我写一篇关于智慧物流的文章，发布到知乎",
  "session_id": "conv_xxx",
  "raw_event": {}
}
```

注意：这里的 `system_user_id` 已经是 AutoGEO 后端解析出来的，不是外部平台传来的。

### 5.3 标准响应

```json
{
  "success": true,
  "status": "accepted",
  "reply": "收到，正在为你生成文章并准备发布到知乎。",
  "conversation_id": "conv_xxx",
  "trace_id": "agent_xxx",
  "intent": "generate_and_publish",
  "need_user_input": false,
  "task_id": 123,
  "next_questions": []
}
```

状态建议统一为：

```text
accepted              已接收
need_clarification    需要补充信息
binding_required      外部账号未绑定
binding_invalid       绑定指向的后台用户不存在或不可用
project_required      无法确定项目
account_required      没有可用发布账号
review_required       生成内容需要人工审核
confirm_required      高风险动作需要确认
running               任务执行中
completed             任务完成
failed                任务失败
```

## 6. 联合后的完整业务流程

### 6.1 用户首次绑定

```text
AutoGEO 后台
1. 用户登录
2. 打开“外部平台绑定”
3. 点击“生成飞书绑定码”
4. 后端创建 feishu_binding_codes
5. 页面显示：绑定 AG8K2Q，30 分钟内有效

飞书
6. 用户私聊机器人：绑定 AG8K2Q
7. 飞书 Webhook 或 OpenClaw Skill 把 open_id 和消息传给 AutoGEO
8. AutoGEO 校验绑定码
9. AutoGEO 创建 feishu_user_bindings / external_user_bindings
10. 返回：绑定成功
```

### 6.2 用户发起生成并发布

```text
1. 用户说：帮我写一篇关于智慧物流的文章，发布到知乎
2. 入口层接收消息
3. 校验来源 token / 签名
4. 根据 open_id 查到 system_user_id
5. 调用 ConversationOrchestrator
6. 解析意图 generate_and_publish
7. 抽取主题：智慧物流
8. 抽取平台：知乎
9. 查询该用户默认项目
10. 如果没有默认项目，返回 project_required 并追问
11. 查询该用户知乎发布账号
12. 如果没有账号，返回 account_required
13. 调用关键词蒸馏
14. 调用文章生成
15. 执行质量检查
16. 质检通过后创建 auto_publish_task
17. 执行 Playwright 发布
18. 返回任务 ID、状态和结果
```

### 6.3 信息不足的多轮追问

第一轮：

```text
用户：帮我发一篇文章
系统：请告诉我要使用哪个项目，以及要发布到哪个平台。
```

状态保存：

```json
{
  "intent": "generate_and_publish",
  "topic": null,
  "project_id": null,
  "platforms": [],
  "waiting_for": ["project", "platform", "topic"]
}
```

第二轮：

```text
用户：用小爱科技项目，发到知乎，主题是智慧物流
系统：收到，正在为小爱科技项目生成智慧物流文章并准备发布到知乎。
```

ConversationOrchestrator 读取上一轮 `slots`，补齐缺失字段后继续执行原任务。

## 7. 建议新增或调整的代码模块

### 7.1 入口层

现有：

```text
backend/api/integrations.py
backend/services/agent_command_handler.py
backend/api/feishu.py
```

建议演进：

```text
backend/api/integrations.py
  - 保持薄层
  - 只做 token 校验、请求校验、调用 AgentCommandHandler

backend/services/agent_command_handler.py
  - 只做外部身份解析
  - 不再直接承担业务编排
  - 解析出 system_user_id 后调用 ConversationOrchestrator

backend/api/conversation.py
  - Web 后台智能对话入口
  - 从登录态获取 system_user_id
  - 调用 ConversationOrchestrator
```

### 7.2 身份绑定层

建议新增：

```text
backend/services/external_identity_service.py
```

职责：

```text
resolve_external_user(source, channel, external_user_id)
create_binding_by_code(code, source, channel, external_user_id, union_id)
unbind_external_user(system_user_id, source, channel, external_user_id)
list_bindings(system_user_id)
```

短期实现可复用：

```text
FeishuUserBinding
FeishuBindingCode
```

长期实现切到：

```text
ExternalUserBinding
```

### 7.3 智能对话层

建议新增：

```text
backend/services/conversation_orchestrator.py
backend/services/conversation_state_service.py
```

职责：

```text
ConversationOrchestrator
  - 统一处理 Web / Feishu / OpenClaw 消息
  - 调用 IntentParser
  - 判断缺失信息
  - 调用 AgentTaskHandler
  - 返回标准响应

ConversationStateService
  - 保存多轮对话 slots
  - 管理 waiting_for
  - 处理会话过期
```

### 7.4 业务编排层

建议从 `FeishuTaskHandler` 中抽出通用部分：

```text
backend/services/agent_task_handler.py
```

职责：

```text
prepare_project()
prepare_keywords()
generate_article()
run_quality_check()
select_publish_accounts()
create_auto_publish_task()
query_task_status()
```

`FeishuTaskHandler` 后续只保留飞书消息格式处理和回复发送。

## 8. 数据库建议

### 8.1 短期继续使用现有表

现有表已经能支持第一阶段：

```text
feishu_user_bindings
feishu_binding_codes
feishu_events
auto_publish_tasks.triggered_by_user_id
```

短期注意：

- `feishu_user_bindings.open_id` 已经唯一，可以用于飞书用户到系统用户的映射。
- `feishu_binding_codes` 已经能做一次性绑定码。
- `auto_publish_tasks.triggered_by_user_id` 应该写入触发用户。

### 8.2 中期新增通用绑定表

```text
external_user_bindings(
  id,
  source,
  channel,
  external_user_id,
  external_union_id,
  external_chat_id,
  system_user_id,
  default_client_id,
  default_project_id,
  status,
  bind_method,
  verified_at,
  created_at,
  updated_at
)
```

建议唯一约束：

```text
unique(source, channel, external_user_id)
```

建议索引：

```text
system_user_id
source, channel
status
```

### 8.3 新增对话状态表

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

`slots` 示例：

```json
{
  "intent": "generate_and_publish",
  "topic": "智慧物流",
  "project_id": null,
  "platforms": ["zhihu"],
  "quantity": 1,
  "publish_strategy": "immediate",
  "waiting_for": ["project"]
}
```

## 9. 安全要求

### 9.1 第一阶段必须做到

- Agent Command API 必须校验 `X-AutoGEO-Agent-Token`。
- token 只放在 OpenClaw 服务端和 AutoGEO 服务端。
- 飞书原生 Webhook 必须校验飞书事件来源。
- 外部请求不能带 `system_user_id`、`account_id`、`project_id`。
- 所有查库动作必须带 `system_user_id` 权限过滤。
- 绑定码必须一次性使用、短期过期。
- 任务必须记录 `source`、`channel`、`external_user_id`、`triggered_by_user_id`、`trace_id`。
- 质检未通过不自动发布。
- 多平台、多账号、高风险动作需要确认或追问。

### 9.2 后续增强

- 固定 token 升级为 HMAC 签名。
- 每个平台独立 token。
- timestamp + nonce 防重放。
- IP allowlist。
- 绑定和发布操作写审计表。
- 飞书群聊启用 allowlist 和必须 @机器人。
- OpenClaw Skill 只允许调用 AutoGEO 指定 API，不给数据库、本机 shell 或浏览器执行权限。

## 10. 分阶段实施计划

### 阶段 0：整理现有 Agent Command API

目标：

```text
外部命令能进 AutoGEO，能解析用户和意图，但不真实发布。
```

任务：

- 保留 `backend/api/integrations.py`。
- 保留 `backend/services/agent_command_handler.py`。
- 确认 `AUTOGEO_AGENT_TOKEN` 已配置。
- `channel=feishu` 时继续查 `feishu_user_bindings`。
- 解析意图后返回 `action/params/reply`。

验收：

```text
curl 调 /api/integrations/agent-command
传入已绑定 open_id
返回 generate_and_publish / generate / query_status 等意图
```

### 阶段 1：打通绑定码闭环

目标：

```text
证明飞书用户和 AutoGEO 后台用户是同一个人。
```

任务：

- 后台提供生成绑定码接口。
- 飞书或 OpenClaw 支持 `绑定 <code>`。
- 后端校验 code、open_id、过期时间、使用状态。
- 创建或更新绑定表。
- 绑定成功后返回明确提示。

验收：

```text
后台用户 A 生成绑定码
飞书用户 X 发送绑定码
feishu_user_bindings.open_id = X
feishu_user_bindings.system_user_id = A
之后 X 的命令只能以 A 的权限执行
```

### 阶段 2：新增 ConversationOrchestrator

目标：

```text
Web、飞书、OpenClaw 都调用同一个自然语言编排模块。
```

任务：

- 新增 `conversation_orchestrator.py`。
- 新增统一输入输出模型。
- 先复用 `FeishuIntentParser`。
- 将 AgentCommandHandler 改为解析身份后调用 ConversationOrchestrator。
- 新增 Web 对话接口 `POST /api/conversation/message`。

验收：

```text
Web 后台和 OpenClaw 发送同一句话
返回同样的 intent、status 和追问逻辑
```

### 阶段 3：接入 AutoGEO 标准业务链路

目标：

```text
自然语言可以创建真实生成或发布任务。
```

任务：

- 从 `FeishuTaskHandler` 抽出 `AgentTaskHandler`。
- 接入项目解析。
- 接入关键词蒸馏。
- 接入文章生成。
- 接入质量检查。
- 接入账号过滤。
- 创建 `auto_publish_task`。

验收：

```text
已绑定用户说“帮我写一篇关于智慧物流的文章发到知乎”
系统创建对应文章生成任务或 auto_publish_task
任务 triggered_by_user_id 是该绑定用户
发布账号属于该用户
```

### 阶段 4：多轮追问与状态保存

目标：

```text
用户信息不完整时不失败，而是追问并继续原任务。
```

任务：

- 新增 `conversation_sessions`。
- 保存 slots。
- 支持 `need_clarification`。
- 支持用户补充项目、平台、主题后继续执行。

验收：

```text
用户：帮我发一篇文章
系统：请告诉我要使用哪个项目，以及发布到哪个平台
用户：小爱科技，知乎，主题智慧物流
系统继续执行同一个任务
```

### 阶段 5：统一外部身份模型

目标：

```text
飞书、OpenClaw、企业微信等都能走同一套绑定和权限模型。
```

任务：

- 新增 `external_user_bindings`。
- 将飞书绑定迁移或同步到通用绑定表。
- Agent Command API 统一查 `external_user_bindings`。
- `/api/feishu/webhook` 保留，但内部也走统一身份服务。

验收：

```text
同一个 AutoGEO 用户可以绑定多个外部身份
任意外部入口触发任务时，权限仍然只按 system_user_id 控制
```

## 11. 项目难点

### 难点 1：身份绑定必须可信

最容易出问题的地方是外部平台冒充用户。解决方式是：

- 只允许后台登录用户生成绑定码。
- 绑定码短期有效、一次性使用。
- 外部身份必须来自平台事件，不从用户文本里提取。
- 每次命令都通过绑定表解析 `system_user_id`。

### 难点 2：OpenClaw 与飞书身份字段要对齐

需要确认 OpenClaw Feishu Channel 传给 Skill 的用户 ID 到底是：

- 飞书 `open_id`
- 飞书 `union_id`
- OpenClaw 自己生成的 user id

如果传的是 OpenClaw 自己的 ID，则不能直接复用 `feishu_user_bindings.open_id`，必须建立 OpenClaw 身份到飞书身份或 AutoGEO 用户的绑定关系。

### 难点 3：业务编排不能继续绑死飞书

现在已有 `FeishuIntentParser` 和 `FeishuTaskHandler`。短期可复用，但长期如果所有能力都写在飞书模块里，Web 和 OpenClaw 会被迫绕路。

需要逐步拆成：

```text
IntentParser           通用意图解析
ConversationOrchestrator 通用对话编排
AgentTaskHandler       通用任务编排
FeishuTaskHandler      飞书适配
OpenClaw Skill         外部适配
```

### 难点 4：多轮对话不能靠模型记忆

不能让模型自己“记得”项目、账号和用户。必须用结构化 `slots` 保存状态，并且每个关键 ID 都由代码查库确认。

### 难点 5：自动发布有误操作风险

用户一句话可能表达不完整或被误解。建议第一版策略保守：

- 信息不完整就追问。
- 多账号、多平台就追问。
- 质检未通过不发布。
- 首期可以先创建草稿或待确认任务。
- 发布前可支持 `confirm_required`。

### 难点 6：异步任务结果回传

文章生成、质检、发布都可能是异步的。外部会话需要知道：

- 已受理
- 处理中
- 需要补充信息
- 需要人工审核
- 已完成
- 失败原因

所以任务必须有 `trace_id`、`task_id`、`source/channel/external_chat_id`，否则很难把结果发回原会话。

### 难点 7：权限过滤要贯穿所有查询

项目、文章、关键词、发布账号、任务记录都要落在当前 `system_user_id` 或其项目成员权限范围内。不能只在入口校验一次。

## 12. 需要你提供或确认的内容

### 12.1 飞书侧

- 飞书机器人 App ID。
- 飞书机器人 App Secret。
- 飞书事件订阅配置。
- 飞书 Webhook URL。
- 是否使用飞书原生 Webhook、OpenClaw Feishu Channel，还是两者并行。
- 飞书事件里能拿到的用户字段：`open_id`、`union_id`、`user_id` 分别有哪些。
- 是否允许群聊触发任务。
- 群聊是否必须 @机器人。
- 测试用户和测试群 allowlist。

### 12.2 OpenClaw 侧

- OpenClaw 服务部署地址。
- OpenClaw 是否已经配置 Feishu Channel。
- OpenClaw Skill 能拿到的用户字段名称。
- OpenClaw 调 AutoGEO 的服务端环境变量：
  - `AUTOGEO_BASE_URL`
  - `AUTOGEO_AGENT_TOKEN`
- 是否允许 OpenClaw 作为飞书主入口，还是只做旁路测试。

### 12.3 AutoGEO 后台侧

- 后台用户表 `users` 的登录态获取方式。
- 当前项目权限模型：
  - 项目是否只属于单个用户
  - 是否使用 `project_members`
  - 默认项目存在哪里
- 当前发布账号模型：
  - `Account.user_id` 是否是唯一权限依据
  - 平台字段取值，例如 `zhihu`、`xiaohongshu`
- 当前文章生成接口或服务调用方式。
- 当前质量检查服务是否已有明确通过/失败状态。
- 当前自动发布任务创建字段要求。

### 12.4 安全与产品策略

- 绑定码有效期，建议 30 分钟。
- 是否允许一个飞书账号绑定多个 AutoGEO 用户，建议不允许。
- 是否允许一个 AutoGEO 用户绑定多个飞书/OpenClaw 身份，建议允许。
- 生成后是否自动发布，还是先草稿/待确认。
- 哪些平台属于高风险发布，需要二次确认。
- 任务失败后是否要自动重试。

## 13. 推荐的当前决策

当前不要把 OpenClaw 直接放进 AutoGEO 核心业务，也不要删除飞书原生 Webhook。

推荐路线：

```text
1. 保留飞书原生 Webhook，保证现有飞书链路可用。
2. 保留并完善 /api/integrations/agent-command。
3. 先让 OpenClaw Skill 只负责转发自然语言和外部身份。
4. 新增 ConversationOrchestrator，让 Web、飞书、OpenClaw 统一调用。
5. 把 FeishuTaskHandler 中的业务编排逐步抽成 AgentTaskHandler。
6. 最后再决定飞书消息是否全部经 OpenClaw 进入。
```

最小可交付版本：

```text
后台生成绑定码
飞书用户完成绑定
OpenClaw 或飞书把自然语言发给 AutoGEO
AutoGEO 解析出 system_user_id
AutoGEO 解析意图
AutoGEO 检查项目和账号
信息完整则创建任务
信息不完整则追问
结果能回到原会话
```

这才是两个原方案真正联合起来后的闭环。
