import json
from typing import AsyncIterator, Dict


class StreamingJSONParser:
    async def parse_stream(self, stream: AsyncIterator[bytes]) -> AsyncIterator[Dict]:
        buffer = b""
        async for chunk in stream:
            buffer += chunk
            while b"\n" in buffer:
                line, buffer = buffer.split(b"\n", 1)
                if line.strip():
                    try:
                        yield json.loads(line)
                    except json.JSONDecodeError:
                        continue
