import json
import aiofiles
from pathlib import Path
from typing import List, Dict, Any


class BoundedContextManager:
    def __init__(self, max_actions: int = 10, scratchpad_dir: str = "data/scratchpads"):
        self.max_actions = max_actions
        self.scratchpad_path = Path(scratchpad_dir)
        self.scratchpad_path.mkdir(parents=True, exist_ok=True)
        self.workspace_snapshots = {}

    async def reconstruct_context(self, conversation_id: str, current_query: str, full_history: List[Dict[str, Any]]) -> str:
        """O(1) guarantee - constant size regardless of history length"""
        recent_actions = full_history[-self.max_actions :]
        snapshot = await self._get_workspace_snapshot(conversation_id)

        return f"""
<workspace_state>
{snapshot}
</workspace_state>

<recent_actions>
{self._format_actions(recent_actions)}
</recent_actions>

<current_query>
{current_query}
</current_query>
"""

    def _format_actions(self, actions: List[Dict[str, Any]]) -> str:
        formatted = []
        for a in actions:
            formatted.append(json.dumps(a))
        return "\n".join(formatted)

    async def _get_workspace_snapshot(self, conversation_id: str) -> str:
        if conversation_id in self.workspace_snapshots:
            return self.workspace_snapshots[conversation_id]

        # Try to load from disk
        file_path = self.scratchpad_path / f"{conversation_id}.json"
        if file_path.exists():
            async with aiofiles.open(file_path, "r") as f:
                data = await f.read()
                self.workspace_snapshots[conversation_id] = data
                return data

        return "No externalized state."

    async def update_snapshot(self, conversation_id: str, new_state: dict):
        """Externalize to disk, keeping active context bounded"""
        state_str = json.dumps(new_state)
        self.workspace_snapshots[conversation_id] = state_str

        file_path = self.scratchpad_path / f"{conversation_id}.json"
        async with aiofiles.open(file_path, "w") as f:
            await f.write(state_str)
