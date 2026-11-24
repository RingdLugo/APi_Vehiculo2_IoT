import asyncio
import hashlib

from fastapi import APIRouter, Depends, Header, HTTPException, Request, status

from schemas.admin_schema import MovimientoInvitado, SolicitudDemoPublica
from schemas.movimiento_schema import DemoRequest
from services.operacion_service import MovimientoLimitadoError

router = APIRouter(prefix="/guest", tags=["Sesión de invitado"])


@router.get("/catalogo", summary="Modelos públicos y disponibilidad agregada para demostración")
def catalogo_publico(request: Request):
    rows = request.app.state.admin_repository.catalogo_publico_invitado()
    result = []
    for row in rows:
        capabilities = row.get("capacidades")
        result.append({
            "id_modelo": row["id_modelo"], "codigo": row["codigo"],
            "nombre": row["nombre"], "marca": row["marca"],
            "descripcion": None, "imagen_url": None,
            "capacidades": [item for item in (capabilities or "").split(",") if item],
            "unidades_disponibles": int(row.get("unidades_disponibles") or 0),
            "disponibilidad": "DISPONIBLE" if int(row.get("unidades_disponibles") or 0) else "SIN UNIDAD DISPONIBLE",
        })
    return result


@router.post("/sesiones", status_code=201, summary="Solicitar una demostración pública temporal",
             description="Reserva exclusiva por 10 minutos de una unidad marcada como exhibición. "
                         "Solo admite los comandos básicos definidos por el servidor.",
             responses={404: {"description": "Sin unidad o DEMO de exhibición disponible."},
                        409: {"description": "La unidad fue reservada por otra solicitud."},
                        429: {"description": "Límite temporal de reservas alcanzado."}})
async def solicitar_sesion(data: SolicitudDemoPublica, request: Request):
    try:
        expired = await asyncio.to_thread(request.app.state.admin_repository.expirar_sesiones_publicas)
        for session in expired:
            await request.app.state.operacion_service.detener_seguro(
                int(session["id_vehiculo"]), "SEGURIDAD_EXPIRACION_INVITADO"
            )
            await request.app.state.connection_manager.cerrar_sesion_invitado(int(session["id_sesion"]))
        return await asyncio.to_thread(
            request.app.state.admin_service.solicitar_sesion_publica, data.id_modelo, data.id_demo
        )
    except LookupError as exc:
        raise HTTPException(404, str(exc)) from exc
    except ValueError as exc:
        raise HTTPException(422, str(exc)) from exc


def _sesion(request: Request, token: str | None):
    if not token:
        raise HTTPException(401, "Se requiere X-Guest-Token.", headers={"WWW-Authenticate": "Guest"})
    token_hash = hashlib.sha256(token.encode()).hexdigest()
    session = request.app.state.admin_repository.sesion_invitado_por_token(token_hash)
    if not session:
        raise HTTPException(401, "La sesión de invitado no está activa o venció.")
    return session


@router.get("/sesion", summary="Consultar permisos de la sesión temporal activa")
def consultar_sesion(request: Request,
                     x_guest_token: str | None = Header(default=None, alias="X-Guest-Token")):
    session = _sesion(request, x_guest_token)
    return {"id_sesion": session["id_sesion"], "id_vehiculo": session["id_vehiculo"],
            "id_demo": session["id_demo"], "estado": session["estado"],
            "expira_en": session["expira_en"],
            "comandos_permitidos": session["comandos_permitidos"]}


@router.delete("/sesiones/actual", summary="Finalizar sesión pública y liberar la unidad")
async def finalizar_sesion(request: Request,
                           x_guest_token: str | None = Header(default=None, alias="X-Guest-Token")):
    session = _sesion(request, x_guest_token)
    token_hash = hashlib.sha256(x_guest_token.encode()).hexdigest()
    result = await asyncio.to_thread(
        request.app.state.admin_repository.finalizar_sesion_publica,
        int(session["id_sesion"]), token_hash, "FINALIZADA",
    )
    if not result:
        raise HTTPException(404, "La sesión ya terminó o no está disponible.")
    await request.app.state.operacion_service.detener_seguro(result["id_vehiculo"], "SEGURIDAD_INVITADO")
    await request.app.state.connection_manager.cerrar_sesion_invitado(result["id_sesion"])
    return {**result, "mensaje": "Sesión finalizada; la ejecución física queda sin verificar."}


@router.get("/vehiculos/{vehicle_id}", summary="Consultar ficha de la unidad disponible para invitado")
def ficha_invitado(vehicle_id: int, request: Request,
                   x_guest_token: str | None = Header(default=None, alias="X-Guest-Token")):
    session = _sesion(request, x_guest_token)
    if int(session["id_vehiculo"]) != vehicle_id:
        raise HTTPException(404, "Vehículo no disponible para esta sesión.")
    vehicle = request.app.state.vehicle_repository.obtener_por_id(vehicle_id)
    if not vehicle or not vehicle.esta_activo():
        raise HTTPException(404, "Vehículo no disponible.")
    return vehicle.a_diccionario()


@router.get("/vehiculos/{vehicle_id}/comandos", summary="Listar solo comandos permitidos al invitado")
def comandos_invitado(vehicle_id: int, request: Request,
                      x_guest_token: str | None = Header(default=None, alias="X-Guest-Token")):
    session = _sesion(request, x_guest_token)
    if int(session["id_vehiculo"]) != vehicle_id:
        raise HTTPException(404, "Vehículo no disponible para esta sesión.")
    commands = request.app.state.command_repository.obtener_detalle_por_vehiculo(vehicle_id)
    allowed = set(session["comandos_permitidos"])
    return [command.a_diccionario() for command in commands
            if int(command.id) in allowed or str(command.nombre).upper() == "DETENER"]


@router.get("/vehiculos/{vehicle_id}/demos", summary="Consultar la demo autorizada al invitado")
def demos_invitado(vehicle_id: int, request: Request,
                   x_guest_token: str | None = Header(default=None, alias="X-Guest-Token")):
    session = _sesion(request, x_guest_token)
    if int(session["id_vehiculo"]) != vehicle_id:
        raise HTTPException(404, "Vehículo no disponible para esta sesión.")
    if session["id_demo"] is None:
        return []
    return [demo.a_diccionario() for demo in request.app.state.demo_repository.obtener_demos_vehiculo(vehicle_id)
            if int(demo.id) == int(session["id_demo"]) and demo.esta_activo()]


@router.get("/vehiculos/{vehicle_id}/demos/{demo_id}/pasos", summary="Consultar pasos de la demo autorizada")
def pasos_invitado(vehicle_id: int, demo_id: int, request: Request,
                   x_guest_token: str | None = Header(default=None, alias="X-Guest-Token")):
    session = _sesion(request, x_guest_token)
    if int(session["id_vehiculo"]) != vehicle_id or session["id_demo"] is None or int(session["id_demo"]) != demo_id:
        raise HTTPException(404, "DEMO no autorizada para esta sesión.")
    demo = next((item for item in request.app.state.demo_repository.obtener_demos_vehiculo(vehicle_id)
                 if int(item.id) == demo_id and item.esta_activo()), None)
    if not demo:
        raise HTTPException(404, "DEMO no disponible.")
    return [item.a_diccionario() for item in request.app.state.demo_repository.obtener_movimientos_demo(demo_id)]


@router.post(
    "/vehiculos/{vehicle_id}/movimiento",
    summary="Enviar un comando autorizado por sesión temporal",
    description=(
        "Requiere el token devuelto al reservar la sesión en `X-Guest-Token`. "
        "La sesión debe estar activada y vigente; el servidor valida vehículo y comando "
        "contra los permisos almacenados antes de emitir el movimiento."
    ),
    responses={
        401: {"description": "Token ausente, inválido, revocado o vencido."},
        403: {"description": "El token no permite ese comando."},
        404: {"description": "Vehículo o comando no disponible."},
        422: {"description": "Cuerpo o parámetros no válidos."},
        429: {"description": "Límite de solicitudes o movimientos alcanzado."},
    },
)
async def enviar_movimiento_invitado(
    vehicle_id: int,
    data: MovimientoInvitado,
    request: Request,
    x_guest_token: str | None = Header(default=None, alias="X-Guest-Token"),
):
    if vehicle_id <= 0:
        raise HTTPException(422, "El ID del vehículo debe ser positivo.")
    if not x_guest_token:
        raise HTTPException(401, "Se requiere X-Guest-Token.", headers={"WWW-Authenticate": "Guest"})

    token_hash = hashlib.sha256(x_guest_token.encode()).hexdigest()
    permitido = await asyncio.to_thread(
        request.app.state.admin_repository.invitado_puede_ejecutar,
        token_hash, vehicle_id, data.comando_id,
    )
    if permitido is None:
        raise HTTPException(401, "La sesión de invitado no está activa o venció.")
    if not permitido:
        raise HTTPException(403, "El comando no está autorizado para esta sesión.")

    try:
        return await request.app.state.operacion_service.ejecutar_movimiento_individual(
            vehicle_id, data.comando_id, "WEB_GUEST", data.estado_salida
        )
    except ValueError as exc:
        raise HTTPException(404, str(exc)) from exc
    except MovimientoLimitadoError as exc:
        raise HTTPException(429, str(exc), headers={"Retry-After": "10"}) from exc


@router.post("/vehiculos/{vehicle_id}/demo/iniciar", summary="Ejecutar la demo incluida en la sesión temporal")
async def iniciar_demo_invitado(vehicle_id: int, data: DemoRequest, request: Request,
                                x_guest_token: str | None = Header(default=None, alias="X-Guest-Token")):
    session = _sesion(request, x_guest_token)
    if int(session["id_vehiculo"]) != vehicle_id or session["id_demo"] is None or int(session["id_demo"]) != data.demo_id:
        raise HTTPException(403, "Esta sesión no autoriza esa DEMO.")
    try:
        return await request.app.state.operacion_service.iniciar_demo(vehicle_id, data.demo_id)
    except ValueError as exc:
        raise HTTPException(400, str(exc)) from exc


@router.post("/vehiculos/{vehicle_id}/demo/detener", summary="Cancelar la demo de la sesión temporal")
async def cancelar_demo_invitado(vehicle_id: int, request: Request,
                                 x_guest_token: str | None = Header(default=None, alias="X-Guest-Token")):
    session = _sesion(request, x_guest_token)
    if int(session["id_vehiculo"]) != vehicle_id:
        raise HTTPException(404, "Vehículo no disponible para esta sesión.")
    try:
        return await request.app.state.operacion_service.cancelar_demo(vehicle_id)
    except ValueError as exc:
        raise HTTPException(400, str(exc)) from exc
