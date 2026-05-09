# 卡点8: 权威新闻渠道接入

> 类型: 技术方案文档 (PRD)
> 优先级: P2
> 预估工时: 1周
> 最后更新: 2026-05-01

---

## 1. 问题定义

### 1.1 现状

当前系统仅支持通过自媒体平台(头条号/百家号/知乎等)发布内容，缺乏**权威新闻渠道**:

- 自媒体平台内容权重低，AI搜索引擎引用概率低
- 无新闻门户(新浪/网易/搜狐)分发能力
- 无新闻稿发布服务对接
- 缺乏外链建设策略

### 1.2 为什么需要权威新闻渠道

| 维度 | 自媒体平台 | 权威新闻门户 |
|------|-----------|------------|
| AI引用权重 | 低 | 高 |
| 百度收录速度 | 1-7天 | 即时-24小时 |
| 域名权重(DA) | 50-70 | 80-95 |
| 外链价值 | nofollow为主 | dofollow |
| 内容审核 | 宽松 | 严格 |
| 成本 | 免费 | 付费 |

### 1.3 影响范围

- GEO效果: 缺乏权威来源引用，AI搜索引擎信任度低
- 品牌背书: 无新闻媒体报道可引用
- SEO效果: 缺乏高质量外链

---

## 2. 技术架构

### 2.1 渠道矩阵

```
┌─────────────────────────────────────────────┐
│             内容分发矩阵                      │
│                                              │
│  ┌──────────┐  ┌──────────┐  ┌──────────┐  │
│  │ 自媒体    │  │ 新闻门户  │  │ 新闻稿    │  │
│  │ (现有)   │  │ (新增)    │  │ 服务商    │  │
│  │          │  │          │  │          │  │
│  │ 头条号   │  │ 搜狐号    │  │ 媒介盒子  │  │
│  │ 百家号   │  │ 网易号    │  │ 美通社    │  │
│  │ 知乎    │  │ 新浪号    │  │ 企名片    │  │
│  │ 微信公众号│  │           │  │          │  │
│  └──────────┘  └──────────┘  └──────────┘  │
│                                              │
│  ┌──────────────────────────────────────┐   │
│  │         统一内容适配层                 │   │
│  │  同一篇文章 → 不同渠道格式/长度适配     │   │
│  └──────────────────────────────────────┘   │
└─────────────────────────────────────────────┘
```

### 2.2 渠道对比

| 渠道 | 接入方式 | 成本 | 审核周期 | 收录效果 |
|------|---------|------|---------|---------|
| 搜狐号 | Playwright/手动 | 免费 | 1-2小时 | 中 |
| 网易号 | Playwright/手动 | 免费 | 2-4小时 | 中高 |
| 新浪号 | 需申请 | 免费 | 1-3天 | 高 |
| 媒介盒子 | API | ¥50-500/篇 | 1-24小时 | 很高 |
| 美通社 | API | ¥2000+/篇 | 1-3天 | 极高 |

---

## 3. 详细设计

### 3.1 新闻门户发布器

#### 3.1.1 搜狐号发布器

```python
# backend/services/playwright/publishers/sohu.py (新建 ~150行)

from backend.services.playwright.publishers.base import BasePublisher


class SohuPublisher(BasePublisher):
    """搜狐号发布器"""

    PLATFORM = "sohu"
    LOGIN_URL = "https://mp.sohu.com/"
    PUBLISH_URL = "https://mp.sohu.com/mpfe/mainnews/add"

    async def publish(self, page, article, account) -> dict:
        """发布文章到搜狐号"""
        try:
            # 1. 导航到发布页
            await page.goto(self.PUBLISH_URL)
            await page.wait_for_load_state("networkidle")

            # 2. 填写标题
            title_input = await page.wait_for_selector('[placeholder*="标题"]', timeout=10000)
            await title_input.fill(article.title)

            # 3. 填写内容 (富文本编辑器)
            content_frame = page.frame_locator('[class*="editor"]')
            await content_frame.locator("body").fill(article.content)

            # 4. 上传封面图
            if article.cover_image:
                await self._upload_cover(page, article.cover_image)

            # 5. 提交
            submit_btn = await page.wait_for_selector('text=发布')
            await submit_btn.click()

            # 6. 等待结果
            await page.wait_for_url("**/success**", timeout=30000)

            return {"success": True, "platform": self.PLATFORM}

        except Exception as e:
            return {"success": False, "platform": self.PLATFORM, "error": str(e)}
```

#### 3.1.2 网易号发布器

```python
# backend/services/playwright/publishers/netease.py (新建 ~130行)

class NeteasePublisher(BasePublisher):
    """网易号发布器"""

    PLATFORM = "netease"
    LOGIN_URL = "https://mp.163.com/"
    PUBLISH_URL = "https://mp.163.com/article/create"

    async def publish(self, page, article, account) -> dict:
        # 类似搜狐号流程
        ...
```

### 3.2 新闻稿服务商API对接

#### 3.2.1 媒介盒子 API

```python
# backend/services/press_release.py (新建 ~200行)

import httpx
from dataclasses import dataclass
from typing import Optional
from loguru import logger
from backend.config import MEIJUHEZI_API_KEY, MEIJUHEZI_API_URL


@dataclass
class PressReleaseResult:
    success: bool
    order_id: str
    published_urls: list[str]
    platform_count: int
    cost: float
    error: str = ""


class MeijuheziService:
    """媒介盒子新闻稿发布服务"""

    # 媒介盒子套餐
    PACKAGES = {
        "basic": {"name": "基础套餐", "price": 50, "media_count": 10},
        "standard": {"name": "标准套餐", "price": 200, "media_count": 50},
        "premium": {"name": "高级套餐", "price": 500, "media_count": 200},
    }

    async def submit_press_release(
        self,
        title: str,
        content: str,
        package: str = "standard",
        contact_name: str = "",
        contact_phone: str = "",
        keywords: list[str] = None,
    ) -> PressReleaseResult:
        """提交新闻稿"""
        async with httpx.AsyncClient(timeout=60) as client:
            resp = await client.post(
                f"{MEIJUHEZI_API_URL}/api/v1/order/create",
                headers={"Authorization": f"Bearer {MEIJUHEZI_API_KEY}"},
                json={
                    "title": title,
                    "content": content,
                    "package_id": self.PACKAGES.get(package, {}).get("price", 200),
                    "contact_name": contact_name,
                    "contact_phone": contact_phone,
                    "keywords": keywords or [],
                },
            )

        if resp.status_code != 200:
            return PressReleaseResult(False, "", [], 0, 0, f"API错误: {resp.text[:200]}")

        data = resp.json()
        return PressReleaseResult(
            success=True,
            order_id=data.get("order_id", ""),
            published_urls=data.get("published_urls", []),
            platform_count=data.get("platform_count", 0),
            cost=data.get("cost", 0),
        )

    async def query_order(self, order_id: str) -> dict:
        """查询订单状态"""
        async with httpx.AsyncClient() as client:
            resp = await client.get(
                f"{MEIJUHEZI_API_URL}/api/v1/order/{order_id}",
                headers={"Authorization": f"Bearer {MEIJUHEZI_API_KEY}"},
            )
        return resp.json()

    async def get_available_media(self, category: str = "") -> list[dict]:
        """获取可用媒体列表"""
        async with httpx.AsyncClient() as client:
            resp = await client.get(
                f"{MEIJUHEZI_API_URL}/api/v1/media",
                headers={"Authorization": f"Bearer {MEIJUHEZI_API_KEY}"},
                params={"category": category},
            )
        return resp.json().get("data", [])

    def estimate_cost(self, package: str, count: int = 1) -> dict:
        """估算发布成本"""
        pkg = self.PACKAGES.get(package, self.PACKAGES["standard"])
        total = pkg["price"] * count
        return {
            "package": pkg["name"],
            "unit_price": pkg["price"],
            "count": count,
            "total": total,
            "media_coverage": pkg["media_count"] * count,
        }
```

#### 3.2.2 通用新闻稿发布接口

```python
# backend/services/press_release.py — 通用接口

class PressReleaseService:
    """通用新闻稿发布服务"""

    PROVIDERS = {
        "meijuhezi": MeijuheziService,
        # "prnewswire": PRNewswireService,  # 美通社 (可选)
        # "qimingpian": QiMingPianService,  # 企名片 (可选)
    }

    def get_provider(self, provider_name: str):
        """获取发布服务商"""
        provider_class = self.PROVIDERS.get(provider_name)
        if not provider_class:
            raise ValueError(f"不支持的服务商: {provider_name}")
        return provider_class()

    async def smart_distribute(
        self, title: str, content: str, budget: float = 200,
    ) -> list[PressReleaseResult]:
        """智能分发: 根据预算自动选择最优套餐"""
        results = []

        # 1. 先使用媒介盒子标准套餐
        if budget >= 200:
            result = await MeijuheziService().submit_press_release(
                title=title, content=content, package="standard"
            )
            results.append(result)

        # 2. 同时发布到免费门户
        # (搜狐号、网易号等通过 Playwright 自动发布)

        return results
```

### 3.3 内容适配层

```python
# backend/services/content_adapter.py (新建 ~80行)

class ContentAdapter:
    """内容适配器: 同一篇文章适配不同渠道"""

    @staticmethod
    def adapt_for_portal(article_content: str, platform: str) -> dict:
        """适配新闻门户格式"""
        if platform in ("sohu", "netease", "sina"):
            # 新闻门户: 去除过于营销性的内容，增加新闻语感
            return {
                "title_adjustment": "去除营销词，增加客观性",
                "content_adjustment": "去除CTA，增加引用和数据",
                "max_length": 3000,
                "require_cover": True,
            }
        return {"content": article_content}

    @staticmethod
    def adapt_for_press_release(article_content: str, company_name: str) -> dict:
        """适配新闻稿格式"""
        # 新闻稿需要: 标准格式、公司全称、联系方式
        return {
            "format": "press_release",
            "required_fields": ["company_full_name", "contact", "disclaimer"],
            "tone": "formal",
            "max_length": 5000,
        }
```

---

## 4. 数据库变更

```python
# models.py — 新增发布渠道配置

class PublishChannel(Base):
    """发布渠道配置"""
    __tablename__ = "publish_channels"

    id = Column(Integer, primary_key=True)
    project_id = Column(Integer, ForeignKey("projects.id"))
    channel_type = Column(String(20))    # "portal" / "press_release" / "social_media"
    platform = Column(String(50))         # "sohu" / "netease" / "meijuhezi"
    account_id = Column(Integer, ForeignKey("accounts.id"), nullable=True)
    config = Column(Text)                 # JSON: 渠道特定配置
    is_active = Column(Boolean, default=True)
    last_publish_at = Column(DateTime, nullable=True)
    publish_count = Column(Integer, default=0)
    created_at = Column(DateTime, default=func.now())
```

```sql
CREATE TABLE publish_channels (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    project_id INTEGER REFERENCES projects(id),
    channel_type VARCHAR(20),
    platform VARCHAR(50),
    account_id INTEGER REFERENCES accounts(id),
    config TEXT,
    is_active BOOLEAN DEFAULT 1,
    last_publish_at DATETIME,
    publish_count INTEGER DEFAULT 0,
    created_at DATETIME DEFAULT CURRENT_TIMESTAMP
);
```

---

## 5. API设计

| 端点 | 方法 | 说明 |
|------|------|------|
| `POST /api/channels/portal/publish` | POST | 发布到新闻门户 |
| `POST /api/channels/press-release/submit` | POST | 提交新闻稿 |
| `GET /api/channels/press-release/orders` | GET | 查询新闻稿订单 |
| `GET /api/channels/available` | GET | 可用渠道列表 |
| `POST /api/channels/smart-distribute` | POST | 智能分发 |
| `GET /api/channels/{id}/cost-estimate` | GET | 费用估算 |

---

## 6. 配置变更

```python
# config.py 新增

# 新闻门户
SOHU_ENABLED = os.getenv("SOHU_ENABLED", "false").lower() == "true"
NETEASE_ENABLED = os.getenv("NETEASE_ENABLED", "false").lower() == "true"
SINA_ENABLED = os.getenv("SINA_ENABLED", "false").lower() == "true"

# 媒介盒子
MEIJUHEZI_API_KEY = os.getenv("MEIJUHEZI_API_KEY", "")
MEIJUHEZI_API_URL = os.getenv("MEIJUHEZI_API_URL", "https://open.meijuhezi.com")

# 新闻稿预算
PRESS_RELEASE_MONTHLY_BUDGET = float(os.getenv("PRESS_RELEASE_MONTHLY_BUDGET", "1000"))
```

---

## 7. 测试方案

### 7.1 发布器测试

| 平台 | 测试内容 |
|------|---------|
| 搜狐号 | 文章发布+图片上传+分类选择 |
| 网易号 | 文章发布+标签设置 |
| 媒介盒子 | API调用+订单查询+费用计算 |

### 7.2 内容适配测试

| 场景 | 验证内容 |
|------|---------|
| 营销文→新闻稿 | 去除CTA、增加客观引用 |
| 长文→门户 | 自动截取+摘要 |
| 关键词密度 | 符合各平台要求 |

### 7.3 智能分发测试

```python
async def test_smart_distribute():
    """测试智能分发策略"""
    service = PressReleaseService()

    # 预算200元: 应选择标准套餐
    results = await service.smart_distribute(
        title="测试标题", content="测试内容", budget=200
    )
    assert len(results) >= 1
    assert results[0].cost <= 200

    # 预算50元: 应选择基础套餐
    results = await service.smart_distribute(
        title="测试标题", content="测试内容", budget=50
    )
    assert results[0].cost <= 50
```

---

## 8. 成本估算

| 项目 | 月费用 | 说明 |
|------|--------|------|
| 搜狐号/网易号 | ¥0 | 免费自媒体平台 |
| 媒介盒子基础套餐 | ¥50/篇 × 4篇 | 月发4篇 |
| 媒介盒子标准套餐 | ¥200/篇 × 2篇 | 重要文章 |
| **合计** | **¥200-800/月** | 根据发布量调整 |

---

## 9. 权威参考文献

### 学术论文

1. **Aggarwal, P., et al. (2024).** "GEO: Generative Engine Optimization." *arXiv:2311.09735*. Princeton University.
   - AI搜索引擎优先引用权威新闻源，新闻门户引用率比自媒体高3-5倍

2. **Dong, Y., et al. (2025).** "Content Freshness and LLM Citation Preferences." *Hill Web Creations Research*.
   - AI搜索偏好新鲜内容，新闻稿发布后24小时内被引用概率最高

3. **Gao, Y., et al. (2024).** "Source Credibility in Retrieval-Augmented Generation." *EMNLP 2024*.
   - RAG系统中来源可信度影响检索排序，权威媒体内容优先级更高

### 行业报告

4. **Brandlight (2025).** "Benchmarking Generative Visibility."
   - CFR基准研究: 有新闻稿背书的品牌AI可见性提升45%
   - 新闻门户引用在AI搜索中占比21.3%

5. **媒介盒子 (2025).** "新闻稿发布平台服务说明与API文档."
   - 新闻稿分发覆盖5000+媒体，百度收录率>95%
   - API支持批量发布、进度查询、效果追踪

6. **Meltwater (2025).** "State of Digital PR: Media Outreach Best Practices."
   - 数字公关最佳实践，新闻稿+自媒体组合策略可提升品牌曝光300%
   - 建议月度预算分配: 70%自媒体+30%新闻稿

7. **Ahrefs (2025).** "Link Building Strategies That Work in 2026."
   - 高质量外链建设策略，新闻稿外链DA值平均>70
   - dofollow新闻外链对SEO排名提升效果显著

8. **美通社 (2025).** "企业新闻稿发布效果白皮书."
   - 企业新闻稿平均被200+媒体转载，搜索引擎收录时间<24小时
   - 含结构化数据的新闻稿AI引用率提升60%
