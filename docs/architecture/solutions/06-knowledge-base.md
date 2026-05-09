# 卡点6: 知识库多租户隔离

> 类型: 技术方案文档 (PRD)
> 优先级: P1
> 预估工时: 1周
> 最后更新: 2026-05-01

---

## 1. 问题定义

### 1.1 现状

当前 RAGFlow 知识库使用**单一全局 dataset**:

```python
# ragflow_client.py:33-34 — 全局单一dataset
self.dataset_id = os.getenv("RAGFLOW_DATASET_ID", "")

# ragflow_client.py:168-191 — get_or_create_dataset
def get_or_create_dataset(self, name: str) -> Optional[str]:
    result = self.list_datasets(name=name)
    # 全局查找，无项目隔离
```

- 所有项目的文章、知识全部存储在同一个 dataset 中
- A 公司的知识可能被 B 公司的文章检索到（跨项目数据泄露）
- 无法为不同项目配置不同的知识库参数（chunk_size, 解析器等）

### 1.2 核心问题

1. **数据隔离缺失**: 项目A上传的行业文档可能影响项目B的检索结果
2. **配置不灵活**: 不同行业/客户需要不同的 chunk 策略（医疗文档 vs 营销文案）
3. **权限控制缺失**: 任何项目都能访问所有知识库
4. **资源无法独立管理**: 无法针对特定客户的知识库进行独立备份/清理

### 1.3 影响范围

- `ragflow_client.py`: 核心客户端，所有知识库操作入口
- `article_collector_service.py:167` (`_sync_to_ragflow`): 文章同步到RAGFlow
- `geo_article_service.py`: 生成文章时检索知识库
- 数据库 `projects` 表: 需关联 `dataset_id`

---

## 2. 技术架构

### 2.1 多 Dataset 隔离方案

```
┌─────────────────────────────────────┐
│           Project Registry           │
│                                      │
│  Project A → Dataset A (独立知识库)   │
│  Project B → Dataset B (独立知识库)   │
│  Project C → Dataset C (独立知识库)   │
│                                      │
│  + 共享知识库 (公共行业数据)           │
└─────────────────────────────────────┘
         │
         ▼
┌─────────────────────────────────────┐
│       Knowledge Base Router          │
│                                      │
│  retrieve() 时:                      │
│  1. 先检索项目私有 Dataset            │
│  2. 可选检索共享 Dataset              │
│  3. 合并结果, 按相似度排序            │
└─────────────────────────────────────┘
         │
         ▼
┌─────────────────────────────────────┐
│        RAGFlow Service               │
│                                      │
│  Dataset A: 医疗行业知识             │
│  Dataset B: 科技行业知识             │
│  Dataset C: 教育行业知识             │
│  Dataset Shared: 公共百科数据         │
└─────────────────────────────────────┘
```

### 2.2 隔离层级

| 层级 | 粒度 | 实现方式 | 适用场景 |
|------|------|---------|---------|
| L1: 项目隔离 | 每项目独立Dataset | 项目绑定dataset_id | 默认方案 |
| L2: 行业共享 | 同行业项目共享 | 行业标签关联 | 降低重复上传 |
| L3: 全局公共 | 所有项目可访问 | 固定共享Dataset | 百科/通用知识 |

---

## 3. 详细设计

### 3.1 数据库变更

```python
# models.py — Project 模型新增字段

class Project(Base):
    __tablename__ = "projects"

    # ... 现有字段 ...

    # 知识库隔离
    ragflow_dataset_id = Column(String(100), nullable=True, comment="项目私有知识库ID")
    ragflow_shared_dataset_id = Column(String(100), nullable=True, comment="行业共享知识库ID")
    ragflow_config = Column(Text, nullable=True, comment="JSON: 知识库配置")
    kb_chunk_size = Column(Integer, default=2048, comment="分块大小")
    kb_chunk_overlap = Column(Integer, default=200, comment="分块重叠")
    kb_similarity_threshold = Column(Float, default=0.5, comment="相似度阈值")
```

```sql
-- 迁移脚本
ALTER TABLE projects ADD COLUMN ragflow_dataset_id VARCHAR(100);
ALTER TABLE projects ADD COLUMN ragflow_shared_dataset_id VARCHAR(100);
ALTER TABLE projects ADD COLUMN ragflow_config TEXT;
ALTER TABLE projects ADD COLUMN kb_chunk_size INTEGER DEFAULT 2048;
ALTER TABLE projects ADD COLUMN kb_chunk_overlap INTEGER DEFAULT 200;
ALTER TABLE projects ADD COLUMN kb_similarity_threshold FLOAT DEFAULT 0.5;
```

### 3.2 知识库路由器

```python
# backend/services/knowledge_router.py (新建 ~200行)

from typing import Optional
from loguru import logger
from backend.services.ragflow_client import RAGFlowClient, get_ragflow_client
from backend.database.models import Project
from sqlalchemy.orm import Session


class KnowledgeRouter:
    """知识库多租户路由器"""

    def __init__(self, db: Session):
        self.db = db
        self._ragflow = get_ragflow_client()
        self._dataset_cache: dict[str, str] = {}  # project_id → dataset_id

    async def get_project_dataset(self, project_id: int) -> Optional[str]:
        """获取项目绑定的知识库ID，不存在则自动创建"""
        project = self.db.query(Project).get(project_id)
        if not project:
            return None

        # 已绑定
        if project.ragflow_dataset_id:
            return project.ragflow_dataset_id

        # 自动创建项目私有知识库
        dataset_name = f"project_{project_id}_{project.name[:20]}"
        dataset_id = self._ragflow.get_or_create_dataset(dataset_name)

        if dataset_id:
            project.ragflow_dataset_id = dataset_id
            self.db.commit()
            logger.info(f"项目 {project_id} 创建知识库: {dataset_id}")

        return dataset_id

    async def retrieve(
        self,
        project_id: int,
        question: str,
        top_k: int = 20,
        include_shared: bool = True,
    ) -> dict:
        """
        多知识库联合检索

        Args:
            project_id: 项目ID
            question: 查询问题
            top_k: 返回结果数
            include_shared: 是否包含共享知识库
        """
        dataset_ids = []

        # 1. 项目私有知识库
        private_ds = await self.get_project_dataset(project_id)
        if private_ds:
            dataset_ids.append(private_ds)

        # 2. 行业共享知识库
        if include_shared:
            project = self.db.query(Project).get(project_id)
            if project and project.ragflow_shared_dataset_id:
                dataset_ids.append(project.ragflow_shared_dataset_id)

        if not dataset_ids:
            logger.warning(f"项目 {project_id} 无可用知识库")
            return {"data": {"chunks": []}}

        # 3. 分知识库检索并合并
        all_chunks = []
        for ds_id in dataset_ids:
            result = self._ragflow.retrieve(
                question=question,
                dataset_ids=[ds_id],
                top_k=top_k,
                similarity_threshold=self._get_threshold(project_id),
            )
            chunks = result.get("data", {}).get("chunks", [])
            all_chunks.extend(chunks)

        # 4. 按相似度排序，取 top_k
        all_chunks.sort(key=lambda x: x.get("similarity", 0), reverse=True)
        return {"data": {"chunks": all_chunks[:top_k]}}

    async def upload_to_project(
        self, project_id: int, title: str, content: str
    ) -> dict:
        """上传文档到项目私有知识库"""
        dataset_id = await self.get_project_dataset(project_id)
        if not dataset_id:
            return {"code": -1, "message": "无法获取项目知识库"}

        return self._ragflow.upload_document_content(
            dataset_id=dataset_id,
            title=title,
            content=content,
        )

    async def delete_project_kb(self, project_id: int) -> bool:
        """删除项目私有知识库"""
        project = self.db.query(Project).get(project_id)
        if not project or not project.ragflow_dataset_id:
            return False

        result = self._ragflow.delete_dataset(project.ragflow_dataset_id)
        if result.get("code") == 0:
            project.ragflow_dataset_id = None
            self.db.commit()
            return True
        return False

    def _get_threshold(self, project_id: int) -> float:
        """获取项目的相似度阈值"""
        project = self.db.query(Project).get(project_id)
        return project.kb_similarity_threshold if project else 0.5
```

### 3.3 修改现有代码

#### 3.3.1 修改 article_collector_service.py

```python
# 修改 _sync_to_ragflow() — 支持项目级知识库

async def _sync_to_ragflow(self, article, project_id: int):
    """同步文章到项目知识库"""
    router = KnowledgeRouter(self.db)
    return await router.upload_to_project(
        project_id=project_id,
        title=article.title,
        content=article.content,
    )
```

#### 3.3.2 修改 RAGFlowClient

```python
# ragflow_client.py — retrieve() 支持多dataset

def retrieve(self, question: str, dataset_ids: list[str] = None,
             top_k: int = 20, similarity_threshold: float = 0.5) -> Dict:
    """
    向量检索

    Args:
        dataset_ids: 指定检索的知识库列表 (默认使用全局dataset)
    """
    target_datasets = dataset_ids or [self.dataset_id]
    # ... 调用 RAGFlow API，传入 dataset_ids 参数 ...
```

### 3.4 知识库管理API

```python
# backend/api/knowledge_base.py (新建 ~100行)

from fastapi import APIRouter, Depends
from pydantic import BaseModel
from backend.services.knowledge_router import KnowledgeRouter

router = APIRouter(prefix="/api/knowledge", tags=["Knowledge Base"])


class KBConfigRequest(BaseModel):
    project_id: int
    chunk_size: int = 2048
    chunk_overlap: int = 200
    similarity_threshold: float = 0.5


class KBUploadRequest(BaseModel):
    project_id: int
    title: str
    content: str


@router.get("/projects/{project_id}/status")
async def get_kb_status(project_id: int):
    """获取项目知识库状态"""
    router = KnowledgeRouter(db=get_db())
    dataset_id = await router.get_project_dataset(project_id)
    return {
        "project_id": project_id,
        "dataset_id": dataset_id,
        "configured": dataset_id is not None,
    }


@router.post("/projects/{project_id}/upload")
async def upload_to_kb(project_id: int, req: KBUploadRequest):
    """上传文档到项目知识库"""
    router = KnowledgeRouter(db=get_db())
    result = await router.upload_to_project(project_id, req.title, req.content)
    return {"code": 200, "data": result}


@router.post("/projects/{project_id}/config")
async def update_kb_config(project_id: int, req: KBConfigRequest):
    """更新知识库配置"""
    # 更新项目的 kb_chunk_size, kb_chunk_overlap, kb_similarity_threshold
    ...


@router.delete("/projects/{project_id}/kb")
async def delete_kb(project_id: int):
    """删除项目知识库"""
    router = KnowledgeRouter(db=get_db())
    success = await router.delete_project_kb(project_id)
    return {"code": 200 if success else 500}
```

---

## 4. API设计

| 端点 | 方法 | 说明 |
|------|------|------|
| `GET /api/knowledge/projects/{id}/status` | GET | 知识库状态 |
| `POST /api/knowledge/projects/{id}/upload` | POST | 上传文档 |
| `POST /api/knowledge/projects/{id}/config` | POST | 更新配置 |
| `DELETE /api/knowledge/projects/{id}/kb` | DELETE | 删除知识库 |
| `GET /api/knowledge/projects/{id}/search` | GET | 检索测试 |
| `POST /api/knowledge/projects/{id}/init` | POST | 初始化知识库 |

---

## 5. 测试方案

### 5.1 隔离性测试

```python
# tests/test_knowledge_isolation.py

async def test_project_isolation():
    """验证A项目的知识不会出现在B项目检索结果中"""
    router = KnowledgeRouter(db)

    # 上传到项目A
    await router.upload_to_project(project_id=1, title="医疗知识", content="...")

    # 检索项目B
    result = await router.retrieve(project_id=2, question="医疗知识")

    # 项目B不应包含项目A的私有知识
    assert len(result["data"]["chunks"]) == 0


async def test_shared_knowledge():
    """验证共享知识库对所有项目可见"""
    # 上传到共享知识库
    # 检索各项目均能返回共享内容
    ...
```

### 5.2 性能测试

| 操作 | 目标耗时 |
|------|---------|
| 创建项目知识库 | < 2s |
| 上传文档(10KB) | < 5s |
| 检索(top_k=20) | < 1s |
| 合并2个知识库检索 | < 2s |

### 5.3 容量测试

| 知识库规模 | 文档数 | 检索延迟 |
|-----------|--------|---------|
| 小型 | < 100 | < 500ms |
| 中型 | 100-1000 | < 1s |
| 大型 | 1000-10000 | < 3s |

---

## 6. 成本估算

| 项目 | 月费用 | 说明 |
|------|--------|------|
| RAGFlow (自部署) | ¥0 | 已有Docker实例 |
| 额外存储 | ¥0 | RAGFlow使用本地磁盘 |
| 运维成本 | ¥0 | 自动化管理 |
| **合计** | **¥0** | 无增量成本 |

---

## 7. 权威参考文献

### 学术论文

1. **Gao, Y., et al. (2024).** "Retrieval-Augmented Generation for Large Language Models: A Survey." *arXiv:2312.10997*.
   - RAG系统全面综述，涵盖多知识库检索、查询路由、结果融合策略

2. **Lewis, P., et al. (2020).** "Retrieval-Augmented Generation for Knowledge-Intensive NLP Tasks." *NeurIPS 2020*.
   - RAG奠基论文，提出知识检索与生成联合训练方法

3. **Borgeaud, S., et al. (2022).** "RETRO: Retrieval-Enhanced Transformer." *ICML 2022*.
   - 检索增强Transformer架构，支持大规模知识库的高效检索

4. **Karpukhin, V., et al. (2020).** "Dense Passage Retrieval for Open-Domain Question Answering." *EMNLP 2020*.
   - 密集向量检索方法，提出DPR双编码器架构，是RAGFlow底层技术基础

### 行业报告

5. **RAGFlow Documentation (2025).** "Multi-Tenant Architecture Guide."
   - RAGFlow多租户最佳实践，推荐每租户独立Dataset + 共享Dataset模式

6. **Pinecone (2025).** "Multi-Tenancy in Vector Databases: Strategies and Patterns."
   - 向量数据库多租户策略对比: 命名空间隔离、集合隔离、集群隔离
   - 推荐中小规模使用集合(Collection)级隔离

7. **Weaviate (2025).** "Multi-Tenancy with Per-Tenant Collections."
   - 向量数据库多租户实现方案，每租户独立集合可确保零数据泄露

8. **LangChain (2025).** "Multi-Vector Retriever and Parent Document Strategies."
   - 多向量检索策略，支持从多个独立知识库合并检索结果
