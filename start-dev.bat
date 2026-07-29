@echo off
chcp 65001 >nul
title NovelAI Writer - 开发模式启动

echo ========================================
echo    NovelAI Writer - 一键启动
echo ========================================
echo.

:: 检查 Python
python --version >nul 2>&1
if %errorlevel% neq 0 (
    echo [❌] 未安装 Python，请先安装 Python 3.12+
    pause
    exit /b
)
echo [✅] Python 已安装

:: 检查 Node.js
node --version >nul 2>&1
if %errorlevel% neq 0 (
    echo [❌] 未安装 Node.js，请先安装 Node 20+
    pause
    exit /b
)
echo [✅] Node.js 已安装

:: 安装后端依赖
echo.
echo [1/4] 安装后端依赖...
cd /d "%~dp0backend"
pip install -r requirements.txt -q
echo [✅] 后端依赖安装完成

:: 安装前端依赖
echo [2/4] 安装前端依赖...
cd /d "%~dp0frontend"
if not exist "node_modules" (
    npm install --silent
)
echo [✅] 前端依赖安装完成

:: 启动后端
echo [3/4] 启动后端服务 (端口 8000)...
cd /d "%~dp0backend"
start "NovelAI-Backend" cmd /c "uvicorn app.main:app --reload --host 0.0.0.0 --port 8000"
echo [✅] 后端已启动

:: 启动前端
echo [4/4] 启动前端服务 (端口 5173)...
cd /d "%~dp0frontend"
start "NovelAI-Frontend" cmd /c "npm run dev"
echo [✅] 前端已启动

echo.
echo ========================================
echo    启动完成！
echo.
echo    前端页面: http://localhost:5173
echo    API 文档: http://localhost:8000/docs
echo    MCP 服务: python -m novel_ai_writer.backend.mcp
echo.
echo    按任意键关闭所有服务...
echo ========================================
pause >nul

:: 关闭服务
taskkill /f /fi "WINDOWTITLE eq NovelAI-Backend" >nul 2>&1
taskkill /f /fi "WINDOWTITLE eq NovelAI-Frontend" >nul 2>&1
echo [✅] 服务已关闭
