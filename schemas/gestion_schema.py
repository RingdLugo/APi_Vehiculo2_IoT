from typing import Optional

from pydantic import BaseModel, Field


class VehiculoCrear(BaseModel):
    nombre: str = Field(..., min_length=1, example="Excavadora 01")
    descripcion: str = Field("", example="Excavadora a escala controlada por ESP32")


class VehiculoActualizar(VehiculoCrear):
    activo: bool = True


class ComandoCrear(BaseModel):
    vehiculo_id: int = Field(..., example=1)
    nombre: str = Field(..., min_length=1, example="Avanzar")
    codigo: int = Field(..., description="Código numérico del comando (único por vehículo).", example=1)
    descripcion: str = Field("", example="Mueve el vehículo hacia adelante")
    mascara: Optional[int] = Field(
        None, ge=0, le=65535, example=1024,
        description="Salidas de los 74HC595 que activa el comando (0-65535). "
                    "Sin máscara, el comando no podrá ejecutarse en el vehículo.")


class ComandoActualizar(BaseModel):
    nombre: str = Field(..., min_length=1)
    codigo: int = Field(..., description="Código numérico del comando (único por vehículo).")
    descripcion: str = ""
    activo: bool = True
    mascara: Optional[int] = Field(
        None, ge=0, le=65535,
        description="Opcional. Si se envía, actualiza la máscara de salida del comando.")


class DemoCrear(BaseModel):
    vehiculo_id: int = Field(..., example=1)
    nombre: str = Field(..., min_length=1, example="Demo de bienvenida")
    descripcion: str = Field("", example="Secuencia de ejemplo")


class DemoActualizar(BaseModel):
    nombre: str = Field(..., min_length=1)
    descripcion: str = ""
    activo: bool = True


class MovimientoDemoCrear(BaseModel):
    comando_id: int = Field(..., example=1)
    orden: int = Field(..., ge=1, example=1)
    duracion_ms: int = Field(1000, ge=0, example=1000)
    pausa_ms: int = Field(500, ge=0, example=500)


class MovimientoDemoActualizar(MovimientoDemoCrear):
    pass


class MascaraRequest(BaseModel):
    mascara: int = Field(..., ge=0, le=65535, example=1024,
                         description="Valor de 16 bits para los 74HC595 (0 = apagar todo). "
                                     "Ej.: 0x0400 = 1024.")
