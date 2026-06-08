# OpenClaw / 飞书接入 AutoGEO 标准工作流规划

## 1. 目标

本规划的目标不是先把所有自动化发布能力一次性做完，而是先解决当前最大的难点：

> 让飞书、OpenClaw 或其他工具平台可以稳定、安全地连接到 AutoGEO，并用一段自然语言触发 AutoGEO 的标准工作流程。

目标自然语言示例：

```text
帮我写一篇关于智慧物流的文章，发布到知乎
```

期望结果：

```text
外部平台收到用户消息
-> AutoGEO 识别用户身份
-> 解析意图
-> 解析项目和知识库
-> 准备关键词
-> 生成文章
-> 质检
-> 使用该用户自己的平台账号发布
-> 把结果回传到飞书或 OpenClaw 会话
```

## 2. 现有基础

AutoGEO 当前已经具备一部分飞书链路基础：

- 飞书 Webhook 入口：`POST /api/feishu/webhook`
- 飞书事件落库：`feishu_events`
- 飞书用户绑定：`feishu_user_bindings`
- 飞书绑定码：`feishu_binding_codes`
- 飞书任务编排器：`FeishuTaskHandler`
- 意图解析器：`FeishuIntentParser`
- 自动发布任务：`auto_publish_tasks` / `auto_publish_records`
- 用户账号隔离：发布账号按 `Account.user_id == system_user_id` 过滤

但如果要接 OpenClaw，建议不要直接让 OpenClaw 操作数据库，也不要让 OpenClaw 自己理解所有业务表。更好的方式是增加一个稳定的「外部 Agent 指令入口」。

## 3. 推荐架构

推荐采用三层架构：

```text
飞书 / OpenClaw / 其他工具平台
        |
        v
外部 Agent 连接层
        |
        v
AutoGEO Agent Command API
        |
        v
AutoGEO 标准业务编排器
```

其中：

- 飞书原生接入：继续使用 `/api/feishu/webhook`
- OpenClaw 接入：先做一个 OpenClaw Skill，通过 HTTP 调用 AutoGEO
- 其他平台：未来也调用同一个 Agent Command API

这样做的好处是：

- 外部工具只负责收消息和转发
- AutoGEO 负责身份、权限、项目、知识库、生成、质检、发布
- 不会因为接入多个平台导致业务逻辑分叉

## 4. 两种接入路径

### 4.1 路径 A：飞书直接接 AutoGEO

适合当前最小闭环。

```text
飞书机器人
-> POST /api/feishu/webhook
-> FeishuIntentParser
-> FeishuTaskHandler
-> AutoGEO 业务流程
-> 飞书回传结果
```

优点：

- 链路最短
- 当前代码已经有基础
- 用户 `open_id` 到系统用户的绑定清晰

缺点：

- 每个平台都要自己做事件接入
- 后续接企业微信、Slack、Telegram 时会重复写连接层

### 4.2 路径 B：OpenClaw 作为统一入口

适合后续多平台扩展。

```text
飞书
-> OpenClaw Feishu Channel
-> OpenClaw AutoGEO Skill
-> POST /api/integrations/agent-command
-> AutoGEO 业务流程
-> OpenClaw 回复飞书
```

优点：

- OpenClaw 已支持 Feishu 通道
- 可复用 OpenClaw 的多渠道入口能力
- 未来接其他聊天平台更轻

缺点：

- 多一层身份映射
- 要设计 OpenClaw 用户和 AutoGEO 用户的绑定关系
- 权限边界必须收紧，不能让 OpenClaw 获得数据库或本机任意操作能力

## 5. 第一阶段建议：先做 OpenClaw Skill

第一阶段不建议重写 AutoGEO 的飞书链路，也不建议让 OpenClaw 直接接管业务。建议先做一个很薄的 OpenClaw Skill：

```text
Skill 名称：autogeo-publish
职责：把用户自然语言和外部身份传给 AutoGEO
不负责：解析业务权限、查数据库、发布平台账号、执行 Playwright
```

Skill 的行为：

```text
当用户要求生成、发布、查询 AutoGEO 任务时：
1. 提取用户原始消息
2. 读取当前平台身份，例如 feishu open_id / chat_id
3. 调用 AutoGEO Agent Command API
4. 将 AutoGEO 返回的进度或结果回复给用户
```

## 6. 新增统一入口 API 规划

建议新增接口：

```text
POST /api/integrations/agent-command
```

请求头：

```http
X-AutoGEO-Agent-Token: <server-side-secret>
Content-Type: application/json
```

请求体：

```json
{
  "source": "openclaw",
  "channel": "feishu",
  "external_user_id": "ou_xxx",
  "external_chat_id": "oc_xxx",
  "message": "帮我写一篇关于智慧物流的文章，发布到知乎",
  "raw_event": {
    "optional": "debug payload"
  }
}
```

响应体：

```json
{
  "success": true,
  "task_id": 123,
  "status": "accepted",
  "reply": "收到，正在为你生成文章并准备发布到知乎。",
  "trace_id": "agent_20260604_xxx"
}
```

失败响应：

```json
{
  "success": false,
  "status": "binding_required",
  "reply": "你还没有绑定 AutoGEO 系统账号，请先完成绑定。",
  "bind_hint": "请发送：绑定 <绑定码>"
}
```

## 7. 身份绑定模型

当前飞书已有：

```text
feishu_user_bindings.open_id -> users.id
```

为了支持 OpenClaw 和其他平台，建议新增一张通用外部身份表，或先复用飞书绑定表做过渡。

推荐长期表结构：

```text
external_user_bindings(
  id,
  source,              -- openclaw / feishu / wechat / slack
  channel,             -- feishu / telegram / web
  external_user_id,    -- ou_xxx
  external_chat_id,
  system_user_id,
  default_client_id,
  default_project_id,
  status,
  created_at,
  updated_at
)
```

第一阶段可以先不建新表，OpenClaw 的 Feishu 通道仍然把 `external_user_id` 传成飞书 `open_id`，AutoGEO 继续查 `feishu_user_bindings`。

## 8. AutoGEO 标准工作流

统一入口最终应该调用同一套业务编排流程：

```text
1. 接收自然语言命令
2. 校验来源 token
3. 根据 source/channel/external_user_id 找系统用户
4. 未绑定则返回绑定提示
5. 调用意图解析
6. 解析目标平台
7. 解析项目
8. 准备关键词
9. 调 n8n / AI 生成文章
10. 等待文章生成完成
11. 执行质量检查
12. 质检未通过则进入 review_required
13. 查找该系统用户自己的发布账号
14. 创建 auto_publish_task
15. 后台执行 Playwright 发布
16. 返回任务状态和结果
```

关键边界：

- 外部工具不能指定 `system_user_id`
- 外部工具不能指定任意 `account_id`
- 外部工具不能绕过绑定表
- 外部工具不能直接调用发布器
- 所有项目、文章、账号查询必须落到当前系统用户作用域内

## 9. OpenClaw Skill 草案

Skill 文件名建议：

```text
autogeo-publish/SKILL.md
```

Skill 内容草案：

```markdown
# AutoGEO Publish

Use this skill when the user asks to generate, draft, publish, or check status for AutoGEO content tasks.

## Behavior

1. Send the user's original instruction to AutoGEO.
2. Include the current channel, user id, and chat id when available.
3. Do not invent project ids, account ids, or platform account names.
4. If AutoGEO returns binding_required, tell the user to bind their AutoGEO account.
5. If AutoGEO returns accepted, show the reply and task id.
6. If AutoGEO returns review_required, tell the user the article needs manual review.

## API

POST {AUTOGEO_BASE_URL}/api/integrations/agent-command

Headers:
- X-AutoGEO-Agent-Token: {AUTOGEO_AGENT_TOKEN}

Body:
{
  "source": "openclaw",
  "channel": "{channel}",
  "external_user_id": "{user_id}",
  "external_chat_id": "{chat_id}",
  "message": "{user_message}"
}
```

第一阶段可以不做复杂工具调用，只让 Skill 调一个 HTTP API。这样 OpenClaw 是入口，AutoGEO 是业务大脑。

## 10. OpenClaw 侧配置要点

根据 OpenClaw Feishu 文档，Feishu 通道可通过以下方式登录配置：

```bash
openclaw channels login --channel feishu
openclaw gateway restart
```

OpenClaw 文档说明 Feishu 通道支持 DM 和群聊，默认 WebSocket 模式，Webhook 模式可选；DM 可通过 `dmPolicy` 控制，群聊可通过 `groupPolicy` 和 `requireMention` 控制。

建议第一阶段：

```text
dmPolicy = allowlist
groupPolicy = allowlist
requireMention = true
```

也就是说：

- 先只允许指定测试用户私聊机器人
- 群聊先只允许测试群
- 群聊必须 @机器人 才响应

参考：

- OpenClaw Feishu channel: https://github.com/openclaw/openclaw/blob/main/docs/channels/feishu.md
- OpenClaw docs: https://docs.openclaw.ai/

## 11. 分阶段实施计划

### 阶段 0：确认最小可用链路

目标：AutoGEO 后端能接收一个模拟外部命令。

任务：

- 新增 `POST /api/integrations/agent-command`
- 用固定 token 做来源校验
- 接收 `message / source / channel / external_user_id`
- 临时复用 `feishu_user_bindings` 查用户
- 调用现有 `FeishuIntentParser`
- 返回解析结果，不真正发布

验收：

```text
curl 调接口，输入“帮我写一篇文章发到知乎”，能返回 action=generate_and_publish。
```

### 阶段 1：打通 AutoGEO 内部标准流程

目标：不用飞书，也不用 OpenClaw，只通过 Agent Command API 触发完整任务。

任务：

- Agent Command API 调用统一任务编排器
- 未绑定返回 `binding_required`
- 无默认项目返回 `project_required`
- 无授权账号返回 `account_required`
- 有完整配置时创建文章生成任务
- 生成完成后质检
- 质检通过后创建自动发布任务

验收：

```text
curl 调接口，可以创建 auto_publish_task。
```

### 阶段 2：做 OpenClaw Skill

目标：OpenClaw 能把自然语言转发给 AutoGEO。

任务：

- 创建 `autogeo-publish/SKILL.md`
- 配置 `AUTOGEO_BASE_URL`
- 配置 `AUTOGEO_AGENT_TOKEN`
- Skill 调用 Agent Command API
- OpenClaw 回复 AutoGEO 返回的 `reply`

验收：

```text
在 OpenClaw 会话里发送“帮我写一篇关于智慧物流的文章发到知乎”，AutoGEO 收到请求并返回任务已受理。
```

### 阶段 3：OpenClaw 接飞书

目标：飞书消息经 OpenClaw 到 AutoGEO。

任务：

- 在 OpenClaw 配置 Feishu channel
- 限制 DM allowlist
- 限制测试群 groupAllowFrom
- 确认 OpenClaw 能拿到 Feishu `open_id`
- Skill 请求中带上 `external_user_id`

验收：

```text
飞书私聊机器人：“任务进度怎么样了”
-> OpenClaw 收到
-> AutoGEO 返回该用户最近任务
-> 飞书显示回复
```

### 阶段 4：补齐绑定与管理界面

目标：用户不用手动调用接口也能完成绑定。

任务：

- 后台页面展示飞书/OpenClaw 绑定状态
- 后台生成绑定码
- 用户在飞书或 OpenClaw 里发送 `绑定 ABC123`
- 绑定成功后可设置默认项目

验收：

```text
新用户可以自助完成绑定，然后发自然语言创建任务。
```

### 阶段 5：多平台入口统一

目标：飞书、OpenClaw、后续微信/企业微信都走同一个入口。

任务：

- 新增 `external_user_bindings`
- 将 `feishu_user_bindings` 迁移或兼容到通用绑定模型
- 所有外部入口统一调用 Agent Command API
- 保留 `/api/feishu/webhook` 作为原生飞书入口

验收：

```text
同一个系统用户可以绑定多个外部身份，但任务权限仍然只按 system_user_id 控制。
```

## 12. 第一阶段接口实现建议

建议新增文件：

```text
backend/api/integrations.py
backend/services/agent_command_handler.py
```

`integrations.py` 只负责：

- 校验 token
- 接收请求
- 调用 `AgentCommandHandler`
- 返回统一响应

`agent_command_handler.py` 负责：

- 根据外部身份找系统用户
- 调用现有意图解析
- 调用现有飞书任务编排器中的可复用逻辑，或抽出通用编排器

中期建议把 `FeishuTaskHandler` 重命名/拆分为：

```text
AgentTaskHandler        -- 通用业务编排
FeishuTaskHandler       -- 飞书消息收发适配
OpenClawTaskAdapter     -- OpenClaw Skill/API 适配
```

## 13. 安全要求

第一阶段最低安全要求：

- Agent Command API 必须有 `X-AutoGEO-Agent-Token`
- token 只存在 AutoGEO 和 OpenClaw 服务端，不出现在前端
- 外部请求不能传 `system_user_id`
- 外部请求不能传 `account_id`
- 所有项目、文章、账号都必须按绑定用户过滤
- 所有任务写入 `source` 和 `external_user_id`
- 所有异常写入日志和事件表

后续增强：

- 使用 HMAC 签名代替固定 token
- 每个外部平台单独 token
- IP allowlist
- 请求重放保护：timestamp + nonce
- 审计表记录原始请求和处理结果

## 14. 推荐当前决策

当前阶段建议：

```text
短期：继续保留原生飞书 webhook，保证飞书直连能跑通
并行：新增 Agent Command API
然后：先做 OpenClaw Skill 调 AutoGEO
最后：再决定是否让 OpenClaw 成为飞书主入口
```

不要一开始就把 OpenClaw 放到核心业务里。它应该先作为入口适配层，而不是替代 AutoGEO 的业务编排器。

## 15. 最小里程碑

第一个可交付版本只需要完成：

```text
1. POST /api/integrations/agent-command
2. OpenClaw Skill: autogeo-publish
3. 通过 Skill 调 AutoGEO 返回任务已受理
4. AutoGEO 内部仍然负责绑定、项目、账号、生成、质检、发布
```

这个版本完成后，用户就可以在 OpenClaw 或飞书里说：

```text
帮我写一篇关于智慧物流的文章发到知乎
```

系统至少能做到：

```text
收到消息
识别用户
解析意图
检查绑定和项目
创建或拒绝任务
返回明确结果
```

然后再逐步把生成、质检、发布、结果卡片做完整。
