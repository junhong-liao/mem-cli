from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Dict, List


@dataclass
class ToolRegistry:
    tools: List[Any] = field(default_factory=list)

    def register(self, tool: Any) -> None:
        self.tools.append(tool)

    def all(self) -> List[Any]:
        return list(self.tools)

    def by_name(self) -> Dict[str, Any]:
        return {
            tool.name: tool
            for tool in self.tools
            if getattr(tool, "name", None)
        }
