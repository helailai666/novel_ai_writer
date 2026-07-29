#!/bin/bash
echo "========================================"
echo "  NovelAI Writer - 一键启动"
echo "========================================"

# 检查依赖
command -v python3 >/dev/null 2>&1 || { echo "❌ 需要 Python 3.12+"; exit 1; }
command -v node >/dev/null 2>&1 || { echo "❌ 需要 Node.js 20+"; exit 1; }
echo "✅ 依赖检查通过"

# 安装依赖
echo "[1/3] 安装后端依赖..."
cd "$(dirname "$0")/backend" && pip install -r requirements.txt -q
echo "✅ 后端依赖就绪"

echo "[2/3] 安装前端依赖..."
cd "$(dirname "$0")/frontend"
[ ! -d "node_modules" ] && npm install --silent
echo "✅ 前端依赖就绪"

# 启动服务
echo "[3/3] 启动服务..."
cd "$(dirname "$0")/backend" && uvicorn app.main:app --reload --host 0.0.0.0 --port 8000 &
BACKEND_PID=$!
cd "$(dirname "$0")/frontend" && npm run dev &
FRONTEND_PID=$!

echo ""
echo "========================================"
echo "  启动完成！"
echo "  前端: http://localhost:5173"
echo "  API:  http://localhost:8000/docs"
echo "  PID:  后端=$BACKEND_PID 前端=$FRONTEND_PID"
echo "  关闭: kill $BACKEND_PID $FRONTEND_PID"
echo "========================================"
wait
