# -*- coding: utf-8 -*-
"""
飞书机器人 Webhook API
接收飞书事件回调，解析消息，分发任务
"""

import asyncio
import json
import random
import string
from typing import Optional, List
from fastapi import APIRouter, Request, Response, Depends, HTTPException, Query
from loguru import logger
from sqlalchemy.exc import IntegrityError
from datetime import datetime, timedelta

from backend.services.feishu_client import get_feishu_client
from backend.services.feishu_intent_parser import get_feishu_intent_parser
from backend.services.feishu_task_handler import get_feishu_task_handler
from backend.database import SessionLocal, get_db
from backend.database.models import (
    FeishuEvent,
    FeishuUserBinding,
    FeishuBindingCode,
    User,
    Project,
)
from backend.schemas import (
    ApiResponse,
    FeishuBindingCreate,
    FeishuBindingUpdate,
    FeishuBindingResponse,
    FeishuBindingCheckResponse,
)

router = APIRouter(prefix="/api/feishu", tags=["飞书机器人"])

log = logger.bind(module="飞书Webhook")


def _cleanup_old_events():
    """清理 7 天前的旧事件（启动时执行）"""
    db = SessionLocal()
    try:
        from sqlalchemy import text
        result = db.execute(
            text("DELETE FROM feishu_events WHERE created_at < datetime('now', '-7 days')")
        )
        db.commit()
        count = result.rowcount
        if count:
            log.info(f"🧹 清理了 {count} 条过期飞书事件")
    except Exception as e:
        db.rollback()
        log.warning(f"清理旧事件失败: {e}")
    finally:
        db.close()


# 应用启动时清理一次旧事件
try:
    _cleanup_old_events()
except Exception:
    pass


# ==================== Webhook 入口 ====================


@router.post("/webhook")
async def feishu_webhook(request: Request):
    """
    飞书事件回调入口

    处理流程：
    1. 解析请求体
    2. 处理 URL 验证（首次配置时）
    3. 验证签名
    4. 提取消息内容
    5. AI 意图解析
    6. 异步执行任务
    7. 立即返回 200
    """
    feishu_client = get_feishu_client()

    # 1. 读取请求体
    try:
        body = await request.body()
        body_str = body.decode("utf-8")
        data = json.loads(body_str)
    except Exception as e:
        log.error(f"解析请求体失败: {e}")
        return Response(status_code=400)

    # 2. 处理 URL 验证挑战（首次配置飞书事件订阅时触发）
    if data.get("type") == "url_verification":
        challenge = data.get("challenge", "")
        token = data.get("token", "")
        log.info(f"收到 URL 验证请求, challenge: {challenge}")

        if feishu_client.verify_token(token):
            return {"challenge": challenge}
        else:
            log.warning("URL 验证 token 不匹配")
            return Response(status_code=403)

    # 3. 验证签名（如果有配置 Encrypt Key）
    timestamp = request.headers.get("X-Lark-Signature-Timestamp", "")
    nonce = request.headers.get("X-Lark-Signature-Nonce", "")
    signature = request.headers.get("X-Lark-Signature", "")

    if not feishu_client.verify_signature(timestamp, nonce, body_str, signature):
        log.warning("飞书 Webhook 签名验证失败")
        return Response(status_code=403)

    # 4. 解析事件数据
    header = data.get("header", {})
    event_id = header.get("event_id", "")
    event_type = header.get("event_type", "")

    log.info(f"📨 收到飞书事件: type={event_type}, event_id={event_id}")

    # 5. 处理消息事件
    if event_type == "im.message.receive_v1":
        event_data = data.get("event", {})
        message = event_data.get("message", {})
        sender = event_data.get("sender", {})

        # 提取关键信息
        chat_id = message.get("chat_id", "")
        msg_type = message.get("message_type", "")
        msg_content = message.get("content", "{}")
        user_id = sender.get("sender_id", {}).get("open_id", "")

        # 过滤机器人自身消息
        sender_type = sender.get("sender_type", "")
        if sender_type == "app":
            log.debug("忽略机器人自身消息")
            return {"code": 0}

        # 解析消息文本
        message_text = _extract_message_text(msg_type, msg_content)
        if not message_text:
            log.debug(f"无法提取文本内容, msg_type={msg_type}")
            return {"code": 0}

        log.info(f"💬 飞书消息: chat_id={chat_id}, user={user_id}, text={message_text[:100]}")

        # 6. 持久化事件（event_id 唯一约束做幂等）
        db = SessionLocal()
        try:
            event = FeishuEvent(
                event_id=event_id,
                message_id=header.get("message_id", ""),
                open_id=user_id,
                chat_id=chat_id,
                event_type=event_type,
                raw_payload=body_str,
                raw_text=message_text or "",
                status="received",
            )
            db.add(event)
            db.commit()
        except IntegrityError:
            db.rollback()
            log.debug(f"事件已处理(幂等跳过): {event_id}")
            return {"code": 0}
        except Exception as e:
            db.rollback()
            log.error(f"持久化事件失败: {e}")
            # 持久化失败不阻塞正常流程，继续处理
        finally:
            db.close()

        # 7. 立即返回 200（飞书要求 3 秒内响应）
        # 然后异步处理意图解析和任务执行
        asyncio.create_task(
            _process_message_async(event_id, message_text, chat_id, user_id)
        )

    # 返回成功
    return {"code": 0}


# ==================== 辅助函数 ====================


def _extract_message_text(msg_type: str, content: str) -> Optional[str]:
    """
    从消息内容中提取纯文本

    支持的消息类型：
    - text: 纯文本
    - post: 富文本（取第一个段落的文本）
    """
    try:
        content_data = json.loads(content) if isinstance(content, str) else content
    except json.JSONDecodeError:
        return None

    if msg_type == "text":
        # {"text": "消息内容"}
        return content_data.get("text", "").strip()

    elif msg_type == "post":
        # {"title": "", "content": [[{"tag": "text", "text": "xxx"}, {"tag": "at", "user_id": "xxx"}]]}
        paragraphs = content_data.get("content", [])
        texts = []
        for paragraph in paragraphs:
            for element in paragraph:
                if element.get("tag") == "text":
                    texts.append(element.get("text", ""))
                elif element.get("tag") == "at":
                    # 忽略 @ 消息标签，只保留文本
                    pass
        return "".join(texts).strip()

    # 其他消息类型暂不支持
    return None


async def _process_message_async(event_id: str, message_text: str, chat_id: str, user_id: str):
    """
    异步处理消息：意图解析 → 任务执行

    所有耗时操作都在这里执行，确保 Webhook 端点能在 3 秒内返回。
    """
    # 更新事件状态为 processing
    _update_event_status(event_id, "processing")

    try:
        # 1. 先回复用户"已收到"
        feishu_client = get_feishu_client()

        # 2. 构建上下文（可选：注入已有客户列表帮助 AI 理解）
        context = await _build_context()

        # 3. AI 意图解析
        intent_parser = get_feishu_intent_parser()
        command = await intent_parser.parse(message_text, context)

        log.info(f"🎯 意图解析结果: action={command.action}, params={command.params}")

        # 4. 先发送 AI 的回复文字
        if command.reply:
            await feishu_client.send_text_message(chat_id, command.reply)

        # 5. 如果不是 unknown，分发任务执行
        if command.action != "unknown":
            task_handler = get_feishu_task_handler()
            await task_handler.dispatch(command, chat_id, user_id)

        # 标记处理完成
        _update_event_status(event_id, "processed")

    except Exception as e:
        log.exception(f"异步处理飞书消息异常: {e}")
        _update_event_status(event_id, "error", str(e)[:500])


def _update_event_status(event_id: str, status: str, error_msg: str = None):
    """更新飞书事件处理状态"""
    db = SessionLocal()
    try:
        event = db.query(FeishuEvent).filter(FeishuEvent.event_id == event_id).first()
        if event:
            event.status = status
            if error_msg:
                event.error_msg = error_msg
            if status in ("processed", "error"):
                event.processed_at = datetime.now()
            db.commit()
    except Exception as e:
        db.rollback()
        log.warning(f"更新事件状态失败 (event_id={event_id}): {e}")
    finally:
        db.close()


async def _build_context() -> dict:
    """
    构建意图解析的附加上下文

    注入已有客户/项目列表，帮助 AI 理解公司名匹配
    """
    from backend.database import SessionLocal
    from backend.database.models import Client

    context = {}

    try:
        db = SessionLocal()
        clients = (
            db.query(Client)
            .filter(Client.status == 1)
            .order_by(Client.created_at.desc())
            .limit(10)
            .all()
        )
        if clients:
            context["clients"] = [
                {"name": c.name, "company_name": c.company_name}
                for c in clients
            ]
        db.close()
    except Exception as e:
        log.warning(f"构建上下文失败: {e}")

    return context


# ==================== 飞书用户绑定管理 API ====================


@router.get("/bindings", response_model=ApiResponse)
async def list_feishu_bindings(
    db=Depends(get_db),
):
    """
    获取所有飞书用户绑定列表（管理员功能）

    返回绑定信息含系统用户名和默认项目名
    """
    try:
        bindings = (
            db.query(FeishuUserBinding)
            .order_by(FeishuUserBinding.created_at.desc())
            .all()
        )

        items = []
        for b in bindings:
            user = db.query(User).filter(User.id == b.system_user_id).first()
            project = db.query(Project).filter(Project.id == b.default_project_id).first() if b.default_project_id else None

            items.append({
                "id": b.id,
                "open_id": b.open_id,
                "union_id": b.union_id,
                "system_user_id": b.system_user_id,
                "username": user.username if user else None,
                "default_project_id": b.default_project_id,
                "default_project_name": project.name if project else None,
                "default_client_id": b.default_client_id,
                "status": b.status,
                "created_at": b.created_at.isoformat() if b.created_at else None,
                "updated_at": b.updated_at.isoformat() if b.updated_at else None,
            })

        return ApiResponse(data={"total": len(items), "items": items})
    except Exception as e:
        log.error(f"获取绑定列表失败: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/bindings", response_model=ApiResponse)
async def create_feishu_binding(
    request: FeishuBindingCreate,
    db=Depends(get_db),
):
    """
    创建飞书用户绑定

    将一个飞书 open_id 绑定到系统用户
    """
    try:
        # 检查 open_id 是否已绑定
        existing = db.query(FeishuUserBinding).filter(
            FeishuUserBinding.open_id == request.open_id,
            FeishuUserBinding.status == 1,
        ).first()
        if existing:
            raise HTTPException(status_code=400, detail="该 open_id 已绑定到其他用户")

        # 验证系统用户存在
        user = db.query(User).filter(User.id == request.system_user_id).first()
        if not user:
            raise HTTPException(status_code=404, detail="系统用户不存在")

        binding = FeishuUserBinding(
            open_id=request.open_id,
            system_user_id=request.system_user_id,
            default_project_id=request.default_project_id,
            default_client_id=request.default_client_id,
            status=1,
        )
        db.add(binding)
        db.commit()
        db.refresh(binding)

        log.info(f"✅ 创建飞书绑定: open_id={request.open_id} -> user_id={request.system_user_id}")

        return ApiResponse(
            data={"id": binding.id, "message": "绑定创建成功"},
        )
    except HTTPException:
        raise
    except Exception as e:
        db.rollback()
        log.error(f"创建绑定失败: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.delete("/bindings/{binding_id}", response_model=ApiResponse)
async def delete_feishu_binding(
    binding_id: int,
    db=Depends(get_db),
):
    """
    删除飞书用户绑定（软删除：设置 status=0）
    """
    try:
        binding = db.query(FeishuUserBinding).filter(FeishuUserBinding.id == binding_id).first()
        if not binding:
            raise HTTPException(status_code=404, detail="绑定记录不存在")

        binding.status = 0
        db.commit()

        log.info(f"🗑️ 已解绑飞书绑定: id={binding_id}, open_id={binding.open_id}")

        return ApiResponse(data={"message": "绑定已解除"})
    except HTTPException:
        raise
    except Exception as e:
        db.rollback()
        log.error(f"删除绑定失败: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.put("/bindings/{binding_id}", response_model=ApiResponse)
async def update_feishu_binding(
    binding_id: int,
    request: FeishuBindingUpdate,
    db=Depends(get_db),
):
    """
    更新飞书用户绑定配置（默认项目、客户端等）
    """
    try:
        binding = db.query(FeishuUserBinding).filter(FeishuUserBinding.id == binding_id).first()
        if not binding:
            raise HTTPException(status_code=404, detail="绑定记录不存在")

        if request.default_project_id is not None:
            binding.default_project_id = request.default_project_id
        if request.default_client_id is not None:
            binding.default_client_id = request.default_client_id
        if request.status is not None:
            binding.status = request.status

        db.commit()

        log.info(f"✏️ 已更新飞书绑定: id={binding_id}")

        return ApiResponse(data={"message": "绑定已更新"})
    except HTTPException:
        raise
    except Exception as e:
        db.rollback()
        log.error(f"更新绑定失败: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/bindings/check/{open_id}", response_model=ApiResponse)
async def check_feishu_binding(
    open_id: str,
    db=Depends(get_db),
):
    """
    检查指定 open_id 是否已绑定

    返回绑定信息（含用户名和项目名）
    """
    try:
        binding = db.query(FeishuUserBinding).filter(
            FeishuUserBinding.open_id == open_id,
            FeishuUserBinding.status == 1,
        ).first()

        if not binding:
            return ApiResponse(data={"bound": False, "binding": None})

        user = db.query(User).filter(User.id == binding.system_user_id).first()
        project = db.query(Project).filter(Project.id == binding.default_project_id).first() if binding.default_project_id else None

        return ApiResponse(data={
            "bound": True,
            "binding": {
                "id": binding.id,
                "open_id": binding.open_id,
                "system_user_id": binding.system_user_id,
                "username": user.username if user else None,
                "default_project_id": binding.default_project_id,
                "default_project_name": project.name if project else None,
                "default_client_id": binding.default_client_id,
                "status": binding.status,
                "created_at": binding.created_at.isoformat() if binding.created_at else None,
            },
        })
    except Exception as e:
        log.error(f"检查绑定失败: {e}")
        raise HTTPException(status_code=500, detail=str(e))


# ==================== 飞书绑定码（自服务绑定） ====================


def _generate_binding_code() -> str:
    """生成6位随机绑定码（大写字母+数字）"""
    chars = string.ascii_uppercase + string.digits
    return ''.join(random.choice(chars) for _ in range(6))


@router.post("/bindings/generate-code/{user_id}", response_model=ApiResponse)
async def generate_binding_code_for_user(
    user_id: int,
    db=Depends(get_db),
):
    """
    为指定用户生成飞书绑定码

    用户登录 AutoGEO 后点击"绑定飞书"获取绑定码，
    然后在飞书中发送「绑定 <code>」完成绑定。
    绑定码 30 分钟有效。
    """
    # 验证用户存在
    user = db.query(User).filter(User.id == user_id).first()
    if not user:
        raise HTTPException(status_code=404, detail="用户不存在")

    # 检查是否已有未使用的绑定码（复用）
    existing = (
        db.query(FeishuBindingCode)
        .filter(
            FeishuBindingCode.system_user_id == user_id,
            FeishuBindingCode.status == 0,
            FeishuBindingCode.expires_at > datetime.now(),
        )
        .first()
    )
    if existing:
        return ApiResponse(data={
            "code": existing.code,
            "expires_at": existing.expires_at.isoformat(),
            "user_id": user_id,
            "username": user.username,
            "message": "已存在有效绑定码，请在30分钟内使用",
        })

    # 生成新绑定码
    code = _generate_binding_code()
    retry = 0
    while db.query(FeishuBindingCode).filter(FeishuBindingCode.code == code).first():
        code = _generate_binding_code()
        retry += 1
        if retry > 5:
            raise HTTPException(status_code=500, detail="生成绑定码失败，请重试")

    binding_code = FeishuBindingCode(
        code=code,
        system_user_id=user_id,
        status=0,
        expires_at=datetime.now() + timedelta(minutes=30),
    )
    db.add(binding_code)
    db.commit()
    db.refresh(binding_code)

    log.info(f"🔑 生成绑定码: code={code}, user_id={user_id}, username={user.username}")

    return ApiResponse(data={
        "code": code,
        "expires_at": binding_code.expires_at.isoformat(),
        "user_id": user_id,
        "username": user.username,
        "message": f"请在飞书中发送「绑定 {code}」完成绑定，30分钟内有效",
    })


@router.get("/bindings/my-status/{user_id}", response_model=ApiResponse)
async def get_user_binding_status(
    user_id: int,
    db=Depends(get_db),
):
    """
    查询用户的飞书绑定状态
    """
    user = db.query(User).filter(User.id == user_id).first()
    if not user:
        raise HTTPException(status_code=404, detail="用户不存在")

    binding = (
        db.query(FeishuUserBinding)
        .filter(
            FeishuUserBinding.system_user_id == user_id,
            FeishuUserBinding.status == 1,
        )
        .first()
    )

    active_code = (
        db.query(FeishuBindingCode)
        .filter(
            FeishuBindingCode.system_user_id == user_id,
            FeishuBindingCode.status == 0,
            FeishuBindingCode.expires_at > datetime.now(),
        )
        .first()
    )

    result = {"is_bound": binding is not None, "has_active_code": active_code is not None}

    if binding:
        bound_user = db.query(User).filter(User.id == binding.system_user_id).first()
        bound_project = db.query(Project).filter(Project.id == binding.default_project_id).first() if binding.default_project_id else None
        result["binding"] = {
            "id": binding.id,
            "open_id": binding.open_id,
            "username": bound_user.username if bound_user else None,
            "default_project_name": bound_project.name if bound_project else None,
            "created_at": binding.created_at.isoformat() if binding.created_at else None,
        }

    if active_code:
        result["active_code"] = {
            "code": active_code.code,
            "expires_at": active_code.expires_at.isoformat(),
        }

    return ApiResponse(data=result)
