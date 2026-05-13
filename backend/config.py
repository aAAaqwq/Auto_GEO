# -*- coding: utf-8 -*-
"""
auto_geo 后端配置
虽然暴躁，但配置必须清晰！
"""

import os
from pathlib import Path
from typing import Literal
from dotenv import load_dotenv

# ==================== 项目路径 ====================
BASE_DIR = Path(__file__).resolve().parent.parent

# 加载环境变量
load_dotenv(BASE_DIR / ".env")
DATA_DIR = BASE_DIR / ".cookies"

# 数据库目录需要和代码目录分离，否则 Docker 挂载会覆盖代码！
# 本地开发: backend/database/
# Docker 环境: /app/database/ (独立目录，不覆盖代码)
_DOCKER_DB_DIR = Path("/app/database")
if _DOCKER_DB_DIR.exists() or os.getenv("ENVIRONMENT") == "production":
    # Docker 环境：使用独立的数据目录
    DATABASE_DIR = _DOCKER_DB_DIR
else:
    # 本地开发环境：使用 backend/database
    DATABASE_DIR = BASE_DIR / "backend" / "database"

# 确保目录存在
DATA_DIR.mkdir(exist_ok=True)
DATABASE_DIR.mkdir(exist_ok=True)

# ==================== 应用配置 ====================
APP_NAME = "AutoGeo Backend"
APP_VERSION = "2.0.0"
DEBUG = True

# ==================== 服务配置 ====================
# 生产环境用0.0.0.0监听所有IP，Docker外部才能访问！
HOST = os.getenv("HOST", "0.0.0.0")
PORT = int(os.getenv("PORT", "8001"))  # 修改的：避开8000端口的Windows残留占用问题
RELOAD = False  # 修复：Windows 上 Playwright 需要 ProactorEventLoop，与 reload 模式冲突！

# CORS配置
# 添加生产服务器IP，否则前端会跨域报错！
_CORS_ORIGINS = os.getenv("CORS_ORIGINS", "")
CORS_ORIGINS = [
    "http://localhost:5179",
    "http://localhost:5173",
    "http://127.0.0.1:5173",
    "capacitor://localhost",
    "http://localhost",
    # 生产服务器（主）
    "http://8.138.59.152:5173",
    "http://8.138.59.152:8001",
    "http://8.138.59.152",
    # 生产服务器（备）
    "http://8.163.39.114",
    "http://8.163.39.114:5173",
    "http://8.163.39.114:8001",
]
# 从环境变量追加额外的CORS源
if _CORS_ORIGINS:
    CORS_ORIGINS.extend([origin.strip() for origin in _CORS_ORIGINS.split(",")])

# ==================== 数据库配置 ====================
# 数据库URL支持多种格式：
# - SQLite: sqlite:///./auto_geo.db
# - PostgreSQL: postgresql://user:password@localhost:5432/auto_geo
# - PostgreSQL with pool: postgresql+psycopg2://user:password@host:5432/db?pool_size=20
DATABASE_URL = os.getenv("DATABASE_URL", f"sqlite:///{DATABASE_DIR}/auto_geo_v3.db")

# 数据库连接池配置 (仅PostgreSQL有效)
DB_POOL_SIZE = int(os.getenv("DB_POOL_SIZE", "10"))
DB_MAX_OVERFLOW = int(os.getenv("DB_MAX_OVERFLOW", "20"))
DB_POOL_TIMEOUT = int(os.getenv("DB_POOL_TIMEOUT", "30"))
DB_POOL_RECYCLE = int(os.getenv("DB_POOL_RECYCLE", "3600"))

# 数据库类型检测
def get_database_type():
    """检测数据库类型"""
    if "postgresql" in DATABASE_URL.lower():
        return "postgresql"
    return "sqlite"

# ==================== 加密配置 ====================
# AES-256加密密钥（32字节）- 生产环境必须从环境变量读取
_encryption_key = os.getenv("AUTO_GEO_ENCRYPTION_KEY")
if not _encryption_key:
    raise ValueError(
        "AUTO_GEO_ENCRYPTION_KEY environment variable is required. "
        "Please set a 32-byte encryption key."
    )
ENCRYPTION_KEY = _encryption_key.encode()[:32]  # 确保是32字节

# ==================== Playwright配置 ====================
# 部署模式：local(本地), cloud(云端), hybrid(混合)
DEPLOYMENT_MODE: Literal["local", "cloud", "hybrid"] = os.getenv(
    "DEPLOYMENT_MODE",
    "local",  # 默认本地模式
)

# 是否启用headless模式（可通过环境变量覆盖）
HEADLESS_MODE = os.getenv("HEADLESS_MODE", "false").lower() == "true"

# 本地浏览器CDP端口（用于混合架构）
LOCAL_BROWSER_CDP_PORT = int(os.getenv("LOCAL_BROWSER_CDP_PORT", "9222"))

# 本地浏览器公网地址（通过内网穿透暴露）
# 格式: http://xxxxx.xxx.io 或 http://IP:PORT
LOCAL_BROWSER_URL = os.getenv("LOCAL_BROWSER_URL", "")

# 是否强制使用本地浏览器（通过CDP连接）
FORCE_LOCAL_BROWSER = os.getenv("FORCE_LOCAL_BROWSER", "false").lower() == "true"

# 浏览器类型
BROWSER_TYPE: Literal["chromium", "firefox", "webkit"] = "chromium"

# 浏览器启动参数
BROWSER_ARGS = [
    "--no-sandbox",
    "--disable-setuid-sandbox",
    "--disable-blink-features=AutomationControlled",
    "--disable-infobars",
    "--window-size=1920,1080",
    "--disable-gpu",  # [新增] 兼容 macOS 和部分 Windows 环境
    "--disable-dev-shm-usage",  # [新增] 避免容器环境内存不足
]

# 默认 User-Agent (保持统一，防止 Session 因 UA 不一致失效)
DEFAULT_USER_AGENT = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36"
)

# 用户数据目录
USER_DATA_DIR = DATA_DIR / "browser_context"

# 登录检测配置
LOGIN_CHECK_INTERVAL = 1000  # 毫秒
LOGIN_MAX_WAIT_TIME = 120000  # 2分钟

# ==================== 平台配置 ====================
PLATFORMS = {
    "zhihu": {
        "id": "zhihu",
        "name": "知乎",
        "code": "ZH",
        "login_url": "https://www.zhihu.com/signin",
        "publish_url": "https://zhuanlan.zhihu.com/write",
        "color": "#0084FF",
    },
    "baijiahao": {
        "id": "baijiahao",
        "name": "百家号",
        "code": "BJH",
        "login_url": "https://baijiahao.baidu.com/builder/rc/static/login/index",
        "home_url": "https://baijiahao.baidu.com/builder/rc/static/edit/index",  # 百家号首页（作者中心）
        "publish_url": "https://baijiahao.baidu.com/builder/rc/edit/index",  # 编辑器首页
        "color": "#E53935",
    },
    "sohu": {
        "id": "sohu",
        "name": "搜狐号",
        "code": "SOHU",
        "login_url": "https://mp.sohu.com/",
        "publish_url": "https://mp.sohu.com/upload/article",
        "color": "#FF6B00",
    },
    "toutiao": {
        "id": "toutiao",
        "name": "头条号",
        "code": "TT",
        "login_url": "https://mp.toutiao.com/",
        "publish_url": "https://mp.toutiao.com/profile_v4/graphic/publish",
        "color": "#333333",
    },
    "wenku": {
        "id": "wenku",
        "name": "百度文库",
        "code": "WK",
        "login_url": "https://passport.baidu.com/v2/?login&tpl=wenku",
        "publish_url": "https://wenku.baidu.com/user/upload",
        "color": "#2932E1",
    },
    "penguin": {
        "id": "penguin",
        "name": "企鹅号",
        "code": "OM",
        "login_url": "https://om.qq.com/userAuth/index",
        "publish_url": "https://om.qq.com/article/articlePublish",
        "color": "#1E8AE8",
    },
    "weixin": {
        "id": "weixin",
        "name": "微信公众号",
        "code": "WX",
        "login_url": "https://mp.weixin.qq.com/",
        "publish_url": "https://mp.weixin.qq.com/cgi-bin/appmsg?t=media/appmsg_edit",
        "color": "#07C160",
    },
    "wangyi": {
        "id": "wangyi",
        "name": "网易号",
        "code": "WY",
        "login_url": "https://mp.163.com/login.html",
        "publish_url": "https://mp.163.com/admin/article/publish",
        "color": "#E60026",
    },
    "zijie": {
        "id": "zijie",
        "name": "字节号",
        "code": "ZJ",
        "login_url": "https://mp.toutiao.com/",
        "publish_url": "https://mp.toutiao.com/profile/article/article_edit",
        "color": "#FA2A2D",
    },
    "xiaohongshu": {
        "id": "xiaohongshu",
        "name": "小红书",
        "code": "XHS",
        "login_url": "https://creator.xiaohongshu.com/login",
        "publish_url": "https://creator.xiaohongshu.com/publish/publish",
        "color": "#FF2442",
    },
    "bilibili": {
        "id": "bilibili",
        "name": "B站专栏",
        "code": "BL",
        "login_url": "https://passport.bilibili.com/login",
        "publish_url": "https://member.bilibili.com/article/post_text",
        "color": "#FB7299",
    },
    "36kr": {
        "id": "36kr",
        "name": "36氪",
        "code": "36KR",
        "login_url": "https://passport.36kr.com/mo/signin",
        "publish_url": "https://36kr.com/publish",
        "color": "#FF6A00",
    },
    "huxiu": {
        "id": "huxiu",
        "name": "虎嗅",
        "code": "HX",
        "login_url": "https://www.huxiu.com/passport/login",
        "publish_url": "https://www.huxiu.com/article/post",
        "color": "#FF9C41",
    },
    "woshipm": {
        "id": "woshipm",
        "name": "人人都是产品经理",
        "code": "PM",
        "login_url": "https://passport.woshipm.com/login",
        "publish_url": "https://www.woshipm.com/article/post",
        "color": "#2ECC71",
    },
    # 新增平台
    "douyin": {
        "id": "douyin",
        "name": "抖音",
        "code": "DY",
        "login_url": "https://www.douyin.com/",
        "publish_url": "https://creator.douyin.com/",
        "color": "#000000",
    },
    "kuaishou": {
        "id": "kuaishou",
        "name": "快手",
        "code": "KS",
        "login_url": "https://cp.kuaishou.com/",
        "publish_url": "https://cp.kuaishou.com/article/publish",
        "color": "#FF4500",
    },
    "video_account": {
        "id": "video_account",
        "name": "视频号",
        "code": "WXV",
        "login_url": "https://channels.weixin.qq.com/",
        "publish_url": "https://channels.weixin.qq.com/post",
        "color": "#07C160",
    },
    "sohu_video": {
        "id": "sohu_video",
        "name": "搜狐视频",
        "code": "SHV",
        "login_url": "https://tv.sohu.com/",
        "publish_url": "https://tv.sohu.com/upload",
        "color": "#FF6B00",
    },
    "weibo": {
        "id": "weibo",
        "name": "新浪微博",
        "code": "WB",
        "login_url": "https://weibo.com/",
        "publish_url": "https://weibo.com/compose",
        "color": "#E6162D",
    },
    "haokan": {
        "id": "haokan",
        "name": "好看视频",
        "code": "HK",
        "login_url": "https://haokan.baidu.com/",
        "publish_url": "https://haokan.baidu.com/upload",
        "color": "#2932E1",
    },
    "xigua": {
        "id": "xigua",
        "name": "西瓜视频",
        "code": "XG",
        "login_url": "https://ixigua.com/",
        "publish_url": "https://ixigua.com/publish",
        "color": "#FA2A2D",
    },
    "jianshu": {
        "id": "jianshu",
        "name": "简书号",
        "code": "JS",
        "login_url": "https://www.jianshu.com/sign_in",
        "publish_url": "https://www.jianshu.com/writer",
        "color": "#EA6F5A",
    },
    "iqiyi": {
        "id": "iqiyi",
        "name": "爱奇艺",
        "code": "IQY",
        "login_url": "https://www.iqiyi.com/",
        "publish_url": "https://mp.iqiyi.com/upload",
        "color": "#00BE06",
    },
    "dayu": {
        "id": "dayu",
        "name": "大鱼号",
        "code": "DYU",
        "login_url": "https://mp.dayu.com/",
        "publish_url": "https://mp.dayu.com/article/post",
        "color": "#FF6A00",
    },
    "acfun": {
        "id": "acfun",
        "name": "AcFun",
        "code": "AC",
        "login_url": "https://www.acfun.cn/login",
        "publish_url": "https://member.acfun.cn/article/publish",
        "color": "#FD4C5D",
    },
    "tencent_video": {
        "id": "tencent_video",
        "name": "腾讯视频",
        "code": "TXV",
        "login_url": "https://v.qq.com/",
        "publish_url": "https://upload.video.qq.com/",
        "color": "#FF6B00",
    },
    "yidian": {
        "id": "yidian",
        "name": "一点号",
        "code": "YD",
        "login_url": "https://mp.yidianzixun.com/",
        "publish_url": "https://mp.yidianzixun.com/publish",
        "color": "#007AFF",
    },
    "pipixia": {
        "id": "pipixia",
        "name": "皮皮虾",
        "code": "PPX",
        "login_url": "https://www.pipixia.com/",
        "publish_url": "https://www.pipixia.com/publish",
        "color": "#FF6900",
    },
    "meipai": {
        "id": "meipai",
        "name": "美拍",
        "code": "MP",
        "login_url": "https://www.meipai.com/",
        "publish_url": "https://www.meipai.com/publish",
        "color": "#1E88E5",
    },
    "douban": {
        "id": "douban",
        "name": "豆瓣",
        "code": "DB",
        "login_url": "https://www.douban.com/",
        "publish_url": "https://www.douban.com/note",
        "color": "#007722",
    },
    "kuai_chuan": {
        "id": "kuai_chuan",
        "name": "快传号",
        "code": "KC",
        "login_url": "https://kuai.360.cn/",
        "publish_url": "https://kuai.360.cn/publish",
        "color": "#00BE3B",
    },
    "dafeng": {
        "id": "dafeng",
        "name": "大风号",
        "code": "DF",
        "login_url": "https://mp.ifeng.com/",
        "publish_url": "https://mp.ifeng.com/article/post",
        "color": "#DD2E1B",
    },
    "xueqiu": {
        "id": "xueqiu",
        "name": "雪球号",
        "code": "XQ",
        "login_url": "https://xueqiu.com/",
        "publish_url": "https://xueqiu.com/post",
        "color": "#2775CA",
    },
    "yiche": {
        "id": "yiche",
        "name": "易车号",
        "code": "YC",
        "login_url": "https://mp.yiche.com/",
        "publish_url": "https://mp.yiche.com/article/post",
        "color": "#FF6600",
    },
    "chejia": {
        "id": "chejia",
        "name": "车家号",
        "code": "CJ",
        "login_url": "https://mp.autohome.com.cn/",
        "publish_url": "https://mp.autohome.com.cn/article/post",
        "color": "#E60012",
    },
    "duoduo": {
        "id": "duoduo",
        "name": "多多视频",
        "code": "DD",
        "login_url": "https://mp.pinduoduo.com/",
        "publish_url": "https://mp.pinduoduo.com/publish",
        "color": "#E02E24",
    },
    "weishi": {
        "id": "weishi",
        "name": "腾讯微视",
        "code": "WS",
        "login_url": "https://weishi.qq.com/",
        "publish_url": "https://weishi.qq.com/publish",
        "color": "#FF6B00",
    },
    "mango": {
        "id": "mango",
        "name": "芒果TV",
        "code": "MG",
        "login_url": "https://www.mgtv.com/",
        "publish_url": "https://www.mgtv.com/upload",
        "color": "#FF7F00",
    },
    "ximalaya": {
        "id": "ximalaya",
        "name": "喜马拉雅",
        "code": "XMLY",
        "login_url": "https://www.ximalaya.com/",
        "publish_url": "https://www.ximalaya.com/upload",
        "color": "#F84438",
    },
    "meituan": {
        "id": "meituan",
        "name": "美团",
        "code": "MT",
        "login_url": "https://meituan.com/",
        "publish_url": "https://meituan.com/publish",
        "color": "#FFBC00",
    },
    "alipay": {
        "id": "alipay",
        "name": "支付宝",
        "code": "ZFB",
        "login_url": "https://open.alipay.com/",
        "publish_url": "https://open.alipay.com/publish",
        "color": "#1677FF",
    },
    "douyin_company": {
        "id": "douyin_company",
        "name": "抖音企业号",
        "code": "DYC",
        "login_url": "https://business.douyin.com/",
        "publish_url": "https://business.douyin.com/publish",
        "color": "#000000",
    },
    "douyin_company_lead": {
        "id": "douyin_company_lead",
        "name": "抖音企业号（线索版）",
        "code": "DYL",
        "login_url": "https://business.douyin.com/",
        "publish_url": "https://business.douyin.com/publish",
        "color": "#000000",
    },
    "custom": {
        "id": "custom",
        "name": "自定义",
        "code": "CUSTOM",
        "login_url": "",
        "publish_url": "",
        "color": "#999999",
    },
}

# ==================== 日志配置 ====================
LOG_DIR = BASE_DIR / "logs"
LOG_FILE = LOG_DIR / "auto_geo.log"
LOG_ROTATION = "100 MB"
LOG_RETENTION = "30 days"

LOG_DIR.mkdir(exist_ok=True)

# ==================== 任务配置 ====================
# 发布任务超时时间（秒）
PUBLISH_TIMEOUT = 300

# 最大并发发布数
MAX_CONCURRENT_PUBLISH = 3

# 失败重试次数
MAX_RETRY_COUNT = 2

# 重试间隔（秒）
RETRY_INTERVAL = 5

# ==================== n8n配置 ====================
# n8n webhook基础URL
N8N_WEBHOOK_URL = os.getenv("N8N_WEBHOOK_URL", "http://localhost:5678/webhook")
# n8n工作流超时时间（秒）
N8N_TIMEOUT = 300
# n8n回调URL（用于异步接收生成结果）
N8N_CALLBACK_URL = os.getenv("N8N_CALLBACK_URL", f"http://{HOST}:{PORT}/api/geo/callback")
# DeepSeek API配置
DEEPSEEK_API_KEY = os.getenv("DEEPSEEK_API_KEY", "")
DEEPSEEK_API_URL = os.getenv("DEEPSEEK_API_URL", "https://api.deepseek.com/v1")

# ==================== RAGFlow 配置 ====================
# RAGFlow 服务地址
RAGFLOW_BASE_URL = os.getenv("RAGFLOW_BASE_URL", "https://ragflow.xinzhixietong.com")
# RAGFlow API Key - 生产环境必须从环境变量读取
RAGFLOW_API_KEY = os.getenv("RAGFLOW_API_KEY")
if not RAGFLOW_API_KEY:
    raise ValueError(
        "RAGFLOW_API_KEY environment variable is required. "
        "Please set your RAGFlow API key."
    )
# RAGFlow 知识库ID（用于存储采集的文章）
RAGFLOW_DATASET_ID = os.getenv("RAGFLOW_DATASET_ID", "dff2935cfc2011f0b36f0e3309b7ec55")
# RAGFlow 知识库名称（自动创建时使用）
RAGFLOW_DATASET_NAME = os.getenv("RAGFLOW_DATASET_NAME", "reference_articles_kb")
# 去重相似度阈值
RAGFLOW_DUPLICATE_THRESHOLD = float(os.getenv("RAGFLOW_DUPLICATE_THRESHOLD", "0.85"))
# 检索返回数量
RAGFLOW_TOP_K = int(os.getenv("RAGFLOW_TOP_K", "50"))
# 检索相似度阈值
RAGFLOW_SIMILARITY_THRESHOLD = float(os.getenv("RAGFLOW_SIMILARITY_THRESHOLD", "0.7"))
# 同步策略：local_to_ragflow, ragflow_to_local, bidirectional
RAGFLOW_SYNC_STRATEGY = os.getenv("RAGFLOW_SYNC_STRATEGY", "local_to_ragflow")

# ==================== AI平台检测配置 ====================
# 收录检测的AI平台列表
AI_PLATFORMS = {
    "doubao": {
        "id": "doubao",
        "name": "豆包",
        "url": "https://www.doubao.com",
        "color": "#0066FF",
    },
    "qianwen": {
        "id": "qianwen",
        "name": "通义千问",
        "url": "https://qianwen.com/?source=tongyiqw",
        "color": "#FF6A00",
    },
    "deepseek": {
        "id": "deepseek",
        "name": "DeepSeek",
        "url": "https://chat.deepseek.com",
        "color": "#4D6BFE",
    },
}

# 收录检测定时任务配置
INDEX_CHECK_HOUR = 2  # 每天凌晨2点执行
INDEX_CHECK_MINUTE = 0
