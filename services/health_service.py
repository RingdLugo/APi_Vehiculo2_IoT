from datetime import datetime, timezone

from repositories.health_repository import HealthRepository


class HealthService:
    def __init__(self, repository: HealthRepository):
        self._repository = repository

    def status(self) -> dict:
        return {
            "api": "disponible",
            "rds": "disponible" if self._repository.database_available() else "no disponible",
            "verificado_en": datetime.now(timezone.utc),
        }
