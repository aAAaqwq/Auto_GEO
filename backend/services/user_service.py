# -*- coding: utf-8 -*-
"""
用户服务
处理用户认证和权限管理
"""

import bcrypt
import jwt
from datetime import datetime, timedelta
from typing import Dict, Any, Optional
from sqlalchemy.orm import Session
from loguru import logger

from backend.database.models import User
from backend.config import ENCRYPTION_KEY


class UserService:
    """用户服务"""

    def __init__(self):
        self.secret_key = ENCRYPTION_KEY[:32].decode() if isinstance(ENCRYPTION_KEY, bytes) else str(ENCRYPTION_KEY)[:32]

    def _hash_password(self, password: str) -> str:
        """哈希密码"""
        return bcrypt.hashpw(password.encode(), bcrypt.gensalt()).decode()

    def _verify_password(self, password: str, hashed: str) -> bool:
        """验证密码"""
        return bcrypt.checkpw(password.encode(), hashed.encode())

    def _generate_token(self, user_id: int, username: str, role: str) -> str:
        """生成 JWT token"""
        payload = {
            "user_id": user_id,
            "username": username,
            "role": role,
            "exp": datetime.utcnow() + timedelta(days=7),
            "iat": datetime.utcnow(),
        }
        return jwt.encode(payload, self.secret_key, algorithm="HS256")

    def _decode_token(self, token: str) -> Optional[Dict[str, Any]]:
        """解码 JWT token"""
        try:
            return jwt.decode(token, self.secret_key, algorithms=["HS256"])
        except jwt.ExpiredSignatureError:
            return None
        except jwt.InvalidTokenError:
            return None

    async def register(self, db: Session, username: str, password: str, email: Optional[str] = None) -> Dict[str, Any]:
        """用户注册"""
        try:
            # 检查用户名是否已存在
            existing = db.query(User).filter(User.username == username).first()
            if existing:
                return {"success": False, "error": "用户名已存在"}

            # 检查邮箱是否已存在
            if email:
                existing_email = db.query(User).filter(User.email == email).first()
                if existing_email:
                    return {"success": False, "error": "邮箱已存在"}

            # 创建新用户
            user = User(
                username=username,
                email=email,
                password_hash=self._hash_password(password),
                role="user",
                is_active=True,
            )
            db.add(user)
            db.commit()
            db.refresh(user)

            logger.info(f"用户注册成功: {username}")
            return {"success": True, "user_id": user.id, "username": user.username}

        except Exception as e:
            logger.error(f"用户注册失败: {e}")
            return {"success": False, "error": str(e)}

    async def login(self, db: Session, username: str, password: str) -> Dict[str, Any]:
        """用户登录"""
        try:
            # 查找用户
            user = db.query(User).filter(User.username == username).first()
            if not user:
                return {"success": False, "error": "用户名或密码错误"}

            # 检查用户状态
            if not getattr(user, "is_active", True):
                return {"success": False, "error": "用户已被禁用"}

            # 验证密码
            if not user.password_hash:
                return {"success": False, "error": "用户未设置密码"}

            if not self._verify_password(password, user.password_hash):
                return {"success": False, "error": "用户名或密码错误"}

            # 更新最后登录时间
            user.last_login = datetime.utcnow()
            db.commit()

            # 生成 token
            role = getattr(user, "role", "user")
            token = self._generate_token(user.id, user.username, role)

            logger.info(f"用户登录成功: {username}")
            return {
                "success": True,
                "token": token,
                "user": {
                    "id": user.id,
                    "username": user.username,
                    "email": user.email,
                    "role": role,
                },
            }

        except Exception as e:
            logger.error(f"用户登录失败: {e}")
            return {"success": False, "error": str(e)}

    async def get_user_by_token(self, db: Session, token: str) -> Optional[User]:
        """通过 token 获取用户"""
        payload = self._decode_token(token)
        if not payload:
            return None

        user_id = payload.get("user_id")
        if not user_id:
            return None

        return db.query(User).filter(User.id == user_id).first()

    async def verify_token(self, token: str) -> Optional[Dict[str, Any]]:
        """验证 token 并返回 payload"""
        return self._decode_token(token)

    async def list_users(self, db: Session, skip: int = 0, limit: int = 100) -> Dict[str, Any]:
        """获取用户列表（管理员功能）"""
        try:
            users = db.query(User).offset(skip).limit(limit).all()
            return {
                "success": True,
                "users": [
                    {
                        "id": u.id,
                        "username": u.username,
                        "email": u.email,
                        "role": getattr(u, "role", "user"),
                        "is_active": getattr(u, "is_active", True),
                        "last_login": getattr(u, "last_login", None),
                        "created_at": u.created_at.isoformat() if u.created_at else None,
                    }
                    for u in users
                ],
            }
        except Exception as e:
            logger.error(f"获取用户列表失败: {e}")
            return {"success": False, "error": str(e)}

    async def toggle_user_status(self, db: Session, user_id: int, is_active: bool) -> Dict[str, Any]:
        """切换用户状态（管理员功能）"""
        try:
            user = db.query(User).filter(User.id == user_id).first()
            if not user:
                return {"success": False, "error": "用户不存在"}

            user.is_active = is_active
            db.commit()

            logger.info(f"用户状态更新: {user.username} -> {'启用' if is_active else '禁用'}")
            return {"success": True, "message": f"用户已{'启用' if is_active else '禁用'}"}

        except Exception as e:
            logger.error(f"更新用户状态失败: {e}")
            return {"success": False, "error": str(e)}

    async def create_admin(self, db: Session, username: str, password: str, email: Optional[str] = None) -> Dict[str, Any]:
        """创建管理员用户"""
        try:
            # 检查用户名是否已存在
            existing = db.query(User).filter(User.username == username).first()
            if existing:
                return {"success": False, "error": "用户名已存在"}

            # 创建管理员用户
            user = User(
                username=username,
                email=email,
                password_hash=self._hash_password(password),
                role="admin",
                is_active=True,
            )
            db.add(user)
            db.commit()
            db.refresh(user)

            logger.info(f"管理员创建成功: {username}")
            return {"success": True, "user_id": user.id, "username": user.username}

        except Exception as e:
            logger.error(f"创建管理员失败: {e}")
            return {"success": False, "error": str(e)}


# 全局服务实例
user_service = UserService()
