# -*- coding: utf-8 -*-
"""
AutoGeo 后端主程序
"""

import sys
import os
import asyncio
from contextlib import asynccontextmanager
import uuid
import uvicorn
from fastapi import FastAPI, HTTPException, WebSocket, WebSocketDisconnect
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from loguru import logger

# 导入配置和数据库
from backend.config import APP_NAME, APP_VERSION, DEBUG, HOST, PORT, RELOAD, CORS_ORIGINS, PLATFORMS
from backend.database import init_db, SessionLocal
from backend.scripts.fix_database import check_and_fix_database

# 导入所有 API 路由模块
import backend.api.account as account
import backend.api.article as article
import backend.api.publish as publish
import backend.api.keywords as keywords
import backend.api.geo as geo
import backend.api.index_check as index_check
import backend.api.reports as reports
import backend.api.notifications as notifications
import backend.api.scheduler as scheduler
import backend.api.knowledge as knowledge
import backend.api.auth as auth
import backend.api.article_collection as article_collection
import backend.api.site_builder as site_builder
import backend.api.upload as upload
import backend.api.client as client  # 客户管理
import backend.api.auto_publish as auto_publish  # 自动发布任务
import backend.api.browser as browser  # 本地浏览器桥接
import backend.api.deployment as deployment  # 部署配置
import backend.api.user as user  # 用户管理
import backend.api.admin as admin  # 管理员配置

# 导入服务组件
from backend.services.websocket_manager import ws_manager
from backend.services.scheduler_service import get_scheduler_service
from backend.services.n8n_service import get_n8n_service
from backend.services.playwright_mgr import playwright_mgr
from backend.services.playwright.publishers import register_publishers


# ==================== 日志拦截器（核心监控功能） ====================
def socket_log_sink(message):
    """
    Loguru 拦截器：将每一条日志通过 WebSocket 广播出去
    """
    try:
        record = message.record
        log_payload = {
            "time": record["time"].strftime("%H:%M:%S"),
            "level": record["level"].name,
            "module": record["extra"].get("module", "系统"),
            "message": record["message"],
        }
        try:
            loop = asyncio.get_event_loop()
            if loop.is_running():
                loop.create_task(ws_manager.broadcast(log_payload))
        except RuntimeError:
            pass
        except Exception:
            pass
    except Exception:
        pass


# 艹，修复 Windows GBK 编码下的 emoji 输出问题！
# 强制重新配置 stdout 使用 UTF-8 编码
import io

sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")
sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding="utf-8", errors="replace")

# 配置 Loguru（stdout 已经是 UTF-8 了，不需要额外指定 encoding）
logger.remove()
logger.add(sys.stdout, level="INFO", colorize=True)
logger.add(socket_log_sink, level="INFO")


# ==================== 应用生命周期管理 ====================
@asynccontextmanager
async def lifespan(app: FastAPI):
    # ---------------- 启动阶段 ----------------
    logger.info(f"🚀 {APP_NAME} v{APP_VERSION} 正在启动...")

    # 1. 初始化数据库
    try:
        init_db()
        # 自动执行数据库修复/迁移（确保新字段存在）
        check_and_fix_database()
        logger.success("✅ 数据库初始化检查完成")
    except Exception as e:
        logger.error(f"❌ 数据库初始化失败: {e}")

    # 2. 注入全局 WebSocket 管理器
    account.set_ws_manager(ws_manager)
    publish.set_ws_manager(ws_manager)
    notifications.set_ws_callback(ws_manager.broadcast)

    # 3. 初始化 Playwright 管理器
    playwright_mgr.set_db_factory(SessionLocal)
    playwright_mgr.set_ws_callback(ws_manager.broadcast)
    logger.bind(module="发布器").success("发布器已配置")

    # 4. 启动定时任务引擎
    scheduler_instance = get_scheduler_service()
    scheduler_instance.set_db_factory(SessionLocal)
    scheduler_instance.start()
    logger.bind(module="调度中心").success("自动化任务引擎已启动")

    # 5. 注册平台发布适配器
    register_publishers(PLATFORMS)
    logger.bind(module="发布器").success(
        f"已注册 {len([k for k in PLATFORMS.keys() if k in ['zhihu', 'baijiahao', 'sohu', 'toutiao', 'xiaohongshu', 'douyin']])} 个平台发布器"
    )

    yield

    # ---------------- 关闭阶段 ----------------
    logger.info("正在关闭服务，释放资源...")
    scheduler_instance.stop()
    await playwright_mgr.stop()
    n8n_service = await get_n8n_service()
    await n8n_service.close()
    logger.info("服务已安全关闭")


# ==================== 创建应用实例 ====================
app = FastAPI(title=APP_NAME, version=APP_VERSION, debug=DEBUG, lifespan=lifespan)

# 跨域中间件
app.add_middleware(
    CORSMiddleware,
    allow_origins=CORS_ORIGINS,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


# ==================== 静态资源挂载 ====================
current_dir = os.path.dirname(os.path.abspath(__file__))
static_dir = os.path.join(current_dir, "static")

if not os.path.exists(static_dir):
    logger.info(f"正在创建静态目录: {static_dir}")
    os.makedirs(static_dir)

if not os.path.exists(os.path.join(static_dir, "uploads")):
    os.makedirs(os.path.join(static_dir, "uploads"))

if not os.path.exists(os.path.join(static_dir, "sites")):
    os.makedirs(os.path.join(static_dir, "sites"))

app.mount("/static", StaticFiles(directory=static_dir), name="static")
logger.success(f"✅ 静态资源已挂载: {static_dir}")


# ==================== 注册路由 ====================
app.include_router(account.router)
app.include_router(article.router)
app.include_router(publish.router)
app.include_router(keywords.router)
app.include_router(geo.router)
app.include_router(index_check.router)
app.include_router(reports.router)
app.include_router(notifications.router)
app.include_router(scheduler.router)
app.include_router(knowledge.router)
app.include_router(upload.router)  # 文件上传
app.include_router(client.router)  # 客户管理
app.include_router(auth.router)
app.include_router(article_collection.router)
app.include_router(site_builder.router)
app.include_router(auto_publish.router)  # 自动发布任务管理
app.include_router(browser.router)  # 本地浏览器桥接
app.include_router(deployment.router)  # 部署配置
app.include_router(user.router)  # 用户认证
app.include_router(admin.router)  # 管理员配置


# ==================== WebSocket 端点 ====================
@app.websocket("/ws")
async def websocket_endpoint(websocket: WebSocket, client_id: str = None):
    if not client_id:
        client_id = f"client_{uuid.uuid4().hex[:8]}"
    await ws_manager.connect(websocket, client_id)
    await ws_manager.send_personal(
        {
            "time": "系统",
            "level": "SUCCESS",
            "module": "系统",
            "message": "实时监控链路已就绪",
        },
        client_id,
    )
    try:
        while True:
            await websocket.receive_text()
    except WebSocketDisconnect:
        ws_manager.disconnect(client_id)
    except Exception as e:
        logger.error(f"WebSocket 异常: {e}")
        ws_manager.disconnect(client_id)


# ==================== 基础健康检查 ====================
@app.get("/")
async def root():
    return {"app": APP_NAME, "version": APP_VERSION, "status": "running"}


@app.get("/api/health")
async def health():
    """增强健康检查端点，返回各服务连接状态"""
    import httpx

    health_status = {
        "status": "ok",
        "timestamp": None,
        "services": {
            "database": {"status": "unknown"},
            "ragflow": {"status": "unknown"},
            "n8n": {"status": "unknown"},
        }
    }

    # 导入时间模块
    from datetime import datetime
    health_status["timestamp"] = datetime.now().isoformat()

    # 1. 数据库连接检测
    try:
        from backend.database import SessionLocal
        db = SessionLocal()
        db.execute("SELECT 1")
        db.close()
        health_status["services"]["database"] = {"status": "connected"}
    except Exception as e:
        health_status["services"]["database"] = {
            "status": "error",
            "message": str(e)[:100]
        }
        health_status["status"] = "degraded"

    # 2. RAGFlow 连接检测
    try:
        from backend.config import RAGFLOW_BASE_URL, RAGFLOW_API_KEY
        if RAGFLOW_API_KEY and RAGFLOW_BASE_URL:
            async with httpx.AsyncClient(timeout=5.0) as client:
                response = await client.get(
                    f"{RAGFLOW_BASE_URL}/api/v1/user",
                    headers={"Authorization": f"Bearer {RAGFLOW_API_KEY}"}
                )
                if response.status_code == 200:
                    health_status["services"]["ragflow"] = {"status": "connected"}
                else:
                    health_status["services"]["ragflow"] = {
                        "status": "error",
                        "code": response.status_code
                    }
        else:
            health_status["services"]["ragflow"] = {"status": "not_configured"}
    except Exception as e:
        health_status["services"]["ragflow"] = {
            "status": "error",
            "message": str(e)[:100]
        }
        health_status["status"] = "degraded"

    # 3. n8n 连接检测
    try:
        from backend.config import N8N_WEBHOOK_URL
        if N8N_WEBHOOK_URL:
            async with httpx.AsyncClient(timeout=5.0) as client:
                # n8n 不需要认证也能检测服务是否可达
                n8n_health_url = N8N_WEBHOOK_URL.replace("/webhook", "/healthz")
                response = await client.get(n8n_health_url)
                if response.status_code == 200:
                    health_status["services"]["n8n"] = {"status": "connected"}
                else:
                    health_status["services"]["n8n"] = {"status": "error", "code": response.status_code}
        else:
            health_status["services"]["n8n"] = {"status": "not_configured"}
    except Exception as e:
        health_status["services"]["n8n"] = {
            "status": "error",
            "message": str(e)[:100]
        }
        health_status["status"] = "degraded"

    return health_status


@app.get("/api/platforms")
async def get_platforms():
    return {"platforms": list(PLATFORMS.values())}


# ==================== 全局异常处理 ====================
@app.exception_handler(Exception)
async def global_exception_handler(request, exc):
    logger.exception(f"未处理的异常: {exc}")
    return HTTPException(status_code=500, detail=str(exc))


# ==================== 启动脚本 ====================
if __name__ == "__main__":
    # 艹！Windows下必须用ProactorEventLoop才能支持Playwright的subprocess
    # SelectorEventLoop在Windows下不支持subprocess，会导致NotImplementedError
    if sys.platform == "win32":
        asyncio.set_event_loop_policy(asyncio.WindowsProactorEventLoopPolicy())

    logger.info(f"正在启动 {APP_NAME} v{APP_VERSION}...")
    logger.info(f"服务地址: http://{HOST}:{PORT}")

    uvicorn.run(app, host=HOST, port=PORT, reload=RELOAD, log_level="info")
