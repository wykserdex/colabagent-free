from code_agent.tools.filesystem.list_files import ListFilesTool
from code_agent.tools.filesystem.read_file import ReadFileTool
from code_agent.tools.filesystem.write_file import WriteFileTool
from code_agent.tools.code.run_script import RunScriptTool
from code_agent.tools.code.apply_patch import ApplyPatchTool
from code_agent.tools.tests.run_tests import RunTestsTool
from code_agent.tools.git.status import GitStatusTool
from code_agent.tools.git.diff import GitDiffTool
from code_agent.tools.registry import ToolRegistry


def create_tool_registry() -> ToolRegistry:
    registry = ToolRegistry()
    registry.register(ListFilesTool())
    registry.register(ReadFileTool())
    registry.register(WriteFileTool())
    registry.register(RunScriptTool())
    registry.register(ApplyPatchTool())
    registry.register(RunTestsTool())
    registry.register(GitStatusTool())
    registry.register(GitDiffTool())
    return registry
