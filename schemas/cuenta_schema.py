from pydantic import BaseModel, ConfigDict, Field, model_validator


class DemoCompradorCrear(BaseModel):
    nombre: str = Field(min_length=1, max_length=100, examples=["Mi recorrido"])
    descripcion: str = Field(default="", max_length=500)


class PasoDemoCompradorCrear(BaseModel):
    comando_id: int = Field(gt=0, examples=[14])
    orden: int = Field(ge=1, examples=[1])
    duracion_ms: int = Field(default=1000, ge=0, le=3_600_000)
    pausa_ms: int = Field(default=500, ge=0, le=3_600_000)


class PasoDemoPrivada(BaseModel):
    model_config = ConfigDict(extra="forbid")
    id_comando: int = Field(gt=0)
    duracion_ms: int = Field(ge=0, le=10_000)
    pausa_ms: int = Field(default=0, ge=0, le=10_000)


class DemoPrivadaGuardar(BaseModel):
    model_config = ConfigDict(extra="forbid")
    nombre: str = Field(min_length=1, max_length=80)
    descripcion: str = Field(default="", max_length=255)
    pasos: list[PasoDemoPrivada] = Field(min_length=1, max_length=20)

    @model_validator(mode="after")
    def validar_duracion_total(self):
        total = sum(paso.duracion_ms + paso.pausa_ms for paso in self.pasos)
        if total > 60_000:
            raise ValueError("La duración total de la DEMO no puede superar 60 segundos.")
        return self
