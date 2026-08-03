#!/bin/bash
# 服务器配件资产管理系统 — 一键启动开发服务（后端 8000 + 前端 5173）
# 用法：Finder 中双击本文件，或终端执行 bash 启动开发服务.command
cd "$(dirname "$0")"

echo "==> 检查后端 (8000)..."
if lsof -nP -iTCP:8000 -sTCP:LISTEN >/dev/null 2>&1; then
  echo "    后端已在运行，跳过"
else
  echo "    启动后端 uvicorn..."
  cd backend
  nohup ./.venv/bin/python -m uvicorn app.main:app --reload --reload-dir app --port 8000 \
    > /tmp/uvicorn_parts.log 2>&1 &
  cd ..
fi

echo "==> 检查前端 (5173)..."
if lsof -nP -iTCP:5173 -sTCP:LISTEN >/dev/null 2>&1; then
  echo "    前端已在运行，跳过"
else
  echo "    启动前端 vite..."
  cd frontend
  nohup npm run dev > /tmp/vite_parts.log 2>&1 &
  cd ..
fi

sleep 3
echo "==> 健康检查："
curl -s -m 3 http://127.0.0.1:8000/api/health && echo "  (后端 OK)" || echo "后端未就绪，看日志 /tmp/uvicorn_parts.log"
curl -s -m 3 -o /dev/null -w "前端 HTTP %{http_code}\n" http://127.0.0.1:5173/ || echo "前端未就绪，看日志 /tmp/vite_parts.log"
echo ""
echo "打开浏览器访问：http://localhost:5173  （账号 admin / 密码 123456）"
