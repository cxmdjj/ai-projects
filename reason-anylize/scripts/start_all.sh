#!/usr/bin/env bash
# 一键启动三服务: 认证中心(8001) → 后端(8000) → 前端(5173)
set -e
PROJ="$(cd "$(dirname "$0")/.." && pwd)"

echo "==> 1/4 生成演示数据(幂等,可跳过)"
(cd "$PROJ" && uv run --project backend python scripts/seed_data.py)
(cd "$PROJ" && uv run --project backend python scripts/demo_assets_generator.py)

echo "==> 2/4 启动认证中心 http://localhost:8001"
(cd "$PROJ/auth-service" && uv run python run.py) &

echo "==> 3/4 启动后端 http://localhost:8000 (接口文档 /docs)"
(cd "$PROJ/backend" && uv run python run.py) &

echo "==> 4/4 启动前端 http://localhost:5173"
(cd "$PROJ/frontend" && npm run dev) &

echo "全部启动完成。浏览器访问 http://localhost:5173 (测试账号: analyst1/analyst123, 管理员: admin1/admin123)"
wait
