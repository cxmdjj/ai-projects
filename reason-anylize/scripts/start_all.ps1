# 一键启动三服务: 认证中心(8001) → 后端(8000) → 前端(5173)
$proj = Split-Path -Parent $PSScriptRoot

Write-Host "==> 1/4 生成演示数据(幂等,可跳过)" -ForegroundColor Cyan
uv run --project backend python scripts/seed_data.py
uv run --project backend python scripts/demo_assets_generator.py

Write-Host "==> 2/4 启动认证中心 http://localhost:8001" -ForegroundColor Cyan
Start-Process powershell -ArgumentList "-NoExit", "-Command", "Set-Location '$proj\auth-service'; uv run python run.py"

Write-Host "==> 3/4 启动后端 http://localhost:8000 (接口文档 /docs)" -ForegroundColor Cyan
Start-Process powershell -ArgumentList "-NoExit", "-Command", "Set-Location '$proj\backend'; uv run python run.py"

Write-Host "==> 4/4 启动前端 http://localhost:5173" -ForegroundColor Cyan
Start-Process powershell -ArgumentList "-NoExit", "-Command", "Set-Location '$proj\frontend'; npm run dev"

Write-Host "全部启动完成。浏览器访问 http://localhost:5173 (测试账号: analyst1/analyst123, 管理员: admin1/admin123)" -ForegroundColor Green
