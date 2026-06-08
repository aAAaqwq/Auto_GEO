# -*- coding: utf-8 -*-
"""
RAG context builder for GEO article generation.

This service keeps business mapping and retrieval in the backend. n8n only
receives a compact `requirements` string and keeps its workflow structure.
"""

import os
from typing import Any, Dict, List, Optional

from loguru import logger
from sqlalchemy.orm import Session

from backend.database.models import Client, KnowledgeCategory, Keyword
from backend.services.ragflow_client import get_ragflow_client


CLIENT_UPLOAD_TAG_PREFIX = "source=client_upload,client_id="
DEFAULT_TOP_K_PER_QUERY = int(os.getenv("RAGFLOW_GEO_TOP_K_PER_QUERY", "8"))
DEFAULT_MAX_CHUNKS = int(os.getenv("RAGFLOW_GEO_MAX_CHUNKS", "12"))
DEFAULT_SIMILARITY_THRESHOLD = float(os.getenv("RAGFLOW_GEO_SIMILARITY_THRESHOLD", "0.3"))
DEFAULT_CONTEXT_MAX_CHARS = int(os.getenv("RAGFLOW_GEO_CONTEXT_MAX_CHARS", "5000"))


class GeoKnowledgeService:
    """Builds compact RAG context for GEO article generation."""

    def __init__(self, db: Session):
        self.db = db
        try:
            self.ragflow = get_ragflow_client()
        except Exception as exc:
            logger.warning("RAGFlow client initialization failed: {}", exc)
            self.ragflow = None

    def build_context_for_keyword(self, keyword_id: int, company_name: str = "") -> Dict[str, Any]:
        """
        Resolve datasets, retrieve relevant chunks, and format them for n8n.

        Returns a stable dict so callers can safely degrade when RAGFlow is not
        configured, no customer dataset exists, or retrieval returns no chunks.
        """
        warnings: List[str] = []

        keyword = self.db.query(Keyword).filter(Keyword.id == keyword_id).first()
        if not keyword:
            return self._empty_context(["keyword not found"])

        project = keyword.project
        client = project.client if project and project.client_id else None

        dataset_ids = self.resolve_dataset_ids(client=client)
        if not dataset_ids:
            warnings.append("no customer RAGFlow dataset found")
            return self._empty_context(warnings)

        if not self.ragflow or not self.ragflow.is_configured():
            warnings.append("RAGFlow is not configured")
            return self._empty_context(warnings, dataset_ids=dataset_ids)

        queries = self.build_retrieval_queries(
            keyword_text=keyword.keyword,
            company_name=company_name or (project.company_name if project else ""),
            project=project,
            client=client,
        )
        chunks = self.retrieve_chunks(dataset_ids=dataset_ids, queries=queries)
        ranked_chunks = self.dedupe_and_rank_chunks(chunks)[:DEFAULT_MAX_CHUNKS]

        if not ranked_chunks:
            warnings.append("no relevant RAGFlow chunks retrieved")
            return self._empty_context(warnings, dataset_ids=dataset_ids)

        context_text = self.format_rag_context(ranked_chunks)
        logger.info(
            "GEO RAG context built: keyword_id={}, datasets={}, chunks={}",
            keyword_id,
            len(dataset_ids),
            len(ranked_chunks),
        )

        return {
            "enabled": True,
            "dataset_ids": dataset_ids,
            "queries": queries,
            "chunks": ranked_chunks,
            "context_text": context_text,
            "warnings": warnings,
        }

    def resolve_dataset_ids(self, client: Optional[Client]) -> List[str]:
        """Resolve customer-scoped RAGFlow datasets."""
        if not client:
            return []

        tags = f"{CLIENT_UPLOAD_TAG_PREFIX}{client.id}"
        categories = (
            self.db.query(KnowledgeCategory)
            .filter(
                KnowledgeCategory.tags == tags,
                KnowledgeCategory.status == 1,
                KnowledgeCategory.ragflow_dataset_id.isnot(None),
            )
            .all()
        )

        dataset_ids = []
        seen = set()
        for category in categories:
            dataset_id = str(category.ragflow_dataset_id or "").strip()
            if dataset_id and dataset_id not in seen:
                dataset_ids.append(dataset_id)
                seen.add(dataset_id)
        return dataset_ids

    def build_retrieval_queries(
        self,
        keyword_text: str,
        company_name: str = "",
        project: Any = None,
        client: Optional[Client] = None,
    ) -> List[str]:
        """Build multiple semantic retrieval queries for article generation."""

        def clean(value: Any) -> str:
            return str(value or "").strip()

        project_description = clean(getattr(project, "description", ""))
        project_industry = clean(getattr(project, "industry", ""))
        project_domain_keyword = clean(getattr(project, "domain_keyword", ""))
        client_description = clean(getattr(client, "description", ""))
        client_industry = clean(getattr(client, "industry", ""))
        client_company = clean(getattr(client, "company_name", "")) or clean(getattr(client, "name", ""))
        final_company_name = clean(company_name) or client_company

        raw_queries = [
            f"{keyword_text} {final_company_name} {project_description} {project_domain_keyword}",
            f"{keyword_text} 产品服务 解决方案 应用场景 核心优势 {project_industry or client_industry}",
            f"{keyword_text} 行业痛点 用户需求 常见问题 选型建议 {client_description}",
            f"{final_company_name} 公司介绍 核心优势 资质 案例 产品 服务",
        ]

        queries = []
        seen = set()
        for query in raw_queries:
            normalized = " ".join(query.split())
            if normalized and normalized not in seen:
                queries.append(normalized)
                seen.add(normalized)
        return queries

    def retrieve_chunks(self, dataset_ids: List[str], queries: List[str]) -> List[Dict[str, Any]]:
        """Retrieve chunks from RAGFlow for each query."""
        all_chunks: List[Dict[str, Any]] = []
        for query in queries:
            result = self.ragflow.retrieve(
                question=query,
                dataset_ids=dataset_ids,
                similarity_threshold=DEFAULT_SIMILARITY_THRESHOLD,
                top_k=DEFAULT_TOP_K_PER_QUERY,
            )
            if result.get("code") != 0:
                logger.warning("RAGFlow retrieval failed: {}", result.get("message"))
                continue

            data = result.get("data") or {}
            chunks = data.get("chunks") if isinstance(data, dict) else []
            if not isinstance(chunks, list):
                continue

            for chunk in chunks:
                if not isinstance(chunk, dict):
                    continue
                copied = dict(chunk)
                copied["_query"] = query
                all_chunks.append(copied)
        return all_chunks

    def dedupe_and_rank_chunks(self, chunks: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """Dedupe chunks and sort by similarity."""
        deduped: Dict[str, Dict[str, Any]] = {}

        for chunk in chunks:
            content = self._clean_content(chunk.get("content", ""))
            if not content:
                continue

            chunk_id = chunk.get("id") or chunk.get("chunk_id")
            document_id = chunk.get("document_id") or chunk.get("doc_id") or ""
            key = str(chunk_id or f"{document_id}:{content[:120]}")

            existing = deduped.get(key)
            if not existing or self._similarity(chunk) > self._similarity(existing):
                normalized = dict(chunk)
                normalized["content"] = content
                deduped[key] = normalized

        return sorted(deduped.values(), key=self._similarity, reverse=True)

    def format_rag_context(self, chunks: List[Dict[str, Any]]) -> str:
        """Format retrieved chunks into a compact prompt section."""
        lines = [
            "请优先参考以下客户知识库资料完成文章写作。",
            "",
            "注意：这些资料是事实参考，不要求逐条引用；不要编造资料中没有的资质、案例、价格、客户名称或承诺。",
        ]

        total_chars = sum(len(line) for line in lines)
        for idx, chunk in enumerate(chunks, start=1):
            document_name = (
                chunk.get("document_name")
                or chunk.get("docname")
                or chunk.get("document_title")
                or chunk.get("document_id")
                or "未知文档"
            )
            similarity = self._similarity(chunk)
            content = self._clean_content(chunk.get("content", ""))
            remaining = DEFAULT_CONTEXT_MAX_CHARS - total_chars
            if remaining <= 200:
                break
            max_content_len = min(900, max(200, remaining - 160))
            if len(content) > max_content_len:
                content = content[:max_content_len].rstrip() + "..."

            block = [
                "",
                f"【客户知识库片段 {idx}】",
                f"来源文档：{document_name}",
                f"相关度：{similarity:.2f}",
                f"内容：{content}",
            ]
            block_text = "\n".join(block)
            lines.append(block_text)
            total_chars += len(block_text)

        lines.extend(
            [
                "",
                "补充要求：",
                "- 文章主题围绕关键词展开。",
                "- 公司名自然出现 2-3 次。",
                "- 知识库没有出现的信息不要编造。",
                "- 资料不足时可以补充通用行业观点，但要保持保守表达。",
            ]
        )
        return "\n".join(lines)

    def build_requirements(
        self,
        *,
        base_requirements: str,
        rag_context: Dict[str, Any],
    ) -> str:
        """Merge baseline writing requirements with optional RAG context."""
        parts = [base_requirements.strip()]
        context_text = (rag_context or {}).get("context_text")
        if context_text:
            parts.extend(["", "### 客户知识库参考资料", context_text])
        else:
            parts.extend(
                [
                    "",
                    "### 客户知识库参考资料",
                    "当前未检索到客户知识库资料，请按通用行业知识写作，但不要编造具体资质、客户案例、价格或承诺。",
                ]
            )

        warnings = (rag_context or {}).get("warnings") or []
        if warnings:
            parts.extend(["", f"资料检索提示：{'; '.join(str(item) for item in warnings)}"])
        return "\n".join(parts)

    def _empty_context(self, warnings: List[str], dataset_ids: Optional[List[str]] = None) -> Dict[str, Any]:
        return {
            "enabled": False,
            "dataset_ids": dataset_ids or [],
            "queries": [],
            "chunks": [],
            "context_text": "",
            "warnings": warnings,
        }

    def _similarity(self, chunk: Dict[str, Any]) -> float:
        value = chunk.get("similarity", chunk.get("vector_similarity", 0))
        try:
            return float(value or 0)
        except (TypeError, ValueError):
            return 0.0

    def _clean_content(self, content: Any) -> str:
        return " ".join(str(content or "").split())
