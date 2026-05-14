# AutoGeo Backend Dockerfile (优化版 v3.3)
# 多阶段构建 + 安全优化 + 生产就绪

# ============================================
# Stage 1: Builder - 构建依赖
# ============================================
FROM python:3.12-slim AS builder

# 构建参数
ARG BUILD_DATE
ARG VCS_REF
ARG VERSION=3.2.0

# 设置标签
LABEL maintainer="AutoGeo Team" \
      org.opencontainers.image.title="AutoGeo Backend" \
      org.opencontainers.image.description="FastAPI backend with Playwright" \
      org.opencontainers.image.version="${VERSION}" \
      org.opencontainers.image.created="${BUILD_DATE}" \
      org.opencontainers.image.revision="${VCS_REF}"

# 设置环境变量
ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    PIP_NO_CACHE_DIR=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1 \
    PLAYWRIGHT_BROWSERS_PATH=/ms-playwright

# 安装构建依赖和 Playwright 系统库（合并安装，避免重复）
RUN apt-get update && apt-get install -y --no-install-recommends \
    # 基础工具
    curl \
    ca-certificates \
    wget \
    gnupg \
    # Playwright 运行时依赖
    libnss3 \
    libnspr4 \
    libatk1.0-0 \
    libatk-bridge2.0-0 \
    libcups2 \
    libdrm2 \
    libxkbcommon0 \
    libxcomposite1 \
    libxdamage1 \
    libxfixes3 \
    libxrandr2 \
    libgbm1 \
    libasound2 \
    libpangocairo-1.0-0 \
    libpango-1.0-0 \
    libxshmfence1 \
    libatspi2.0-0 \
    # 字体支持（中文）
    fonts-wqy-microhei \
    fonts-freefont-ttf \
    && rm -rf /var/lib/apt/lists/* \
    && apt-get clean

# 创建虚拟环境
RUN python -m venv /opt/venv
ENV PATH="/opt/venv/bin:$PATH"

# 复制并安装依赖（利用层缓存）
COPY requirements.txt /tmp/
RUN pip install --no-cache-dir --upgrade pip setuptools wheel && \
    pip install --no-cache-dir -r /tmp/requirements.txt && \
    rm /tmp/requirements.txt

# 安装 Playwright 浏览器
RUN playwright install chromium

# ============================================
# Stage 2: Runtime - 生产运行时
# ============================================
FROM python:3.12-slim

# 获取构建参数
ARG BUILD_DATE
ARG VCS_REF
ARG VERSION=3.2.0

# 设置标签（继承自 builder）
LABEL maintainer="AutoGeo Team" \
      org.opencontainers.image.title="AutoGeo Backend" \
      org.opencontainers.image.description="FastAPI backend with Playwright" \
      org.opencontainers.image.version="${VERSION}" \
      org.opencontainers.image.created="${BUILD_DATE}" \
      org.opencontainers.image.revision="${VCS_REF}"

# 设置环境变量
ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    PIP_NO_CACHE_DIR=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1 \
    PLAYWRIGHT_BROWSERS_PATH=/ms-playwright \
    PYTHONPATH="/app"

# 安装运行时依赖（不需要 build-essential）
RUN apt-get update && apt-get install -y --no-install-recommends \
    curl \
    ca-certificates \
    # Playwright 运行时依赖
    libnss3 \
    libnspr4 \
    libatk1.0-0 \
    libatk-bridge2.0-0 \
    libcups2 \
    libdrm2 \
    libxkbcommon0 \
    libxcomposite1 \
    libxdamage1 \
    libxfixes3 \
    libxrandr2 \
    libgbm1 \
    libasound2 \
    libpangocairo-1.0-0 \
    libpango-1.0-0 \
    libxshmfence1 \
    libatspi2.0-0 \
    # 字体支持
    fonts-wqy-microhei \
    fonts-freefont-ttf \
    && rm -rf /var/lib/apt/lists/* \
    && apt-get clean

# 创建应用用户（安全最佳实践）
RUN useradd -m -u 1000 -s /bin/bash autogeo && \
    mkdir -p /app/data /app/logs /app/database /app/.cookies /app/backend/static && \
    chown -R autogeo:autogeo /app

# 从 builder 复制虚拟环境和 Playwright
COPY --from=builder /opt/venv /opt/venv
COPY --from=builder /ms-playwright /ms-playwright
ENV PATH="/opt/venv/bin:$PATH"

# 复制应用代码
RUN mkdir -p /app/backend
COPY --chown=autogeo:autogeo . /app/backend/

# 设置PYTHONPATH和工作目录
ENV PYTHONPATH="/app"
WORKDIR /app

# 生产环境变量（敏感信息通过外部环境变量注入，不硬编码）
ENV ENVIRONMENT=production \
    HOST=0.0.0.0 \
    PORT=8001 \
    PYTHONUNBUFFERED=1 \
    # 以下变量必须由外部环境提供，这里仅作为文档说明
    N8N_WEBHOOK_URL="" \
    RAGFLOW_BASE_URL="" \
    DATABASE_URL="" \
    AUTO_GEO_ENCRYPTION_KEY=""

# 切换到非 root 用户（安全最佳实践）
USER autogeo

# 暴露端口
EXPOSE 8001

# 健康检查
HEALTHCHECK --interval=15s --timeout=10s --start-period=40s --retries=3 \
    CMD curl -f http://localhost:8001/api/health || exit 1

# 使用 -m 参数以模块方式运行
CMD ["python", "-m", "backend.main"]
