# 卡点2: 收录数据与曝光量获取

> 类型: 技术方案文档 (PRD)
> 优先级: P0
> 预估工时: 1.5周
> 最后更新: 2026-05-01

---

## 1. 问题定义

### 1.1 现状

- `index_check_service.py` (824行): 通过Playwright模拟检测AI平台(豆包/通义千问/DeepSeek)是否引用目标文章
- 只检测AI平台，不检测传统搜索引擎收录
- 曝光量/阅读量数据未接入
- 检测方式资源消耗大 (每次1-3GB内存)

### 1.2 核心问题

需要建立**分层量化指标体系**，回答：
1. 文章是否被百度/Google收录？
2. 文章是否被AI搜索引擎引用？
3. 文章在各平台的曝光量、阅读量、互动量如何？

---

## 2. 技术架构

### 2.1 分层数据采集架构

```
┌─────────────────────────────────────────────┐
│              数据采集调度器 (APScheduler)       │
└──────────────────┬──────────────────────────┘
                   │
    ┌──────────────┼──────────────┐
    │              │              │
┌───▼────┐  ┌─────▼─────┐  ┌────▼─────┐
│ 第一层  │  │  第二层    │  │  第三层   │
│ 免费    │  │  付费API   │  │  自有埋点  │
│         │  │            │  │          │
│百度推送  │  │5118收录API │  │百度统计   │
│头条API  │  │¥199-599/月 │  │JS SDK    │
│AI引用检测│  │            │  │短链追踪   │
└───┬────┘  └─────┬─────┘  └────┬─────┘
    │              │              │
    └──────────────┼──────────────┘
                   │
            ┌──────▼──────┐
            │  统一数据层   │
            │  DataWarehouse│
            └─────────────┘
```

### 2.2 数据渠道对比

| 数据类型 | 来源 | API能力 | 自动化难度 | 可靠性 |
|----------|------|---------|-----------|--------|
| 百度收录 | 百度站长平台 | URL推送API (仅提交) | 低 | 高 |
| 百度收录查询 | site:指令 | 无官方API | 中 | 中 |
| 百度收录查询 | 5118 API | 付费API | 低 | 高 |
| 百家号数据 | 百家号后台 | 无公开API | 需爬虫 | 中 |
| 头条号数据 | 头条创作者中心 | **有API** | 低 | 高 |
| 知乎数据 | 知乎API v4 | 有限 | 中 | 中 |
| AI引用检测 | 当前Playwright | 无API | 已实现 | 中 |

---

## 3. 详细设计

### 3.1 第一层: 免费数据源

#### 3.1.1 百度站长URL推送

文章发布后自动推送URL给百度。

```python
# backend/services/baidu_webmaster.py (新建 ~80行)

class BaiduWebmasterService:
    """百度站长平台 URL推送"""
    
    PUSH_URL = "http://data.zz.baidu.com/urls"
    
    async def push_urls(self, site: str, token: str, urls: list[str]):
        """批量推送URL给百度"""
        async with httpx.AsyncClient() as client:
            resp = await client.post(
                f"{self.PUSH_URL}?site={site}&token={token}",
                content="\n".join(urls),
                headers={"Content-Type": "text/plain"}
            )
        return resp.json()
        # 返回: {"success": 5, "remain": 9995}
```

#### 3.1.2 头条号数据API

```python
# backend/services/toutiao_analytics.py (新建 ~120行)

class ToutiaoAnalyticsService:
    """头条号数据分析"""
    
    async def get_article_stats(self, access_token: str, item_ids: list[str]):
        """获取文章阅读/点赞/评论数据"""
        # 头条创作者服务API
        async with httpx.AsyncClient() as client:
            resp = await client.get(
                "https://open.toutiao.com/api/articles/stats",
                headers={"Authorization": f"Bearer {access_token}"},
                params={"item_ids": ",".join(item_ids)}
            )
        return self._parse_stats(resp.json())
```

### 3.2 第二层: 付费API

#### 3.2.1 5118 API接入

```python
# backend/services/data_5118.py (新建 ~150行)

class Data5118Service:
    """5118大数据平台 API"""
    
    def __init__(self):
        self.api_key = config.DATA_5118_API_KEY
        self.base_url = "https://openapi.5118.com"
    
    async def check_baidu_index(self, urls: list[str]) -> list[dict]:
        """批量查询百度收录状态"""
        async with httpx.AsyncClient() as client:
            resp = await client.post(
                f"{self.base_url}/baidu/indexed",
                headers={"Authorization": f"Bearer {self.api_key}"},
                json={"urls": urls}
            )
        # 返回: [{"url": "...", "indexed": true, "index_date": "2026-04-28"}]
        return resp.json().get("data", [])
    
    async def get_keyword_ranking(self, keyword: str, domain: str):
        """查询关键词在百度的排名"""
        async with httpx.AsyncClient() as client:
            resp = await client.get(
                f"{self.base_url}/keyword/ranking",
                headers={"Authorization": f"Bearer {self.api_key}"},
                params={"keyword": keyword, "domain": domain}
            )
        return resp.json()
```

### 3.3 第三层: AI引用检测优化

保留现有Playwright方案，做性能优化:

```python
# 优化 index_check_service.py

class IndexCheckService:
    
    async def check_keyword_optimized(self, keyword: str):
        """优化后的关键词检测"""
        
        # 1. 缓存检查: 7天内相同关键词不重复检测
        cache_key = f"index_check:{keyword}"
        cached = await self._check_cache(cache_key)
        if cached:
            return cached
        
        # 2. 并发检测3个平台
        tasks = [
            self._check_single_platform(checker, keyword)
            for checker in self._checkers
        ]
        results = await asyncio.gather(*tasks, return_exceptions=True)
        
        # 3. 缓存结果
        await self._set_cache(cache_key, results, ttl=7*24*3600)
        return results
```

---

## 4. 数据库变更

### 4.1 新增数据采集表

```python
# models.py 新增

class IndexRecord(Base):
    """收录/引用记录"""
    __tablename__ = "index_records"
    
    id = Column(Integer, primary_key=True)
    article_id = Column(Integer, ForeignKey("geo_articles.id"))
    platform = Column(String(50))        # "baidu" / "google" / "doubao" / "qianwen" / "deepseek"
    record_type = Column(String(20))     # "index" / "citation" / "impression"
    is_indexed = Column(Boolean, default=False)
    position = Column(Integer, nullable=True)    # 排名位置
    citation_found = Column(Boolean, default=False)
    company_found = Column(Boolean, default=False)
    checked_at = Column(DateTime, default=func.now())
    
class PlatformStats(Base):
    """平台数据统计"""
    __tablename__ = "platform_stats"
    
    id = Column(Integer, primary_key=True)
    article_id = Column(Integer, ForeignKey("geo_articles.id"))
    platform = Column(String(50))        # "toutiao" / "baijiahao" / "zhihu" / ...
    views = Column(Integer, default=0)
    likes = Column(Integer, default=0)
    comments = Column(Integer, default=0)
    shares = Column(Integer, default=0)
    collected_at = Column(DateTime, default=func.now())
```

---

## 5. API设计

| 端点 | 方法 | 说明 |
|------|------|------|
| `/api/analytics/dashboard` | GET | 数据总览 (收录率/AI引用率/阅读量) |
| `/api/analytics/index-status` | GET | 文章收录状态查询 |
| `/api/analytics/platform-stats` | GET | 各平台数据统计 |
| `/api/analytics/ai-citations` | GET | AI引用检测报告 |
| `/api/analytics/trends` | GET | 趋势数据 (收录/引用随时间变化) |

---

## 6. 配置变更

```python
# config.py 新增

# 百度站长平台
BAIDU_WEBMASTER_SITE = os.getenv("BAIDU_WEBMASTER_SITE", "")
BAIDU_WEBMASTER_TOKEN = os.getenv("BAIDU_WEBMASTER_TOKEN", "")

# 5118 大数据平台
DATA_5118_API_KEY = os.getenv("DATA_5118_API_KEY", "")

# 头条号API
TOUTIAO_ACCESS_TOKEN = os.getenv("TOUTIAO_ACCESS_TOKEN", "")

# 检测缓存
INDEX_CHECK_CACHE_TTL = int(os.getenv("INDEX_CHECK_CACHE_TTL", "604800"))  # 7天
```

---

## 7. 测试方案

1. **单元测试**: mock各API响应，测试解析逻辑
2. **集成测试**: 对10篇已发布文章验证收录查询准确性
3. **性能测试**: 验证缓存机制减少80%重复查询
4. **端到端**: 发布文章 → 自动推送URL → 7天后查询收录 → 更新统计

---

## 8. 成本估算

| 项目 | 月费用 | 说明 |
|------|--------|------|
| 百度站长推送 | 免费 | URL推送API免费 |
| 5118 API (标准版) | ¥599/月 | 百度收录+关键词排名 |
| 头条号API | 免费 | 官方开放API |
| AI引用检测 (优化后) | ¥0 (自有) | 减少资源消耗 |
| **合计** | **¥599/月** | |

---

## 9. 权威参考文献

### 学术论文

1. **Aggarwal, P., et al. (2024).** "GEO: Generative Engine Optimization." *arXiv:2311.09735*.
   - GEO-bench数据集定义，包含AI引用可见性评估标准

2. **Fang, T., et al. (2025).** "CiteEval: Citation Evaluation in Retrieval-Augmented Generation." *ACL 2025*.
   - 引文质量评估框架，提出CFR(引文频率率)等核心指标

3. **Dong, Y., et al. (2025).** "Content Freshness and LLM Citation Preferences." *Hill Web Creations Research*.
   - AI搜索引用源比传统搜索结果平均新25.7%
   - ChatGPT偏好比传统结果新一年以上的内容

### 行业报告

4. **Brandlight (2025).** "Benchmarking Generative Visibility."
   - CFR基准: 成熟品牌15-30%，新兴品牌5-10%
   - RPI>7.0，CSOV>25%为健康指标

5. **Ahrefs (2025).** "Google AI Overviews: 36M+ Citations Analysis."
   - Top 20域名占66.18%引用，Top 5占38.13%
   - Google自属域名占22.81%引用

6. **百度站长平台文档 (2025).** "百度搜索资源平台 — 链接提交API."
   - URL推送接口规范，每日配额10万条

7. **5118大数据平台 (2025).** "开放API文档 v3.0."
   - 百度收录查询、关键词排名、竞品分析API接口

8. **字节跳动开放平台 (2025).** "头条号创作者服务API."
   - 文章数据统计接口，支持阅读/点赞/评论/分享查询
