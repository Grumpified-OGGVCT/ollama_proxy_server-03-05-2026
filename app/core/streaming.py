import asyncio
from typing import Callable
from dataclasses import dataclass
import logging

logger = logging.getLogger(__name__)


@dataclass
class AbortResponse:
    tokens_wasted: int
    aborted: bool = True


async def abort_aware_stream(backend_request: Callable, client_disconnect_event: asyncio.Event, max_waste_tokens: int = 100):  # Allow small buffer
    """Cancel backend generation if client disconnects."""
    task = asyncio.create_task(backend_request())
    disconnect_task = asyncio.create_task(client_disconnect_event.wait())

    done, pending = await asyncio.wait([task, disconnect_task], return_when=asyncio.FIRST_COMPLETED)

    if disconnect_task in done:
        # Client disconnected - cancel backend immediately
        task.cancel()

        # In a real impl, signal Ollama /api/generate cancellation
        logger.warning("Client disconnected. Aborting backend generation.")

        return AbortResponse(tokens_wasted=max_waste_tokens)

    return await task
