# 卡点1: 关键词蒸馏 — 高价值关键词定义与评分系统

> 类型: 技术方案文档 (PRD)
> 优先级: P0
> 预估工时: 2周
> 最后更新: 2026-05-01

---

## 1. 问题定义

### 1.1 现状

当前 `keyword_service.py` (182行) 实现了基础关键词CRUD + n8n蒸馏调用，但缺乏**高价值关键词的量化评分体系**。

- `distill()` 方法 (line 63): 调用 n8n webhook 生成关键词变体，返回数量由 `count` 参数控制
- `generate_questions()` (line 132): 生成问题变体，同样调用 n8n
- **无评分机制**: 关键词无优先级、无价值量化，全部一视同仁投入内容生成

### 1.2 核心问题

如何判断一个关键词/问题值得投入资源生成GEO文章？需要回答：
1. 这个关键词被AI搜索引擎引用的概率有多大？
2. 这个关键词的实体连接度是否足够？
3. 竞争难度如何，能否快速见效？

### 1.3 影响范围

- 文章生成成本: 每篇约 ¥0.5-1 (AI API + n8n + Playwright)
- 资源消耗: 每篇文章需要 Playwright 自动化发布 (1-3GB内存)
- 如果低价值关键词占用资源，高价值关键词被延误

---

## 2. 技术架构

### 2.1 三维评分模型

```
关键词价值 = f(AI引用潜力, 实体连接度, 竞争难度)
```

采用 **LLM多维评分 + RAGFlow向量相似度 + 人工校准** 的混合方案。

### 2.2 系统架构

```
用户输入关键词/主题
       │
       ▼
┌──────────────────────────────┐
│     KeywordScoringEngine      │
│                               │
│  ┌─────────┐ ┌─────────────┐ │
│  │ LLM评分 │ │ 向量相似度   │ │
│  │ (DeepSeek)│ (RAGFlow)   │ │
│  └────┬────┘ └──────┬──────┘ │
│       │             │        │
│  ┌────▼─────────────▼──────┐ │
│  │   综合评分 + 人工校准     │ │
│  │   输出: 0-100分 + 等级    │ │
│  └─────────────────────────┘ │
└──────────────────────────────┘
```

---

## 3. 详细设计

### 3.1 维度1: AI引用潜力评分 (Citation Potential Score)

基于GEO学术研究，AI引用内容的5大特征:

| 特征 | 权重 | 说明 | 量化方法 |
|------|------|------|---------|
| 问题式意图 | 30% | "什么是..." "如何..." 被引用概率高58% | 正则匹配+LLM分类 |
| 品牌对比意图 | 25% | "A vs B" 格式，表格引用率52% | LLM意图识别 |
| 列表/特征意图 | 20% | 功能列表引用率64-82% | 关键词模式匹配 |
| 长尾精准意图 | 15% | 超具体查询竞争低、命中高 | 词长度+特异度 |
| 通用信息意图 | 10% | 覆盖面广但竞争大 | 逆向文档频率 |

**实现**: 使用 DeepSeek API 做单次LLM评分调用。

### 3.2 维度2: 实体连接度评分 (Entity Connectivity Score)

**方案: 纯向量方案 (复用RAGFlow)**

```
1. 提取关键词中的命名实体
2. 用 RAGFlow retrieve() 检索相关文档数量和相似度
3. 相关文档越多 = 实体连接度越高 = AI更容易检索到
```

**无需引入 Neo4j**。RAGFlow 已有向量检索能力，`retrieve()` 方法 (ragflow_client.py:519) 支持 top_k=1024 的检索。

### 3.3 维度3: 竞争难度评估

| 指标 | 来源 | 方法 |
|------|------|------|
| 搜索结果数量 | 百度/Google site: | Playwright查询 |
| 已有权威内容数 | RAGFlow检索 | 相关文档质量 |
| 关键词长度 | 本地计算 | 词数+特异度 |

---

## 4. 数据库变更

### 4.1 Keyword 表新增字段

```python
# backend/database/models.py — Keyword 模型

class Keyword(Base):
    # ... 现有字段 ...
    
    # 新增评分字段
    citation_score = Column(Integer, nullable=True, comment="AI引用潜力评分 0-100")
    entity_score = Column(Integer, nullable=True, comment="实体连接度评分 0-100")  
    difficulty_score = Column(Integer, nullable=True, comment="竞争难度评分 0-100")
    final_score = Column(Integer, nullable=True, comment="综合评分 0-100")
    score_level = Column(String(10), nullable=True, comment="等级: high/medium/low")
    scored_at = Column(DateTime, nullable=True, comment="最近评分时间")
    score_version = Column(String(10), default="v1", comment="评分模型版本")
```

### 4.2 迁移脚本

```sql
ALTER TABLE keywords ADD COLUMN citation_score INTEGER;
ALTER TABLE keywords ADD COLUMN entity_score INTEGER;
ALTER TABLE keywords ADD COLUMN difficulty_score INTEGER;
ALTER TABLE keywords ADD COLUMN final_score INTEGER;
ALTER TABLE keywords ADD COLUMN score_level VARCHAR(10);
ALTER TABLE keywords ADD COLUMN scored_at DATETIME;
ALTER TABLE keywords ADD COLUMN score_version VARCHAR(10) DEFAULT 'v1';
```

---

## 5. API 设计

### 5.1 关键词评分端点

| 端点 | 方法 | 说明 |
|------|------|------|
| `/api/keywords/{id}/score` | POST | 对单个关键词评分 |
| `/api/keywords/batch-score` | POST | 批量评分 (project_id) |
| `/api/keywords/{id}/score` | GET | 获取评分详情 |
| `/api/keywords/rankings` | GET | 项目关键词排行 (按分数排序) |

### 5.2 请求/响应格式

```python
# POST /api/keywords/{id}/score 响应
{
    "keyword_id": 123,
    "keyword": "如何选择合适的企业SEO工具",
    "scores": {
        "citation_potential": 85,    # AI引用潜力
        "entity_connectivity": 72,   # 实体连接度
        "difficulty": 45,            # 竞争难度(越低越好)
        "final": 76                  # 综合评分
    },
    "level": "high",
    "reasoning": "问题式意图明确，实体关联丰富，中等竞争",
    "suggestions": [
        "可以加入数据对比增强引用概率",
        "建议生成FAQ结构内容"
    ]
}
```

---

## 6. 核心代码设计

### 6.1 新建 `backend/services/keyword_scorer.py` (~200行)

```python
from dataclasses import dataclass
from backend.services.ragflow_client import get_ragflow_client
from backend.config import DEEPSEEK_API_KEY, DEEPSEEK_API_URL
import httpx

@dataclass
class KeywordScoreResult:
    citation_potential: int      # 0-100
    entity_connectivity: int     # 0-100
    difficulty: int              # 0-100
    final_score: int             # 0-100
    level: str                   # high/medium/low
    reasoning: str
    suggestions: list[str]

class KeywordScorer:
    """关键词三维评分器"""
    
    SCORING_PROMPT = """
    评估以下关键词在GEO(生成式引擎优化)场景中的价值。
    
    行业: {industry}
    关键词: "{keyword}"
    目标公司: {company_name}
    
    从以下维度评分(0-100):
    1. citation_potential: AI搜索引擎(豆包/通义千问/DeepSeek/ChatGPT)回答相关问题时引用该内容的概率
       - 问题式意图("什么是"/"如何")= 高分
       - 品牌对比意图("A vs B") = 高分
       - 列表/特征意图 = 高分
       - 通用信息 = 低分
    2. entity_connectivity: 关键词与行业核心实体的语义关联强度
       - 包含多个命名实体 = 高分
       - 与行业核心概念关联 = 高分
    3. difficulty: 现有内容的竞争激烈程度
       - 搜索结果少 = 低分(容易) = 好
       - 权威内容多 = 高分(困难) = 差
    
    严格返回JSON:
    {{"scores": {{"citation_potential": N, "entity_connectivity": N, "difficulty": N}},
      "reasoning": "...",
      "suggestions": ["建议1", "建议2"]}}
    """
    
    async def score(self, keyword: str, industry: str = "", 
                    company_name: str = "") -> KeywordScoreResult:
        # 1. LLM评分
        llm_result = await self._llm_score(keyword, industry, company_name)
        
        # 2. 实体连接度向量验证 (用RAGFlow补充)
        entity_score = await self._vector_score(keyword)
        
        # 3. 如果LLM和向量分数差异>20，取平均
        final_entity = self._merge_scores(
            llm_result["scores"]["entity_connectivity"], 
            entity_score
        )
        
        # 4. 综合评分
        citation = llm_result["scores"]["citation_potential"]
        difficulty = llm_result["scores"]["difficulty"]
        final = citation * 0.4 + final_entity * 0.3 + (100 - difficulty) * 0.3
        
        return KeywordScoreResult(
            citation_potential=citation,
            entity_connectivity=final_entity,
            difficulty=difficulty,
            final_score=round(final),
            level="high" if final > 70 else "medium" if final > 40 else "low",
            reasoning=llm_result["reasoning"],
            suggestions=llm_result["suggestions"]
        )
    
    async def _llm_score(self, keyword, industry, company_name):
        """调用DeepSeek做LLM评分"""
        prompt = self.SCORING_PROMPT.format(
            industry=industry, keyword=keyword, company_name=company_name
        )
        async with httpx.AsyncClient() as client:
            resp = await client.post(
                f"{DEEPSEEK_API_URL}/chat/completions",
                headers={"Authorization": f"Bearer {DEEPSEEK_API_KEY}"},
                json={
                    "model": "deepseek-chat",
                    "messages": [{"role": "user", "content": prompt}],
                    "temperature": 0.3,
                    "response_format": {"type": "json_object"}
                }
            )
        return self._parse_json(resp.json())
    
    async def _vector_score(self, keyword: str) -> int:
        """用RAGFlow向量检索验证实体连接度"""
        ragflow = get_ragflow_client()
        if not ragflow.is_configured():
            return 50  # 未配置RAGFlow时返回默认值
        result = ragflow.retrieve(
            question=keyword,
            dataset_ids=[config.RAGFLOW_DATASET_ID],
            top_k=20,
            similarity_threshold=0.5
        )
        # 匹配文档数量越多 = 实体连接度越高
        chunks = result.get("data", {}).get("chunks", [])
        return min(100, len(chunks) * 5)
```

### 6.2 修改 `keyword_service.py`

```python
# 在 distill() 方法返回后，自动对生成的关键词评分
async def distill_and_score(self, *, core_kw: str, industry: str = "", 
                            company_name: str = "", **kwargs):
    # 1. 原有蒸馏流程
    result = await self.distill(core_kw=core_kw, **kwargs)
    
    # 2. 对蒸馏出的关键词批量评分
    scorer = KeywordScorer()
    keywords = result.get("keywords", [])
    for kw in keywords:
        score_result = await scorer.score(kw, industry, company_name)
        # 保存到数据库
        db_keyword = self.db.query(Keyword).filter_by(keyword=kw).first()
        if db_keyword:
            db_keyword.citation_score = score_result.citation_potential
            db_keyword.entity_score = score_result.entity_connectivity
            db_keyword.difficulty_score = score_result.difficulty
            db_keyword.final_score = score_result.final_score
            db_keyword.score_level = score_result.level
            db_keyword.scored_at = datetime.now()
    self.db.commit()
    return result
```

---

## 7. 测试方案

### 7.1 单元测试

```python
# tests/test_keyword_scorer.py

def test_citation_potential_question_format():
    """问题式关键词应得到高引用潜力分"""
    scorer = KeywordScorer()
    # mock LLM response
    result = scorer.score("如何选择合适的企业SEO工具", industry="科技")
    assert result.citation_potential > 70

def test_entity_connectivity_rich_entity():
    """包含多个实体的关键词应得到高连接度"""
    result = scorer.score("华为云 vs 阿里云企业级服务对比")
    assert result.entity_connectivity > 60

def test_difficulty_niche_keyword():
    """长尾精准关键词应得到低难度分"""
    result = scorer.score("2026年苏州中小型SaaS企业CRM选型指南")
    assert result.difficulty < 50
```

### 7.2 集成测试

1. 对10个已知高价值关键词评分，验证排序正确性
2. 对比LLM评分与人工标注的一致性 (目标: >70%)
3. 验证RAGFlow向量评分的补充效果

### 7.3 A/B验证

| 组 | 方法 | 指标 |
|----|------|------|
| 对照组 | 随机选择关键词发布 | AI引用率 |
| 实验组 | 使用评分系统筛选>70分的关键词 | AI引用率 |
| 目标 | 实验组AI引用率 > 对照组 30% | |

---

## 8. 成本估算

| 项目 | 单价 | 数量 | 月成本 |
|------|------|------|--------|
| DeepSeek API (评分) | ¥0.001/次 | 1000个关键词 | ¥1 |
| RAGFlow 检索 | ¥0 (自有) | — | ¥0 |
| **合计** | | | **¥1/月** |

---

## 9. 权威参考文献

### 学术论文

1. **Aggarwal, P., et al. (2024).** "GEO: Generative Engine Optimization." *arXiv:2311.09735*. Princeton University.
   - 里程碑论文，首次定义GEO概念，证明优化内容可将生成引擎可见性提升40%
   - 提出GEO-bench数据集 (10,000查询)，确立领域评估标准

2. **He, J., et al. (2025).** "Benchmarking Generative Visibility Across AI Search Platforms." *arXiv:2509.08919*.
   - 跨平台AI搜索对比研究，覆盖多语言多垂直领域
   - 发现AI搜索与传统搜索在域名多样性、时效性、查询稳定性方面存在显著差异

3. **Fang, T., et al. (2025).** "CiteEval: Principles-driven Citation Evaluation." *ACL 2025*.
   - 引文质量评估框架，提出基于全文检索上下文的细粒度引文评估
   - CITEEVAL-AUTO自动化指标与人类判断高度相关

### 行业报告

4. **Evertune Research (2025).** "How AI Systems Choose Which Brands to Cite in Search Results."
   - 分析75,000品牌，品牌搜索量与AI引用频率相关系数0.334
   - 发现90%的ChatGPT引用来自非传统搜索前两页

5. **Ziptie Analysis (2025).** "How Perplexity AI Answers Work — Citation Gauntlet Model."
   - 详细解析Perplexity的5层引文筛选机制
   - 发现90%顶级引用源遵循BLUF (Bottom Line Up Front) 模式

6. **Ahrefs Analysis (2025).** "Google AI Overviews: Top Cited Domains 2025."
   - 分析3600万AI Overviews，Wikipedia占11.22%引用，YouTube 9.51%
   - Reddit引用率3个月增长450% (1.30% → 7.15%)

7. **Statista (2025).** "Top Web Domains Cited by Large Language Models."
   - LLM引用域名集中度分析，Top 20域名占66.18%引用

8. **Brandlight (2025).** "Benchmarking Generative Visibility: CFR, RPI, CSOV Metrics."
   - 提出AI可见性三大核心指标: CFR (引文频率率), RPI (相对位置指数), CSOV (引文声量份额)
   - 基准: CFR 15-30%(成熟品牌), RPI>7.0, CSOV>25%
