from datetime import datetime
from typing import Literal

from pydantic import BaseModel, ConfigDict


class HealthResponse(BaseModel):
    model_config = ConfigDict(json_schema_extra={"examples": [{
        "api": "disponible", "rds": "disponible", "verificado_en": "2026-11-22T18:30:00Z"
    }]})
    api: Literal["disponible"]
    rds: Literal["disponible", "no disponible"]
    verificado_en: datetime
