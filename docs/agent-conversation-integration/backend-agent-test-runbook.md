# 后台 Agent 真实链路测试说明

## 1. 本次要测试什么

目标是测试：

```text
用户用大白话说任务
-> Agent 用大模型抽取字段
-> 缺字段就追问
-> 字段齐全就自动生成文章
-> 生成完成后自动质检
-> 自动创建待确认发布任务
-> 用户确认后发布
```

建议第一轮测试指令：

```text
帮我给小爱科技生成一篇关于智慧物流的文章，发布到知乎
```

## 2. 你需要填写的环境变量

### 2.1 Agent 大模型解析

你说有 `deepseek v4-pro` 的 API Key，请配置：

```env
AUTOGEO_CONVERSATION_USE_LLM=true
AUTOGEO_CONVERSATION_LLM_PROVIDER=deepseek
AUTOGEO_CONVERSATION_LLM_MODEL=deepseek v4-pro
AUTOGEO_CONVERSATION_LLM_API_KEY=你的deepseek-v4-pro-api-key
AUTOGEO_CONVERSATION_LLM_BASE_URL=你的OpenAI兼容BaseURL
```

`AUTOGEO_CONVERSATION_LLM_BASE_URL` 必须是 OpenAI-compatible 的 base URL，后端会调用：

```text
{AUTOGEO_CONVERSATION_LLM_BASE_URL}/chat/completions
```

如果你的服务地址就是 DeepSeek 官方兼容接口，常见形式类似：

```env
AUTOGEO_CONVERSATION_LLM_BASE_URL=https://api.deepseek.com/v1
```

如果是中转服务，请填中转服务给你的 base URL。

### 2.2 后端基础配置

至少需要：

```env
JWT_SECRET_KEY=你的JWT密钥
```

项目当前还要求 RAGFlow 配置存在：

```env
RAGFLOW_API_KEY=你的RAGFlow key
RAGFLOW_BASE_URL=你的RAGFlow地址
```

### 2.3 文章生成链路

Agent 会调用现有：

```text
GeoArticleService.generate
```

它依赖 n8n / AI 生成链路。请确认：

```env
N8N_WEBHOOK_URL=你的n8n webhook基础地址
N8N_TIMEOUT=300
N8N_CALLBACK_URL=http://127.0.0.1:8001/api/geo/callback
```

并确认 n8n 中至少这些能力可用：

```text
generate_geo_article
keyword-distill
```

### 2.4 发布账号

测试“发布到知乎”前，需要后台账号表里有：

```text
platform = zhihu
status = 1
user_id = 当前登录用户 ID
storage_state 或 cookies 有效
deleted_at = null
```

否则 Agent 会返回：

```text
你还没有可用的 zhihu 发布账号，请先在账号管理里完成授权。
```

### 2.5 项目数据

需要至少有一个可用项目：

```text
项目名包含：小爱科技
status = 1
domain_keyword 可选但建议填写
company_name 建议填写
```

如果有 `ProjectMember` 权限模型，请确保当前登录用户能访问该项目。

## 3. 推荐测试顺序

### 测试 1：字段齐全的一句话

输入：

```text
帮我给小爱科技生成一篇关于智慧物流的文章，发布到知乎
```

预期：

```text
1. Agent 识别 intent=generate_and_publish
2. slots 中有 topic=智慧物流
3. slots 中有 project_hint=小爱科技
4. slots 中有 platforms=[zhihu]
5. 后端解析出 project_id
6. 后端解析出 account_ids
7. 开始生成文章
```

如果文章生成是异步的，Agent 会返回：

```text
文章生成任务已启动，文章 ID：xxx。我会在生成完成后自动质检，并创建待确认发布任务。
```

### 测试 2：缺少主题

输入：

```text
帮我给小爱科技发布到知乎
```

预期：

```text
Agent 追问：这篇文章的主题是什么？
```

继续输入：

```text
主题是智慧物流
```

预期：

```text
Agent 合并上一轮 slots，然后继续执行。
```

### 测试 3：缺少项目

输入：

```text
帮我生成一篇关于智慧物流的文章，发布到知乎
```

预期：

如果当前用户只有一个可用项目：

```text
Agent 自动使用唯一项目
```

如果多个项目：

```text
Agent 追问使用哪个项目
```

### 测试 4：确认发布

当 Agent 创建待确认任务后，输入：

```text
确认发布
```

预期：

```text
Agent 校验 task.triggered_by_user_id == 当前用户
然后调用 execute_auto_publish_task
```

## 4. 当前安全策略

当前默认策略：

```text
生成文章：自动执行
质检：自动执行
创建待确认发布任务：自动执行
真正发布：必须用户确认
```

这样可以避免模型误判后直接向知乎发错内容。

## 5. 常见失败原因

### 5.1 模型没有启用

表现：

```text
前端解析器显示 local_rules
```

检查：

```env
AUTOGEO_CONVERSATION_USE_LLM=true
AUTOGEO_CONVERSATION_LLM_API_KEY=是否填写
AUTOGEO_CONVERSATION_LLM_BASE_URL=是否正确
AUTOGEO_CONVERSATION_LLM_MODEL=deepseek v4-pro
```

### 5.2 找不到项目

表现：

```text
请告诉我要使用哪个项目或客户
```

检查：

```text
项目是否存在
项目 status 是否为 1
当前用户是否有权限访问
```

### 5.3 找不到知乎账号

表现：

```text
你还没有可用的 zhihu 发布账号
```

检查：

```text
accounts.platform = zhihu
accounts.user_id = 当前用户
accounts.status = 1
accounts.deleted_at is null
storage_state/cookies 是否有效
```

### 5.4 文章生成失败

表现：

```text
文章生成任务启动失败
```

检查：

```text
n8n 是否可用
generate_geo_article webhook 是否可用
RAGFlow 是否可用
N8N_WEBHOOK_URL 是否配置
```

### 5.5 生成后没有自动进入待确认

当前后台会等待最多约 10 分钟：

```text
60 次 * 10 秒
```

如果 n8n 异步回调很慢，或者文章状态一直不是 `completed`，Agent 不会创建发布任务。

检查：

```text
geo_articles.publish_status 是否变成 completed
geo_articles.content 是否已更新
```

## 6. 测试时你需要给我的信息

请不要直接把 API Key 发在聊天里。你只需要告诉我这些非敏感信息：

```text
1. deepseek v4-pro 的 base URL 是什么？
2. 你的服务是否 OpenAI-compatible？
3. 当前测试用户 ID 是多少？
4. 测试项目名是什么？
5. 知乎账号是否已经授权？
6. n8n 文章生成链路是否已经能单独跑通？
```

API Key 请写入本地 `.env` 或启动环境变量。
