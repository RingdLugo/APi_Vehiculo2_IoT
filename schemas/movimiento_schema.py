from pydantic import BaseModel, Field


class MovimientoIndividualRequest(BaseModel):
    """Cuerpo del POST de movimiento individual (el vehículo va en la URL)."""
    comando_id: int = Field(..., description="Identificador del comando asignado al vehículo.", example=1)
    origen: str = Field("WEB_API", description="Origen de la solicitud (Ej. WEB_API, APP_MOVIL).", example="WEB_API")


class DemoRequest(BaseModel):
    """Cuerpo del POST que inicia una DEMO."""
    demo_id: int = Field(..., description="Identificador de la DEMO a ejecutar.", example=1)


class MensajeRequest(BaseModel):
    """Cuerpo del POST que envía un mensaje de texto al dispositivo."""
    texto: str = Field(..., min_length=1, max_length=200,
                       description="Texto que aparecerá en el Monitor Serie del Arduino.",
                       example="Hola Arduino")
