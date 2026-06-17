# 基于飞书的自动化内容发布系统设计方案

## 1. 目标与边界

本方案用于支持用户在飞书中通过自然语言触发内容生成与自动发布。例如用户发送“帮我发一篇文章到知乎”，系统能够识别发送者身份，找到该用户绑定的项目、公司、知识库和发布账号，自动完成关键词蒸馏、文章生成、质量检查和平台发布，并将进度与结果回传到飞书。

系统的核心目标不是简单地“飞书触发一次全局发布”，而是实现严格的用户级闭环：

- 飞书用户只能使用自己绑定的系统用户身份。
- 用户只能访问自己有权限的客户、项目、知识库和平台账号。
- 文章只能发布到该用户已授权且可用的账号。
- 任何无法确定归属的步骤都必须停止并提示用户补齐绑定信息，而不是回退到全局默认数据。

本方案默认先支持单篇文章即时发布，随后扩展到批量生成、定时发布、多账号分发和人工审核模式。

## 2. 总体架构

系统采用事件驱动的异步管道架构，以飞书机器人为统一入口，串联以下核心模块：

1. 飞书 Webhook 接收与验签
2. 飞书 open_id 到系统用户的绑定解析
3. 自然语言意图解析
4. 用户作用域内的项目、公司、知识库和账号解析
5. 关键词提取、蒸馏、去重和随机选择
6. RAGFlow 知识库检索
7. AI 文章生成与质量检查
8. 多平台 Playwright 自动发布
9. 飞书进度通知、结果卡片和异常引导

运行时基座是一套基于 FastAPI 的异步 Web 服务。飞书 Webhook 回调地址建议为：

```text
POST /api/feishu/webhook
```

Webhook 入口只负责完成验签、去重、事件落库和快速返回。真正耗时的意图解析、内容生成和发布执行由后台任务队列处理。生产环境不建议只使用 `asyncio.create_task` 承载关键任务，应使用 Redis Stream、Celery、RQ、Dramatiq 或数据库任务表实现可恢复的异步队列。

## 3. 飞书接入与消息接收

飞书机器人的接入依托飞书开放平台的企业自建应用。需要配置 App ID、App Secret、Verification Token 和 Encrypt Key，并订阅 `im.message.receive_v1` 事件。

Webhook 接收流程如下：

1. 读取原始请求体，不提前修改 body 内容。
2. 处理飞书 URL verification challenge。
3. 校验 Verification Token。
4. 使用 `timestamp + nonce + encrypt_key + body` 计算 SHA256 摘要，校验 `X-Lark-Signature`。
5. 解析事件类型和 `event_id`。
6. 将原始事件写入持久化事件表或消息队列。
7. 对 `event_id` 做幂等检查。
8. 立即返回 `200`，异步启动后续处理。

需要支持的消息类型：

- `text`：读取 `$.event.message.content.text`
- `post`：遍历富文本 content 数组，拼接所有 `tag=text` 的文本

消息中必须提取并保存：

- `event_id`：用于幂等
- `message_id`：用于排查和后续引用
- `chat_id`：用于飞书回信
- `open_id`：用于绑定系统用户
- `sender_type`：过滤机器人自身消息
- `raw_text`：用户原始指令

`event_id` 不应只放在内存集合中。内存去重在服务重启后会失效，生产环境应建表：

```text
feishu_events(
  id,
  event_id unique,
  message_id,
  open_id,
  chat_id,
  raw_payload,
  raw_text,
  status,
  error_msg,
  created_at,
  processed_at
)
```

## 4. 用户绑定与权限模型

这是本方案最关键的部分。飞书入口必须先解决“这个 open_id 对应系统里的谁”，否则后续项目、知识库和发布账号都会有串租户风险。

建议新增绑定表：

```text
feishu_user_bindings(
  id,
  open_id unique,
  union_id nullable,
  system_user_id,
  default_client_id nullable,
  default_project_id nullable,
  status,
  created_at,
  updated_at
)
```

绑定流程：

1. 管理后台生成绑定码或绑定链接。
2. 用户在飞书中发送“绑定 xxxx”或点击链接完成绑定。
3. 后端将飞书 `open_id` 绑定到系统 `users.id`。
4. 可选配置默认客户、默认项目和默认发布账号。

每次飞书消息处理时，第一步必须执行：

```text
open_id -> feishu_user_bindings -> system_user_id
```

如果未绑定，系统不继续执行任务，直接回复：

```text
你还没有绑定系统账号。请先在管理后台完成飞书绑定后再发起发布任务。
```

权限边界：

- 查询账号必须加 `Account.user_id == system_user_id`
- 查询账号分组必须加 `AccountGroup.user_id == system_user_id`
- 查询用户默认项目必须从绑定表或授权关系表读取
- 查询客户和项目不能随意取“第一个 active 项目”
- 查询知识库必须从当前用户有权限的 client/project 出发
- 查询最近文章、最近发布任务也必须按用户或项目过滤

如果未来支持团队协作，建议增加项目成员表：

```text
project_members(
  id,
  project_id,
  user_id,
  role,
  created_at
)
```

这样用户可以访问自己拥有或被授权的项目，而不是只能访问自己创建的项目。

## 5. 用户指令解析

意图解析采用“AI 优先、规则兜底”的双路策略。AI 解析器将用户消息转化为结构化命令：

```json
{
  "action": "generate_and_publish",
  "params": {
    "company_name": "",
    "project_name": "",
    "keywords": [],
    "quantity": 1,
    "platforms": ["zhihu"],
    "account_name": "",
    "publish_strategy": "immediate",
    "scheduled_at": null,
    "need_review": false
  },
  "reply": "收到，我会为你生成 1 篇文章并发布到知乎。"
}
```

动作类型：

- `generate_and_publish`：生成文章并发布
- `generate`：只生成草稿
- `publish`：发布已有文章
- `query_status`：查询任务状态
- `bind_help`：绑定说明
- `unknown`：无法识别

解析规则：

- 用户明确说“发到知乎”时，`platforms=["zhihu"]`
- 用户只说“发一篇文章”但未指定平台时，不自动猜测平台，应提示用户指定平台或使用默认发布配置
- 用户未指定公司或项目时，使用该飞书用户绑定的默认项目
- 如果该用户有多个项目且没有默认项目，必须让用户选择，不能随机使用全局项目
- 用户明确说“先生成草稿”“我确认后再发”时，`publish_strategy="draft"` 或 `need_review=true`
- 用户指定账号名时，后续账号查询必须按该账号名过滤

规则兜底只负责基础场景，不能绕过用户绑定和权限检查。

## 6. 项目、公司与知识库解析

任务编排阶段需要将命令参数解析为确定的业务上下文：

```text
TaskContext(
  system_user_id,
  open_id,
  chat_id,
  client_id,
  project_id,
  company_name,
  ragflow_dataset_ids,
  target_platforms,
  account_ids
)
```

项目解析优先级：

1. 用户命令中明确指定的项目名或公司名
2. 飞书绑定表中的 `default_project_id`
3. 用户唯一可访问的 active 项目
4. 无法唯一确定时，飞书回复候选项目列表，让用户补充说明

禁止使用以下兜底方式：

- 任意取数据库第一个 active 项目
- 任意取最新创建项目
- 任意取全局客户

知识库解析必须从项目关联客户出发：

```text
project -> client -> knowledge_categories / ragflow_dataset_id
```

如果项目没有可用知识库，系统可以降级生成通用行业文章，但必须明确记录 warning，并在飞书中提示：

```text
当前项目没有检索到专属知识库资料，本次文章将基于通用行业信息生成，不会编造具体资质、案例、价格或客户名称。
```

更推荐的策略是：没有知识库时只生成草稿，不自动发布。

## 7. 关键词蒸馏与随机选择

关键词流程需要真正落地，而不是只从已有关键词表取前几个。

输入来源优先级：

1. 用户显式指定关键词，例如“围绕智能仓储写一篇”
2. 用户消息中抽取的业务主题，例如“智慧物流”
3. 项目配置的 `domain_keyword`
4. 项目已有 active 关键词池

当用户没有显式指定关键词时，系统应调用关键词蒸馏服务，例如：

```text
POST /api/keywords/distill
```

请求参数建议包含：

```json
{
  "project_id": 123,
  "core_kw": "智慧物流",
  "target_info": "某某科技有限公司",
  "count": 10
}
```

蒸馏结果进入候选池后，需要执行过滤和加权：

- 过滤空词、过短词、明显无关词
- 过滤与平台规则冲突的敏感词
- 同一项目下近 N 天已发布过的关键词降权
- 使用次数超过阈值的关键词降权
- 与最近文章标题相似度过高的关键词降权
- 保留一定随机性，避免内容同质化

最终选择策略建议为“加权随机”：

```text
score = relevance_score * freshness_weight * platform_fit_weight * random_factor
```

被选中的关键词需要写入使用历史：

```text
keyword_usage_records(
  id,
  project_id,
  keyword_id nullable,
  keyword_text,
  article_id nullable,
  source,
  used_by_user_id,
  used_at
)
```

这样后续可以持续降低重复选题概率。

## 8. 文章生成与质量检查

文章生成由 `GeoArticleService` 负责，生成前需要组装完整上下文：

- 当前系统用户
- 项目 ID
- 客户 ID
- 公司名称
- 目标平台
- 被选中的关键词
- RAGFlow 检索上下文
- 用户补充要求
- 平台风格规则

RAGFlow 检索建议使用多查询策略：

- `{keyword} {company_name}`
- `{keyword} 产品 服务 解决方案 应用场景`
- `{keyword} 行业痛点 用户需求 常见问题`
- `{company_name} 公司介绍 核心优势 案例 资质`

Prompt 必须包含知识约束：

- 优先基于知识库材料写作
- 不编造资料中没有的资质、案例、价格、客户名称和承诺
- 知识库不足时可以补充通用行业观点，但必须保守表达
- 输出结构化 JSON：标题、摘要、正文、标签、建议平台、风险提示

生成完成后进入质量检查：

- `quality_score`：内容完整性、结构、可读性
- `fact_risk_score`：事实风险和幻觉风险
- `platform_risk_score`：是否可能违反目标平台规则
- `duplication_score`：与历史文章相似度

自动发布阈值建议：

```text
quality_score >= 75
fact_risk_score <= 30
platform_risk_score <= 30
duplication_score <= 70
```

低于阈值时，文章状态设为 `review_required`，飞书通知用户或运营人员审核，不进入自动发布。

## 9. 发布账号选择与多平台发布

发布账号选择必须在用户作用域内执行：

```text
Account.user_id == system_user_id
Account.platform in target_platforms
Account.status == 1
Account.deleted_at is null
```

账号选择优先级：

1. 用户指令中指定的账号名
2. 用户在项目中配置的默认账号
3. 用户在该平台下唯一可用账号
4. 多个账号可用时，让用户选择或使用明确配置的默认策略

禁止在飞书任务中使用全局任意账号。

发布执行采用 Playwright 平台适配器。每个平台一个 Publisher，例如：

- `zhihu`
- `baijiahao`
- `sohu`
- `toutiao`
- `xiaohongshu`

所有发布器继承统一基类，提供以下标准方法：

- 打开创作页
- 注入登录态
- 填充标题
- 填充正文
- 处理封面或标签
- 勾选 AI 内容声明
- 点击发布或保存草稿
- 等待结果
- 返回平台链接或错误信息

发布任务表建议区分主任务和子任务：

```text
auto_publish_tasks(
  id,
  triggered_by_user_id,
  source,
  feishu_event_id,
  article_ids,
  account_ids,
  status,
  total_count,
  completed_count,
  failed_count,
  created_at,
  started_at,
  completed_at
)
```

```text
auto_publish_records(
  id,
  task_id,
  article_id,
  account_id,
  platform,
  status,
  platform_url,
  error_msg,
  retry_count,
  created_at,
  started_at,
  completed_at
)
```

后台执行任务时应重新创建数据库 Session，不要把 Webhook 请求中的 Session 传入后台任务。每个子任务都要有超时、重试和资源清理：

- 单个发布子任务超时：5 到 10 分钟
- 浏览器必须在 `finally` 中关闭
- 登录态失效时将账号标记为 `expired`
- 遇到验证码时进入 `manual_required`
- 截图和 HTML 快照写入 debug 目录

## 10. 飞书进度与交互

飞书消息不是只在最后通知一次，而应覆盖关键节点：

1. 已收到任务
2. 已识别用户与项目
3. 正在蒸馏关键词
4. 已选定关键词
5. 正在检索知识库
6. 正在生成文章
7. 质量检查通过或需要审核
8. 正在发布到目标平台
9. 发布成功或失败

结果卡片建议包含：

- 项目/公司
- 关键词
- 文章标题
- 目标平台
- 发布账号
- 发布状态
- 平台链接
- 错误原因
- 重新授权或重试入口

对于需要用户补充信息的情况，应通过飞书直接提示。例如：

- 未绑定系统账号
- 未配置默认项目
- 指定平台没有授权账号
- 多个项目匹配，需要用户补充公司名或项目名
- 多个账号匹配，需要用户指定账号
- 内容质量未达自动发布阈值，需要审核

## 11. 端到端数据流示例

用户在飞书发送：

```text
帮我写一篇关于智慧物流的文章发到知乎
```

完整流程：

1. 飞书推送事件到 `/api/feishu/webhook`。
2. 后端验签、去重、事件落库并返回 200。
3. 后台任务根据 `open_id` 查找 `feishu_user_bindings`。
4. 如果未绑定，回复绑定提示并结束。
5. 如果已绑定，得到 `system_user_id`。
6. 意图解析得到 `generate_and_publish`、`platforms=["zhihu"]`、`quantity=1`。
7. 解析项目：优先使用用户默认项目；如无法唯一确定，提示用户指定项目。
8. 从项目解析公司名、客户 ID 和 RAGFlow dataset。
9. 未显式指定关键词，调用关键词蒸馏服务生成候选词。
10. 对候选词按历史使用、相关度和随机因子加权，选中一个关键词。
11. 使用关键词和项目知识库检索 RAGFlow。
12. 组装 Prompt，调用 n8n 或模型 API 生成文章。
13. 保存到 `GeoArticle`，写入 `project_id`、`keyword_id`、`created_by_user_id` 等归属字段。
14. 执行质量检查。若不达标，状态设为 `review_required` 并通知用户。
15. 查询当前用户名下可用的知乎账号。
16. 如果没有账号，通知用户授权知乎账号并结束。
17. 创建 `AutoPublishTask` 和 `AutoPublishRecord`。
18. 后台发布任务启动 Playwright，注入该账号登录态，发布文章。
19. 更新发布记录和文章状态。
20. 飞书发送结果卡片，包含标题、状态和知乎链接。

## 12. 定时任务与批量运营

定时任务应复用同一套用户作用域和项目作用域，不应绕过绑定逻辑。定时任务配置需要明确：

- 创建人 `user_id`
- 项目 ID
- 目标平台
- 目标账号
- 关键词来源
- 生成数量
- 审核策略
- 调度规则

执行时仍需检查：

- 用户是否仍有项目权限
- 账号是否仍有效
- 知识库是否可用
- 关键词是否重复过高
- 内容质量是否达到自动发布阈值

定时任务适合批量运营，但默认建议先生成草稿或进入审核队列，确认稳定后再开启全自动发布。

## 13. 风险与应对

### 13.1 飞书事件丢失

风险：后端服务宕机或处理异常导致事件丢失。

应对：Webhook 入口先落库或写入 Redis Stream，再返回 200。后台消费者基于事件表状态重试，保证可恢复。

### 13.2 重复消费

风险：飞书重试、队列重放或服务重启导致同一消息重复执行。

应对：`event_id` 建唯一索引，任务表记录 `feishu_event_id`，生成和发布均做幂等检查。

### 13.3 多租户越权

风险：用户 A 使用用户 B 的项目、知识库或账号。

应对：所有业务查询强制带 `system_user_id` 或项目成员权限过滤。禁止全局默认项目、全局默认账号兜底。

### 13.4 知识库串用

风险：文章使用了错误客户的 RAGFlow dataset。

应对：dataset 只能通过当前项目关联客户解析，知识库分类必须带 client/project 归属标识。

### 13.5 内容幻觉

风险：AI 编造案例、价格、资质或承诺。

应对：Prompt 强约束、质量检查、事实风险评分、低分进入审核，不自动发布。

### 13.6 内容同质化

风险：长期围绕同一关键词生成类似文章。

应对：关键词使用历史、标题相似度检查、候选词降权、加权随机和去重 Prompt。

### 13.7 平台登录态过期

风险：cookies 或 storage_state 过期导致发布失败。

应对：发布前检测登录态；失败时识别登录态失效，将账号标记为 `expired`，飞书通知用户重新授权。

### 13.8 Playwright 资源泄露

风险：浏览器实例未关闭导致内存上涨。

应对：每个子任务设置超时，浏览器在 `finally` 中关闭，并限制最大并发。

### 13.9 平台风控与验证码

风险：平台检测自动化操作或出现验证码。

应对：降低并发、模拟真实输入节奏、保存调试快照；遇到验证码进入人工接管，不无限重试。

### 13.10 自动发布合规风险

风险：未经确认直接发布不合适内容。

应对：为项目配置自动发布策略。新项目默认 `need_review=true`，连续稳定通过后再开启全自动。

## 14. 推荐落地顺序

第一阶段：飞书入口和用户绑定

- 完成 Webhook 验签、事件落库和幂等。
- 建立 `feishu_user_bindings`。
- 未绑定用户直接提示绑定。
- 修正所有飞书链路中的用户作用域。

第二阶段：单用户单项目闭环

- 支持默认项目解析。
- 支持知乎账号按用户过滤。
- 支持关键词蒸馏、文章生成、质量检查和知乎发布。
- 飞书返回完整结果卡片。

第三阶段：多项目和多账号

- 支持项目选择。
- 支持账号选择。
- 支持多平台发布任务。
- 增加人工审核和重试入口。

第四阶段：批量与定时运营

- 支持定时任务。
- 支持关键词池运营。
- 支持发布效果统计和失败归因。

## 15. 当前代码需要优先修正的点

结合现有实现，建议优先处理以下问题：

1. `FeishuTaskHandler.dispatch` 收到了飞书 `user_id/open_id`，但后续没有将其解析为系统用户，也没有在账号、项目、文章查询中使用用户过滤。
2. `_create_and_execute_publish_task` 查询账号时只按平台和状态过滤，需要增加 `Account.user_id == system_user_id`。
3. `_find_project` 在没有公司名时会返回第一个 active 项目，需要改为当前用户默认项目或当前用户唯一可访问项目。
4. `_resolve_keywords` 当前主要读取已有关键词，缺少“调用蒸馏接口、生成候选池、加权随机选择、写入使用历史”的完整流程。
5. `query_status` 和 `publish` 查询最近文章时没有用户作用域，存在查看或发布他人文章的风险。
6. 飞书签名校验应使用 Python 的 `hmac.compare_digest`。
7. 后台发布任务不应复用即将关闭的数据库 Session，应在任务函数内部重新创建 Session。
8. 文章表建议补充 `created_by_user_id` 或通过项目成员关系实现文章归属过滤。

完成以上修正后，本方案就能较稳地支撑“用户在飞书发一句话，系统用该用户绑定的知识库和发布账号自动生成并发布到知乎”的核心场景。
