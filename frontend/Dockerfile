# ── NovelAI Writer Frontend ────────────────────────────────────
# 阶段 1：Node 构建
FROM node:20-alpine AS builder

WORKDIR /app

# 利用缓存层：先装依赖
COPY package.json package-lock.json ./
RUN npm ci --legacy-peer-deps

# 复制源码并构建
COPY . .
RUN npm run build

# ── 阶段 2：Nginx 静态服务 ────────────────────────────────────
FROM nginx:1.27-alpine

# 复制构建产物
COPY --from=builder /app/dist /usr/share/nginx/html

# 复制 nginx 配置
COPY nginx.conf /etc/nginx/conf.d/default.conf

# 健康检查
HEALTHCHECK --interval=30s --timeout=5s --start-period=10s --retries=3 \
    CMD wget -q --spider http://localhost:80/ || exit 1

EXPOSE 80

CMD ["nginx", "-g", "daemon off;"]
