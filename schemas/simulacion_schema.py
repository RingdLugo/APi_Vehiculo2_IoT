from pydantic import BaseModel, ConfigDict, Field, model_validator


class MovimientoSimulado(BaseModel):
    model_config = ConfigDict(extra="forbid")
    id: str = Field(min_length=1, max_length=40, pattern=r"^[a-zA-Z0-9_-]+$")
    nombre: str = Field(min_length=1, max_length=60)
    grados: int | None = Field(default=None, ge=0, le=360)
    duracion_ms: int = Field(default=1000, ge=100, le=10_000)


class ConfiguracionSimulacion(BaseModel):
    model_config = ConfigDict(extra="forbid")
    movimientos: list[MovimientoSimulado] = Field(default_factory=list, max_length=30)
    asignaciones: dict[str, dict[str, str | None]] = Field(default_factory=dict)

    @model_validator(mode="after")
    def validar_asignaciones(self):
        ids = {mov.id for mov in self.movimientos}
        if len(ids) != len(self.movimientos):
            raise ValueError("Los identificadores de movimientos deben ser únicos.")
        for grupo, direcciones in self.asignaciones.items():
            if grupo not in {"drive", "arm"}:
                raise ValueError("Grupo de joystick no válido.")
            if set(direcciones) - {"forward", "backward", "left", "right"}:
                raise ValueError("Dirección de joystick no válida.")
            if any(value is not None and value not in ids for value in direcciones.values()):
                raise ValueError("Una asignación apunta a un movimiento inexistente.")
        return self


class EjecutarMovimientoSimulado(BaseModel):
    model_config = ConfigDict(extra="forbid")
    movimiento_id: str = Field(min_length=1, max_length=40)
    direccion: str = Field(pattern=r"^(forward|backward|left|right)$")
    grupo: str = Field(pattern=r"^(drive|arm)$")
