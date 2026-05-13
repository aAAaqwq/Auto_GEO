# AutoGeo Frontend Dockerfile (v3.2.0)
# 多阶段构建：构建静态文件 + Nginx 服务

# ============================================
# Stage 1: Builder - 构建静态文件
# ============================================
FROM node:20-alpine AS builder

# 构建参数
ARG BUILD_DATE
ARG VCS_REF
ARG VERSION=3.2.0

# 设置标签
LABEL maintainer="AutoGeo Team" \
      org.opencontainers.image.title="AutoGeo Frontend" \
      org.opencontainers.image.description="Vue 3 + Vite Frontend" \
      org.opencontainers.image.version="${VERSION}" \
      org.opencontainers.image.created="${BUILD_DATE}" \
      org.opencontainers.image.revision="${VCS_REF}"

# 设置工作目录
WORKDIR /app

# 安装依赖（利用层缓存）
COPY package*.json ./
RUN npm ci --only=production=false

# 复制源代码
COPY . .

# 构建（构建时会读取 .env.production）
ARG VITE_API_BASE_URL
ARG VITE_WS_URL
ARG VITE_STATIC_URL
ARG VITE_ENABLE_MOCK
ARG VITE_APP_TITLE

ENV VITE_API_BASE_URL=${VITE_API_BASE_URL}
ENV VITE_WS_URL=${VITE_WS_URL}
ENV VITE_STATIC_URL=${VITE_STATIC_URL}
ENV VITE_ENABLE_MOCK=${VITE_ENABLE_MOCK:-false}
ENV VITE_APP_TITLE=${VITE_APP_TITLE:-AutoGeo}

RUN npm run build:renderer

# ============================================
# Stage 2: Nginx - 生产服务器
# ============================================
FROM nginx:alpine

# 构建参数
ARG BUILD_DATE
ARG VCS_REF
ARG VERSION=3.2.0

LABEL maintainer="AutoGeo Team" \
      org.opencontainers.image.title="AutoGeo Frontend" \
      org.opencontainers.image.description="Vue 3 + Vite Frontend served by Nginx" \
      org.opencontainers.image.version="${VERSION}" \
      org.opencontainers.image.created="${BUILD_DATE}" \
      org.opencontainers.image.revision="${VCS_REF}"

# 安装安全更新
RUN apk update && apk upgrade && rm -rf /var/cache/apk/*

# 创建 nginx 运行用户（安全最佳实践）
RUN adduser -D -u 1000 -s /bin/sh nginxuser || true

# 复制自定义 nginx 配置
COPY nginx.conf /etc/nginx/conf.d/default.conf

# 从 builder 复制构建产物
COPY --from=builder /app/out/renderer /usr/share/nginx/html

# 设置权限
RUN chown -R nginx:nginx /usr/share/nginx/html && \
    chown -R nginx:nginx /var/cache/nginx && \
    chown -R nginx:nginx /var/log/nginx && \
    chown -R nginx:nginx /etc/nginx/conf.d && \
    touch /var/run/nginx.pid && \
    chown -R nginx:nginx /var/run/nginx.pid

# 切换到非 root 用户
USER nginx

# 暴露端口
EXPOSE 80

# 健康检查
HEALTHCHECK --interval=30s --timeout=5s --start-period=5s --retries=3 \
    CMD wget -q --spider http://localhost/ || exit 1

# 启动 nginx
CMD ["nginx", "-g", "daemon off;"]
