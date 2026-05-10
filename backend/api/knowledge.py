# -*- coding: utf-8 -*-
"""
知识库管理API
管理企业知识库分类和知识条目
"""

from datetime import datetime
from typing import List, Optional
from fastapi import APIRouter, Depends, HTTPException, Query, UploadFile, File, Form
from pydantic import BaseModel
from sqlalchemy.orm import Session

from backend.database import get_db
from backend.database.models import KnowledgeCategory, Knowledge
from backend.schemas import ApiResponse, PaginatedResponse
from loguru import logger


router = APIRouter(prefix="/api/knowledge", tags=["知识库管理"])


# ==================== 请求/响应模型 ====================


class KnowledgeCategoryCreate(BaseModel):
    """创建知识库分类请求"""

    name: str
    industry: Optional[str] = None
    description: Optional[str] = None
    tags: Optional[str] = None
    color: str = "#6366f1"


class KnowledgeCategoryUpdate(BaseModel):
    """更新知识库分类请求"""

    name: Optional[str] = None
    industry: Optional[str] = None
    description: Optional[str] = None
    tags: Optional[str] = None
    color: Optional[str] = None


class KnowledgeCategoryResponse(BaseModel):
    """知识库分类响应"""

    id: int
    name: str
    industry: Optional[str]
    description: Optional[str]
    tags: Optional[str]
    color: str
    knowledge_count: int
    project_count: int
    created_at: str
    updated_at: str


class KnowledgeCreate(BaseModel):
    """创建知识条目请求"""

    category_id: int
    title: str
    content: str
    type: str = "other"


class KnowledgeUpdate(BaseModel):
    """更新知识条目请求"""

    title: Optional[str] = None
    content: Optional[str] = None
    type: Optional[str] = None


class KnowledgeResponse(BaseModel):
    """知识条目响应"""

    id: int
    category_id: int
    title: str
    content: str
    type: str
    created_at: str
    updated_at: str


# ==================== 知识库分类API ====================


@router.get("/categories", response_model=PaginatedResponse[KnowledgeCategoryResponse])
async def get_categories(
    page: int = Query(1, ge=1, description="页码"),
    limit: int = Query(20, ge=1, le=100, description="每页数量"),
    search: Optional[str] = None,
    db: Session = Depends(get_db)
):
    """
    获取知识库分类列表（支持分页）
    """
    # ... 同步RAGFlow的代码保持不变 ...
    from backend.services.ragflow_client import get_ragflow_client

    try:
        ragflow_client = get_ragflow_client()
        ragflow_result = ragflow_client.list_datasets()

        if ragflow_result.get("code") == 0:
            ragflow_datasets = ragflow_result.get("data", [])

            for dataset in ragflow_datasets:
                ragflow_dataset_id = dataset.get("id")
                category = (
                    db.query(KnowledgeCategory)
                    .filter(KnowledgeCategory.ragflow_dataset_id == ragflow_dataset_id)
                    .first()
                )

                if category:
                    category.name = dataset.get("name")
                    category.description = dataset.get("description", "")
                    category.sync_status = "synced"
                    category.last_sync_at = datetime.now()
                else:
                    category = KnowledgeCategory(
                        ragflow_dataset_id=ragflow_dataset_id,
                        name=dataset.get("name"),
                        description=dataset.get("description", ""),
                        sync_status="synced",
                        last_sync_at=datetime.now(),
                    )
                    db.add(category)

            db.commit()
    except Exception as e:
        logger.warning(f"从RAGFlow同步分类失败，使用SQLite缓存: {e}")

    # 查询（带搜索）
    query = db.query(KnowledgeCategory).filter(KnowledgeCategory.status == 1)

    if search:
        query = query.filter(
            (KnowledgeCategory.name.like(f"%{search}%"))
            | (KnowledgeCategory.industry.like(f"%{search}%"))
            | (KnowledgeCategory.tags.like(f"%{search}%"))
        )

    # 统计总数
    total = query.count()

    # 分页查询
    categories = query.order_by(KnowledgeCategory.updated_at.desc()).offset((page - 1) * limit).limit(limit).all()

    # 构建响应
    result = []
    for cat in categories:
        knowledge_count = (
            db.query(Knowledge)
            .filter(Knowledge.ragflow_dataset_id == cat.ragflow_dataset_id, Knowledge.status == 1)
            .count()
        )

        from backend.database.models import Project
        project_count = (
            db.query(Project).filter(Project.industry == cat.industry, Project.status == 1).count()
            if cat.industry
            else 0
        )

        result.append(
            KnowledgeCategoryResponse(
                id=cat.id,
                name=cat.name,
                industry=cat.industry,
                description=cat.description,
                tags=cat.tags,
                color=cat.color,
                knowledge_count=knowledge_count,
                project_count=project_count,
                created_at=cat.created_at.isoformat() if cat.created_at else "",
                updated_at=cat.updated_at.isoformat() if cat.updated_at else "",
            )
        )

    # 计算分页信息
    pages = (total + limit - 1) // limit if total > 0 else 1

    return PaginatedResponse(
        total=total,
        items=result,
        page=page,
        limit=limit,
        pages=pages,
        has_next=page < pages,
        has_prev=page > 1
    )


@router.post("/categories", response_model=ApiResponse)
async def create_category(data: KnowledgeCategoryCreate, db: Session = Depends(get_db)):
    """
    创建知识库分类
    先在RAGFlow创建知识库，再更新SQLite缓存

    Args:
        data: 分类数据
        db: 数据库会话

    Returns:
        创建结果
    """
    from backend.services.ragflow_client import get_ragflow_client

    try:
        # 1. 在RAGFlow创建知识库
        ragflow_client = get_ragflow_client()
        ragflow_result = ragflow_client.create_dataset(
            name=data.name, description=data.description or f"{data.name} - AutoGeo知识库"
        )

        logger.info(f"RAGFlow返回结果: {ragflow_result}")

        if ragflow_result.get("code") != 0:
            raise HTTPException(status_code=500, detail=f"RAGFlow创建失败: {ragflow_result.get('message')}")

        # 尝试多种方式获取 dataset_id
        dataset_id = None

        # 方式1: data.id (标准格式)
        if not dataset_id and ragflow_result.get("data"):
            dataset_id = ragflow_result.get("data", {}).get("id")

        # 方式2: 直接在 result 中 (某些 API 格式)
        if not dataset_id:
            dataset_id = ragflow_result.get("id")

        # 方式3: data 是数组，取第一个
        if not dataset_id and isinstance(ragflow_result.get("data"), list):
            data_list = ragflow_result.get("data", [])
            if data_list:
                dataset_id = data_list[0].get("id")

        logger.info(f"解析到的 dataset_id: {dataset_id}")

        if not dataset_id:
            raise HTTPException(status_code=500, detail=f"RAGFlow返回的dataset_id为空，返回数据: {ragflow_result}")

        # 2. 在SQLite创建缓存记录
        logger.info(f"准备创建数据库记录，dataset_id类型: {type(dataset_id)}, 值: {dataset_id}")
        category = KnowledgeCategory(
            ragflow_dataset_id=str(dataset_id),  # 确保转换为字符串
            name=data.name,
            industry=data.industry,
            description=data.description,
            tags=data.tags,
            color=data.color,
            sync_status="synced",
            last_sync_at=datetime.now(),
        )
        db.add(category)
        db.commit()
        db.refresh(category)
        logger.info(f"数据库记录创建成功，category.id: {category.id}")

        logger.info(f"分类创建成功（RAGFlow ID: {dataset_id}）: {category.name}")

        return ApiResponse(
            success=True, data={"id": category.id, "ragflow_dataset_id": dataset_id}, message="分类创建成功"
        )
    except HTTPException:
        raise
    except Exception as e:
        db.rollback()
        logger.error(f"创建分类失败: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.put("/categories/{category_id}", response_model=ApiResponse)
async def update_category(category_id: int, data: KnowledgeCategoryUpdate, db: Session = Depends(get_db)):
    """
    更新知识库分类

    Args:
        category_id: 分类ID
        data: 更新数据
        db: 数据库会话

    Returns:
        更新结果
    """
    try:
        category = db.query(KnowledgeCategory).filter(KnowledgeCategory.id == category_id).first()

        if not category:
            raise HTTPException(status_code=404, detail="分类不存在")

        if data.name is not None:
            category.name = data.name
        if data.industry is not None:
            category.industry = data.industry
        if data.description is not None:
            category.description = data.description
        if data.tags is not None:
            category.tags = data.tags
        if data.color is not None:
            category.color = data.color

        db.commit()
        return ApiResponse(success=True, message="分类更新成功")
    except HTTPException:
        raise
    except Exception as e:
        db.rollback()
        logger.error(f"更新分类失败: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.delete("/categories/{category_id}", response_model=ApiResponse)
async def delete_category(category_id: int, db: Session = Depends(get_db)):
    """
    删除知识库分类

    Args:
        category_id: 分类ID
        db: 数据库会话

    Returns:
        删除结果
    """
    try:
        category = db.query(KnowledgeCategory).filter(KnowledgeCategory.id == category_id).first()

        if not category:
            raise HTTPException(status_code=404, detail="分类不存在")

        # 删除分类（会级联删除关联的知识）
        db.delete(category)
        db.commit()

        return ApiResponse(success=True, message="分类删除成功")
    except HTTPException:
        raise
    except Exception as e:
        db.rollback()
        logger.error(f"删除分类失败: {e}")
        raise HTTPException(status_code=500, detail=str(e))


# ==================== 知识条目API ====================


@router.get("/categories/{category_id}/knowledge", response_model=List[KnowledgeResponse])
async def get_knowledge_list(category_id: int, search: Optional[str] = None, db: Session = Depends(get_db)):
    """
    获取指定分类的知识列表
    从RAGFlow获取文档并更新SQLite缓存

    Args:
        category_id: 分类ID
        search: 搜索关键词（可选）
        db: 数据库会话

    Returns:
        知识条目列表
    """
    from backend.services.ragflow_client import get_ragflow_client

    # 1. 获取分类的RAGFlow知识库ID
    category = db.query(KnowledgeCategory).filter(KnowledgeCategory.id == category_id).first()
    if not category:
        raise HTTPException(status_code=404, detail="分类不存在")

    if not category.ragflow_dataset_id:
        raise HTTPException(status_code=400, detail="分类未关联RAGFlow知识库")

    try:
        # 2. 从RAGFlow获取文档列表
        ragflow_client = get_ragflow_client()
        ragflow_result = ragflow_client.list_documents(category.ragflow_dataset_id)

        if ragflow_result.get("code") == 0:
            ragflow_docs = ragflow_result.get("data", [])

            # 3. 同步到SQLite缓存
            for doc in ragflow_docs:
                ragflow_doc_id = doc.get("id")

                # 检查是否存在
                knowledge = db.query(Knowledge).filter(Knowledge.ragflow_document_id == ragflow_doc_id).first()

                if not knowledge:
                    # 创建缓存
                    knowledge = Knowledge(
                        ragflow_document_id=ragflow_doc_id,
                        ragflow_dataset_id=category.ragflow_dataset_id,
                        title=doc.get("name", ""),
                        type="other",
                        sync_status="synced",
                        last_sync_at=datetime.now(),
                    )
                    db.add(knowledge)

            db.commit()
    except Exception as e:
        logger.warning(f"从RAGFlow同步知识失败，使用SQLite缓存: {e}")

    # 4. 从SQLite返回（带搜索）
    query = db.query(Knowledge).filter(
        Knowledge.ragflow_dataset_id == category.ragflow_dataset_id, Knowledge.status == 1
    )

    if search:
        # 从RAGFlow搜索
        try:
            ragflow_client = get_ragflow_client()
            search_result = ragflow_client.retrieve(
                question=search, dataset_ids=[category.ragflow_dataset_id], top_k=100, similarity_threshold=0.0
            )

            if search_result.get("code") == 0:
                chunks = search_result.get("data", {}).get("chunks", [])
                doc_ids = set(chunk.get("document_id") for chunk in chunks)

                # 过滤出搜索到的文档
                if doc_ids:
                    query = query.filter(Knowledge.ragflow_document_id.in_(doc_ids))
        except Exception as e:
            logger.warning(f"RAGFlow搜索失败，使用本地搜索: {e}")
            # 降级到本地标题搜索
            query = query.filter(Knowledge.title.like(f"%{search}%"))

    items = query.order_by(Knowledge.updated_at.desc()).all()

    # 5. 获取文档内容（从RAGFlow）
    result = []
    for item in items:
        content = item.title  # 默认使用标题

        try:
            # 从RAGFlow获取完整内容
            content_result = ragflow_client.get_document_content(category.ragflow_dataset_id, item.ragflow_document_id)
            if content_result.get("code") == 0:
                content = content_result.get("data", {}).get("content", item.title)
        except Exception as e:
            logger.warning(f"获取文档内容失败: {e}")

        result.append(
            KnowledgeResponse(
                id=item.id,
                category_id=category_id,
                title=item.title,
                content=content,
                type=item.type,
                created_at=item.created_at.isoformat() if item.created_at else "",
                updated_at=item.updated_at.isoformat() if item.updated_at else "",
            )
        )

    return result


@router.post("/knowledge", response_model=ApiResponse)
async def create_knowledge(data: KnowledgeCreate, db: Session = Depends(get_db)):
    """
    创建知识条目
    先在RAGFlow上传文档，再更新SQLite缓存

    Args:
        data: 知识数据
        db: 数据库会话

    Returns:
        创建结果
    """
    from backend.services.ragflow_client import get_ragflow_client

    try:
        # 1. 获取分类的RAGFlow知识库ID
        category = db.query(KnowledgeCategory).filter(KnowledgeCategory.id == data.category_id).first()
        if not category:
            raise HTTPException(status_code=404, detail="分类不存在")

        if not category.ragflow_dataset_id:
            raise HTTPException(status_code=400, detail="分类未关联RAGFlow知识库")

        # 2. 在RAGFlow上传文档
        ragflow_client = get_ragflow_client()
        ragflow_result = ragflow_client.upload_document_content(
            dataset_id=category.ragflow_dataset_id, title=data.title, content=data.content
        )

        if ragflow_result.get("code") != 0:
            raise HTTPException(status_code=500, detail=f"RAGFlow上传失败: {ragflow_result.get('message')}")

        docs = ragflow_result.get("data", [])
        if not docs:
            raise HTTPException(status_code=500, detail="RAGFlow返回的文档列表为空")

        doc_id = docs[0].get("id")
        if not doc_id:
            raise HTTPException(status_code=500, detail="RAGFlow返回的文档ID为空")

        # 3. 在SQLite创建缓存记录
        knowledge = Knowledge(
            ragflow_document_id=doc_id,
            ragflow_dataset_id=category.ragflow_dataset_id,
            category_id=data.category_id,  # 添加 category_id
            title=data.title,
            content=data.content[:500] if data.content else data.title,  # 保存内容摘要到数据库
            type=data.type,
            sync_status="synced",
            last_sync_at=datetime.now(),
        )
        db.add(knowledge)
        db.commit()
        db.refresh(knowledge)

        logger.info(f"知识创建成功（RAGFlow ID: {doc_id}）: {knowledge.title}")

        return ApiResponse(
            success=True, data={"id": knowledge.id, "ragflow_document_id": doc_id}, message="知识添加成功"
        )
    except HTTPException:
        raise
    except Exception as e:
        db.rollback()
        logger.error(f"创建知识失败: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/knowledge/upload", response_model=ApiResponse)
async def upload_knowledge_file(
    category_id: int = Form(...),
    file: UploadFile = File(...),
    title: Optional[str] = Form(None),
    type: Optional[str] = Form("other"),
    db: Session = Depends(get_db),
):
    """
    上传文件到知识库（支持PDF、Word、Excel等格式）

    Args:
        category_id: 分类ID
        file: 上传的文件
        title: 自定义标题（可选，默认使用文件名）
        type: 知识类型
        db: 数据库会话

    Returns:
        创建结果
    """
    from backend.services.ragflow_client import get_ragflow_client

    try:
        # 1. 获取分类的RAGFlow知识库ID
        category = db.query(KnowledgeCategory).filter(KnowledgeCategory.id == category_id).first()
        if not category:
            raise HTTPException(status_code=404, detail="分类不存在")

        if not category.ragflow_dataset_id:
            raise HTTPException(status_code=400, detail="分类未关联RAGFlow知识库")

        # 2. 读取上传的文件内容
        file_content = await file.read()
        file_name = title or file.filename

        # 3. 在RAGFlow上传文件
        ragflow_client = get_ragflow_client()
        ragflow_result = ragflow_client.upload_document_bytes(
            dataset_id=category.ragflow_dataset_id,
            file_content=file_content,
            file_name=file_name,
        )

        if ragflow_result.get("code") != 0:
            raise HTTPException(status_code=500, detail=f"RAGFlow上传失败: {ragflow_result.get('message')}")

        docs = ragflow_result.get("data", [])
        if not docs:
            raise HTTPException(status_code=500, detail="RAGFlow返回的文档列表为空")

        doc_id = docs[0].get("id")
        if not doc_id:
            raise HTTPException(status_code=500, detail="RAGFlow返回的文档ID为空")

        # 4. 在SQLite创建缓存记录
        knowledge = Knowledge(
            ragflow_document_id=doc_id,
            ragflow_dataset_id=category.ragflow_dataset_id,
            category_id=category_id,
            title=file_name,
            content=f"文件: {file_name}",  # 保存文件名作为摘要
            type=type,
            sync_status="synced",
            last_sync_at=datetime.now(),
        )
        db.add(knowledge)
        db.commit()
        db.refresh(knowledge)

        logger.info(f"文件上传成功（RAGFlow ID: {doc_id}）: {file_name}")

        return ApiResponse(
            success=True,
            data={"id": knowledge.id, "ragflow_document_id": doc_id, "file_name": file_name},
            message="文件上传成功",
        )
    except HTTPException:
        raise
    except Exception as e:
        db.rollback()
        logger.error(f"文件上传失败: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.put("/knowledge/{knowledge_id}", response_model=ApiResponse)
async def update_knowledge(knowledge_id: int, data: KnowledgeUpdate, db: Session = Depends(get_db)):
    """
    更新知识条目

    Args:
        knowledge_id: 知识ID
        data: 更新数据
        db: 数据库会话

    Returns:
        更新结果
    """
    try:
        knowledge = db.query(Knowledge).filter(Knowledge.id == knowledge_id).first()

        if not knowledge:
            raise HTTPException(status_code=404, detail="知识不存在")

        if data.title is not None:
            knowledge.title = data.title
        if data.content is not None:
            knowledge.content = data.content
        if data.type is not None:
            knowledge.type = data.type

        db.commit()
        return ApiResponse(success=True, message="知识更新成功")
    except HTTPException:
        raise
    except Exception as e:
        db.rollback()
        logger.error(f"更新知识失败: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.delete("/knowledge/{knowledge_id}", response_model=ApiResponse)
async def delete_knowledge(knowledge_id: int, db: Session = Depends(get_db)):
    """
    删除知识条目

    Args:
        knowledge_id: 知识ID
        db: 数据库会话

    Returns:
        删除结果
    """
    try:
        knowledge = db.query(Knowledge).filter(Knowledge.id == knowledge_id).first()

        if not knowledge:
            raise HTTPException(status_code=404, detail="知识不存在")

        db.delete(knowledge)
        db.commit()

        return ApiResponse(success=True, message="知识删除成功")
    except HTTPException:
        raise
    except Exception as e:
        db.rollback()
        logger.error(f"删除知识失败: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/knowledge/search", response_model=List[KnowledgeResponse])
async def search_knowledge(keyword: str = Query(..., min_length=1), db: Session = Depends(get_db)):
    """
    全局搜索知识

    Args:
        keyword: 搜索关键词
        db: 数据库会话

    Returns:
        知识条目列表
    """
    items = (
        db.query(Knowledge)
        .filter(
            Knowledge.status == 1, (Knowledge.title.like(f"%{keyword}%")) | (Knowledge.content.like(f"%{keyword}%"))
        )
        .order_by(Knowledge.updated_at.desc())
        .limit(50)
        .all()
    )

    return [
        KnowledgeResponse(
            id=item.id,
            category_id=item.category_id,
            title=item.title,
            content=item.content,
            type=item.type,
            created_at=item.created_at.isoformat() if item.created_at else "",
            updated_at=item.updated_at.isoformat() if item.updated_at else "",
        )
        for item in items
    ]


# ==================== RAGFlow同步API ====================


@router.post("/sync/categories/{category_id}", response_model=ApiResponse)
async def sync_category(category_id: int, db: Session = Depends(get_db)):
    """
    同步指定分类到RAGFlow

    Args:
        category_id: 分类ID
        db: 数据库会话

    Returns:
        同步结果
    """
    try:
        category = db.query(KnowledgeCategory).filter(KnowledgeCategory.id == category_id).first()
        if not category:
            raise HTTPException(status_code=404, detail="分类不存在")

        from backend.services.knowledge_sync_service import get_sync_service

        sync_service = get_sync_service(db)

        success = sync_service.sync_category_to_ragflow(category)
        if success:
            return ApiResponse(success=True, message="分类同步成功")
        else:
            return ApiResponse(success=False, message="分类同步失败")

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"同步分类失败: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/sync/knowledge/{knowledge_id}", response_model=ApiResponse)
async def sync_knowledge(knowledge_id: int, db: Session = Depends(get_db)):
    """
    同步指定知识条目到RAGFlow

    Args:
        knowledge_id: 知识ID
        db: 数据库会话

    Returns:
        同步结果
    """
    try:
        knowledge = db.query(Knowledge).filter(Knowledge.id == knowledge_id).first()
        if not knowledge:
            raise HTTPException(status_code=404, detail="知识不存在")

        from backend.services.knowledge_sync_service import get_sync_service

        sync_service = get_sync_service(db)

        success = sync_service.sync_knowledge_to_ragflow(knowledge)
        if success:
            return ApiResponse(success=True, message="知识同步成功")
        else:
            return ApiResponse(success=False, message="知识同步失败")

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"同步知识失败: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/sync/all", response_model=ApiResponse)
async def sync_all(db: Session = Depends(get_db)):
    """
    同步所有分类和知识到RAGFlow

    Args:
        db: 数据库会话

    Returns:
        同步结果
    """
    try:
        from backend.services.knowledge_sync_service import get_sync_service

        sync_service = get_sync_service(db)

        # 同步分类
        cat_success, cat_fail = sync_service.sync_all_categories()

        # 同步知识
        know_success, know_fail = sync_service.sync_all_knowledge()

        return ApiResponse(
            success=True,
            data={
                "categories": {"success": cat_success, "failed": cat_fail},
                "knowledge": {"success": know_success, "failed": know_fail},
            },
            message=f"同步完成: 分类成功{cat_success}失败{cat_fail}, 知识成功{know_success}失败{know_fail}",
        )

    except Exception as e:
        logger.error(f"全量同步失败: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/sync/status/{category_id}", response_model=ApiResponse)
async def get_sync_status(category_id: int, db: Session = Depends(get_db)):
    """
    获取分类的同步状态

    Args:
        category_id: 分类ID
        db: 数据库会话

    Returns:
        同步状态信息
    """
    try:
        from backend.services.knowledge_sync_service import get_sync_service

        sync_service = get_sync_service(db)

        status = sync_service.get_sync_status(category_id)
        return ApiResponse(success=True, data=status)

    except Exception as e:
        logger.error(f"获取同步状态失败: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/search/semantic", response_model=ApiResponse)
async def semantic_search(
    query: str = Query(..., min_length=1),
    category_id: Optional[int] = None,
    top_k: int = Query(50, ge=1, le=100),
    similarity_threshold: float = Query(0.7, ge=0.0, le=1.0),
    db: Session = Depends(get_db),
):
    """
    使用RAGFlow进行语义搜索

    Args:
        query: 搜索查询
        category_id: 限定分类ID（可选）
        top_k: 返回结果数量
        similarity_threshold: 相似度阈值
        db: 数据库会话

    Returns:
        搜索结果
    """
    try:
        from backend.services.knowledge_sync_service import get_sync_service
        from backend.config import RAGFLOW_DATASET_ID

        sync_service = get_sync_service(db)

        # 确定要搜索的知识库ID列表
        dataset_ids = []

        if category_id:
            # 搜索指定分类
            category = db.query(KnowledgeCategory).filter(KnowledgeCategory.id == category_id).first()
            if not category:
                raise HTTPException(status_code=404, detail="分类不存在")
            if category.ragflow_dataset_id:
                dataset_ids.append(category.ragflow_dataset_id)
        else:
            # 搜索所有已同步的分类
            categories = (
                db.query(KnowledgeCategory)
                .filter(KnowledgeCategory.ragflow_dataset_id.isnot(None), KnowledgeCategory.status == 1)
                .all()
            )
            dataset_ids = [cat.ragflow_dataset_id for cat in categories]

        # 如果没有知识库，使用默认知识库
        if not dataset_ids and RAGFLOW_DATASET_ID:
            dataset_ids.append(RAGFLOW_DATASET_ID)

        if not dataset_ids:
            return ApiResponse(success=True, data=[], message="没有可搜索的知识库")

        # 执行搜索
        results = sync_service.search_in_ragflow(
            query=query, dataset_ids=dataset_ids, top_k=top_k, similarity_threshold=similarity_threshold
        )

        return ApiResponse(success=True, data=results, message=f"找到 {len(results)} 个相关结果")

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"语义搜索失败: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/extract-info", response_model=ApiResponse)
async def extract_document_info(
    knowledge_id: int,
    db: Session = Depends(get_db),
):
    """
    从知识库文档中提取客户信息

    使用AI从上传的文档中自动提取客户信息：
    - 公司名称
    - 联系人
    - 电话
    - 邮箱
    - 行业
    - 地址
    - 业务描述

    Args:
        knowledge_id: 知识ID
        db: 数据库会话

    Returns:
        提取的客户信息
    """
    try:
        from backend.services.document_extractor import get_document_extractor
        from backend.services.ragflow_client import get_ragflow_client

        # 1. 获取知识记录
        knowledge = db.query(Knowledge).filter(Knowledge.id == knowledge_id).first()
        if not knowledge:
            raise HTTPException(status_code=404, detail="知识不存在")

        # 2. 从RAGFlow提取文档信息
        ragflow_client = get_ragflow_client()
        extractor = get_document_extractor()

        extracted_info = extractor.extract_from_ragflow_document(
            dataset_id=knowledge.ragflow_dataset_id,
            document_id=knowledge.ragflow_document_id,
            ragflow_client=ragflow_client,
        )

        if not extracted_info:
            return ApiResponse(
                success=False,
                data={},
                message="未能从文档中提取到客户信息，请确认文档内容包含相关信息",
            )

        # 3. 尝试自动创建或更新客户记录
        client_data = {}
        if extracted_info.get("company_name"):
            # 查找是否已存在该公司
            from backend.database.models import Client

            existing_client = (
                db.query(Client)
                .filter(
                    (Client.company_name == extracted_info["company_name"])
                    | (Client.name == extracted_info["company_name"])
                )
                .first()
            )

            if existing_client:
                # 更新现有客户信息
                if extracted_info.get("contact_person"):
                    existing_client.contact_person = extracted_info["contact_person"]
                if extracted_info.get("phone"):
                    existing_client.phone = extracted_info["phone"]
                if extracted_info.get("email"):
                    existing_client.email = extracted_info["email"]
                if extracted_info.get("industry"):
                    existing_client.industry = extracted_info["industry"]
                if extracted_info.get("address"):
                    existing_client.address = extracted_info["address"]
                if extracted_info.get("description"):
                    existing_client.description = extracted_info["description"]

                db.commit()
                client_data = {
                    "client_id": existing_client.id,
                    "name": existing_client.name,
                    "company_name": existing_client.company_name,
                }
                logger.info(f"已更新客户信息: {existing_client.name}")
            else:
                # 创建新客户
                new_client = Client(
                    name=extracted_info.get("company_name", "未知客户")[:200],
                    company_name=extracted_info.get("company_name"),
                    contact_person=extracted_info.get("contact_person"),
                    phone=extracted_info.get("phone"),
                    email=extracted_info.get("email"),
                    industry=extracted_info.get("industry"),
                    address=extracted_info.get("address"),
                    description=extracted_info.get("description"),
                    status=1,
                )
                db.add(new_client)
                db.commit()
                db.refresh(new_client)

                client_data = {
                    "client_id": new_client.id,
                    "name": new_client.name,
                    "company_name": new_client.company_name,
                }
                logger.info(f"已创建新客户: {new_client.name}")

        return ApiResponse(
            success=True,
            data={
                "extracted_info": extracted_info,
                "client": client_data if client_data else None,
            },
            message="信息提取成功"
            + (
                f"，已{'更新' if client_data.get('client_id') and existing_client else '创建'}客户记录"
                if client_data
                else ""
            ),
        )

    except HTTPException:
        raise
    except Exception as e:
        db.rollback()
        logger.error(f"提取文档信息失败: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/extract-info-from-text", response_model=ApiResponse)
async def extract_info_from_text(
    text: str,
    db: Session = Depends(get_db),
):
    """
    从文本中提取客户信息（直接文本输入）

    用于用户直接粘贴文本内容进行信息提取

    Args:
        text: 文本内容
        db: 数据库会话

    Returns:
        提取的客户信息
    """
    try:
        from backend.services.document_extractor import get_document_extractor

        if not text or not text.strip():
            raise HTTPException(status_code=400, detail="文本内容不能为空")

        # 使用AI提取客户信息
        extractor = get_document_extractor()
        extracted_info = extractor.extract_from_text(text)

        if not extracted_info:
            return ApiResponse(
                success=False,
                data={},
                message="未能从文本中提取到客户信息",
            )

        return ApiResponse(
            success=True,
            data={"extracted_info": extracted_info},
            message="信息提取成功",
        )

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"从文本提取信息失败: {e}")
        raise HTTPException(status_code=500, detail=str(e))
