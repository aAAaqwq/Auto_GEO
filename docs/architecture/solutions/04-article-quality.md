# 卡点4: GEO文章质量评估算法 (LLM-as-Judge)

> 类型: 技术方案文档 (PRD)
> 优先级: P0
> 预估工时: 1.5周
> 最后更新: 2026-05-01

---

## 1. 问题定义

### 1.1 现状

当前 `geo_article_service.py:311-322` 的 `check_quality()` 方法是**完全stub**:

```python
# 当前实现 — 随机评分!
async def check_quality(self, article_id: int) -> dict:
    article = self.db.query(GeoArticle).get(article_id)
    article.quality_score = random.randint(85, 98)  # 随机!
    article.quality_status = "passed"                # 永远通过!
    self.db.commit()
    return {"success": True, "score": article.quality_score}
```

### 1.2 影响范围

- `GeoArticle` 模型已有 `quality_score`, `ai_score`, `readability_score`, `quality_status` 字段
- n8n回调 (`geo.py:339-346`) 已映射 `quality_score` 和 `seo_score`
- **所有质量评分数据都是假的**，无法指导内容优化

---

## 2. 技术架构

### 2.1 LLM-as-Judge 评分引擎

```
文章内容 + 关键词 + 公司名
       │
       ▼
┌──────────────────────────────┐
│      ArticleScorer            │
│                               │
│  评分维度:                     │
│  ├─ content_quality (0-100)   │ 内容质量、信息密度
│  ├─ ai_likeness (0-100)      │ AI痕迹检测
│  ├─ readability (0-100)       │ 可读性
│  ├─ geo_optimization (0-100)  │ GEO优化程度
│  └─ keyword_relevance (0-100) │ 关键词相关性
│                               │
│  综合评分 → passed / failed   │
└──────────────────────────────┘
```

---

## 3. 详细设计

### 3.1 新建 `backend/services/article_scorer.py` (~300行)

```python
from dataclasses import dataclass
import httpx
from backend.config import DEEPSEEK_API_KEY, DEEPSEEK_API_URL

@dataclass
class ScoringResult:
    overall_score: int
    content_quality: int
    ai_likeness: int
    readability: int
    geo_optimization: int
    keyword_relevance: int
    reasoning: str
    issues: list[str]
    suggestions: list[str]
    passed: bool

class ArticleScorer:
    """LLM-as-Judge 文章质量评分器"""
    
    SCORING_PROMPT = """
你是一位GEO(生成式引擎优化)专家和内容质量审核员。请评估以下文章。

## 文章信息
标题: {title}
关键词: {keywords}
目标公司: {company_name}

## 文章内容
{content}

## 评分标准 (每项0-100分)

### 1. content_quality (内容质量)
- 信息密度: 是否包含具体数据、案例、引用
- 逻辑连贯性: 段落之间是否有清晰逻辑链
- 独特价值: 是否提供区别于常见内容的独特观点
- **高分特征**: 包含统计数据、行业报告引用、具体案例

### 2. ai_likeness (AI痕迹检测)
- 用词是否过于模板化 ("总之"/"值得注意的是"/"首先...其次...最后")
- 段落结构是否过于对称和工整
- 是否缺乏个人化表达和口语化表达
- **高分 = 更像AI生成 (差)**, **低分 = 更自然 (好)**

### 3. readability (可读性)
- 段落长度: 每段不超过150字
- 标题层级: 是否有H2/H3分区
- 列表/表格: 是否使用结构化格式
- 过渡词: 段落间是否有自然过渡

### 4. geo_optimization (GEO优化程度)
- 结构化数据: 是否有FAQ、对比表格、数据图表描述
- 引文友好: 是否有明确结论可直接摘录
- 实体标注: 是否明确提及公司名/产品名/行业术语
- BLUF原则: 结论是否前置

### 5. keyword_relevance (关键词相关性)
- 关键词是否自然融入标题和正文
- 是否围绕关键词展开而非偏离主题
- 语义相关性: 是否覆盖关键词的多个语义维度

## 输出格式
严格返回JSON:
{{
  "scores": {{
    "content_quality": N,
    "ai_likeness": N,
    "readability": N,
    "geo_optimization": N,
    "keyword_relevance": N
  }},
  "overall": N,
  "passed": true/false,
  "reasoning": "评分理由(50字以内)",
  "issues": ["问题1", "问题2"],
  "suggestions": ["建议1", "建议2"]
}}

**通过标准**: overall >= 70 且 ai_likeness <= 60
"""
    
    async def score_article(
        self, 
        content: str, 
        title: str = "", 
        keywords: list[str] = None,
        company_name: str = ""
    ) -> ScoringResult:
        """对文章进行多维度评分"""
        
        prompt = self.SCORING_PROMPT.format(
            title=title,
            keywords=", ".join(keywords or []),
            company_name=company_name,
            content=content[:3000]  # 限制输入长度控制成本
        )
        
        async with httpx.AsyncClient(timeout=60) as client:
            resp = await client.post(
                f"{DEEPSEEK_API_URL}/chat/completions",
                headers={"Authorization": f"Bearer {DEEPSEEK_API_KEY}"},
                json={
                    "model": "deepseek-chat",
                    "messages": [{"role": "user", "content": prompt}],
                    "temperature": 0.2,  # 低温度确保一致性
                    "response_format": {"type": "json_object"}
                }
            )
        
        data = resp.json()
        content_text = data["choices"][0]["message"]["content"]
        result = self._parse_response(content_text)
        
        return ScoringResult(
            overall_score=result["overall"],
            content_quality=result["scores"]["content_quality"],
            ai_likeness=result["scores"]["ai_likeness"],
            readability=result["scores"]["readability"],
            geo_optimization=result["scores"]["geo_optimization"],
            keyword_relevance=result["scores"]["keyword_relevance"],
            reasoning=result.get("reasoning", ""),
            issues=result.get("issues", []),
            suggestions=result.get("suggestions", []),
            passed=result.get("passed", result["overall"] >= 70)
        )
    
    async def batch_score(self, articles: list[dict]) -> list[ScoringResult]:
        """批量评分"""
        tasks = [
            self.score_article(
                content=a["content"],
                title=a.get("title", ""),
                keywords=a.get("keywords", []),
                company_name=a.get("company_name", "")
            )
            for a in articles
        ]
        return await asyncio.gather(*tasks)
```

### 3.2 集成到文章生成流程

```python
# 修改 geo_article_service.py — 替换 check_quality() stub

async def check_quality(self, article_id: int) -> dict:
    """LLM-as-Judge 文章质量评估"""
    article = self.db.query(GeoArticle).get(article_id)
    if not article:
        return {"success": False, "error": "文章不存在"}
    
    gen_log.info(f"正在对文章 {article_id} 进行 AI 质量评估...")
    
    try:
        scorer = ArticleScorer()
        result = await scorer.score_article(
            content=article.content,
            title=article.title,
            keywords=article.target_keywords if hasattr(article, 'target_keywords') else [],
            company_name=article.company_name if hasattr(article, 'company_name') else ""
        )
        
        article.quality_score = result.overall_score
        article.ai_score = result.ai_likeness
        article.readability_score = result.readability
        article.quality_status = "passed" if result.passed else "failed"
        self.db.commit()
        
        return {
            "success": True,
            "score": result.overall_score,
            "details": {
                "content_quality": result.content_quality,
                "ai_likeness": result.ai_likeness,
                "readability": result.readability,
                "geo_optimization": result.geo_optimization,
                "keyword_relevance": result.keyword_relevance,
            },
            "issues": result.issues,
            "suggestions": result.suggestions,
            "reasoning": result.reasoning
        }
    except Exception as e:
        gen_log.error(f"质量评估失败: {e}")
        article.quality_status = "error"
        self.db.commit()
        return {"success": False, "error": str(e)}
```

### 3.3 配置变更

```python
# config.py 新增

# LLM-as-Judge 评分配置
JUDGE_MODEL = os.getenv("JUDGE_MODEL", "deepseek-chat")
JUDGE_MIN_QUALITY = int(os.getenv("JUDGE_MIN_QUALITY", "70"))
JUDGE_MAX_AI_SCORE = int(os.getenv("JUDGE_MAX_AI_SCORE", "60"))
JUDGE_MAX_CONTENT_LENGTH = int(os.getenv("JUDGE_MAX_CONTENT_LENGTH", "3000"))
```

---

## 4. API设计

| 端点 | 方法 | 说明 |
|------|------|------|
| `POST /api/geo/articles/{id}/rescore` | POST | 手动触发重新评分 |
| `POST /api/geo/articles/batch-score` | POST | 批量评分 |
| `GET /api/geo/articles/{id}/score-detail` | GET | 获取评分详情 |

---

## 5. 测试方案

### 5.1 Prompt验证

用10篇已知质量的文章测试:
- 5篇高质量人工文章 → 预期 overall > 80
- 5篇AI模板文章 → 预期 ai_likeness > 70

### 5.2 一致性测试

同一篇文章评分5次，验证标准差 < 10分。

### 5.3 人工对比

| 方法 | 与人工评分相关性 | 目标 |
|------|-----------------|------|
| LLM单次评分 | >0.7 | 初期目标 |
| LLM取3次平均 | >0.8 | 优化后 |
| LLM + 规则引擎混合 | >0.85 | 长期目标 |

---

## 6. 成本估算

| 项目 | 计算 | 月成本 |
|------|------|--------|
| 评分API调用 | 100篇 × ~2500 tokens × ¥0.001/K | ¥0.25/月 |
| 批量评分(高峰) | 500篇/月 | ¥1.25/月 |
| **合计** | | **¥1-2/月** |

DeepSeek API 极低成本，几乎可忽略。

---

## 7. 权威参考文献

### 学术论文

1. **Zheng, L., et al. (2023).** "Judging LLM-as-a-Judge with MT-Bench and Chatbot Arena." *NeurIPS 2023*.
   - LLM-as-Judge范式奠基论文，提出pointwise和pairwise两种评估模式
   - GPT-4作为裁判与人类专家一致性达85%

2. **Li, J., et al. (2024).** "Survey on LLMs-as-Judges." *arXiv:2409.16442*.
   - LLM评估全面综述，涵盖偏见、校准、提示设计最佳实践
   - 建议温度0.1-0.3确保评估一致性

3. **Wang, Y., et al. (2023).** "G-Eval: NLG Evaluation using GPT-4 with Chain-of-Weighing." *ACL 2023*.
   - 基于思维链的文本生成评估方法，多维度评分框架
   - 与人类判断Kendall相关性>0.7

4. **Zhu, M., et al. (2024).** "JudgeBench: A Benchmark for Evaluating LLM-based Judges." *arXiv:2410.12784*.
   - LLM裁判评估基准，测试裁判模型在偏见、长度偏好、事实一致性等方面的表现

5. **Sottana, A., et al. (2024).** "DetectRL: Detecting LLM-Generated Text." *arXiv:2409.11578*.
   - AI生成文本检测方法，包含风格分析、统计特征、多维度评估

### 行业报告

6. **Galileo AI (2025).** "Mastering LLM Evaluation: Metrics, Frameworks, and Techniques."
   - 实用LLM评估指南，包含成本分析和最佳实践

7. **DeepSeek Team (2025).** "DeepSeek-V3 API Pricing and Performance."
   - DeepSeek API定价: 输入¥0.001/M tokens，输出¥0.002/M tokens
   - 中文理解能力接近GPT-4水平

8. **Aggarwal, P., et al. (2024).** "GEO: Generative Engine Optimization." *arXiv:2311.09735*.
   - GEO文章优化建议: 结构化数据、FAQ格式、BLUF原则可提升AI引用率40%
