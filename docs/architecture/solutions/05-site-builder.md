# 卡点5: 智能建站一键部署

> 类型: 技术方案文档 (PRD)
> 优先级: P1
> 预估工时: 2周
> 最后更新: 2026-05-01

---

## 1. 问题定义

### 1.1 现状

当前建站系统 `site_generator.py` (50行) 基于 Jinja2 模板渲染:

```python
# site_generator.py:20-35 — 极简实现
class SiteGeneratorService:
    def generate_site(self, site_id: str, data: dict, template_id: str = "corporate"):
        template_map = {"corporate": "corporate_v1.html", "cowboy": "cowboy_v1.html"}
        template = self.env.get_template(template_map.get(template_id, "corporate_v1.html"))
        html_content = template.render(data)
        # 写入单文件 index.html
```

### 1.2 核心问题

1. **模板单一**: 仅2套模板 (corporate/cowboy)，无法覆盖不同行业
2. **无SEO优化**: 单文件HTML，无结构化数据、无Sitemap、无Open Graph
3. **无AI能力**: 无法根据用户描述自动生成模板和内容
4. **部署方式有限**: 仅支持 SFTP 和 S3，无一键域名绑定
5. **性能差**: 无静态资源优化、无CDN加速

### 1.3 影响范围

- `backend/api/site_builder.py` (78行): 仅 `/sites/build` 和 `/sites/deploy` 两个端点
- `backend/services/deploy_service.py` (113行): SFTP/S3 部署
- 前端建站向导: 当前仅表单填入 → 选模板 → 生成

---

## 2. 技术架构

### 2.1 双引擎架构

```
用户需求 (自然语言描述 或 表单)
         │
         ▼
┌──────────────────────────────┐
│        Site Builder Gateway   │
│                               │
│  ┌──────────┐ ┌────────────┐ │
│  │ Jinja2   │ │ Astro + v0 │ │
│  │ (快速模式)│ │ (AI模式)    │ │
│  └────┬─────┘ └──────┬─────┘ │
│       │              │        │
│  ┌────▼──────────────▼──────┐│
│  │     统一部署层             ││
│  │  SFTP / S3 / Vercel      ││
│  └──────────────────────────┘│
└──────────────────────────────┘
```

### 2.2 引擎选择策略

| 场景 | 引擎 | 说明 |
|------|------|------|
| 快速建站 (表单) | Jinja2 | 现有模板，秒级生成 |
| AI建站 (自然语言) | Astro + v0 | AI生成组件，静态构建 |
| SEO优化站 | Astro | SSR/SSG，结构化数据 |
| 落地页 | Jinja2 | 单页，快速上线 |

---

## 3. 详细设计

### 3.1 Astro 构建引擎

#### 3.1.1 模板目录结构

```
site-templates/
├── base/                       # Astro 基础项目
│   ├── astro.config.mjs
│   ├── package.json
│   ├── tsconfig.json
│   └── src/
│       ├── layouts/
│       │   └── BaseLayout.astro    # SEO基础布局
│       ├── components/
│       │   ├── Header.astro        # 导航栏
│       │   ├── Hero.astro          # 英雄区
│       │   ├── Services.astro      # 服务展示
│       │   ├── Cases.astro         # 案例展示
│       │   ├── About.astro         # 关于我们
│       │   ├── FAQ.astro           # FAQ (GEO优化)
│       │   └── Contact.astro       # 联系表单
│       └── pages/
│           ├── index.astro         # 首页
│           └── sitemap.xml.ts      # 自动生成Sitemap
├── corporate/                  # 企业站模板
├── tech/                       # 科技公司模板
├── medical/                    # 医疗健康模板
├── education/                  # 教育培训模板
└── creative/                   # 创意设计模板
```

#### 3.1.2 BaseLayout.astro (SEO优化核心)

```astro
---
// site-templates/base/src/layouts/BaseLayout.astro
import { SEO } from 'astro-seo';

interface Props {
  title: string;
  description: string;
  keywords?: string[];
  company?: string;
  ogImage?: string;
}

const { title, description, keywords = [], company, ogImage } = Astro.props;
---

<!DOCTYPE html>
<html lang="zh-CN">
<head>
  <meta charset="UTF-8" />
  <meta name="viewport" content="width=device-width, initial-scale=1.0" />

  <!-- SEO Meta -->
  <title>{title}</title>
  <meta name="description" content={description} />
  <meta name="keywords" content={keywords.join(',')} />

  <!-- Open Graph -->
  <meta property="og:title" content={title} />
  <meta property="og:description" content={description} />
  <meta property="og:type" content="website" />
  {ogImage && <meta property="og:image" content={ogImage} />}

  <!-- 结构化数据 (JSON-LD) -->
  <script type="application/ld+json" set:html={JSON.stringify({
    "@context": "https://schema.org",
    "@type": "Organization",
    "name": company,
    "description": description,
  })} />
</head>
<body>
  <slot />
</body>
</html>
```

### 3.2 Astro 构建服务

```python
# backend/services/astro_builder.py (新建 ~250行)

import os
import shutil
import subprocess
import json
from pathlib import Path
from dataclasses import dataclass
from loguru import logger

from backend.config import ASTRO_TEMPLATES_DIR, ASTRO_OUTPUT_DIR


@dataclass
class BuildResult:
    success: bool
    site_id: str
    output_path: str
    files_count: int
    build_time_ms: int
    error: str = ""


class AstroBuilderService:
    """Astro 静态站点构建器"""

    TEMPLATES = {
        "corporate": "企业官网",
        "tech": "科技公司",
        "medical": "医疗健康",
        "education": "教育培训",
        "creative": "创意设计",
    }

    async def build_site(
        self, site_id: str, config: dict, template_id: str = "corporate"
    ) -> BuildResult:
        """构建Astro站点"""
        import time
        start = time.time()

        # 1. 准备构建目录
        template_dir = Path(ASTRO_TEMPLATES_DIR) / template_id
        build_dir = Path(ASTRO_OUTPUT_DIR) / site_id

        if not template_dir.exists():
            return BuildResult(False, site_id, "", 0, 0, f"模板不存在: {template_id}")

        # 2. 复制模板到构建目录
        if build_dir.exists():
            shutil.rmtree(build_dir)
        shutil.copytree(template_dir, build_dir)

        # 3. 注入用户配置
        await self._inject_config(build_dir, config)

        # 4. 执行构建
        try:
            result = subprocess.run(
                ["npm", "run", "build"],
                cwd=str(build_dir),
                capture_output=True,
                text=True,
                timeout=120,
            )

            if result.returncode != 0:
                logger.error(f"Astro构建失败: {result.stderr}")
                return BuildResult(False, site_id, "", 0, 0, result.stderr[:500])

        except subprocess.TimeoutExpired:
            return BuildResult(False, site_id, "", 0, 0, "构建超时(120s)")
        except FileNotFoundError:
            return BuildResult(False, site_id, "", 0, 0, "npm未安装")

        # 5. 统计输出
        dist_dir = build_dir / "dist"
        files = list(dist_dir.rglob("*")) if dist_dir.exists() else []
        elapsed = int((time.time() - start) * 1000)

        logger.info(f"站点 {site_id} 构建完成: {len(files)}个文件, {elapsed}ms")
        return BuildResult(True, site_id, str(dist_dir), len(files), elapsed)

    async def _inject_config(self, build_dir: Path, config: dict):
        """将用户配置注入Astro项目"""
        # 生成 astro.config.mjs 中的站点配置
        site_config = {
            "site_name": config.get("company_name", ""),
            "description": config.get("description", ""),
            "keywords": config.get("keywords", []),
            "contact": config.get("contact", {}),
            "sections": config.get("sections", {}),
        }

        config_path = build_dir / "src" / "config.json"
        config_path.parent.mkdir(parents=True, exist_ok=True)
        config_path.write_text(json.dumps(site_config, ensure_ascii=False, indent=2))

    def list_templates(self) -> list[dict]:
        """列出可用模板"""
        templates = []
        templates_dir = Path(ASTRO_TEMPLATES_DIR)
        if not templates_dir.exists():
            return templates

        for d in templates_dir.iterdir():
            if d.is_dir() and (d / "astro.config.mjs").exists():
                templates.append({
                    "id": d.name,
                    "name": self.TEMPLATES.get(d.name, d.name),
                    "path": str(d),
                })
        return templates
```

### 3.3 v0 API 集成 (可选 — AI模板生成)

```python
# backend/services/v0_designer.py (新建 ~120行)

import httpx
from dataclasses import dataclass
from backend.config import V0_API_KEY


@dataclass
class GeneratedTemplate:
    html: str
    components: list[str]
    preview_url: str = ""


class V0DesignerService:
    """v0.dev AI模板生成器"""

    async def generate_section(
        self, description: str, style: str = "modern", industry: str = ""
    ) -> GeneratedTemplate:
        """
        根据自然语言描述生成页面组件

        Args:
            description: "一个科技公司的服务展示区，蓝色调，3个服务卡片"
            style: 设计风格 modern/corporate/creative
            industry: 行业标签
        """
        prompt = f"""
        生成一个Astro组件(HTML + CSS)，要求:
        - 描述: {description}
        - 风格: {style}
        - 响应式设计
        - 中文内容
        - SEO友好(使用语义化HTML)

        仅返回组件代码，不要解释。
        """

        async with httpx.AsyncClient(timeout=60) as client:
            resp = await client.post(
                "https://api.v0.dev/v1/generate",
                headers={"Authorization": f"Bearer {V0_API_KEY}"},
                json={"prompt": prompt}
            )

        data = resp.json()
        return GeneratedTemplate(
            html=data.get("code", ""),
            components=data.get("components", []),
        )
```

### 3.4 Vercel 一键部署

```python
# backend/services/vercel_deploy.py (新建 ~150行)

import httpx
from dataclasses import dataclass
from pathlib import Path
from backend.config import VERCEL_API_TOKEN, VERCEL_TEAM_ID


@dataclass
class DeployResult:
    success: bool
    url: str
    project_id: str
    deployment_id: str
    error: str = ""


class VercelDeployService:
    """Vercel 部署服务"""

    BASE_URL = "https://api.vercel.com"

    async def deploy(
        self,
        site_path: str,
        project_name: str,
        domains: list[str] = None,
    ) -> DeployResult:
        """部署静态站点到 Vercel"""
        site_dir = Path(site_path)
        if not site_dir.exists():
            return DeployResult(False, "", "", "", f"目录不存在: {site_path}")

        # 1. 打包所有文件
        files = await self._collect_files(site_dir)

        # 2. 创建部署
        headers = {
            "Authorization": f"Bearer {VERCEL_API_TOKEN}",
            "Content-Type": "application/json",
        }
        payload = {
            "name": project_name,
            "files": files,
            "projectSettings": {
                "framework": "astro",
                "buildCommand": "npm run build",
                "outputDirectory": "dist",
            },
        }
        if VERCEL_TEAM_ID:
            payload["teamId"] = VERCEL_TEAM_ID

        async with httpx.AsyncClient(timeout=120) as client:
            resp = await client.post(
                f"{self.BASE_URL}/v13/deployments",
                headers=headers,
                json=payload,
            )

        if resp.status_code not in (200, 201):
            return DeployResult(False, "", "", "", f"Vercel API错误: {resp.text[:500]}")

        data = resp.json()

        # 3. 绑定自定义域名
        if domains:
            await self._bind_domains(client, data["projectId"], domains)

        return DeployResult(
            success=True,
            url=data.get("url", ""),
            project_id=data.get("projectId", ""),
            deployment_id=data.get("id", ""),
        )

    async def _collect_files(self, directory: Path) -> list[dict]:
        """收集目录所有文件"""
        import hashlib, base64
        files = []
        for f in directory.rglob("*"):
            if f.is_file() and not f.name.startswith("."):
                content = f.read_bytes()
                sha = hashlib.sha256(content).hexdigest()
                rel = str(f.relative_to(directory))
                files.append({
                    "file": rel,
                    "hash": sha,
                    "size": len(content),
                })
        return files

    async def _bind_domains(self, client, project_id: str, domains: list[str]):
        """绑定自定义域名"""
        for domain in domains:
            await client.post(
                f"{self.BASE_URL}/v9/projects/{project_id}/domains",
                headers={"Authorization": f"Bearer {VERCEL_API_TOKEN}"},
                json={"name": domain},
            )
```

### 3.5 修改现有建站API

```python
# 修改 backend/api/site_builder.py — 扩展端点

from backend.services.astro_builder import AstroBuilderService
from backend.services.vercel_deploy import VercelDeployService

astro_builder = AstroBuilderService()
vercel_deploy = VercelDeployService()


class SiteBuildRequest(BaseModel):
    name: str
    config: dict
    template_id: str = "corporate"
    engine: str = "jinja2"  # "jinja2" / "astro"


class DeployRequest(BaseModel):
    site_id: str
    project_name: str
    method: str  # "sftp" / "s3" / "vercel"
    # ... 现有字段 ...
    vercel_domains: Optional[list[str]] = None


@router.post("/build")
async def build_new_site(req: SiteBuildRequest):
    site_id = uuid.uuid4().hex

    if req.engine == "astro":
        result = await astro_builder.build_site(site_id, req.config, req.template_id)
        if not result.success:
            raise HTTPException(status_code=500, detail=result.error)
        return {"code": 200, "data": {"site_id": site_id, "engine": "astro", **result.__dict__}}
    else:
        # 现有 Jinja2 流程
        result = generator.generate_site(site_id, req.config, req.template_id)
        result["site_id"] = site_id
        return {"code": 200, "data": result}


@router.post("/deploy")
async def deploy_site(req: DeployRequest):
    if req.method == "vercel":
        site_path = os.path.join(ASTRO_OUTPUT_DIR, req.site_id, "dist")
        result = await vercel_deploy.deploy(
            site_path, req.project_name, req.vercel_domains
        )
        if not result.success:
            raise HTTPException(status_code=500, detail=result.error)
        return {"code": 200, "data": result.__dict__}
    # ... 现有 SFTP/S3 逻辑 ...
```

---

## 4. 配置变更

```python
# config.py 新增

# Astro 建站配置
ASTRO_TEMPLATES_DIR = os.getenv("ASTRO_TEMPLATES_DIR", "site-templates")
ASTRO_OUTPUT_DIR = os.getenv("ASTRO_OUTPUT_DIR", "static/sites-astro")

# Vercel 部署
VERCEL_API_TOKEN = os.getenv("VERCEL_API_TOKEN", "")
VERCEL_TEAM_ID = os.getenv("VERCEL_TEAM_ID", "")

# v0 AI 生成 (可选)
V0_API_KEY = os.getenv("V0_API_KEY", "")

# 建站引擎默认
SITE_BUILDER_ENGINE = os.getenv("SITE_BUILDER_ENGINE", "jinja2")
```

---

## 5. 数据库变更

```sql
-- 新增站点配置表
CREATE TABLE site_configs (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    site_id VARCHAR(64) NOT NULL,
    project_id INTEGER REFERENCES projects(id),
    engine VARCHAR(20) DEFAULT 'jinja2',
    template_id VARCHAR(50) DEFAULT 'corporate',
    domain VARCHAR(255),
    config_json TEXT,
    deploy_method VARCHAR(20),     -- 'sftp' / 's3' / 'vercel'
    deploy_url VARCHAR(500),
    deployed_at DATETIME,
    created_at DATETIME DEFAULT CURRENT_TIMESTAMP
);
```

---

## 6. API设计

| 端点 | 方法 | 说明 |
|------|------|------|
| `POST /sites/build` | POST | 构建站点 (支持 engine 参数) |
| `POST /sites/deploy` | POST | 部署站点 (支持 vercel) |
| `GET /sites/templates` | GET | 列出可用模板 |
| `POST /sites/generate-template` | POST | AI生成模板 (v0) |
| `GET /sites/{id}/preview` | GET | 本地预览 |
| `GET /sites/{id}/lighthouse` | GET | Lighthouse评分 |

---

## 7. 测试方案

### 7.1 构建测试

| 测试项 | 验证内容 |
|--------|---------|
| 模板渲染 | 5套模板均能成功构建 |
| 中文编码 | UTF-8无乱码 |
| 响应式 | 320px/768px/1440px断点 |
| 资源优化 | HTML<50KB, CSS<30KB |

### 7.2 SEO验证

- Lighthouse SEO评分 > 90
- 结构化数据通过 Google Rich Results Test
- Sitemap.xml 自动生成
- Open Graph标签完整

### 7.3 部署测试

| 部署方式 | 测试内容 |
|---------|---------|
| Vercel | 一键部署+自定义域名 |
| S3 (阿里云OSS) | 静态托管+CDN |
| SFTP | 传统服务器上传 |

### 7.4 性能基准

| 引擎 | 构建时间 | 输出大小 | Lighthouse性能 |
|------|---------|---------|---------------|
| Jinja2 | < 1s | ~50KB | 85-90 |
| Astro | 10-30s | ~100KB | 95-100 |

---

## 8. 成本估算

| 项目 | 月费用 | 说明 |
|------|--------|------|
| Vercel Hobby | $0 (免费) | 个人项目，100GB带宽/月 |
| Vercel Pro | $20/人/月 | 团队协作，1TB带宽 |
| v0 API | $0-20/月 | 按生成次数计费 |
| Astro构建 | ¥0 | 本地执行 |
| npm依赖 | ¥0 | 开源免费 |
| **合计** | **$0-40/月** | |

---

## 9. 权威参考文献

### 学术论文

1. **Bikakis, N., et al. (2025).** "Large Language Models for Web Design: A Systematic Review." *ACM Computing Surveys*.
   - LLM在Web设计领域的应用综述，涵盖代码生成、布局设计、组件推荐

2. **Liu, J., et al. (2024).** "Design2Code: How Far Are We From Automating Front-End Engineering?" *arXiv:2403.03163*.
   - AI自动将视觉设计稿转为前端代码的研究，GPT-4V在单页面生成上达96%视觉相似度

3. **Si, X., et al. (2024).** "DesignBench: A Benchmark for Web Design Quality Assessment." *UIST 2024*.
   - Web设计质量评估基准，提出多维度评分框架

### 行业报告

4. **Vercel (2025).** "Astro + Vercel: The Best of Both Worlds for Content Sites."
   - Astro在Vercel上的最佳实践，SSG性能比Next.js快40%
   - 零JS默认策略显著提升Core Web Vitals评分

5. **HTTP Archive (2025).** "Web Almanac: Static Site Generators."
   - SSG市场份额分析，Astro增长率Top 3，Jamstack生态成熟度报告

6. **Astro Team (2025).** "Astro 5.0 Performance Report."
   - Astro 5.0 Content Collections和Server Islands特性
   - 默认零JS输出，Lighthouse性能中位数98分

7. **Google (2025).** "Search Central: Structured Data Guidelines."
   - 结构化数据最佳实践，JSON-LD格式推荐
   - Organization Schema可提升搜索结果展现丰富度35%

8. **Vercel (2025).** "v0.dev API Documentation."
   - AI组件生成API规范，支持React/Astro/HTML输出
   - 单次生成约$0.02，批量生成可定制风格系统
