from fastapi import APIRouter, Request

from schemas.health_schema import HealthResponse

router = APIRouter(tags=["Salud y conectividad"])


@router.get("/health", response_model=HealthResponse,
            summary="Comprobar API y conectividad real de Amazon RDS",
            description="La prueba de RDS ejecuta SELECT 1 desde el backend; no devuelve credenciales ni datos.")
def health(request: Request):
    return request.app.state.health_service.status()
