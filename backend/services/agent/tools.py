# -*- coding: utf-8 -*-
"""Business tools used by the AutoGEO backend Agent."""

import random
from typing import Any, Dict, List, Optional

from sqlalchemy.orm import Session

from backend.database.models import Account, Keyword, Project, ProjectMember
from backend.services.keyword_service import KeywordService


class AgentTools:
    def list_user_projects(self, db: Session, system_user_id: int) -> List[Project]:
        member_project_ids = [
            row.project_id
            for row in db.query(ProjectMember.project_id)
            .filter(ProjectMember.user_id == system_user_id, ProjectMember.status == 1)
            .all()
        ]
        query = db.query(Project).filter(Project.status == 1)
        if member_project_ids:
            query = query.filter(Project.id.in_(member_project_ids))
        return query.order_by(Project.updated_at.desc()).limit(50).all()

    def resolve_project(
        self,
        db: Session,
        system_user_id: int,
        project_hint: Optional[str],
        company_name: Optional[str] = None,
    ) -> Dict[str, Any]:
        projects = self.list_user_projects(db, system_user_id)
        if not projects:
            return {"status": "missing", "project": None, "candidates": []}

        hints = [self._normalize_hint(item) for item in (project_hint, company_name) if item and item.strip()]
        hints = [item for item in hints if item]
        if not hints:
            if len(projects) == 1:
                return {"status": "resolved", "project": projects[0], "candidates": []}
            return {"status": "ambiguous", "project": None, "candidates": projects[:8]}

        exact = [project for project in projects if self._project_matches_all_hints(project, hints, fuzzy=False)]
        if len(exact) == 1:
            return {"status": "resolved", "project": exact[0], "candidates": []}
        if len(exact) > 1:
            return {"status": "ambiguous", "project": None, "candidates": exact[:8]}

        fuzzy = [project for project in projects if self._project_matches_any_hint(project, hints, fuzzy=True)][:8]
        if len(fuzzy) == 1:
            return {"status": "resolved", "project": fuzzy[0], "candidates": []}
        if fuzzy:
            return {"status": "ambiguous", "project": None, "candidates": fuzzy}
        return {"status": "missing", "project": None, "candidates": []}

    def _project_matches_all_hints(self, project: Project, hints: List[str], fuzzy: bool) -> bool:
        return all(self._project_matches_hint(project, hint, fuzzy=fuzzy) for hint in hints)

    def _project_matches_any_hint(self, project: Project, hints: List[str], fuzzy: bool) -> bool:
        return any(self._project_matches_hint(project, hint, fuzzy=fuzzy) for hint in hints)

    def _project_matches_hint(self, project: Project, hint: str, fuzzy: bool) -> bool:
        fields = [
            project.name or "",
            project.company_name or "",
            project.domain_keyword or "",
            project.industry or "",
            project.description or "",
        ]
        normalized_fields = [self._normalize_hint(value) for value in fields if value]
        if fuzzy:
            low_hint = hint.lower()
            return any(
                low_hint in value.lower() or value.lower() in low_hint
                for value in normalized_fields
                if value
            )
        return any(hint == value or hint in value or value in hint for value in normalized_fields if value)

    def _normalize_hint(self, value: str) -> str:
        value = (value or "").strip().strip(" ，。,.")
        for prefix in ("我说的", "我要用", "这个", "该", "当前"):
            if value.startswith(prefix):
                value = value[len(prefix):].strip(" ，。,.")
        while len(value) > 1:
            for suffix in ("项目", "公司", "客户", "的"):
                if value.endswith(suffix) and len(value) > len(suffix):
                    value = value[: -len(suffix)].strip(" ，。,.")
                    break
            else:
                return value
        return value

    def resolve_accounts(
        self,
        db: Session,
        system_user_id: int,
        platforms: List[str],
    ) -> Dict[str, Any]:
        if not platforms:
            accounts = (
                db.query(Account)
                .filter(
                    Account.user_id == system_user_id,
                    Account.status == 1,
                    Account.deleted_at.is_(None),
                )
                .all()
            )
        else:
            accounts = (
                db.query(Account)
                .filter(
                    Account.user_id == system_user_id,
                    Account.platform.in_(platforms),
                    Account.status == 1,
                    Account.deleted_at.is_(None),
                )
                .all()
            )

        if not accounts:
            return {"status": "missing", "accounts": [], "candidates": []}
        if platforms and all(len([a for a in accounts if a.platform == p]) == 1 for p in platforms):
            return {"status": "resolved", "accounts": accounts, "candidates": []}
        if len(accounts) == 1:
            return {"status": "resolved", "accounts": accounts, "candidates": []}
        return {"status": "ambiguous", "accounts": [], "candidates": accounts[:12]}

    async def prepare_keyword(
        self,
        db: Session,
        project: Project,
        topic: Optional[str],
        company_name: Optional[str] = None,
        prefer_distill: bool = False,
    ) -> Optional[Keyword]:
        if topic:
            existing = (
                db.query(Keyword)
                .filter(
                    Keyword.project_id == project.id,
                    Keyword.status == "active",
                    Keyword.keyword.like(f"%{topic}%"),
                )
                .first()
            )
            if existing and not prefer_distill:
                return existing

        if prefer_distill and project.domain_keyword:
            distilled = await self.distill_project_keywords(db, project, company_name or project.company_name or topic)
            if distilled:
                return random.choice(distilled)

        active_query = (
            db.query(Keyword)
            .filter(Keyword.project_id == project.id, Keyword.status == "active")
        )
        active = active_query.all()
        if active:
            return random.choice(active)

        if project.domain_keyword:
            distilled = await self.distill_project_keywords(db, project, company_name or project.company_name or topic)
            if distilled:
                return random.choice(distilled)

        fallback_text = topic or project.domain_keyword or project.company_name or project.name
        if not fallback_text:
            return None
        keyword = Keyword(project_id=project.id, keyword=fallback_text, status="active")
        db.add(keyword)
        db.commit()
        db.refresh(keyword)
        return keyword

    async def distill_project_keywords(
        self,
        db: Session,
        project: Project,
        target_info: Optional[str],
    ) -> List[Keyword]:
        if not project.domain_keyword:
            return []

        result = await KeywordService(db).distill(
            core_kw=project.domain_keyword,
            target_info=target_info or project.company_name or project.name,
            company_name=project.company_name or "",
            industry=project.industry or "",
            description=project.description or "",
        )
        if not isinstance(result, dict):
            return []

        candidates: List[Any] = []
        for key in ("keywords", "similar_keywords", "variants", "conversion_phrases"):
            values = result.get(key)
            if isinstance(values, list):
                candidates.extend(values)

        keywords: List[Keyword] = []
        seen = set()
        for item in candidates:
            keyword_text = self._keyword_text(item)
            if not keyword_text or keyword_text in seen:
                continue
            seen.add(keyword_text)
            existing = (
                db.query(Keyword)
                .filter(
                    Keyword.project_id == project.id,
                    Keyword.keyword == keyword_text,
                )
                .first()
            )
            if existing:
                if existing.status != "active":
                    existing.status = "active"
                    db.commit()
                    db.refresh(existing)
                keywords.append(existing)
                continue
            keyword = Keyword(project_id=project.id, keyword=keyword_text, status="active")
            db.add(keyword)
            db.commit()
            db.refresh(keyword)
            keywords.append(keyword)
        return keywords

    def _keyword_text(self, item: Any) -> Optional[str]:
        if isinstance(item, str):
            return item.strip()[:200]
        if isinstance(item, dict):
            for key in ("keyword", "text", "phrase", "question", "name"):
                value = item.get(key)
                if isinstance(value, str) and value.strip():
                    return value.strip()[:200]
        return None

    def project_to_dict(self, project: Project) -> Dict[str, Any]:
        return {
            "id": project.id,
            "name": project.name,
            "company_name": project.company_name,
            "domain_keyword": project.domain_keyword,
        }

    def account_to_dict(self, account: Account) -> Dict[str, Any]:
        return {
            "id": account.id,
            "platform": account.platform,
            "account_name": account.account_name,
            "username": account.username,
        }


_instance: Optional[AgentTools] = None


def get_agent_tools() -> AgentTools:
    global _instance
    if _instance is None:
        _instance = AgentTools()
    return _instance
