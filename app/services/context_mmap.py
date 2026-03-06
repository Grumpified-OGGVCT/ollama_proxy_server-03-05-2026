import mmap
from pathlib import Path
from typing import Dict


class MMapContextStore:
    def __init__(self, base_path: Path = Path("/dev/shm/ollama_ctx")):
        self.base_path = base_path
        self.active_maps: Dict[str, mmap.mmap] = {}
        # Make sure directory exists if /dev/shm is available, else fallback
        try:
            self.base_path.mkdir(parents=True, exist_ok=True)
        except OSError:
            self.base_path = Path("/tmp/ollama_ctx")
            self.base_path.mkdir(parents=True, exist_ok=True)

    async def store(self, conversation_id: str, data: bytes) -> str:
        file_path = self.base_path / f"{conversation_id}.ctx"
        with open(file_path, "wb") as f:
            f.write(data)
            f.flush()
            # Need to open it for reading to create mmap

        with open(file_path, "r+b") as f:
            mm = mmap.mmap(f.fileno(), 0, access=mmap.ACCESS_READ)
            self.active_maps[conversation_id] = mm

        return str(file_path)

    async def retrieve(self, conversation_id: str) -> bytes:
        if conversation_id in self.active_maps:
            mm = self.active_maps[conversation_id]
            mm.seek(0)
            return mm.read()
        # Fallback to disk
        file_path = self.base_path / f"{conversation_id}.ctx"
        if file_path.exists():
            return file_path.read_bytes()
        return b""
