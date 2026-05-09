# Auto_GEO 关键卡点分析与解决方案

> 日期: 2026-05-01
> 版本: v1.0
> 状态: 待讨论

---

## 卡点总览

| # | 卡点 | 优先级 | 复杂度 | 状态 |
|---|------|--------|--------|------|
| 1 | 关键词蒸馏：高价值关键词定义 | P0 | 高 | 部分实现 |
| 2 | 收录数据与曝光量获取 | P0 | 高 | 部分实现 |
| 3 | 自动化程序执行稳定性 | P1 | 中 | 开发中 |
| 4 | GEO文章质量评估算法 | P0 | 高 | 未实现 |
| 5 | 智能建站一键部署 | P2 | 中 | 原型阶段 |
| 6 | 知识库多租户隔离 | P1 | 中 | 部分实现 |
| 7 | 自动化发布稳定性与防封 | P0 | 极高 | 开发中 |
| 8 | 官方权威新闻渠道接入 | P1 | 中 | 未实现 |
| 9 | 多账号管理与指纹浏览器 | P1 | 高 | 未实现 |

---

## 卡点1: 关键词蒸馏 — 高价值关键词定义

### 现状

当前 `keyword_service.py` 实现了基础的关键词CRUD + n8n蒸馏调用，但缺乏**高价值关键词的量化评分体系**。

### 核心问题

如何判断一个关键词/问题值得投入资源生成GEO文章？

### 解决方案: 三维评分模型

```
关键词价值 = f(搜索意图, 实体连接度, 竞争难度)
```

#### 维度1: AI引用潜力评分 (Citation Potential Score)

基于研究, AI模型引用内容的特征:

| 特征 | 权重 | 说明 |
|------|------|------|
| 问题式意图 | 30% | "什么是..." "如何..." 格式被引用概率高58% |
| 品牌对比意图 | 25% | "A vs B" 格式, 表格被引用概率52% |
| 列表/特征意图 | 20% | 功能列表64-82%引用率 |
| 长尾精准意图 | 15% | 超具体查询竞争低、命中高 |
| 通用信息意图 | 10% | 覆盖面广但竞争大 |

#### 维度2: 实体连接度评分 (Entity Connectivity Score)

```
实体连接度计算流程:
1. 提取关键词中的命名实体 (人名/公司/产品/概念)
2. 构建实体关系图 (知识图谱子图)
3. 计算 Katz Centrality / 余弦相似度
4. 高连接度 = 该实体在网络中关联丰富 = AI更容易检索到
```

**实现路径**:
- 利用 RAGFlow 已有的向量检索能力
- 维护一个行业实体关系图谱 (Neo4j 或简单的图结构)
- 关键词蒸馏时计算其包含实体的连接度分数

#### 维度3: 人工校准层

| 环节 | 方法 | 输出 |
|------|------|------|
| 关键词入库 | 算法初筛 + 人工标注 | approve/reject/adjust |
| 优先级排序 | 机器评分 + 人工权重调整 | 发布队列排序 |
| 效果反馈 | 收录率 → 反哺评分模型 | 模型迭代 |

### 建议实现

```python
class KeywordScorer:
    """关键词三维评分器"""

    def score(self, keyword: str, context: dict) -> dict:
        citation_score = self._citation_potential(keyword)      # 0-100
        entity_score = self._entity_connectivity(keyword)       # 0-100
        difficulty_score = self._competition_difficulty(keyword) # 0-100 (越低越好)

        # 加权综合
        final_score = (
            citation_score * 0.4 +
            entity_score * 0.3 +
            (100 - difficulty_score) * 0.3
        )
        return {
            "keyword": keyword,
            "citation_potential": citation_score,
            "entity_connectivity": entity_score,
            "difficulty": difficulty_score,
            "final_score": final_score,
            "recommendation": "high" if final_score > 70 else "medium" if final_score > 40 else "low"
        }
```

---

## 卡点2: 收录数据与曝光量获取

### 现状

`index_check_service.py` 已实现通过 Playwright 模拟检测 AI 平台(豆包/通义千问/DeepSeek)是否引用了目标文章，但:
- 只检测 AI 平台，不检测传统搜索引擎收录
- 曝光量/阅读量数据未接入
- 检测方式是 UI 自动化，资源消耗大

### 数据获取渠道对比

| 数据类型 | 来源 | API能力 | 自动化难度 | 可靠性 |
|----------|------|---------|-----------|--------|
| **百度收录** | 百度站长平台 | URL推送API (仅提交, 不查询) | 低 | 高 |
| **百度收录查询** | site:指令 + 爬虫 | 无官方API | 中 | 中 |
| **百度收录查询** | 第三方 (爱站/站长工具) | 付费API | 低 | 中 |
| **百家号数据** | 百家号后台 | 无公开API | 需爬虫 | 中 |
| **头条号数据** | 头条创作者中心 | **有API** (阅读/点赞/评论) | 低 | 高 |
| **知乎数据** | 知乎API v4 | 用户/回答信息 | 中 | 中 |
| **AI引用检测** | 当前Playwright方案 | 无API | 已实现 | 中 |
| **全网曝光** | 百度统计/CNZZ | JavaScript埋点+API | 低 | 高 |

### 推荐方案: 分层数据采集

```
第一层 (必须): 百度站长平台 URL推送 + site:批量查询
    └── 文章发布后自动推送URL给百度
    └── 定时任务批量查询收录状态

第二层 (推荐): 各平台数据采集
    ├── 头条号 API → 阅读量/互动数据 (有API, 优先)
    ├── 百家号/知乎 → Cookie爬虫 / RPA采集
    └── AI引用检测 → 当前Playwright方案优化

第三层 (增值): 自有埋点
    ├── 百度统计 JS SDK → 流量来源/用户行为
    └── 自建短链系统 → 跨平台点击追踪
```

### 量化指标体系

| 指标 | 定义 | 数据源 | 获取方式 |
|------|------|--------|---------|
| 收录率 | 被收录文章/总发布文章 | 百度/Google | site:查询 |
| AI引用率 | 被AI回答引用/总文章 | AI平台检测 | Playwright |
| 曝光量 | 搜索结果展现次数 | 百度统计 | JS埋点 |
| 点击率 | 点击次数/曝光次数 | 百度统计 | JS埋点 |
| 阅读量 | 文章实际阅读次数 | 各平台API | API/爬虫 |
| 互动率 | (赞+评+转)/阅读量 | 各平台API | API/爬虫 |
| 转化率 | 目标行为/访问量 | 自有埋点 | 短链追踪 |

---

## 卡点3: 自动化程序执行稳定性

### 核心问题

自动化流程的可靠性直接影响用户体验。

### 当前风险点

| 风险 | 影响 | 概率 | 缓解措施 |
|------|------|------|---------|
| Playwright崩溃 | 发布任务中断 | 高 | 进程守护 + 自动重启 |
| 浏览器内存泄漏 | 服务器OOM | 中 | 定时重启浏览器实例 |
| 网络超时 | 任务卡死 | 中 | 全链路超时控制 |
| n8n工作流失败 | AI生成中断 | 中 | 重试队列 + 降级方案 |
| RAGFlow不可用 | 知识检索失败 | 低 | 本地缓存兜底 |

### 建议架构改进

```
                    ┌──────────────┐
                    │   任务调度器   │ (APScheduler)
                    └──────┬───────┘
                           │
                    ┌──────▼───────┐
                    │   任务队列     │ (Redis Stream / 内存队列)
                    └──────┬───────┘
                           │
              ┌────────────┼────────────┐
              │            │            │
        ┌─────▼─────┐ ┌───▼────┐ ┌────▼─────┐
        │ Worker 1  │ │Worker 2│ │ Worker 3 │  (最多3并发)
        │ Playwright│ │Publish │ │  AI Gen  │
        └─────┬─────┘ └───┬────┘ └────┬─────┘
              │            │            │
        ┌─────▼────────────▼────────────▼─────┐
        │           状态持久化 + 错误恢复        │
        └──────────────────────────────────────┘
```

关键设计:
- **任务状态机**: pending → running → success/failed → retry
- **断点续跑**: 任务失败后可从上次断点恢复
- **资源隔离**: Playwright实例池, 用完归还/超时释放
- **健康探针**: Worker心跳检测, 挂了自动拉起

---

## 卡点4: GEO文章质量评估算法

### 核心问题

如何确保生成的文章被AI搜索引擎高概率引用?

### AI引用内容的5大特征 (基于5000+样本研究)

| 特征 | 说明 | 量化指标 | 权重 |
|------|------|---------|------|
| **清晰度** | 快速理解能力 | 段落≤120字, 标题直述 | 30% |
| **可信度** | 来源权威性 | 引用数量, 数据来源可溯源 | 25% |
| **可组合性** | 模块化结构 | 独立观点单元数, 无需上下文 | 20% |
| **一致性** | 信息互补性 | 与已引用内容的互补度 | 15% |
| **格式规范** | 提取效率 | 问题-答案-依据结构化程度 | 10% |

### 文章质量评分算法

```python
class GeoArticleScorer:
    """GEO文章质量评分器"""

    def evaluate(self, article: dict) -> dict:
        scores = {
            "structure": self._score_structure(article),      # 结构化程度
            "citation_worthy": self._score_citation(article), # 可引用性
            "entity_density": self._score_entities(article),  # 实体密度
            "data_richness": self._score_data(article),       # 数据丰富度
            "image_quality": self._score_images(article),     # 图片质量
        }

        final = sum(scores.values()) / len(scores)
        return {
            "scores": scores,
            "final_score": final,
            "pass": final >= 70,  # 低于70分建议重写
            "suggestions": self._generate_suggestions(scores)
        }

    def _score_structure(self, article):
        """结构化评分: 标题层级、列表使用、段落长度"""
        checks = {
            "has_h2_h3": bool(re.findall(r'##', article['content'])),
            "has_lists": bool(re.findall(r'^\s*[-*]\s', article['content'], re.M)),
            "short_paragraphs": all(
                len(p) <= 120 for p in article['content'].split('\n\n') if p.strip()
            ),
            "has_table": '|' in article['content'],
        }
        return sum(checks.values()) / len(checks) * 100

    def _score_citation(self, article):
        """可引用性: 统计数据、权威引用、具体数字"""
        content = article['content']
        citation_signals = {
            "has_statistics": bool(re.search(r'\d+\.?\d*%', content)),      # 百分比
            "has_data_source": bool(re.search(r'据.*数据显示|根据.*报告', content)),
            "has_quotes": bool(re.search(r'".*".*表示|.*认为', content)),
            "specific_numbers": len(re.findall(r'\d+', content)) >= 5,      # 具体数字≥5个
        }
        return sum(citation_signals.values()) / len(citation_signals) * 100
```

### 图片素材策略

| 素材类型 | 来源 | 成本 | GEO效果 |
|----------|------|------|---------|
| AI生成图 | DALL-E / Midjourney / Stable Diffusion | 低 | 中 (AI可能识别为生成) |
| 图表/信息图 | ECharts / matplotlib 自动生成 | 极低 | **高** (数据可视化=高引用率) |
| 实景照片 | Unsplash / Pexels (免费版权) | 免费 | 中 |
| 品牌素材 | 用户提供 | 免费 | 高 (实体权重提升) |

**建议**: 优先使用**数据图表自动生成**, 对GEO引用率提升最大。

---

## 卡点5: 智能建站一键部署

### 现状

`site_generator.py` 实现了基于 Jinja2 模板生成静态HTML, 但:
- 仅本地生成, 无部署能力
- 仅有 corporate 和 cowboy 两个模板
- 无域名/SSL配置
- 无服务器部署流程

### 一键部署方案对比

| 方案 | 部署资源 | 成本 | 复杂度 | 适用场景 |
|------|---------|------|--------|---------|
| **Vercel/Netlify** | 平台提供 | 免费额度大 | 低 | 静态站, 最推荐 |
| **Cloudflare Pages** | 平台提供 | 免费 | 低 | 全球CDN |
| **GitHub Pages** | 平台提供 | 免费 | 低 | 简单展示站 |
| **自有服务器** | 用户自备 | 用户承担 | 中 | 自定义需求 |
| **OSS+CDN** | 阿里云/腾讯云 | 低 | 中 | 国内优化 |

### 推荐: Vercel API 一键部署

```
用户点击"一键部署"
    ↓
Auto_GEO 后端
    ├── 1. Jinja2 生成静态 HTML (已有)
    ├── 2. 上传到 Vercel/GitHub (通过 API)
    ├── 3. 绑定用户域名 (可选)
    └── 4. 配置 SSL (自动)

用户获得: https://brand-name.vercel.app
    或: https://user-domain.com
```

**部署资源**: 平台免费额度内由平台承担, 用户零成本。
**Demo展示**: 需要制作一个完整的品牌站生成 → 部署 → 访问的演示视频。

### 建议实现路径

```
Phase 1: 静态站生成优化 (当前 → 2周)
    ├── 丰富模板 (5-10套行业模板)
    ├── 数据驱动的模板渲染
    └── 本地预览功能

Phase 2: 一键部署 (2-4周)
    ├── Vercel API 集成
    ├── GitHub 自动创建仓库 + 推送
    └── 域名绑定引导

Phase 3: SEO/GEO 基础优化 (4-6周)
    ├── Schema.org 结构化数据
    ├── Sitemap 自动生成
    ├── 百度/Google 站长验证
    └── Open Graph / Twitter Card
```

---

## 卡点6: 知识库多租户隔离

### 现状

`ragflow_client.py` 支持单知识库操作, `config.py` 配置了单一 `RAGFLOW_DATASET_ID`, 缺乏多客户/多项目的知识库隔离能力。

### RAGFlow 多知识库架构

```
RAGFlow 实例
├── 知识库: 客户A_科技行业
│   ├── 文档集: 参考文章
│   ├── 文档集: 品牌素材
│   └── 对话助手: 客户A专属助手
├── 知识库: 客户B_医疗行业
│   ├── 文档集: 行业知识
│   └── 对话助手: 客户B专属助手
└── 知识库: 公共知识库 (共享)
    └── 文档集: 写作规范/平台规则
```

### 实现方案

```python
class MultiTenantRAGFlowManager:
    """多租户知识库管理器"""

    def __init__(self):
        self.client = RAGFlowClient()
        self._cache = {}  # project_id → dataset_id 映射缓存

    def get_or_create_dataset(self, project_id: int, project_name: str) -> str:
        """获取或创建项目专属知识库"""
        if project_id in self._cache:
            return self._cache[project_id]

        # 查询数据库中的映射
        mapping = self.db.query(RAGFlowMapping).filter_by(project_id=project_id).first()
        if mapping:
            self._cache[project_id] = mapping.dataset_id
            return mapping.dataset_id

        # 创建新知识库
        dataset_name = f"project_{project_id}_{project_name}"
        result = self.client.create_dataset(name=dataset_name)

        # 持久化映射关系
        dataset_id = result["id"]
        mapping = RAGFlowMapping(project_id=project_id, dataset_id=dataset_id)
        self.db.add(mapping)
        self.db.commit()

        self._cache[project_id] = dataset_id
        return dataset_id

    def search(self, project_id: int, query: str, top_k: int = 10):
        """项目隔离的检索"""
        dataset_id = self.get_or_create_dataset(project_id)
        return self.client.search(dataset_id=dataset_id, query=query, top_k=top_k)

    def upload_documents(self, project_id: int, documents: list):
        """上传文档到项目专属知识库"""
        dataset_id = self.get_or_create_dataset(project_id)
        return self.client.upload_documents(dataset_id=dataset_id, documents=documents)
```

### 数据库表设计

```python
class RAGFlowMapping(Base):
    """项目与RAGFlow知识库映射"""
    __tablename__ = "ragflow_mappings"

    id = Column(Integer, primary_key=True)
    project_id = Column(Integer, ForeignKey("projects.id"), unique=True)
    dataset_id = Column(String(100), nullable=False)      # RAGFlow知识库ID
    dataset_name = Column(String(200), nullable=False)
    assistant_id = Column(String(100), nullable=True)      # RAGFlow对话助手ID
    created_at = Column(DateTime, default=func.now())
    updated_at = Column(DateTime, default=func.now(), onupdate=func.now())
```

---

## 卡点7: 自动化发布稳定性与防封

### 核心风险

| 风险 | 原因 | 影响 | 当前缓解 |
|------|------|------|---------|
| **平台封号** | 频繁操作/异常行为 | 账号资产损失 | 无有效防护 |
| **平台UI变更** | 平台定期改版 | 脚本失效 | 手动修复 |
| **AI脚本错位** | AI生成的选择器不准确 | 发布失败 | 人工校验 |
| **浏览器资源** | 并发窗口消耗大 | OOM/卡顿 | MAX_CONCURRENT=3 |
| **无API平台** | 大多数平台无开放API | 只能走UI自动化 | Playwright |

### 方案: Chrome插件 + 云端协同

```
方案对比:
┌─────────────────────────────────────────────────────┐
│ 当前方案: 纯 Playwright 服务端自动化                    │
│   优点: 全自动, 无需用户操作                            │
│   缺点: 易封号, UI变更影响大, 资源消耗高               │
├─────────────────────────────────────────────────────┤
│ 建议方案: Chrome插件辅助 + Playwright 降级备用          │
│   优点: 用户本地浏览器操作, 不易封号, 零服务器资源       │
│   缺点: 需要用户安装插件, 半自动                        │
├─────────────────────────────────────────────────────┤
│ 长期方案: 平台API优先 + 插件补充 + Playwright兜底       │
│   优点: 最稳定, 最省资源                                │
│   缺点: 各平台API接入工作量大                           │
└─────────────────────────────────────────────────────┘
```

### Chrome插件架构设计

```
Chrome Extension (用户本地浏览器)
├── content_script.js  ← 注入到目标平台页面
│   ├── 检测当前平台 (知乎/百家号/头条...)
│   ├── 从 Auto_GEO 后端获取待发布内容
│   ├── 自动填充表单 + 上传图片
│   └── 用户确认后点击发布
├── background.js      ← 与后端通信
│   ├── WebSocket 连接 Auto_GEO 后端
│   ├── 接收发布任务指令
│   └── 上报发布结果
└── popup.html         ← 用户界面
    ├── 任务队列展示
    ├── 发布状态监控
    └── 账号管理

Auto_GEO 后端
├── 发布任务API → 推送任务到Chrome插件
├── Playwright → 兜底方案 (插件不在线时)
└── 发布结果收集 → 记录到数据库
```

### 防封策略

| 策略 | 说明 | 实现难度 |
|------|------|---------|
| 请求频率控制 | 模拟人类操作节奏, 随机延迟 | 低 |
| User-Agent轮换 | 避免同一UA频繁操作 | 低 |
| IP代理池 | 不同账号使用不同出口IP | 中 |
| Cookie隔离 | 每个账号独立浏览器上下文 | 已实现 |
| 行为模拟 | 随机鼠标移动、滚动、停留 | 中 |
| 操作时间分散 | 避免集中时间批量操作 | 低 |
| Chrome插件方案 | 用户本地浏览器, 风险最低 | 中 |

---

## 卡点8: 官方权威新闻渠道接入

### 权威媒体发布定价参考

| 媒体层级 | 官方投稿 | 第三方平台 | 审核周期 |
|----------|---------|-----------|---------|
| 人民网 | 免费 (采纳率极低) | 3,000-8,000元/篇 | 3-7天 |
| 新华网 | 免费 (需合作) | 800-3,000元/篇 | 3-7天 |
| 央视网 | 免费 | 1,000元/篇起 | 3-5天 |
| 学习强国 | 免费 (机构) | 500-2,000元/篇 | 不定 |
| 省级媒体 | 免费 | 1,000-5,000元/篇 | 1-3天 |
| 门户频道 | 协商 | 200-500元/篇 | 1-3天 |

### 推荐接入平台: 媒介盒子

**优势**: API最完善, 10万+媒体资源, 支持程序化批量投稿

| 套餐 | 费用 | 能力 |
|------|------|------|
| 入门 | ¥499 | 基础发稿 |
| VIP | ¥3,888 | 高级媒体通道 |
| **SVIP** | **¥18,888** | **API接口 + 白标系统** |

**API集成路径**:
```
n8n工作流编排
    ├── [触发] GEO文章生成完成
    ├── [预处理] 敏感词过滤 → 合规性检查
    ├── [API提交] 媒介盒子API → 选择目标媒体 → 批量投稿
    ├── [监控] 定时查询收录状态
    └── [反馈] 收录结果 → 更新关键词评分
```

### 分层发布策略

```
第一层 (权威背书): 人民网/新华网 → 品牌信任度  (预算: 5,000-10,000/月)
第二层 (行业覆盖): 行业垂直媒体 → 精准触达    (预算: 2,000-5,000/月)
第三层 (流量矩阵): 腾讯/网易/新浪门户 → 扩大曝光 (预算: 1,000-3,000/月)
第四层 (长尾收录): 地方媒体/行业网站 → 大量外链 (预算: 500-1,000/月)
```

---

## 卡点9: 多账号管理与指纹浏览器

### 指纹浏览器产品对比 (2025-2026)

| 产品 | 50账号/月 | 200账号/月 | 特点 | 推荐度 |
|------|----------|-----------|------|--------|
| **AdsPower** | $30 (≈¥216) | $50-100 (≈¥360-720) | 性价比最高, API自动化 | ★★★★★ |
| **GoLogin** | $49 (≈¥353) | $99 (≈¥713) | 内置免费代理 | ★★★★ |
| **Hubstudio** | ¥350 | ¥700+ | 国产, 团队协作好 | ★★★★ |
| **Multilogin** | $108 (≈¥778) | $217 (≈¥1,562) | 最贵, 指纹伪装最佳 | ★★★ |
| **花沐/花漾** | ¥70-210 (估) | ¥350+ (估) | 国产轻量 | ★★★ |

### 开源免费替代方案

| 方案 | 能力 | 适合场景 |
|------|------|---------|
| **VirtualBrowser** (GitHub开源) | 完全免费, Chromium内核, API兼容Playwright | **首选** |
| **Hubstudio** 免费版 | 不限环境, 日开20次 | 低频使用 |
| **MoreLogin** 免费版 | 2个永久免费Profile | 测试 |
| **ebrower** | 终身免费, 多账号/IP隔离 | 轻量场景 |

### 推荐方案: 分级策略

```
Phase 1: 低成本启动 (VirtualBrowser 开源方案)
    ├── 部署 VirtualBrowser 服务
    ├── 集成 Auto_GEO Playwright 接口
    ├── 支持 50 个账号以内
    └── 成本: ¥0 (自有服务器)

Phase 2: 规模化 (AdsPower 专业版)
    ├── 接入 AdsPower API
    ├── 支持 200+ 账号
    ├── 团队协作 + 权限管理
    └── 成本: ¥216-720/月

Phase 3: 自研方案 (长期)
    ├── 基于 Chromium 定制编译
    ├── 指纹参数全面可控
    ├── 无限账号, 零边际成本
    └── 成本: 开发投入 (2-3人月)
```

### Chrome插件 vs 指纹浏览器

| 维度 | Chrome插件 | 指纹浏览器 |
|------|-----------|-----------|
| **防检测** | 弱 (仅能修改部分参数) | 强 (30+参数全面伪造) |
| **成本** | 免费 | ¥200-1,500/月 |
| **自动化** | 需自行开发 | API接口成熟 |
| **稳定性** | 依赖Chrome更新 | 专业维护 |
| **推荐** | 辅助方案 (轻量操作) | **主力方案** (批量管理) |

---

## 决策记录 (2026-05-01)

| # | 决策项 | 结论 | 理由 |
|---|--------|------|------|
| 1 | 实体连接度图谱 | **纯向量方案** — 用RAGFlow已有能力 | 零额外基建, MVP阶段精度够用, 避免引入Neo4j增加运维复杂度 |
| 2 | 收录数据采集 | **多API聚合** — 百度推送 + 站长工具 + 5118 + 头条号API + AI引用 | 串联多个第三方接口, 数据维度最全, 开发量约1.5周 |
| 3 | 多账号管理 | **AdsPower过渡** — ¥216/月起, API自动化 | 先不做Chrome插件, AdsPower接口成熟即买即用 |
| 4 | 权威新闻渠道 | **媒介盒子入门¥499先验证** | 先验证API流程和业务模式, 确认有客户需求再升级 |
| 5 | 智能建站部署 | **Vercel** — 免费额度 + API一键部署 | 全球CDN, 免费100GB带宽/月, 部署API方便 |
| 6 | 指纹浏览器 | **AdsPower为主** (同#3) | Phase 1 AdsPower, 后期视规模考虑自研 |

---

## 实施优先级 (基于决策调整)

### 第一阶段: MVP上线必须 (P0) — 约6周

| 卡点 | 动作 | 预估工时 | 依赖 |
|------|------|---------|------|
| #1 关键词蒸馏 | 纯向量评分 + 三维模型 + 人工校准UI | 2周 | RAGFlow |
| #2 收录数据 | 多API聚合 (百度推送+站长工具+5118+头条+AI引用) | 1.5周 | 5118 API ¥199-599/月 |
| #4 文章质量 | 评分算法 + ECharts图表自动生成 | 2周 | — |
| #7 发布稳定性 | AdsPower API集成 + 防封策略 | 2周 | AdsPower ¥216/月 |

### 第二阶段: 产品完善 (P1) — 约5周

| 卡点 | 动作 | 预估工时 | 依赖 |
|------|------|---------|------|
| #3 执行稳定性 | Redis任务队列 + Worker池 + 断点续跑 | 2周 | Redis |
| #6 知识库隔离 | 多租户RAGFlow管理器 + 映射表 | 1周 | — |
| #8 权威渠道 | 媒介盒子API集成 (入门套餐验证) | 1周 | 媒介盒子 ¥499 |
| #9 多账号 | AdsPower批量管理 + 指纹隔离 | 1周 | — |

### 第三阶段: 差异化竞争力 (P2) — 约8周

| 卡点 | 动作 | 预估工时 |
|------|------|---------|
| #5 智能建站 | Vercel API一键部署 + 5-10套行业模板 | 3周 |
| #1 关键词 | 实体向量自动蒸馏 + 评分模型优化 | 2周 |
| #4 文章质量 | 评分模型数据积累 + AI训练 | 3周 |

### 月度运营成本估算 (P0阶段)

| 项目 | 费用 |
|------|------|
| AdsPower (50账号) | ¥216/月 |
| 5118 API (标准版) | ¥599/月 |
| 媒介盒子 (入门) | ¥499 (一次性) |
| AI API (DeepSeek等) | ¥200-500/月 (按用量) |
| 服务器 (应用+RAGFlow) | ¥1,000-1,800/月 |
| **合计** | **约¥2,000-3,100/月** |
