# -*- coding: utf-8 -*-
"""
文档信息提取服务 - AI驱动
从上传的文档中自动提取客户信息（公司名称、联系人、电话、邮箱、行业、地址等）
"""

import json
import re
import zipfile
from io import BytesIO
from typing import Dict, Optional, List
from xml.etree import ElementTree
from loguru import logger

try:
    import httpx

    HAS_HTTPX = True
except ImportError:
    HAS_HTTPX = False
    logger.warning("httpx未安装，AI信息提取功能可能受限")

from backend.config import DEEPSEEK_API_KEY, DEEPSEEK_API_URL, GLM_API_KEY, GLM_API_URL, GLM_MODEL


class DocumentExtractor:
    """
    文档信息提取服务
    使用AI从文档内容中提取结构化的客户信息
    """

    def __init__(self, api_key: str = None, api_url: str = None):
        """
        初始化文档提取器

        Args:
            api_key: DeepSeek API Key（默认从配置读取）
            api_url: DeepSeek API URL（默认从配置读取）
        """
        if GLM_API_KEY:
            self.provider = "glm"
            self.api_key = api_key or GLM_API_KEY
            self.api_url = api_url or GLM_API_URL
            self.model = GLM_MODEL
        else:
            self.provider = "deepseek"
            self.api_key = api_key or DEEPSEEK_API_KEY
            self.api_url = api_url or DEEPSEEK_API_URL
            self.model = "deepseek-chat"
        self.timeout = 60

    def is_configured(self) -> bool:
        """检查是否已配置API"""
        return bool(self.api_key and self.api_url and HAS_HTTPX)

    def _chat_completions_url(self) -> str:
        base_url = self.api_url.rstrip("/")
        if base_url.endswith("/chat/completions"):
            return base_url
        return f"{base_url}/chat/completions"

    def extract_from_text(self, text: str) -> Dict:
        """
        从文本中提取客户信息

        Args:
            text: 文档文本内容

        Returns:
            提取的客户信息字典
        """
        if not self.is_configured():
            logger.warning("AI服务未配置，使用正则表达式提取")
            return self._normalize_extracted_info(self._extract_with_regex(text))

        try:
            extracted = self._extract_with_ai(text)
        except Exception as e:
            logger.error(f"AI提取失败，使用正则表达式: {e}")
            extracted = self._extract_with_regex(text)

        return self._normalize_extracted_info(extracted)

    def _normalize_extracted_info(self, extracted: Dict) -> Dict:
        """Drop empty fields and keep only client fields the frontend can edit."""
        if not isinstance(extracted, dict):
            return {}

        allowed_fields = {
            "company_name",
            "contact_person",
            "phone",
            "email",
            "industry",
            "address",
            "description",
        }
        normalized = {}
        for key in allowed_fields:
            value = extracted.get(key)
            if value is None:
                continue
            if isinstance(value, str):
                value = value.strip(" \t\r\n：:，,；;")
            if value:
                normalized[key] = value
        return normalized

    def extract_text_from_file_bytes(self, file_content: bytes, file_name: str) -> str:
        """
        从上传文件字节中尽量提取可读文本，用于客户信息识别。

        RAGFlow 仍然负责完整文档入库与解析；这里仅做上传后的即时字段提取。
        """
        ext = file_name.rsplit(".", 1)[-1].lower() if "." in file_name else ""

        if ext in {"txt", "md", "csv", "json", "xml", "html", "htm", "log"}:
            return self._decode_text_bytes(file_content)

        if ext == "docx":
            return self._extract_docx_text(file_content)

        if ext == "pdf":
            return self._extract_pdf_text(file_content)

        return ""

    def _decode_text_bytes(self, file_content: bytes) -> str:
        for encoding in ("utf-8-sig", "utf-8", "gbk", "gb18030"):
            try:
                return file_content.decode(encoding)
            except UnicodeDecodeError:
                continue
        return ""

    def _extract_docx_text(self, file_content: bytes) -> str:
        try:
            with zipfile.ZipFile(BytesIO(file_content)) as docx:
                xml_content = docx.read("word/document.xml")
            root = ElementTree.fromstring(xml_content)
            namespace = "{http://schemas.openxmlformats.org/wordprocessingml/2006/main}"
            texts = [node.text for node in root.iter(f"{namespace}t") if node.text]
            return "\n".join(texts)
        except Exception as e:
            logger.warning(f"DOCX文本提取失败: {e}")
            return ""

    def _extract_pdf_text(self, file_content: bytes) -> str:
        try:
            from pypdf import PdfReader

            reader = PdfReader(BytesIO(file_content))
            pages = [page.extract_text() or "" for page in reader.pages[:10]]
            return "\n".join(pages)
        except ImportError:
            logger.warning("pypdf未安装，PDF客户信息即时提取将依赖RAGFlow解析结果")
            return ""
        except Exception as e:
            logger.warning(f"PDF文本提取失败: {e}")
            return ""

    def _extract_with_ai(self, text: str) -> Dict:
        """
        使用AI提取客户信息

        Args:
            text: 文档文本内容

        Returns:
            提取的客户信息字典
        """
        if not HAS_HTTPX:
            raise ImportError("httpx未安装，无法使用AI提取功能")

        # 截取前5000字符（避免token超限）
        text = text[:5000]

        prompt = f"""请从以下文档内容中提取客户信息，并以JSON格式返回：

文档内容：
{text}

请提取以下信息（如果文档中存在）：
- company_name: 公司名称
- contact_person: 联系人姓名
- phone: 联系电话
- email: 邮箱地址
- industry: 所属行业
- address: 公司地址
- description: 公司/业务描述

返回格式要求：
1. 必须是有效的JSON格式
2. 只返回提取到的信息，未提取到的字段返回null
3. 不要添加任何其他说明文字

返回示例：
{{
    "company_name": "绿阳环保科技有限公司",
    "contact_person": "张三",
    "phone": "13800138000",
    "email": "zhangsan@example.com",
    "industry": "环保工程",
    "address": "北京市朝阳区xxx路xxx号",
    "description": "专注于环保工程和清洁服务..."
}}
"""

        try:
            with httpx.Client(timeout=self.timeout) as client:
                response = client.post(
                    self._chat_completions_url(),
                    headers={
                        "Authorization": f"Bearer {self.api_key}",
                        "Content-Type": "application/json",
                    },
                    json={
                        "model": self.model,
                        "messages": [{"role": "user", "content": prompt}],
                        "temperature": 0.1,  # 降低温度提高稳定性
                        "max_tokens": 1000,
                    },
                )
                response.raise_for_status()
                result = response.json()

                # 提取AI返回的JSON
                content = result.get("choices", [{}])[0].get("message", {}).get("content", "")

                # 尝试解析JSON
                try:
                    # 清理可能的markdown代码块标记
                    content = content.strip()
                    if content.startswith("```json"):
                        content = content[7:]
                    if content.startswith("```"):
                        content = content[3:]
                    if content.endswith("```"):
                        content = content[:-3]
                    content = content.strip()

                    extracted = json.loads(content)
                    logger.info(f"AI提取成功 provider={self.provider}, model={self.model}: {extracted}")
                    return extracted
                except json.JSONDecodeError as e:
                    logger.warning(f"AI返回的不是有效JSON: {content[:200]}")
                    return self._extract_with_regex(text)

        except httpx.HTTPError as e:
            logger.error(f"AI API请求失败: {e}")
            raise
        except Exception as e:
            logger.error(f"AI提取失败: {e}")
            raise

    def _extract_with_regex(self, text: str) -> Dict:
        """
        使用正则表达式提取客户信息（降级方案）

        Args:
            text: 文档文本内容

        Returns:
            提取的客户信息字典
        """
        result = {}

        def first_capture(patterns: List[str], max_len: int = 200) -> Optional[str]:
            for pattern in patterns:
                match = re.search(pattern, text, re.IGNORECASE | re.MULTILINE)
                if not match:
                    continue
                value = match.group(1).strip(" \t\r\n：:，,；;")
                if value and len(value) <= max_len:
                    return value
            return None

        company_name = first_capture(
            [
                r"(?:公司名称|企业名称|客户名称|单位名称)[:：\s]*([^\n\r，,；;]{2,80})",
                r"([\u4e00-\u9fffA-Za-z0-9（）()·\-]{2,80}(?:股份有限公司|集团有限公司|科技有限公司|有限责任公司|有限公司|集团|工厂|中心))",
            ],
            max_len=100,
        )
        generic_company_names = {"我们公司", "我司", "本公司", "贵公司", "该公司", "公司"}
        if company_name and company_name not in generic_company_names:
            result["company_name"] = company_name

        contact_person = first_capture(
            [
                r"(?:联系人|业务联系人|负责人|联系人员|姓名)(?:[:：\s]*(?:是|为)?[:：\s]*)([\u4e00-\u9fffA-Za-z·]{2,20})",
                r"(?:联系人|负责人)(?:[:：\s]*(?:是|为)?[:：\s]*)([^\n\r，,；;]{2,20})",
            ],
            max_len=30,
        )
        if contact_person:
            result["contact_person"] = contact_person

        address = first_capture(
            [
                r"(?:公司地址|办公地址|联系地址|地址)[:：\s]*([^\n\r]{4,120})",
            ],
            max_len=150,
        )
        if address:
            result["address"] = address

        description = first_capture(
            [
                r"(?:公司简介|企业简介|业务描述|主营业务|经营范围)[:：\s]*([^\n\r]{6,200})",
            ],
            max_len=220,
        )
        if description:
            result["description"] = description

        # 提取邮箱
        email_pattern = r"[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}"
        emails = re.findall(email_pattern, text)
        if emails:
            result["email"] = emails[0]

        # 提取电话（手机号或座机）
        phone_patterns = [
            r"1[3-9]\d{9}",  # 手机号
            r"\d{3,4}-?\d{7,8}",  # 座机
            r"\d{11}",  # 11位数字（可能是手机号）
        ]
        for pattern in phone_patterns:
            phones = re.findall(pattern, text)
            if phones:
                result["phone"] = phones[0]
                break

        # 提取可能的行业关键词
        industry_keywords = [
            "环保工程",
            "工业清洗",
            "无人机服务",
            "电商",
            "教育培训",
            "金融服务",
            "医疗健康",
            "制造业",
            "房地产",
            "餐饮美食",
            "旅游出行",
            "物流运输",
            "新能源",
            "化工行业",
            "建筑工程",
            "SaaS软件",
            "互联网",
            "科技",
        ]
        industry_keywords.extend(
            [
                "人工智能",
                "软件开发",
                "信息技术",
                "环保",
                "工程服务",
                "机械设备",
                "企业服务",
                "咨询服务",
                "广告传媒",
                "跨境电商",
            ]
        )
        for industry in industry_keywords:
            if industry in text:
                result["industry"] = industry
                break

        logger.info(f"正则表达式提取结果: {result}")
        return result

    def extract_from_ragflow_document(self, dataset_id: str, document_id: str, ragflow_client) -> Dict:
        """
        从RAGFlow文档中提取客户信息

        Args:
            dataset_id: RAGFlow知识库ID
            document_id: RAGFlow文档ID
            ragflow_client: RAGFlow客户端实例

        Returns:
            提取的客户信息字典
        """
        try:
            # 获取文档内容
            doc_result = ragflow_client.get_document_content(dataset_id, document_id)

            if doc_result.get("code") != 0:
                logger.error(f"获取RAGFlow文档内容失败: {doc_result.get('message')}")
                return {}

            content = doc_result.get("data", {}).get("content", "")
            if not content:
                logger.warning("RAGFlow文档内容为空")
                return {}

            # 提取客户信息
            return self.extract_from_text(content)

        except Exception as e:
            logger.error(f"从RAGFlow文档提取信息失败: {e}")
            return {}


# 全局单例
_extractor: Optional[DocumentExtractor] = None


def get_document_extractor() -> DocumentExtractor:
    """获取文档提取器单例"""
    global _extractor
    if _extractor is None:
        _extractor = DocumentExtractor()
    return _extractor
