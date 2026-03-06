import logging
from app.models.catalog import ModelStatus

logger = logging.getLogger(__name__)


class ThermalScheduler:
    THERMAL_THRESHOLD = 82  # Celsius

    async def check_gpu_health(self, server_id: str) -> ModelStatus:
        metrics = await self._query_nvidia_smi(server_id)
        if metrics.get("temperature", 0) > self.THERMAL_THRESHOLD:
            await self._deprioritize_server(server_id)
            return ModelStatus.DEGRADED
        return ModelStatus.HEALTHY

    async def _query_nvidia_smi(self, server_id: str) -> dict:
        # Placeholder for actual hardware telemetry logic
        return {"temperature": 65}

    async def _deprioritize_server(self, server_id: str):
        logger.warning(f"Server {server_id} exceeded thermal threshold. Deprioritizing.")
