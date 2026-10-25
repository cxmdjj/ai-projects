"""工具注册表: 每个工具绑定 feature.* 功能开关,关闭后不注入 tools 参数且执行时拒绝。"""

from app.tools.base import ToolContext, ToolRegistry, ToolResult, ToolSpec
from app.tools.command_exec import SPEC as COMMAND_EXEC_SPEC
from app.tools.command_exec import run_command_exec
from app.tools.db_query import SPEC as DB_QUERY_SPEC
from app.tools.db_query import run_db_query
from app.tools.file_ops import LIST_SPEC, READ_SPEC, WRITE_SPEC
from app.tools.file_ops import run_file_list, run_file_read, run_file_write
from app.tools.result_file import SPEC as RESULT_FILE_SPEC
from app.tools.result_file import run_result_file
from app.tools.text_search import SPEC as TEXT_SEARCH_SPEC
from app.tools.text_search import run_text_search

tool_registry = ToolRegistry()

tool_registry.register(
    ToolSpec(
        name="db_query",
        description=(
            "对经营数据库执行只读查询。只允许单条 SELECT/WITH 语句,"
            "可查询 scn1_* 与 scn2_* 演示业务表(字段见数据字典),返回列名与行数据(上限 1000 行)。"
        ),
        parameters=DB_QUERY_SPEC,
        feature_key="feature.db_query",
        handler=run_db_query,
        timeout=15.0,
    )
)

tool_registry.register(
    ToolSpec(
        name="file_read",
        description="读取当前会话 workspace 临时目录中的文本文件。",
        parameters=READ_SPEC,
        feature_key="feature.file_ops",
        handler=run_file_read,
        timeout=15.0,
    )
)

tool_registry.register(
    ToolSpec(
        name="file_write",
        description="向当前会话 workspace 临时目录写入文本文件(可用于保存中间计算结果)。",
        parameters=WRITE_SPEC,
        feature_key="feature.file_ops",
        handler=run_file_write,
        timeout=15.0,
    )
)

tool_registry.register(
    ToolSpec(
        name="file_list",
        description="列出当前会话 workspace 临时目录中的文件。",
        parameters=LIST_SPEC,
        feature_key="feature.file_ops",
        handler=run_file_list,
        timeout=15.0,
    )
)

tool_registry.register(
    ToolSpec(
        name="text_search",
        description=(
            "对当前会话已解析的附件内容与 workspace 临时文件进行关键词检索,"
            "返回命中文件、相关片段与得分,用于从上传资料中查找证据。"
        ),
        parameters=TEXT_SEARCH_SPEC,
        feature_key="feature.text_search",
        handler=run_text_search,
        timeout=30.0,
    )
)

tool_registry.register(
    ToolSpec(
        name="command_exec",
        description=(
            "在沙箱中执行一段 Python 程序(非 shell 命令),用于数据模拟与计算验证。"
            "程序在会话 workspace 目录下运行,禁止联网与安装包。"
        ),
        parameters=COMMAND_EXEC_SPEC,
        feature_key="feature.command_exec",
        handler=run_command_exec,
        timeout=60.0,
    )
)

tool_registry.register(
    ToolSpec(
        name="result_file",
        description=(
            "生成用户可下载的结果文件(写入导出目录),支持 markdown/html/csv/txt,"
            "返回文件路径与下载链接。"
        ),
        parameters=RESULT_FILE_SPEC,
        feature_key="feature.result_file",
        handler=run_result_file,
        timeout=30.0,
    )
)

__all__ = ["tool_registry", "ToolContext", "ToolResult", "ToolSpec"]
