from fastapi import APIRouter, Depends, HTTPException, Request, status
from schemas.movimiento_schema import DemoRequest, MovimientoIndividualRequest
from schemas.cuenta_schema import DemoCompradorCrear, DemoPrivadaGuardar, PasoDemoCompradorCrear
from schemas.simulacion_schema import ConfiguracionSimulacion, EjecutarMovimientoSimulado
from security.dependencies import require_roles
from services.operacion_service import MovimientoLimitadoError

router = APIRouter(prefix="/cuenta", tags=["Cuenta y vehículos autorizados"])
account_required = require_roles("ADMINISTRADOR", "USUARIO")
buyer_required = require_roles("ADMINISTRADOR", "USUARIO")


def _principal_vehicle(request: Request, principal: dict, vehicle_id: int) -> None:
    if vehicle_id <= 0:
        raise HTTPException(422, "El ID debe ser positivo.")
    allowed = request.app.state.cuenta_repository.puede_operar(
        principal["id_usuario"], principal["id_empresa"], principal["roles"], vehicle_id
    )
    if not allowed:
        # 404 evita confirmar la existencia de una unidad ajena a la cuenta.
        raise HTTPException(404, "Vehículo no disponible para esta cuenta.")


def _dict(value):
    return value.a_diccionario() if hasattr(value, "a_diccionario") else value


def _require_simulated_vehicle(request: Request, principal: dict, vehicle_id: int) -> None:
    _principal_vehicle(request, principal, vehicle_id)
    vehicle = request.app.state.vehicle_repository.obtener_por_id(vehicle_id)
    if not vehicle or str(vehicle.obtener("microcontrolador", "")).upper() != "SIMULADO":
        raise HTTPException(404, "Carrito simulado no disponible para esta cuenta.")


@router.get("/vehiculos", summary="Listar unidades permitidas para la cuenta")
def mis_vehiculos(request: Request, principal: dict = Depends(account_required)):
    return request.app.state.cuenta_repository.unidades(
        principal["id_usuario"], principal["id_empresa"], principal["roles"]
    )


@router.get("/vehiculos/{vehicle_id}", summary="Consultar ficha de una unidad autorizada")
def ficha_unidad(vehicle_id: int, request: Request, principal: dict = Depends(account_required)):
    _principal_vehicle(request, principal, vehicle_id)
    rows = request.app.state.cuenta_repository.unidades(
        principal["id_usuario"], principal["id_empresa"], principal["roles"]
    )
    return next((row for row in rows if int(row["id_vehiculo"]) == vehicle_id), None)


@router.get("/vehiculos/{vehicle_id}/estado", summary="Consultar estado de una unidad autorizada")
def estado(vehicle_id: int, request: Request, principal: dict = Depends(account_required)):
    _principal_vehicle(request, principal, vehicle_id)
    result = request.app.state.state_repository.obtener_estado(vehicle_id)
    if not result:
        raise HTTPException(404, "No hay estado registrado para esta unidad.")
    return _dict(result)


@router.get("/vehiculos/{vehicle_id}/historial", summary="Consultar historial de una unidad autorizada")
def historial(vehicle_id: int, request: Request, principal: dict = Depends(account_required)):
    _principal_vehicle(request, principal, vehicle_id)
    return [_dict(row) for row in request.app.state.state_repository.obtener_historial_reciente(vehicle_id)]


@router.get("/vehiculos/{vehicle_id}/comandos", summary="Listar comandos de una unidad autorizada")
def comandos(vehicle_id: int, request: Request, principal: dict = Depends(account_required)):
    _principal_vehicle(request, principal, vehicle_id)
    return [_dict(row) for row in request.app.state.command_repository.obtener_detalle_por_vehiculo(vehicle_id)]


@router.get("/vehiculos/{vehicle_id}/simulacion", summary="Consultar movimientos personalizados del carrito simulado")
def obtener_configuracion_simulada(vehicle_id: int, request: Request,
                                   principal: dict = Depends(buyer_required)):
    _require_simulated_vehicle(request, principal, vehicle_id)
    return request.app.state.simulacion_repository.obtener_configuracion(
        principal["id_usuario"], vehicle_id
    )


@router.put("/vehiculos/{vehicle_id}/simulacion", summary="Guardar movimientos y asignaciones del joystick simulado")
def guardar_configuracion_simulada(vehicle_id: int, data: ConfiguracionSimulacion,
                                   request: Request, principal: dict = Depends(buyer_required)):
    _require_simulated_vehicle(request, principal, vehicle_id)
    config = data.model_dump()
    request.app.state.simulacion_repository.guardar_configuracion(
        principal["id_usuario"], vehicle_id, config["movimientos"], config["asignaciones"]
    )
    return {"mensaje": "Configuración del simulador guardada.", **config}


@router.post("/vehiculos/{vehicle_id}/simulacion/ejecutar", summary="Emitir evento virtual sin accionar hardware")
async def ejecutar_movimiento_simulado(vehicle_id: int, data: EjecutarMovimientoSimulado,
                                        request: Request, principal: dict = Depends(buyer_required)):
    _require_simulated_vehicle(request, principal, vehicle_id)
    if request.app.state.operacion_service.tiene_demo_activa(vehicle_id):
        raise HTTPException(409, "Detén la DEMO antes de operar el joystick simulado.")
    config = request.app.state.simulacion_repository.obtener_configuracion(
        principal["id_usuario"], vehicle_id
    )
    assigned_id = (config.get("asignaciones", {}).get(data.grupo, {})
                   .get(data.direccion))
    if assigned_id != data.movimiento_id:
        raise HTTPException(422, "El movimiento no está asignado a esa dirección del joystick.")
    movement = next((item for item in config.get("movimientos", [])
                     if item.get("id") == data.movimiento_id), None)
    if not movement:
        raise HTTPException(404, "Movimiento personalizado no disponible.")
    import time
    payload = {"tipo": "movimiento_simulado", "vehiculo_id": vehicle_id,
               "actor_id": int(principal["id_usuario"]), "grupo": data.grupo,
               "direccion": data.direccion, "movimiento_id": movement["id"],
               "nombre": movement["nombre"], "grados": movement.get("grados"),
               "duracion_ms": int(movement["duracion_ms"]),
               "marca_temporal": int(time.time() * 1000), "simulado": True}
    await request.app.state.connection_manager.broadcast_simulation_to_user(
        vehicle_id, principal["id_usuario"], payload
    )
    return {"mensaje": "Movimiento simulado emitido; no se envió al hardware.", **payload}


@router.get("/vehiculos/{vehicle_id}/demos", summary="Listar demos de una unidad autorizada")
def demos(vehicle_id: int, request: Request, principal: dict = Depends(account_required)):
    _principal_vehicle(request, principal, vehicle_id)
    rows = []
    for demo in request.app.state.demo_repository.obtener_demos_vehiculo(vehicle_id):
        item = _dict(demo)
        item["editable"] = bool(set(principal.get("roles", [])).intersection({"ADMINISTRADOR", "USUARIO"}) and
                                request.app.state.demo_editor_repository.es_propietario(
                                    int(demo.id), vehicle_id, principal["id_usuario"]))
        rows.append(item)
    return rows


@router.post("/vehiculos/{vehicle_id}/demos", status_code=status.HTTP_201_CREATED,
             summary="Crear DEMO propia para una unidad autorizada")
def crear_demo(vehicle_id: int, data: DemoCompradorCrear, request: Request,
               principal: dict = Depends(buyer_required)):
    _principal_vehicle(request, principal, vehicle_id)
    try:
        return request.app.state.demo_editor_repository.crear_demo_privada(
            vehicle_id, principal["id_usuario"], principal["id_empresa"], data.nombre, data.descripcion,
            allow_admin="ADMINISTRADOR" in principal.get("roles", [])
        )
    except LookupError as exc:
        raise HTTPException(403, str(exc)) from exc


@router.post("/vehiculos/{vehicle_id}/demos/{demo_id}/pasos", status_code=status.HTTP_201_CREATED,
             summary="Agregar paso ordenado a una DEMO propia")
def agregar_paso_demo(vehicle_id: int, demo_id: int, data: PasoDemoCompradorCrear,
                      request: Request, principal: dict = Depends(buyer_required)):
    _principal_vehicle(request, principal, vehicle_id)
    editor = request.app.state.demo_editor_repository
    if not editor.es_propietario(demo_id, vehicle_id, principal["id_usuario"]):
        raise HTTPException(404, "DEMO privada no encontrada para esta cuenta.")
    demos_propias = request.app.state.demo_repository.obtener_demos_vehiculo(vehicle_id)
    demo = next((item for item in demos_propias if int(item.id) == demo_id and item.esta_activo()), None)
    if not demo:
        raise HTTPException(404, "DEMO no disponible para este carrito.")
    existing = request.app.state.demo_repository.obtener_movimientos_demo(demo_id)
    steps = [{"id_comando": int(item.comando_id), "duracion_ms": int(item.duracion_ms),
              "pausa_ms": int(item.pausa_ms)} for item in existing]
    new_step = {"id_comando": data.comando_id, "duracion_ms": data.duracion_ms,
                "pausa_ms": data.pausa_ms}
    steps.insert(min(max(data.orden - 1, 0), len(steps)), new_step)
    try:
        return editor.guardar_demo_privada(demo_id, vehicle_id, principal["id_usuario"],
                                           principal["id_empresa"],
                                           demo.nombre, demo.obtener("descripcion", ""), steps)
    except LookupError as exc:
        raise HTTPException(404, str(exc)) from exc
    except ValueError as exc:
        raise HTTPException(422, str(exc)) from exc


@router.put("/vehiculos/{vehicle_id}/demos/{demo_id}", summary="Guardar metadatos y secuencia de una DEMO propia",
            responses={403: {"description": "La demo no pertenece al comprador."},
                       404: {"description": "Unidad o demo no disponible."},
                       409: {"description": "La DEMO está en ejecución."},
                       422: {"description": "Comando incompatible o duración excedida."}})
def guardar_demo_privada(vehicle_id: int, demo_id: int, data: DemoPrivadaGuardar,
                         request: Request, principal: dict = Depends(buyer_required)):
    _principal_vehicle(request, principal, vehicle_id)
    if request.app.state.operacion_service.tiene_demo_activa(vehicle_id):
        raise HTTPException(409, "No se puede guardar mientras una DEMO está ejecutándose.")
    try:
        return request.app.state.demo_editor_repository.guardar_demo_privada(
            demo_id, vehicle_id, principal["id_usuario"], principal["id_empresa"],
            data.nombre, data.descripcion,
            [step.model_dump() for step in data.pasos],
        )
    except LookupError as exc:
        raise HTTPException(404, str(exc)) from exc
    except ValueError as exc:
        raise HTTPException(422, str(exc)) from exc


@router.get("/vehiculos/{vehicle_id}/demos/{demo_id}/pasos", summary="Listar pasos de una demo autorizada")
def pasos_demo(vehicle_id: int, demo_id: int, request: Request,
               principal: dict = Depends(account_required)):
    _principal_vehicle(request, principal, vehicle_id)
    demos_disponibles = request.app.state.demo_repository.obtener_demos_vehiculo(vehicle_id)
    if not any(int(demo.id) == demo_id and demo.esta_activo() for demo in demos_disponibles):
        raise HTTPException(404, "DEMO no disponible para este vehículo.")
    return [_dict(row) for row in request.app.state.demo_repository.obtener_movimientos_demo(demo_id)]


@router.post("/vehiculos/{vehicle_id}/movimiento", status_code=status.HTTP_201_CREATED,
             summary="Enviar movimiento con autorización de empresa/asignación",
             responses={401: {"description": "Falta autenticación."},
                        403: {"description": "Rol sin permiso de operación."},
                        404: {"description": "Unidad fuera del alcance de la cuenta."},
                        409: {"description": "Conflicto con una demo activa."},
                        429: {"description": "Límite temporal de movimientos alcanzado."}})
async def movimiento(vehicle_id: int, data: MovimientoIndividualRequest, request: Request,
                     principal: dict = Depends(account_required)):
    _principal_vehicle(request, principal, vehicle_id)
    try:
        # El origen se fija en el servidor; el cliente no puede atribuir otro origen.
        return await request.app.state.operacion_service.ejecutar_movimiento_individual(
            vehicle_id, data.comando_id, "WEB_CONTROL", data.estado_salida
        )
    except ValueError as exc:
        raise HTTPException(400, str(exc)) from exc
    except MovimientoLimitadoError as exc:
        raise HTTPException(429, str(exc), headers={"Retry-After": "10"}) from exc


@router.post("/vehiculos/{vehicle_id}/demo/iniciar", summary="Iniciar demo autorizada")
async def iniciar_demo(vehicle_id: int, data: DemoRequest, request: Request,
                       principal: dict = Depends(account_required)):
    _principal_vehicle(request, principal, vehicle_id)
    try:
        return await request.app.state.operacion_service.iniciar_demo(vehicle_id, data.demo_id)
    except ValueError as exc:
        raise HTTPException(400, str(exc)) from exc


@router.post("/vehiculos/{vehicle_id}/demo/detener", summary="Cancelar demo autorizada")
async def cancelar_demo(vehicle_id: int, request: Request,
                        principal: dict = Depends(account_required)):
    _principal_vehicle(request, principal, vehicle_id)
    try:
        return await request.app.state.operacion_service.cancelar_demo(vehicle_id)
    except ValueError as exc:
        raise HTTPException(400, str(exc)) from exc
