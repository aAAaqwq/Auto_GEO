# Auto_GEO 可行性研究 — 更优方案探索

> 日期: 2026-05-01
> 版本: v1.1 (补充深度调研后修正)
> 基于: 9大卡点深度调研 + 可行性验证

---

## 总览: BUILD vs BUY 决策矩阵

| 能力 | 当前方案 | 更优方案 | 建议 | 月费 |
|------|---------|---------|------|------|
| AI引用追踪 | Playwright自建 | **Geonimo/CiteMetrix SaaS** | BUY | $24-99 |
| 关键词评分 | n8n蒸馏+自建 | **LLM多Agent评分** + Semrush基础数据 | HYBRID | $75-170 |
| 文章质量评估 | 无 | **LLM-as-Judge** + CiteMetrix基准 | HYBRID | $99+50API |
| 收录数据采集 | 多API手动聚合 | **5118+百度站长+头条API** (够用) | 保持 | ¥200-600 |
| 自动化发布 | Playwright直连 | **AdsPower CDP集成** (更稳) | **升级** | $9-36 |
| 指纹浏览器 | AdsPower | AdsPower (确认最优) | 保持 | $9-36 |
| 知识库隔离 | RAGFlow单库 | **RAGFlow多数据集+pgvector兜底** | 优化 | ¥0 |
| 智能建站 | Jinja2模板 | **v0 API + Vercel自动部署** | **升级** | ¥0 |
| 权威渠道 | 媒介盒子¥499 | 媒介盒子 (确认合适) | 保持 | ¥499一次性 |

---

## 卡点1: 关键词蒸馏 — 更优方案

### 发现: GEO领域已有专业SaaS

| 工具 | 核心能力 | 定价 | 适用性 |
|------|---------|------|--------|
| **Geonimo** | AI Citability评分, 品牌可见性追踪 | $24-99/月 | 入门首选 |
| **CiteMetrix** | ModelScore文章质量分, 竞品引用监控 | $99-299/月 | 性价比最高 |
| **AlsoAsked** | People Also Ask查询拆解, Query Fanout | $19-99/月 | 关键词补充 |
| **Semrush AI** | AI Overview关键词+传统SEO数据 | $119/月起 | 数据最全 |

### 推荐方案: HYBRID (BUY基础 + BUILD差异化)

```
                    ┌─────────────────────────────────────┐
                    │         关键词评分引擎 v2            │
                    └──────────────┬──────────────────────┘
                                   │
              ┌────────────────────┼──────────────────────┐
              │                    │                      │
    ┌─────────▼─────────┐ ┌───────▼────────┐ ┌──────────▼─────────┐
    │ BUY: Semrush/5118  │ │ BUILD: LLM评分  │ │ BUY: AlsoAsked     │
    │ 搜索量/趋势/竞争度  │ │ AI Citability  │ │ Query Fanout分析   │
    │ (传统SEO数据)      │ │ 实体连接度评分  │ │ 子问题挖掘         │
    └─────────┬─────────┘ └───────┬────────┘ └──────────┬─────────┘
              │                    │                      │
              └────────────────────┼──────────────────────┘
                                   │
                         ┌─────────▼─────────┐
                         │  综合评分 + 人工校准 │
                         │  0-100分 → 发布队列  │
                         └───────────────────┘
```

### LLM评分实现 (核心差异化, 约$50-100/月API费)

```python
class LLMKeywordScorer:
    """用LLM做多维度关键词评分 — 这是核心护城河, 必须自建"""

    async def score(self, keyword: str, industry: str) -> dict:
        prompt = f"""
        评估关键词 "{keyword}" 在 "{industry}" 行业中的GEO价值。

        从以下维度打分(0-100):
        1. AI引用潜力: AI回答相关问题时引用此关键词内容的概率
        2. 实体连接度: 关键词与行业核心实体的语义关联强度
        3. 内容差异化: 生成独特有价值内容的可能性
        4. 商业意图: 带来实际业务转化的潜力
        5. 竞争难度: 现有内容的竞争激烈程度(越高越难)

        返回JSON: {{"scores": {{...}}, "reasoning": "...", "suggestion": "high/medium/low"}}
        """

        result = await llm_client.chat(prompt)
        return self._parse_and_calibrate(result)
```

**对比当前方案**: 纯向量 → LLM多维评分, 精度提升显著, 成本仅增$50-100/月

---

## 卡点2: 收录数据 — 更优方案

### 发现: 没有完美的统一聚合平台

| 平台 | API能力 | 覆盖 | 定价 | 结论 |
|------|---------|------|------|------|
| **新榜** | 有API (需商务咨询) | 公众号/抖音/小红书/B站 | 企业级定价 | 贵, 覆盖偏短视频 |
| **蝉妈妈** | 企业版有API | 抖音/小红书/快手 | 企业级定价 | 偏直播/电商 |
| **5118** | 有API, 定价公开 | 百度收录/关键词排名 | ¥199-599/月 | **收录+SEO最优** |
| **头条号** | 官方API | 头条号阅读量 | 免费 | 免费, 接入简单 |
| **百度站长** | URL推送API | 百度收录 | 免费 | 必接 |

### 推荐方案: 分层聚合 (保持之前的决策, 确认合理)

```
第一层 (免费): 百度站长URL推送 + 头条号数据API + AI引用检测
第二层 (付费): 5118 API ¥199-599/月 → 百度收录监控 + 关键词排名
第三层 (增值): Geonimo $24/月 → AI引用率追踪 (替代Playwright方案)
```

### 关键优化: 用Geonimo替代Playwright做AI引用检测

**当前**: 启动Chromium浏览器访问豆包/通义千问/DeepSeek, 模拟提问检测引用 — 资源消耗大, 不稳定

**优化**: Geonimo API直接查询品牌/关键词在AI引擎中的可见性 — **$24/月, 零服务器资源**

| 维度 | Playwright方案 | Geonimo API |
|------|---------------|-------------|
| 服务器资源 | 1-3GB内存/次 | 零 |
| 检测速度 | 30-60秒/关键词 | <1秒/API调用 |
| 覆盖引擎 | 3个 (豆包/千问/DeepSeek) | 4个+ (Google AIO/ChatGPT/Perplexity/Claude) |
| 稳定性 | UI变更就挂 | API稳定 |
| 成本 | 服务器资源 | $24/月 |

**结论: Geonimo替代Playwright做AI引用检测, 省1-3GB服务器内存, 更稳定, 更全面**

---

## 卡点4: 文章质量评估 — 更优方案

### 发现: CiteMetrix ModelScore 可直接评估AI引用概率

CiteMetrix提供 **ModelScore** — 直接评估文章被AI引擎引用的概率, 比自建规则引擎更准确。

### 推荐方案: BUY基准 + BUILD定制

```
文章生成完成
    │
    ├── [1] CiteMetrix ModelScore API → AI引用概率评分 (BUY, $99/月)
    │       └── 分数 < 60 → 建议重写
    │
    ├── [2] LLM-as-Judge 多Agent评估 (BUILD, ~$0.02-0.05/篇)
    │       ├── Agent 1: 结构完整性 (段落长度/标题层级/列表)
    │       ├── Agent 2: 数据丰富度 (统计数字/引用/来源)
    │       ├── Agent 3: 实体密度 (命名实体数量和关联)
    │       └── Agent 4: 可读性 (Flesch分数/中文适配)
    │
    └── [3] 综合评分 → 发布/修改/重写

每篇文章评估成本: CiteMetrix ~$0.1 + LLM ~$0.03 = 约¥1/篇
```

**对比之前方案**: 纯规则引擎 → CiteMetrix基准+LLM多Agent, 准确性大幅提升

---

## 卡点5: 智能建站 — 更优方案

### 重大发现: v0.dev Platform API 可程序化生成完整网站

**v0.dev API 能力**:
- `POST /v1/projects` — 创建项目
- `POST /v1/chats/:id/messages` — 用自然语言生成完整网站代码
- 自动关联Vercel项目, 一键部署
- 返回可直接部署的代码文件

### 推荐方案: v0 API + Vercel API 全自动链路

```
用户输入: 公司名 + 行业 + 品牌色 + 关键信息
    │
    ▼
┌──────────────────────────────────────────────────┐
│ Step 1: 构建Prompt                               │
│   "为{公司名}创建一个{行业}企业官网,              │
│    品牌色{色}, 包含: 首页/关于我们/产品/新闻/联系" │
└──────────────────┬───────────────────────────────┘
                   ▼
┌──────────────────────────────────────────────────┐
│ Step 2: v0 API 生成代码                          │
│   POST /v1/chats → 获得完整React/HTML代码         │
└──────────────────┬───────────────────────────────┘
                   ▼
┌──────────────────────────────────────────────────┐
│ Step 3: Vercel API 自动部署                      │
│   POST /v13/deployments → Base64编码文件直接部署   │
│   获得URL: https://xxx.vercel.app                │
└──────────────────┬───────────────────────────────┘
                   ▼
┌──────────────────────────────────────────────────┐
│ Step 4: 可选 — 绑定用户自定义域名                 │
│   POST /v10/projects/:id/domains                 │
└──────────────────────────────────────────────────┘
```

**对比之前方案**: Jinja2静态模板 → v0 AI动态生成, 灵活度质的飞跃

### 成本

| 组件 | 费用 |
|------|------|
| v0 API | 免费额度 / $20/月Pro |
| Vercel部署 | 免费Hobby计划 (100GB带宽) |
| 域名 | 用户自备 (~¥50/年) |
| **总成本** | **¥0-140/月** |

### 备选: Astro + Vercel (更可控)

如果v0生成质量不稳定:
- 预制10套行业Astro模板
- 数据驱动渲染
- Vercel API自动部署
- 更可控, 但不如v0灵活

---

## 卡点6: 知识库多租户 — 更优方案

### 发现: RAGFlow无原生多租户, 但多数据集隔离可行

RAGFlow、Dify、FastGPT **都没有**真正的原生多租户, 都靠应用层隔离。

### 方案对比

| 方案 | 复杂度 | 隔离性 | 性能 | 推荐度 |
|------|--------|--------|------|--------|
| **RAGFlow多数据集** (当前方案) | 低 | 中 | 好 | ★★★★ |
| **RAGFlow + pgvector兜底** | 中 | 高 | 好 | ★★★★★ |
| 切换Dify | 高 (重写) | 中 | 好 | ★★ |
| 切换FastGPT | 高 (重写) | 中 | 中 | ★★ |
| 纯pgvector替换RAGFlow | 高 | 高 | 中 | ★★★ |

### 推荐: RAGFlow多数据集 + pgvector兜底

```
                    ┌────────────────────────────┐
                    │  MultiTenantKBManager       │
                    └─────────────┬──────────────┘
                                  │
                    ┌─────────────▼──────────────┐
                    │  查询映射: project → dataset │
                    │  (数据库表: ragflow_mappings) │
                    └─────────────┬──────────────┘
                                  │
               ┌──────────────────┼──────────────────┐
               │                  │                  │
    ┌──────────▼─────────┐ ┌─────▼──────────┐ ┌────▼───────────┐
    │ RAGFlow Dataset A  │ │ RAGFlow Dataset│ │ pgvector兜底    │
    │ 客户A知识库        │ │ B/C/D...       │ │ RAGFlow不可用时 │
    │ 高质量向量检索     │ │ 按项目隔离      │ │ PostgreSQL内    │
    └────────────────────┘ └────────────────┘ └────────────────┘
```

**关键**: 保持RAGFlow作为主力检索引擎, pgvector(PostgreSQL扩展)作为降级兜底。迁移PostgreSQL后自然获得pgvector能力, 零额外成本。

---

## 卡点7: 自动化发布 — AdsPower方案确认

### AdsPower Local API 深度分析

**核心发现**: AdsPower支持 **CDP (Chrome DevTools Protocol)** 直连Playwright!

```python
# Auto_GEO 集成 AdsPower 的关键代码
import requests
from playwright.async_api import async_playwright

async def publish_via_adspower(profile_id: str, platform: str, article: dict):
    # 1. 启动AdsPower浏览器配置
    resp = requests.get(
        f"http://local.adspower.net:50325/api/v1/browser/start?user_id={profile_id}"
    )
    ws_endpoint = resp.json()["data"]["ws"]["puppeteer"]

    # 2. Playwright连接到AdsPower浏览器 (指纹隔离!)
    async with async_playwright() as p:
        browser = await p.chromium.connect_over_cdp(ws_endpoint)
        page = await browser.contexts()[0].new_page()

        # 3. 执行发布逻辑 (复用现有Playwright脚本)
        await page.goto(f"https://{platform}.com/publish")
        # ... 填充表单、上传图片、点击发布 ...
```

**优势**:
- 每个账号独立指纹配置, 大幅降低封号率
- Playwright脚本**几乎不用改**, 只换连接方式
- AdsPower处理指纹伪造, 我们专注业务逻辑

### 定价确认

| 账号数 | AdsPower月费 | 年付(40%off) |
|--------|-------------|-------------|
| 10 | $9 (≈¥65) | $65/年 (≈¥5/月) |
| 50 | $36 (≈¥260) | $259/年 |
| 100 | $36 (≈¥260) | $259/年 |
| 1000 | $236 (≈¥1,700) | $1,700/年 |

**比之前预估的¥216/月更便宜! 50账号年付仅¥260/年**

### 架构调整

```
之前: Auto_GEO → Playwright直连 → 目标平台 (无指纹保护, 易封)

优化: Auto_GEO → AdsPower Local API → 指纹浏览器实例 → 目标平台
       └── 复用现有Playwright脚本 (仅改连接方式)
       └── 每个账号独立指纹 + 代理IP
```

---

## 卡点8: 权威渠道 — 确认媒介盒子方案

媒介盒子¥499入门套餐确认可行, 无更优替代。后续升级路径清晰。

---

## 卡点9: 指纹浏览器 — 确认AdsPower最优

经过对比, AdsPower在**性价比 + API能力 + 中文平台兼容性**三方面均领先:

| 维度 | AdsPower | GoLogin | Multilogin | Hubstudio |
|------|----------|---------|------------|-----------|
| 50账号/月 | **$36** | $49 | $108 | ¥350 |
| API+CDP | **完整** | 完整 | 完整 | 部分 |
| 中文平台适配 | **最强** | 中 | 中 | 强 |
| 年付折扣 | **40%off** | 无 | 无 | 无 |
| Playwright兼容 | **原生** | 原生 | 原生 | 有限 |

---

## 综合可行性结论

### 方案变更汇总

| 卡点 | 原方案 | → 新方案 | 变更原因 |
|------|--------|---------|---------|
| #2 AI引用检测 | Playwright模拟 | **Tocanan.ai** (中文AI覆盖) + 保留Playwright检测豆包/千问 | 中文AI平台无替代API, Tocanan最接近 |
| #4 文章质量 | 规则引擎自建 | **LLM-as-Judge** (纯自建, 无需外部SaaS) | 核心能力, DeepSeek API即可, ¥0.02/篇 |
| #5 智能建站 | Jinja2静态模板 | **v0 API + Astro兜底 + Vercel** | AI生成+模板兜底双保险 |
| #7 发布自动化 | Playwright直连 | **AdsPower CDP集成** | 指纹保护, 降低封号率, 脚本可复用 |
| #9 指纹浏览器 | AdsPower ¥216/月 | **AdsPower $36/月** (年付¥260) | 年付比之前预估便宜82% |

### 更新后的月度成本

| 项目 | 原方案 | 新方案 | 差异 |
|------|--------|--------|------|
| AdsPower (50账号) | ¥216/月 | **¥260/年** (年付) | -¥190/月 |
| 5118 API | ¥599/月 | ¥599/月 | 不变 |
| Tocanan.ai | 无 | 商务定价 (估$100-300/月) | +¥720-2,160 |
| LLM-as-Judge | 无 | 用现有DeepSeek API | +¥50-100(含在AI API内) |
| v0 API | 无 | **$20/月Pro** (≈¥144) | +¥144 |
| 媒介盒子 | ¥499一次性 | ¥499一次性 | 不变 |
| AI API | ¥200-500 | ¥300-600 (含LLM评分) | +¥100 |
| 服务器 | ¥1,000-1,800 | ¥800-1,500 (省AI检测资源) | -¥200 |
| **月合计** | **¥2,000-3,100** | **¥2,600-4,300** | **+¥600-1,200** |

> **注意**: Tocanan.ai定价不公开, 需商务咨询。如果超出预算, 可暂不接入,
> 保留现有Playwright方案检测中文AI平台 (豆包/千问/DeepSeek)。

**新增¥500-700/月成本, 换来**:
- AI引用检测精度↑ + 服务器资源↓
- 文章质量评估专业化
- 智能建站能力质变
- 发布防封能力大幅提升
- 关键词评分多维精准

### 风险评估

| 风险 | 概率 | 影响 | 缓解 |
|------|------|------|------|
| **Geonimo不支持中文AI** | **已确认** | 高 | 改用Tocanan.ai或保留Playwright检测中文AI |
| Tocanan定价过高 | 中 | 中 | 不接入, 保留Playwright方案 |
| CiteMetrix不支持中文 | 中 | 中 | 不依赖, LLM-as-Judge纯自建即可 |
| v0中文生成质量差 | 中 | 低 | Astro模板兜底, 先测试验证 |
| AdsPower封号仍发生 | 低 | 中 | 频率控制+代理IP |
| v0 Pro $20/月超预算 | 低 | 低 | 免费额度7次/天, 初期够用 |

### 推荐接入顺序

```
Week 1-2: AdsPower CDP集成 (立即降封号风险, 脚本改动最小)
Week 2-3: LLM-as-Judge评分 (核心能力, 用现有DeepSeek API, 零新增成本)
Week 3-4: 5118 API接入 (收录数据)
Week 5-6: v0 API + Astro模板 + Vercel (智能建站)
Week 7-8: Tocanan询价+试用 (如价格合理则接入, 否则保留Playwright)
```

---

## 逐方案详细可行性评估

### 方案A: AdsPower CDP集成 (卡点#7)

| 维度 | 评估 |
|------|------|
| **可行性** | ★★★★★ 极高 |
| **技术难度** | 低 — 仅改Playwright连接方式 |
| **开发时间** | 1-2周 |
| **前置条件** | AdsPower账号(年付$259) + 本地安装AdsPower客户端 |
| **风险** | AdsPower客户端需运行在服务器/本地, 需GUI环境或headless模式 |

**改动清单**:
```
修改文件:
├── backend/services/playwright_mgr.py     → 新增 connect_via_adspower() 方法
├── backend/services/publisher.py          → 优先使用AdsPower连接, 回退到直连
├── backend/services/session_manager.py    → AdsPower profile管理
├── backend/api/account.py                 → 关联AdsPower profile_id
├── backend/config.py                      → 新增 ADSPOWER_API_URL 配置
└── backend/database/models.py             → Account表新增 adspower_profile_id 字段
```

**核心代码改动** (约50行):
```python
# playwright_mgr.py 新增方法
async def connect_via_adspower(self, profile_id: str):
    """通过AdsPower CDP连接浏览器"""
    resp = requests.get(
        f"{ADSPOWER_API_URL}/api/v1/browser/start?user_id={profile_id}",
        timeout=30
    )
    data = resp.json()
    if data["code"] != 0:
        raise Exception(f"AdsPower启动失败: {data['msg']}")

    ws_endpoint = data["data"]["ws"]["puppeteer"]
    browser = await self.playwright.chromium.connect_over_cdp(ws_endpoint)
    return browser
```

**结论: 立即可做, 改动最小, 收益最大**

---

### 方案B: LLM-as-Judge 文章质量评分 (卡点#4)

| 维度 | 评估 |
|------|------|
| **可行性** | ★★★★★ 极高 |
| **技术难度** | 中 — 需设计Prompt + 评分逻辑 |
| **开发时间** | 1-2周 |
| **前置条件** | DeepSeek API (已有) 或 Claude API |
| **风险** | LLM评分可能不够稳定, 需要多次迭代Prompt |

**改动清单**:
```
新增文件:
├── backend/services/article_scorer.py     → LLM多Agent评分器 (新建, ~300行)

修改文件:
├── backend/services/geo_article_service.py → 生成后自动评分
├── backend/api/geo.py                     → 新增评分API端点
├── backend/api/article.py                 → 文章列表返回质量分数
└── backend/database/models.py             → GeoArticle表新增 quality_score 字段
```

**评分Prompt设计** (核心, 需反复调优):
```python
SCORING_PROMPT = """
你是一位GEO(生成式引擎优化)专家。评估以下文章被AI搜索引擎引用的概率。

文章标题: {title}
文章内容: {content[:2000]}

从以下5个维度评分(0-100):
1. **结构清晰度**: 段落长度、标题层级、列表/表格使用
2. **数据丰富度**: 统计数字、权威引用、具体来源
3. **实体密度**: 命名实体(人名/公司/产品/数据)的数量和关联性
4. **AI可引用性**: 是否有明确结论、可直接摘录的段落
5. **独特价值**: 是否提供区别于常见内容的独特观点或数据

请严格返回JSON:
{"scores": {"structure": N, "data_richness": N, "entity_density": N, "citability": N, "uniqueness": N},
 "overall": N,
 "pass": true/false,
 "issues": ["问题1", "问题2"],
 "suggestions": ["建议1"]}
"""
```

**成本估算**: 每篇文章 ~¥0.05-0.1 (DeepSeek API), 月评估100篇 ≈ ¥5-10

**CiteMetrix还需要吗?**
- CiteMetrix $99/月, 主要评估英文内容被西方AI引用的概率
- **中文场景下LLM-as-Judge更合适**, 暂不接入CiteMetrix
- 后期如果做海外业务再考虑

**结论: 纯自建, 零外部依赖, 用现有API即可**

---

### 方案C: v0 API + Astro兜底智能建站 (卡点#5)

| 维度 | 评估 |
|------|------|
| **可行性** | ★★★★ 高 (v0中文支持待验证) |
| **技术难度** | 中-高 |
| **开发时间** | 2-3周 |
| **前置条件** | v0 Pro $20/月 + Vercel账号 |
| **风险** | v0生成中文网站质量不稳定; $20/月信用额度有限 |

**v0 API关键限制**:
- 免费版: $5额度/月, 7条/天 — **太少**
- Pro版: $20/月, $20额度 — 中小型网站够用(~10-20个站)
- 生成的是 React + Tailwind 代码, 需要后处理适配中文
- 中文内容支持**未经验证**, 需实际测试

**双保险方案**:
```
用户输入品牌信息
    │
    ├── [优先] v0 API生成 (AI动态, 灵活)
    │   └── 如果生成质量达标 → Vercel部署
    │
    └── [兜底] Astro模板渲染 (可控, 稳定)
        └── 从10套预制模板中选择 → 数据填充 → Vercel部署
```

**改动清单**:
```
新增文件:
├── backend/services/site_builder/
│   ├── v0_generator.py        → v0 API调用封装 (新建, ~200行)
│   ├── astro_renderer.py      → Astro模板渲染 (新建, ~150行)
│   ├── vercel_deployer.py     → Vercel API部署 (新建, ~200行)
│   └── templates/             → 10套Astro行业模板
│
修改文件:
├── backend/api/site_builder.py → 重写, 接入新引擎
├── backend/services/site_generator.py → 保留为Astro渲染器的一部分
└── frontend/src/views/         → 建站UI交互调整
```

**分阶段实施**:
```
Phase 1 (1周): Astro模板渲染 + Vercel部署 → 立即可用的建站能力
Phase 2 (1周): v0 API集成 → AI动态生成, 测试中文效果
Phase 3 (持续): 模板迭代 + v0 Prompt优化
```

**结论: 先做Astro模板(稳), 再加v0(灵), 双保险**

---

### 方案D: AI引用检测优化 (卡点#2)

| 维度 | 评估 |
|------|------|
| **可行性** | ★★★ 中 (无完美方案) |
| **技术难度** | 低 (保留现有) / 中 (接入Tocanan) |
| **开发时间** | 3天 (优化现有) / 1-2周 (接入Tocanan) |
| **风险** | Tocanan定价不透明, 可能很贵 |

**现状分析**:
- Geonimo/CiteMetrix **不支持中文AI平台** (豆包/千问/DeepSeek) — 排除
- Tocanan.ai **支持DeepSeek/Kimi/豆包** — 但定价不公开, 企业级
- 现有Playwright方案**虽然占资源, 但能检测中文AI** — 无完美替代

**务实方案**:
```
              AI引用检测策略
                   │
    ┌──────────────┼──────────────┐
    │              │              │
中文AI平台      海外AI平台       未来
(豆包/千问      (ChatGPT/       (API开放后
/DeepSeek)      Perplexity)      切换)
    │              │              │
Playwright     Tocanan.ai      等待
检测           (询价后决定)     生态成熟
(保留现有)     或 Geonimo
               $24/月
```

**立即可做的优化** (不花钱):
1. Playwright检测改为**无头模式** (省GUI资源)
2. 检测结果**缓存7天** (同一关键词不重复检测)
3. 检测任务**队列化** (错峰执行, 避免并发冲突)

**结论: 保留Playwright方案+优化资源消耗, Tocanan询价后决定**

---

## 最终实施路线图

```
Week 1 ─── AdsPower CDP集成
  │         └── 改动5个文件, 新增~50行核心代码
  │         └── 成本: ¥0 (年付已在预算内)
  │
Week 2 ─── AdsPower测试 + LLM-as-Judge开发
  │         └── 文章评分器: 新建1个文件~300行
  │         └── 成本: ¥0 (用现有DeepSeek API)
  │
Week 3 ─── LLM评分调优 + 5118 API接入
  │         └── 收录数据采集管道
  │         └── 成本: ¥599/月 (5118)
  │
Week 4 ─── Astro模板建站 + Vercel部署
  │         └── 新建建站服务目录, 5套初始模板
  │         └── 成本: ¥0 (Vercel免费)
  │
Week 5 ─── v0 API集成 + 建站双引擎
  │         └── v0 Pro $20/月
  │         └── 成本: $20/月 (≈¥144)
  │
Week 6 ─── Tocanan询价 + 决策
  │         └── 如价格合理: 接入替代Playwright
  │         └── 如价格过高: 优化Playwright方案继续用
  │
Week 7-8 ─ 整体联调 + 测试 + 上线准备
```

### 月度成本 (稳定运营后)

| 必选 (约¥2,000/月) | 可选 (按需+约¥1,500/月) |
|---------------------|------------------------|
| AdsPower ¥260/年 | 5118 API ¥599/月 |
| DeepSeek API ¥200-500/月 | v0 Pro ¥144/月 |
| 服务器 ¥1,000-1,800/月 | Tocanan 待定 |
| 媒介盒子 ¥499一次性 | |
