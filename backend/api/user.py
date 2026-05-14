# -*- coding: utf-8 -*-
"""
用户管理API
处理用户注册、登录、JWT认证等
"""

from fastapi import APIRouter, HTTPException, Depends, status
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from sqlalchemy.orm import Session
from sqlalchemy.exc import IntegrityError
from typing import Optional, List
from datetime import datetime, timedelta
from loguru import logger
import bcrypt
import jwt
import os

from backend.database.models import User
from backend.database import get_db
from backend.schemas import ApiResponse, ErrorResponse
from pydantic import BaseModel, Field, EmailStr

# 路由配置
router = APIRouter(prefix="/api/users", tags=["users"])

# JWT配置
JWT_SECRET_KEY = os.getenv("JWT_SECRET_KEY")
if not JWT_SECRET_KEY:
    raise ValueError("JWT_SECRET_KEY environment variable is required")
JWT_ALGORITHM = "HS256"
JWT_ACCESS_TOKEN_EXPIRE_MINUTES = 60 * 24 * 7  # 7天

# 安全配置
MAX_LOGIN_ATTEMPTS = 5  # 最大登录失败次数
LOCKOUT_DURATION = 15  # 账户锁定时间（分钟）

# 安全依赖
security = HTTPBearer(auto_error=False)


# ==================== Pydantic模型 ====================
class UserRegisterRequest(BaseModel):
    """用户注册请求"""
    username: str = Field(..., min_length=3, max_length=50, description="用户名")
    email: Optional[EmailStr] = Field(None, description="邮箱")
    password: str = Field(..., min_length=6, max_length=100, description="密码")


class UserLoginRequest(BaseModel):
    """用户登录请求"""
    username: str = Field(..., description="用户名或邮箱")
    password: str = Field(..., description="密码")


class UserResponse(BaseModel):
    """用户响应模型"""
    id: int
    username: str
    email: Optional[str] = None
    role: str
    is_active: bool
    created_at: datetime

    class Config:
        from_attributes = True


class UserUpdateRequest(BaseModel):
    """用户更新请求"""
    email: Optional[EmailStr] = Field(None, description="邮箱")
    password: Optional[str] = Field(None, min_length=6, max_length=100, description="新密码")
    role: Optional[str] = Field(None, description="角色: admin, user")
    is_active: Optional[bool] = Field(None, description="是否激活")


class UserLoginResponse(BaseModel):
    """用户登录响应"""
    access_token: str
    token_type: str = "bearer"
    expires_in: int
    user: UserResponse


class UserListResponse(BaseModel):
    """用户列表响应"""
    total: int
    items: List[UserResponse]


class TokenPayload(BaseModel):
    """Token载荷"""
    user_id: int
    username: str
    exp: datetime


# ==================== 工具函数 ====================
def hash_password(password: str) -> str:
    """密码哈希加密"""
    return bcrypt.hashpw(password.encode(), bcrypt.gensalt()).decode()


def verify_password(password: str, hashed: str) -> bool:
    """验证密码"""
    try:
        return bcrypt.checkpw(password.encode(), hashed.encode())
    except Exception:
        return False


def create_access_token(user_id: int, username: str, expires_delta: Optional[timedelta] = None) -> str:
    """创建JWT访问令牌"""
    if expires_delta:
        expire = datetime.utcnow() + expires_delta
    else:
        expire = datetime.utcnow() + timedelta(minutes=JWT_ACCESS_TOKEN_EXPIRE_MINUTES)

    payload = {
        "user_id": user_id,
        "username": username,
        "exp": expire,
        "iat": datetime.utcnow(),
        "type": "access"
    }
    return jwt.encode(payload, JWT_SECRET_KEY, algorithm=JWT_ALGORITHM)


def decode_token(token: str) -> Optional[dict]:
    """解码JWT令牌"""
    try:
        payload = jwt.decode(token, JWT_SECRET_KEY, algorithms=[JWT_ALGORITHM])
        return payload
    except jwt.ExpiredSignatureError:
        return None
    except jwt.InvalidTokenError:
        return None


def get_current_user_from_token(
    credentials: HTTPAuthorizationCredentials = Depends(security),
    db: Session = Depends(get_db)
) -> User:
    """从Token获取当前用户"""
    if not credentials:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="未提供认证令牌",
            headers={"WWW-Authenticate": "Bearer"},
        )

    payload = decode_token(credentials.credentials)
    if not payload:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="无效的认证令牌",
            headers={"WWW-Authenticate": "Bearer"},
        )

    user_id = payload.get("user_id")
    if not user_id:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="无效的令牌内容",
            headers={"WWW-Authenticate": "Bearer"},
        )

    user = db.query(User).filter(User.id == user_id).first()
    if not user:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="用户不存在",
            headers={"WWW-Authenticate": "Bearer"},
        )

    if not user.is_active:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="用户已被禁用",
        )

    return user


def get_current_active_user(current_user: User = Depends(get_current_user_from_token)) -> User:
    """获取当前活跃用户"""
    if not current_user.is_active:
        raise HTTPException(status_code=400, detail="用户已被禁用")
    return current_user


def require_admin(current_user: User = Depends(get_current_user_from_token)) -> User:
    """需要管理员权限"""
    if current_user.role != "admin":
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="需要管理员权限"
        )
    return current_user


# ==================== API端点 ====================
@router.post("/register", response_model=ApiResponse)
async def register_user(request: UserRegisterRequest, db: Session = Depends(get_db)):
    """
    用户注册

    - **username**: 用户名（3-50字符）
    - **email**: 邮箱（可选）
    - **password**: 密码（至少6位）
    """
    try:
        # 检查用户名是否已存在
        existing_user = db.query(User).filter(User.username == request.username).first()
        if existing_user:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="用户名已存在"
            )

        # 检查邮箱是否已存在（如果提供了邮箱）
        if request.email:
            existing_email = db.query(User).filter(User.email == request.email).first()
            if existing_email:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail="邮箱已被注册"
                )

        # 确定角色：第一个注册的用户自动成为管理员
        user_count = db.query(User).count()
        role = "admin" if user_count == 0 else "user"

        # 创建新用户
        hashed_password = hash_password(request.password)
        new_user = User(
            username=request.username,
            email=request.email,
            password_hash=hashed_password,
            role=role,
            is_active=True,
            status=1
        )

        db.add(new_user)
        db.commit()
        db.refresh(new_user)

        logger.info(f"新用户注册成功: {request.username}, 角色: {role}")

        return ApiResponse(
            success=True,
            message="注册成功" + ("（已设为管理员）" if role == "admin" else ""),
            data={
                "id": new_user.id,
                "username": new_user.username,
                "email": new_user.email,
                "role": new_user.role,
                "is_active": new_user.is_active,
                "created_at": new_user.created_at.isoformat() if new_user.created_at else None
            }
        )

    except HTTPException:
        raise
    except IntegrityError as e:
        db.rollback()
        logger.error(f"数据库完整性错误: {e}")
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="用户数据冲突"
        )
    except Exception as e:
        db.rollback()
        logger.error(f"用户注册失败: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"注册失败: {str(e)}"
        )


@router.post("/login", response_model=ApiResponse)
async def login_user(request: UserLoginRequest, db: Session = Depends(get_db)):
    """
    用户登录

    - **username**: 用户名或邮箱
    - **password**: 密码
    """
    try:
        # 查找用户（支持用户名或邮箱登录）
        user = db.query(User).filter(
            (User.username == request.username) | (User.email == request.username)
        ).first()

        if not user:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="用户名或密码错误"
            )

        # 检查账户锁定
        if user.locked_until and user.locked_until > datetime.utcnow():
            remaining_seconds = int((user.locked_until - datetime.utcnow()).total_seconds())
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail=f"账户已被锁定，请在 {remaining_seconds // 60 + 1} 分钟后重试"
            )

        # 检查用户激活状态
        if not user.is_active:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="用户已被禁用"
            )

        # 验证密码
        if not verify_password(request.password, user.password_hash):
            # 增加失败登录次数
            user.failed_login_attempts = (user.failed_login_attempts or 0) + 1

            # 如果失败次数超过阈值，锁定账户
            if user.failed_login_attempts >= MAX_LOGIN_ATTEMPTS:
                user.locked_until = datetime.utcnow() + timedelta(minutes=LOCKOUT_DURATION)
                db.commit()
                logger.warning(f"用户 {user.username} 登录失败次数过多，账户已锁定")
                raise HTTPException(
                    status_code=status.HTTP_403_FORBIDDEN,
                    detail=f"登录失败次数过多，账户已被锁定 {LOCKOUT_DURATION} 分钟"
                )

            db.commit()
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="用户名或密码错误"
            )

        # 登录成功：重置失败计数，更新登录信息
        user.failed_login_attempts = 0
        user.locked_until = None
        user.last_login = datetime.utcnow()
        user.login_count = (user.login_count or 0) + 1
        db.commit()

        # 创建访问令牌
        access_token = create_access_token(user.id, user.username)
        expires_in = JWT_ACCESS_TOKEN_EXPIRE_MINUTES * 60

        logger.info(f"用户登录成功: {user.username} (角色: {user.role})")

        return ApiResponse(
            success=True,
            message="登录成功",
            data={
                "access_token": access_token,
                "token_type": "bearer",
                "expires_in": expires_in,
                "user": {
                    "id": user.id,
                    "username": user.username,
                    "email": user.email,
                    "role": user.role,
                    "is_active": user.is_active,
                    "created_at": user.created_at.isoformat() if user.created_at else None
                }
            }
        )

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"用户登录失败: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"登录失败: {str(e)}"
        )


@router.get("/me", response_model=ApiResponse)
async def get_current_user_info(current_user: User = Depends(get_current_active_user)):
    """
    获取当前用户信息
    需要有效的JWT令牌
    """
    return ApiResponse(
        success=True,
        message="获取成功",
        data={
            "id": current_user.id,
            "username": current_user.username,
            "email": current_user.email,
            "role": current_user.role,
            "is_active": current_user.is_active,
            "created_at": current_user.created_at.isoformat() if current_user.created_at else None,
            "updated_at": current_user.updated_at.isoformat() if current_user.updated_at else None,
            "last_login": current_user.last_login.isoformat() if current_user.last_login else None,
            "login_count": current_user.login_count or 0
        }
    )


@router.get("", response_model=ApiResponse)
async def list_users(
    page: int = 1,
    limit: int = 20,
    role: Optional[str] = None,
    is_active: Optional[bool] = None,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_admin)
):
    """
    获取用户列表（仅管理员）

    - **page**: 页码，默认1
    - **limit**: 每页数量，默认20
    - **role**: 按角色筛选（admin, user）
    - **is_active**: 按激活状态筛选
    """
    try:
        query = db.query(User)

        # 角色筛选
        if role:
            query = query.filter(User.role == role)

        # 激活状态筛选
        if is_active is not None:
            query = query.filter(User.is_active == is_active)

        # 计算总数
        total = query.count()

        # 分页
        users = query.order_by(User.id.desc()).offset((page - 1) * limit).limit(limit).all()

        items = []
        for user in users:
            items.append({
                "id": user.id,
                "username": user.username,
                "email": user.email,
                "role": user.role,
                "is_active": user.is_active,
                "status": user.status,
                "created_at": user.created_at.isoformat() if user.created_at else None,
                "last_login": user.last_login.isoformat() if user.last_login else None,
                "login_count": user.login_count or 0
            })

        return ApiResponse(
            success=True,
            message="获取成功",
            data={
                "total": total,
                "items": items,
                "page": page,
                "limit": limit,
                "pages": (total + limit - 1) // limit if total > 0 else 0
            }
        )

    except Exception as e:
        logger.error(f"获取用户列表失败: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"获取用户列表失败: {str(e)}"
        )


@router.put("/{user_id}/status", response_model=ApiResponse)
async def update_user_status(
    user_id: int,
    request: UserUpdateRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_admin)
):
    """
    更新用户状态/角色（仅管理员）

    - **user_id**: 用户ID
    - **is_active**: 是否激活
    - **role**: 角色（admin, user）
    """
    try:
        user = db.query(User).filter(User.id == user_id).first()
        if not user:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="用户不存在"
            )

        # 不能禁用自己
        if user.id == current_user.id:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="不能修改当前登录用户的状态"
            )

        updated_fields = []

        if request.is_active is not None:
            user.is_active = request.is_active
            user.status = 1 if request.is_active else 0
            updated_fields.append(f"is_active={request.is_active}")

        if request.role is not None:
            if request.role not in ["admin", "user"]:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail="无效的角色，仅支持 admin 或 user"
                )
            # 不能移除自己的管理员角色
            if user.role == "admin" and request.role != "admin" and user.id == current_user.id:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail="不能移除自己的管理员角色"
                )
            user.role = request.role
            updated_fields.append(f"role={request.role}")

        db.commit()

        logger.info(f"管理员 {current_user.username} 更新了用户 {user.username}: {', '.join(updated_fields)}")

        return ApiResponse(
            success=True,
            message="用户已更新",
            data={
                "id": user.id,
                "username": user.username,
                "role": user.role,
                "is_active": user.is_active,
                "status": user.status
            }
        )

    except HTTPException:
        raise
    except Exception as e:
        db.rollback()
        logger.error(f"更新用户失败: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"更新失败: {str(e)}"
        )


@router.delete("/{user_id}", response_model=ApiResponse)
async def delete_user(
    user_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_admin)
):
    """
    删除用户（仅管理员）

    - **user_id**: 用户ID
    """
    try:
        user = db.query(User).filter(User.id == user_id).first()
        if not user:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="用户不存在"
            )

        # 不能删除自己
        if user.id == current_user.id:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="不能删除当前登录的用户"
            )

        username = user.username
        user_role = user.role
        db.delete(user)
        db.commit()

        logger.info(f"管理员 {current_user.username} 删除了用户 {username} (角色: {user_role})")

        return ApiResponse(
            success=True,
            message="用户已删除",
            data={"id": user_id, "username": username}
        )

    except HTTPException:
        raise
    except Exception as e:
        db.rollback()
        logger.error(f"删除用户失败: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"删除失败: {str(e)}"
        )


@router.put("/me/password", response_model=ApiResponse)
async def change_password(
    old_password: str,
    new_password: str = Field(..., min_length=6, max_length=100),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_active_user)
):
    """
    修改当前用户密码

    - **old_password**: 旧密码
    - **new_password**: 新密码（至少6位）
    """
    try:
        # 验证旧密码
        if not verify_password(old_password, current_user.password_hash):
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="旧密码错误"
            )

        # 更新密码
        current_user.password_hash = hash_password(new_password)
        db.commit()

        logger.info(f"用户 {current_user.username} 修改了密码")

        return ApiResponse(
            success=True,
            message="密码修改成功"
        )

    except HTTPException:
        raise
    except Exception as e:
        db.rollback()
        logger.error(f"修改密码失败: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"修改密码失败: {str(e)}"
        )


@router.post("/unlock/{user_id}", response_model=ApiResponse)
async def unlock_user(
    user_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_admin)
):
    """
    解锁用户账户（仅管理员）

    - **user_id**: 用户ID
    """
    try:
        user = db.query(User).filter(User.id == user_id).first()
        if not user:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="用户不存在"
            )

        # 重置锁定状态
        user.failed_login_attempts = 0
        user.locked_until = None
        db.commit()

        logger.info(f"管理员 {current_user.username} 解锁了用户 {user.username}")

        return ApiResponse(
            success=True,
            message="用户已解锁",
            data={
                "id": user.id,
                "username": user.username,
                "failed_login_attempts": 0,
                "locked_until": None
            }
        )

    except HTTPException:
        raise
    except Exception as e:
        db.rollback()
        logger.error(f"解锁用户失败: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"解锁失败: {str(e)}"
        )
