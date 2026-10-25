"""command_exec 工具: 沙箱化命令执行(默认功能开关关闭)。

- ProcessSandbox(默认,Windows 友好): 命令为完整 Python 程序文本,写入 workspace/cmd/ 下临时脚本,
  用 `python -I script.py` 执行(-I 隔离环境变量注入;禁 pip/-m;30s 超时强杀;输出截断 1MB)。
- DockerSandbox(生产推荐): docker run --rm --network none --memory 512m --cpus 1 --read-only
  -v workspace:/data python:3.11-slim python -I /data/cmd/script.py
"""

import asyncio
import json
import sys
import time

from app.core import paths
from app.core.config_manager import config_manager
from app.tools.base import ToolContext, ToolResult

TIMEOUT = 30.0
MAX_OUTPUT_CHARS = 1_000_000

SPEC = {
    "type": "object",
    "required": ["command"],
    "properties": {
        "command": {
            "type": "string",
            "description": (
                "要执行的完整 Python 程序源代码(非 shell 命令)。"
                "程序在当前会话 workspace 目录下运行,可读取/写入该目录内的临时文件,"
                "用于数据模拟、计算验证等。禁止联网、安装包、修改系统文件。"
            ),
        }
    },
}


async def run_command_exec(arguments: dict, ctx: ToolContext) -> ToolResult:
    sandbox_type = config_manager.get("sandbox.type", "process")
    code = (arguments.get("command") or "").strip()
    if not code:
        return ToolResult.fail("command 不能为空")
    if len(code) > 100_000:
        return ToolResult.fail("程序过长(上限 10 万字符)")
    for forbidden in ("import pip", "pip install", "subprocess", "os.system", "socket", "shutil.rmtree", "__import__"):
        if forbidden in code:
            return ToolResult.fail(f"程序包含被禁止的操作片段: {forbidden}")

    ws = paths.workspace_dir(ctx.user_id, ctx.conversation_id)
    cmd_dir = ws / "cmd"
    cmd_dir.mkdir(parents=True, exist_ok=True)
    script = cmd_dir / f"_exec_{int(time.time() * 1000)}.py"
    script.write_text(code, encoding="utf-8")

    if sandbox_type == "docker":
        return await _run_docker(script, cmd_dir)
    return await _run_process(script, cmd_dir)


async def _run_process(script, cmd_dir) -> ToolResult:
    try:
        proc = await asyncio.create_subprocess_exec(
            sys.executable,
            "-I",
            str(script.name),
            cwd=str(cmd_dir),
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
        )
        try:
            stdout_b, stderr_b = await asyncio.wait_for(proc.communicate(), timeout=TIMEOUT)
        except asyncio.TimeoutError:
            proc.kill()
            await proc.wait()
            return ToolResult.fail(f"程序执行超时(>{TIMEOUT:.0f}s)已终止")
        stdout = stdout_b.decode("utf-8", errors="ignore")[:MAX_OUTPUT_CHARS]
        stderr = stderr_b.decode("utf-8", errors="ignore")[:MAX_OUTPUT_CHARS]
        return ToolResult.success(
            json.dumps(
                {"exit_code": proc.returncode, "stdout": stdout, "stderr": stderr, "script_file": script.name},
                ensure_ascii=False,
            ),
            f"command_exec 退出码 {proc.returncode}",
        )
    except FileNotFoundError:
        return ToolResult.fail("未找到 Python 解释器")


async def _run_docker(script, cmd_dir) -> ToolResult:
    try:
        proc = await asyncio.create_subprocess_exec(
            "docker",
            "run",
            "--rm",
            "--network",
            "none",
            "--memory",
            "512m",
            "--cpus",
            "1",
            "--read-only",
            "-v",
            f"{cmd_dir}:/data/cmd:rw",
            "python:3.11-slim",
            "python",
            "-I",
            f"/data/cmd/{script.name}",
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
        )
        try:
            stdout_b, stderr_b = await asyncio.wait_for(proc.communicate(), timeout=TIMEOUT + 15)
        except asyncio.TimeoutError:
            proc.kill()
            await proc.wait()
            return ToolResult.fail(f"容器执行超时(>{TIMEOUT:.0f}s)已终止")
        stdout = stdout_b.decode("utf-8", errors="ignore")[:MAX_OUTPUT_CHARS]
        stderr = stderr_b.decode("utf-8", errors="ignore")[:MAX_OUTPUT_CHARS]
        return ToolResult.success(
            json.dumps(
                {"exit_code": proc.returncode, "stdout": stdout, "stderr": stderr, "sandbox": "docker"},
                ensure_ascii=False,
            ),
            f"command_exec(docker) 退出码 {proc.returncode}",
        )
    except FileNotFoundError:
        return ToolResult.fail("未找到 docker,请安装或切换 sandbox.type=process")
