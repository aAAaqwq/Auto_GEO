# AutoGEO 发布助手

当用户希望通过 AutoGEO 生成文章、起草内容、发布文章、查询任务进度或绑定账号时，使用本 Skill。

本 Skill 只负责把外部会话里的自然语言指令标准化转发给 AutoGEO。项目识别、知识库选择、账号权限、文章生成、质量检查、自动发布和任务状态都由 AutoGEO 后端处理。

## 适用场景

用户表达以下意图时触发：

- 生成文章：例如“帮我写一篇关于智慧物流的文章”
- 生成并发布：例如“帮我写一篇关于智慧物流的文章，发布到知乎”
- 发布已有文章：例如“把最近生成的文章发到小红书”
- 查询状态：例如“任务进度怎么样了”
- 绑定账号：例如“绑定 ABC123”

如果用户只是闲聊、解释概念、询问非 AutoGEO 任务，不调用 AutoGEO。

## 标准流程

1. 保留用户原始指令，不改写、不补充不存在的信息。
2. 从当前会话环境读取外部身份：
   - `channel`：当前渠道，例如 `feishu`
   - `user_id`：当前渠道用户 ID，例如飞书 `open_id`
   - `chat_id`：当前会话 ID，例如飞书 `chat_id`
3. 组装 Agent Command 请求，固定 `source` 为 `openclaw`。
4. 调用 AutoGEO Agent Command API。
5. 根据 AutoGEO 返回的 `status` 给用户回复。
6. 回复用户时优先使用 AutoGEO 返回的 `reply`，不要自行承诺已发布成功。

## 严格边界

不要做这些事：

- 不要编造 `project_id`、`client_id`、`account_id`、`system_user_id`
- 不要直接操作 AutoGEO 数据库
- 不要绕过 AutoGEO 的绑定、项目、账号和权限校验
- 不要直接调用 Playwright 发布器
- 不要替用户选择平台账号，除非 AutoGEO 返回结果里已经明确指定
- 不要把 `AUTOGEO_AGENT_TOKEN` 展示给用户或写入前端代码

可以做这些事：

- 转发用户原始自然语言指令
- 传递当前外部平台身份
- 展示 AutoGEO 返回的任务状态、解析动作、绑定提示和 trace id
- 在 AutoGEO 要求补充信息时，向用户追问必要信息

## API

请求地址：

```text
POST {AUTOGEO_BASE_URL}/api/integrations/agent-command
```

请求头：

```text
X-AutoGEO-Agent-Token: {AUTOGEO_AGENT_TOKEN}
Content-Type: application/json
```

请求体：

```json
{
  "source": "openclaw",
  "channel": "{channel}",
  "external_user_id": "{user_id}",
  "external_chat_id": "{chat_id}",
  "message": "{user_message}",
  "raw_event": {
    "optional": "保留当前平台原始事件，便于排查问题"
  }
}
```

字段规则：

- `source` 固定为 `openclaw`
- `channel` 使用当前渠道名，飞书为 `feishu`
- `external_user_id` 必须来自平台真实用户身份，飞书场景优先使用 `open_id`
- `external_chat_id` 可以为空，但有会话 ID 时必须传
- `message` 必须是用户原始消息
- `raw_event` 可选，只有当前运行环境能安全取得原始事件时才传

## 返回处理

### accepted

表示 AutoGEO 已接收并解析指令。

回复格式：

```text
{reply}

任务状态：已受理
动作：{action}
追踪 ID：{trace_id}
```

如果返回了 `task_id`，额外显示：

```text
任务 ID：{task_id}
```

### binding_required

表示外部账号还没有绑定 AutoGEO 用户。

回复格式：

```text
{reply}

绑定提示：{bind_hint}
```

不要继续尝试发布或生成。

### project_required

表示用户已绑定，但 AutoGEO 无法确定项目。

回复格式：

```text
{reply}

请补充要使用的公司、客户或项目名称。
```

### account_required

表示没有可用的平台发布账号。

回复格式：

```text
{reply}

请先在 AutoGEO 后台授权对应平台账号。
```

### review_required

表示文章已生成，但需要人工审核。

回复格式：

```text
{reply}

当前内容需要人工审核后才能继续发布。
```

### failed 或 error

表示 AutoGEO 处理失败。

回复格式：

```text
{reply}

追踪 ID：{trace_id}
```

不要猜测失败原因，只展示 AutoGEO 返回的信息。

## 示例

用户：

```text
帮我写一篇关于智慧物流的文章，发布到知乎
```

请求：

```json
{
  "source": "openclaw",
  "channel": "feishu",
  "external_user_id": "ou_xxx",
  "external_chat_id": "oc_xxx",
  "message": "帮我写一篇关于智慧物流的文章，发布到知乎"
}
```

AutoGEO 返回：

```json
{
  "success": true,
  "status": "accepted",
  "reply": "收到，正在为你生成文章并准备发布。",
  "trace_id": "agent_xxx",
  "action": "generate_and_publish",
  "params": {
    "quantity": 1,
    "platforms": ["zhihu"],
    "publish_strategy": "immediate"
  }
}
```

回复用户：

```text
收到，正在为你生成文章并准备发布。

任务状态：已受理
动作：generate_and_publish
追踪 ID：agent_xxx
```
