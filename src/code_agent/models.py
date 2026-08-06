from enum import Enum
from typing import Any, Literal, Optional

from pydantic import BaseModel, Field, model_validator


class RiskLevel(str, Enum):
    SAFE = "safe"
    REVIEW = "review"
    FORBIDDEN = "forbidden"


class AgentAction(BaseModel):
    type: Literal[
        "tool_call",
        "ask_user",
        "blocked",
        "finish",
        "message",
    ]
    
    tool: Optional[str] = None
    arguments: dict[str, Any] = Field(default_factory=dict)
    reason: str = ""
    question: Optional[str] = None
    required_action: Optional[str] = None
    summary: Optional[str] = None
    verification: Optional[str] = None
    message: Optional[str] = None
    
    @model_validator(mode="after")
    def validate_action(self):
        if self.type == "tool_call" and not self.tool:
            raise ValueError("tool_call требует tool")
        if self.type == "ask_user" and not self.question:
            raise ValueError("ask_user требует question")
        if self.type == "blocked" and not self.reason:
            raise ValueError("blocked требует reason")
        if self.type == "finish" and not self.summary:
            raise ValueError("finish требует summary")
        if self.type == "message" and not self.message:
            raise ValueError("message требует message")
        return self


class ToolResult(BaseModel):
    success: bool
    output: str = ""
    error: str = ""
    error_type: str = ""
    exit_code: Optional[int] = None
    stdout: str = ""
    stderr: str = ""
    timed_out: bool = False
    retryable: bool = False
    changed_files: list[str] = Field(default_factory=list)
