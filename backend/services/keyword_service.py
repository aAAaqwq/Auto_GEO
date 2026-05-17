# -*- coding: utf-8 -*-
"""
关键词服务 - 工业加固版
负责：关键词的增删改查、调用 n8n 进行蒸馏逻辑、变体生成
"""

from typing import List, Dict, Any, Optional
from sqlalchemy.orm import Session
from loguru import logger

from backend.database.models import Keyword, Project, QuestionVariant

# 🌟 关键修改：引入新的 n8n 服务，替换旧的 client
from backend.services.n8n_service import get_n8n_service


class KeywordService:
    def __init__(self, db: Session):
        self.db = db

    def add_keyword(self, project_id: int, keyword: str, difficulty_score: Optional[int] = None) -> Keyword:
        """
        添加单个关键词 (带查重逻辑)
        """
        # 1. 检查是否存在
        exists = self.db.query(Keyword).filter(Keyword.project_id == project_id, Keyword.keyword == keyword).first()

        if exists:
            # 如果已存在但状态不是 active，则激活它
            if exists.status != "active":
                exists.status = "active"
                exists.difficulty_score = difficulty_score or exists.difficulty_score
                self.db.commit()
                logger.info(f"激活已有关键词: {keyword}")
            return exists

        # 2. 创建新词
        new_kw = Keyword(project_id=project_id, keyword=keyword, difficulty_score=difficulty_score, status="active")
        self.db.add(new_kw)
        self.db.commit()
        self.db.refresh(new_kw)
        logger.info(f"新增关键词: {keyword}")
        return new_kw

    def add_question_variant(self, keyword_id: int, question: str) -> QuestionVariant:
        """添加问题变体"""
        # 简单查重
        exists = (
            self.db.query(QuestionVariant)
            .filter(QuestionVariant.keyword_id == keyword_id, QuestionVariant.question == question)
            .first()
        )

        if exists:
            return exists

        new_qv = QuestionVariant(keyword_id=keyword_id, question=question)
        self.db.add(new_qv)
        self.db.commit()
        self.db.refresh(new_qv)
        return new_qv

    async def distill(
        self,
        *,
        core_kw: str,
        target_info: str,
        prefixes: str = "",
        suffixes: str = "",
        company_name: str = "",
        industry: str = "",
        description: str = "",
        count: int = 10,
    ) -> Dict[str, Any]:
        """
        🌟 核心方法：执行关键词蒸馏 (调用 n8n)
        v2: 增强n8n响应解析，支持多种嵌套格式
        """
        logger.info(f"🧪 开始关键词蒸馏: {core_kw} - {target_info}")

        # 兼容旧调用：如果没有传 core_kw/target_info，则退化为旧版拼装
        legacy_keywords_list = [f"公司:{company_name}", f"行业:{industry}", f"业务:{description}"]

        try:
            # 1. 获取服务单例
            n8n = await get_n8n_service()

            # 2. 调用 /webhook/keyword-distill
            if core_kw and target_info:
                result = await n8n.distill_keywords(
                    core_kw=core_kw,
                    target_info=target_info,
                    prefixes=prefixes or None,
                    suffixes=suffixes or None,
                    project_id=None,
                )
            else:
                result = await n8n.distill_keywords(keywords=legacy_keywords_list, project_id=None)

            if result.status == "success":
                logger.success("✅ n8n 响应成功")

                # 3. 深度解析n8n响应数据
                raw_data = result.data

                # 记录原始响应结构用于调试
                import json as _json
                try:
                    raw_str = _json.dumps(raw_data, ensure_ascii=False, default=str)[:2000]
                    logger.info(f"🔍 n8n原始响应: {raw_str}")
                except Exception:
                    logger.info(f"🔍 n8n原始响应(非序列化): {type(raw_data)} - {str(raw_data)[:1000]}")

                # 深度解包：处理多层嵌套 (output/body/data/result 等)
                raw_data = self._deep_unpack(raw_data)

                keywords_list = []
                similar_keywords = []
                variants = []
                conversion_phrases = []

                if isinstance(raw_data, dict):
                    # 1. 相近关键词
                    similar_keywords = self._extract_list(raw_data, [
                        "similar_keywords", "similar", "related_keywords",
                        "related", "long_tail_keywords", "longTailKeywords",
                    ])

                    # 2. 核心关键词变体
                    variants_raw = self._extract_list(raw_data, [
                        "variants", "keyword_variants", "keywordVariants",
                        "core_keywords", "coreKeywords",
                    ])
                    variants = variants_raw

                    # 3. 高转化搜索短语
                    conversion_phrases = self._extract_list(raw_data, [
                        "conversion_phrases", "conversionPhrases",
                        "high_conversion_phrases", "highConversionPhrases",
                        "questions", "search_phrases", "searchPhrases",
                        "long_tail_phrases", "longTailPhrases",
                        "phrases", "search_questions",
                    ])

                    # 4. 核心关键词（可能和 variants 重叠，需区分格式）
                    keywords_raw = raw_data.get("keywords", [])
                    if isinstance(keywords_raw, list):
                        # 检查是否是对象数组 [{keyword, ...}] 还是字符串数组
                        if keywords_raw and isinstance(keywords_raw[0], dict) and "keyword" in keywords_raw[0]:
                            # 已经是标准格式 [{keyword: "xx", ...}]
                            keywords_list = keywords_raw
                        elif keywords_raw and isinstance(keywords_raw[0], str):
                            # 字符串数组 -> 转为对象格式
                            keywords_list = [{"keyword": kw, "difficulty_score": 50} for kw in keywords_raw if kw]
                        elif keywords_raw and isinstance(keywords_raw[0], dict) and not keywords and not variants:
                            # 可能是对象数组但不含 keyword 字段，尝试提取
                            keywords_list = keywords_raw

                # 兜底：如果所有字段都为空，尝试从 raw_data 的所有键中自动检测数组
                if not keywords_list and not similar_keywords and not variants and not conversion_phrases:
                    logger.warning("⚠️ 标准字段解析为空，尝试自动检测数组字段...")
                    auto_result = self._auto_detect_arrays(raw_data)
                    similar_keywords = auto_result.get("similar_keywords", [])
                    keywords_list = auto_result.get("keywords", [])
                    variants = auto_result.get("variants", [])
                    conversion_phrases = auto_result.get("conversion_phrases", [])

                # 构建响应数据
                response_data = {"status": "success", "raw_response": raw_data}

                if similar_keywords:
                    response_data["similar_keywords"] = similar_keywords

                if variants:
                    response_data["variants"] = variants

                if conversion_phrases:
                    response_data["conversion_phrases"] = conversion_phrases

                # 解析 keywords 列表
                formatted_keywords = []
                for item in keywords_list:
                    if isinstance(item, str):
                        formatted_keywords.append({"keyword": item, "difficulty_score": 50})
                    elif isinstance(item, dict):
                        if "keyword" in item:
                            formatted_keywords.append(item)

                if formatted_keywords:
                    response_data["keywords"] = formatted_keywords

                logger.info(f"📊 蒸馏结果: {len(formatted_keywords)} 个核心词, {len(similar_keywords)} 个相近词, {len(variants)} 个变体, {len(conversion_phrases)} 个转化短语")

                return response_data
            else:
                logger.error(f"❌ n8n 业务逻辑报错: {result.error}")
                return {"status": "error", "message": result.error}

        except Exception as e:
            logger.exception(f"🚨 蒸馏服务连接异常: {e}")
            return {"status": "error", "message": str(e)}

    def _deep_unpack(self, data: Any) -> Any:
        """深度解包n8n嵌套响应"""
        import json as _json

        if data is None:
            return {}

        # 处理JSON字符串
        if isinstance(data, str):
            try:
                data = _json.loads(data)
            except (_json.JSONDecodeError, ValueError):
                return {"text_content": data}

        if not isinstance(data, dict):
            return data

        # 常见n8n嵌套键，逐层解包
        nested_keys = ["output", "body", "data", "result", "response", "json"]
        for key in nested_keys:
            if key in data and isinstance(data[key], dict):
                inner = data[key]
                # 只有当内层数据看起来像业务数据（非完整n8n响应）时才解包
                # 如果内层还有 status/data/output 等元数据键，继续解包
                if any(k in inner for k in nested_keys + ["keywords", "similar_keywords", "variants", "phrases", "questions"]):
                    return self._deep_unpack(inner)

        return data

    def _extract_list(self, data: dict, keys: list) -> list:
        """从字典中按多个候选键名提取列表"""
        for key in keys:
            val = data.get(key)
            if isinstance(val, list) and len(val) > 0:
                return val
            if isinstance(val, str):
                # 可能是逗号分隔的字符串
                try:
                    import json as _json
                    parsed = _json.loads(val)
                    if isinstance(parsed, list):
                        return parsed
                except (_json.JSONDecodeError, ValueError):
                    if "," in val:
                        return [v.strip() for v in val.split(",") if v.strip()]
        return []

    def _auto_detect_arrays(self, data: Any) -> Dict[str, list]:
        """自动从raw_data中检测数组字段并分类"""
        if not isinstance(data, dict):
            return {}

        result = {
            "similar_keywords": [],
            "keywords": [],
            "variants": [],
            "conversion_phrases": [],
        }

        for key, val in data.items():
            if not isinstance(val, list) or len(val) == 0:
                continue

            key_lower = key.lower()

            # 分类
            if any(kw in key_lower for kw in ["similar", "related", "long_tail", "related_keyword"]):
                if not result["similar_keywords"]:
                    result["similar_keywords"] = val
            elif any(kw in key_lower for kw in ["variant", "core_keyword", "corekeyword"]):
                if not result["variants"]:
                    result["variants"] = val
            elif any(kw in key_lower for kw in ["conversion", "phrase", "question", "search"]):
                if not result["conversion_phrases"]:
                    result["conversion_phrases"] = val
            elif any(kw in key_lower for kw in ["keyword", "key_word"]):
                if not result["keywords"]:
                    result["keywords"] = val
            # 如果没匹配到，且是字符串数组，归入 conversion_phrases
            elif val and isinstance(val[0], str) and not result["conversion_phrases"]:
                result["conversion_phrases"] = val

        return result

    async def generate_questions(self, keyword: str, count: int = 5) -> List[str]:
        """
        生成问题变体 (调用 n8n)
        """
        logger.info(f"❓ 正在为 [{keyword}] 生成长尾问题...")
        try:
            n8n = await get_n8n_service()
            # 调用 /webhook/generate-questions
            result = await n8n.generate_questions(keyword, count)

            if result.status == "success":
                data = result.data
                questions = []

                if isinstance(data, list):
                    questions = data
                elif isinstance(data, dict):
                    questions = data.get("questions") or data.get("data") or []

                # 过滤有效字符串
                final_questions = [str(q) for q in questions if q]
                logger.success(f"✅ 生成了 {len(final_questions)} 个问题")
                return final_questions
            else:
                logger.error(f"❌ 变体生成失败: {result.error}")
                return []
        except Exception as e:
            logger.error(f"🚨 变体服务异常: {e}")
            return []

    # ==================== 基础 CRUD 方法 ====================

    def create_project(
        self, name: str, company_name: str, description: Optional[str] = None, industry: Optional[str] = None
    ) -> Project:
        project = Project(name=name, company_name=company_name, description=description, industry=industry, status=1)
        self.db.add(project)
        self.db.commit()
        self.db.refresh(project)
        return project

    def get_project_keywords(self, project_id: int) -> List[Keyword]:
        """获取项目关键词 (包含软删除的，以便查看历史)"""
        return self.db.query(Keyword).filter(Keyword.project_id == project_id).all()

    def get_keyword_questions(self, keyword_id: int) -> List[QuestionVariant]:
        return self.db.query(QuestionVariant).filter(QuestionVariant.keyword_id == keyword_id).all()

    def list_projects(self) -> List[Project]:
        return self.db.query(Project).filter(Project.status == 1).all()
