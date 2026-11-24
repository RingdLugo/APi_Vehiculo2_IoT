import logging
from datetime import datetime, timezone

import pymysql

from fastapi import APIRouter, Depends, HTTPException, Query, Request, Response, status

from schemas.admin_schema import (
    AsignacionCerrar, AsignacionCreate, ClienteCreate, ClientePatch,
    AdminDashboardResponse, AdminDemoCreate, AdminDemoPatch, AdminPasoCreate, AdminPasoPatch,
    ModeloCreate, ModeloPatch, SesionInvitadoCreate, UnidadCreate, UnidadPatch,
    UsuarioCreate, UsuarioEstadoPatch, UsuarioRolesPatch,
)
from security.dependencies import require_roles

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/admin", tags=["Administración"])
admin_required = require_roles("ADMINISTRADOR")


def _repo(request: Request):
    return request.app.state.admin_repository


def _actor(principal: dict) -> dict:
    return {"id_usuario": principal["id_usuario"], "id_empresa": principal["id_empresa"]}


@router.get("/dashboard", response_model=AdminDashboardResponse,
            summary="Consultar métricas reales del panel administrativo")
def dashboard(request: Request, principal: dict = Depends(admin_required)):
    repository = _repo(request)
    metrics = repository.metricas_dashboard(principal["id_empresa"])
    observable_units = repository.unidades_observables_wss(principal["id_empresa"])
    connected = sum(
        1 for row in observable_units
        if request.app.state.connection_manager.total_navegadores(int(row["id_vehiculo"])) > 0
    )
    devices_connected = sum(
        1 for row in observable_units
        if request.app.state.connection_manager.total_dispositivos(int(row["id_vehiculo"])) > 0
    )
    return {**metrics, "unidades_con_sesion_wss": connected,
            "unidades_con_dispositivo_wss": devices_connected,
            "nota_wss": "Cuenta sesiones WSS autenticadas del navegador.",
            "nota_dispositivo_wss": "Cuenta ESP8266 autenticados conectados a este proceso API; no confirma el estado eléctrico de las salidas.",
            "generado_en": datetime.now(timezone.utc)}


@router.get("/modelos", summary="Listar modelos comerciales",
            responses={401: {"description": "Requiere autenticación."},
                       403: {"description": "Requiere rol administrador."}})
def listar_modelos(request: Request, q: str | None = Query(None, max_length=120),
                   estado: str | None = Query(None, pattern="^(ACTIVO|INACTIVO|BAJA)$"),
                   limit: int = Query(50, ge=1, le=100), offset: int = Query(0, ge=0),
                   _: dict = Depends(admin_required)):
    return _repo(request).listar_modelos(q, estado, limit, offset)


@router.post("/modelos", status_code=status.HTTP_201_CREATED, summary="Crear modelo comercial",
             responses={409: {"description": "El código de modelo ya existe."}})
def crear_modelo(data: ModeloCreate, request: Request, principal: dict = Depends(admin_required)):
    try:
        model_id = _repo(request).crear_modelo(data.model_dump(), _actor(principal))
    except Exception as exc:
        if getattr(exc, "args", [None])[0] == 1062:
            raise HTTPException(409, "El código de modelo ya existe.") from exc
        raise
    return {"id_modelo": model_id, **data.model_dump(), "estado": "ACTIVO"}


@router.get("/modelos/{model_id}", summary="Obtener modelo comercial", responses={404: {"description": "No encontrado."}})
def obtener_modelo(model_id: int, request: Request, _: dict = Depends(admin_required)):
    if model_id <= 0:
        raise HTTPException(422, "El ID debe ser positivo.")
    row = _repo(request).obtener_modelo(model_id)
    if not row:
        raise HTTPException(404, "Modelo no encontrado.")
    return row


@router.patch("/modelos/{model_id}", summary="Actualizar modelo comercial",
              responses={404: {"description": "No encontrado."}})
def actualizar_modelo(model_id: int, data: ModeloPatch, request: Request,
                      principal: dict = Depends(admin_required)):
    if model_id <= 0:
        raise HTTPException(422, "El ID debe ser positivo.")
    if not _repo(request).actualizar_modelo(model_id, data.model_dump(exclude_unset=True), _actor(principal)):
        raise HTTPException(404, "Modelo no encontrado.")
    return obtener_modelo(model_id, request, principal)


@router.delete("/modelos/{model_id}", status_code=status.HTTP_204_NO_CONTENT,
               summary="Dar de baja lógica un modelo")
def baja_modelo(model_id: int, request: Request, principal: dict = Depends(admin_required)):
    if model_id <= 0:
        raise HTTPException(422, "El ID debe ser positivo.")
    if not _repo(request).baja_modelo(model_id, _actor(principal)):
        raise HTTPException(404, "Modelo no encontrado.")
    return Response(status_code=204)


@router.get("/unidades", summary="Listar unidades de la empresa autenticada")
def listar_unidades(request: Request, principal: dict = Depends(admin_required),
                    q: str | None = Query(None, max_length=120), activo: bool | None = None,
                    limit: int = Query(50, ge=1, le=100), offset: int = Query(0, ge=0)):
    rows = _repo(request).listar_unidades(principal["id_empresa"], q, activo, limit, offset)
    for row in rows:
        row["conectividad"] = (
            "ESP8266 conectado por WSS"
            if request.app.state.connection_manager.total_dispositivos(int(row["id_vehiculo"]))
            else "ESP8266 sin sesión WSS"
        )
    return rows


@router.post("/unidades", status_code=status.HTTP_201_CREATED, summary="Registrar unidad en inventario",
             responses={404: {"description": "Modelo no encontrado."}, 409: {"description": "Conflicto de datos."}})
def crear_unidad(data: UnidadCreate, request: Request, principal: dict = Depends(admin_required)):
    try:
        vehicle_id = _repo(request).crear_unidad(data.model_dump(), _actor(principal))
    except LookupError as exc:
        raise HTTPException(404, str(exc)) from exc
    return {"id_vehiculo": vehicle_id, **data.model_dump(), "activo": True}


@router.get("/unidades/{vehicle_id}", summary="Consultar unidad dentro de la empresa", responses={404: {"description": "No encontrada."}})
def obtener_unidad(vehicle_id: int, request: Request, principal: dict = Depends(admin_required)):
    if vehicle_id <= 0:
        raise HTTPException(422, "El ID debe ser positivo.")
    row = _repo(request).unidad_en_empresa(vehicle_id, principal["id_empresa"])
    if not row:
        raise HTTPException(404, "Unidad no encontrada en la empresa.")
    return row


@router.patch("/unidades/{vehicle_id}", summary="Actualizar unidad",
              responses={404: {"description": "No encontrada."}, 409: {"description": "Conflicto de integridad."}})
def actualizar_unidad(vehicle_id: int, data: UnidadPatch, request: Request,
                      principal: dict = Depends(admin_required)):
    if vehicle_id <= 0:
        raise HTTPException(422, "El ID debe ser positivo.")
    values = data.model_dump(exclude_unset=True)
    if values.get("activo") is False:
        try:
            ok = _repo(request).baja_unidad(vehicle_id, _actor(principal))
        except FileExistsError as exc:
            raise HTTPException(409, str(exc)) from exc
    else:
        try:
            ok = _repo(request).actualizar_unidad(vehicle_id, values, _actor(principal))
        except LookupError as exc:
            raise HTTPException(404, str(exc)) from exc
        except FileExistsError as exc:
            raise HTTPException(409, str(exc)) from exc
    if not ok:
        raise HTTPException(404, "Unidad no encontrada en el inventario de la empresa.")
    return obtener_unidad(vehicle_id, request, principal)


@router.delete("/unidades/{vehicle_id}", status_code=status.HTTP_204_NO_CONTENT,
               summary="Dar de baja lógica una unidad",
               responses={404: {"description": "No encontrada."}, 409: {"description": "Tiene asignación o sesión activa."}})
def baja_unidad(vehicle_id: int, request: Request, principal: dict = Depends(admin_required)):
    if vehicle_id <= 0:
        raise HTTPException(422, "El ID debe ser positivo.")
    try:
        ok = _repo(request).baja_unidad(vehicle_id, _actor(principal))
    except FileExistsError as exc:
        raise HTTPException(409, str(exc)) from exc
    if not ok:
        raise HTTPException(404, "Unidad no encontrada en el inventario de la empresa.")
    return Response(status_code=204)


@router.get("/clientes", summary="Listar clientes de la empresa autenticada")
def listar_clientes(request: Request, principal: dict = Depends(admin_required),
                    q: str | None = Query(None, max_length=160),
                    estado: str | None = Query(None, pattern="^(ACTIVO|INACTIVO|BAJA)$"),
                    limit: int = Query(50, ge=1, le=100), offset: int = Query(0, ge=0)):
    return _repo(request).listar_clientes(principal["id_empresa"], q, estado, limit, offset)


@router.post("/clientes", status_code=status.HTTP_201_CREATED, summary="Crear comprador, cuenta y carrito virtual")
def crear_cliente(data: ClienteCreate, request: Request, principal: dict = Depends(admin_required)):
    try:
        result = request.app.state.auth_service.crear_comprador_administrativo(
            principal["id_empresa"], principal["id_usuario"], data.correo_contacto,
            data.nombre, data.password, data.id_modelo, data.telefono_contacto,
        )
    except LookupError as exc:
        raise HTTPException(404, str(exc)) from exc
    except pymysql.err.IntegrityError as exc:
        if getattr(exc, "args", [None])[0] == 1062:
            raise HTTPException(409, "El correo ya está registrado.") from exc
        raise
    return {**result, "id_empresa": principal["id_empresa"],
            "correo_contacto": data.correo_contacto, "telefono_contacto": data.telefono_contacto,
            "nombre": data.nombre, "estado": "ACTIVO", "tipo_vehiculo": "SIMULADO"}


@router.get("/clientes/{client_id}", summary="Obtener cliente de la empresa", responses={404: {"description": "No encontrado."}})
def obtener_cliente(client_id: int, request: Request, principal: dict = Depends(admin_required)):
    if client_id <= 0:
        raise HTTPException(422, "El ID debe ser positivo.")
    row = _repo(request).obtener_cliente(client_id, principal["id_empresa"])
    if not row:
        raise HTTPException(404, "Cliente no encontrado en la empresa.")
    return row


@router.patch("/clientes/{client_id}", summary="Actualizar cliente",
              responses={404: {"description": "No encontrado."}, 409: {"description": "Tiene asignaciones activas."}})
def actualizar_cliente(client_id: int, data: ClientePatch, request: Request,
                       principal: dict = Depends(admin_required)):
    if client_id <= 0:
        raise HTTPException(422, "El ID debe ser positivo.")
    try:
        ok = _repo(request).actualizar_cliente(client_id, principal["id_empresa"],
                                               data.model_dump(exclude_unset=True), _actor(principal))
    except FileExistsError as exc:
        raise HTTPException(409, str(exc)) from exc
    if not ok:
        raise HTTPException(404, "Cliente no encontrado en la empresa.")
    return obtener_cliente(client_id, request, principal)


@router.delete("/clientes/{client_id}", status_code=status.HTTP_204_NO_CONTENT,
               summary="Dar de baja lógica un cliente",
               responses={404: {"description": "No encontrado."}, 409: {"description": "Tiene asignaciones activas."}})
def baja_cliente(client_id: int, request: Request, principal: dict = Depends(admin_required)):
    if client_id <= 0:
        raise HTTPException(422, "El ID debe ser positivo.")
    try:
        ok = _repo(request).baja_cliente(client_id, principal["id_empresa"], _actor(principal))
    except FileExistsError as exc:
        raise HTTPException(409, str(exc)) from exc
    if not ok:
        raise HTTPException(404, "Cliente no encontrado en la empresa.")
    return Response(status_code=204)


@router.get("/roles", summary="Listar roles disponibles")
def listar_roles(request: Request, _: dict = Depends(admin_required)):
    return _repo(request).listar_roles()


@router.get("/usuarios", summary="Listar usuarios de la empresa autenticada")
def listar_usuarios(request: Request, principal: dict = Depends(admin_required),
                    estado: str | None = Query(None, pattern="^(PENDIENTE|ACTIVO|BLOQUEADO|BAJA)$"),
                    limit: int = Query(50, ge=1, le=100), offset: int = Query(0, ge=0)):
    return _repo(request).listar_usuarios(principal["id_empresa"], estado, limit, offset)


@router.post("/usuarios", status_code=status.HTTP_201_CREATED, summary="Crear comprador con carrito virtual",
             description=("Da de alta usuario y cliente comprador y crea automáticamente un carrito virtual "
                          "con ID propio, comandos y asignación. No utiliza una unidad física."),
             responses={404: {"description": "Modelo o plantilla de comandos no disponible."},
                        409: {"description": "Correo ya registrado."}})
def crear_usuario(data: UsuarioCreate, request: Request, principal: dict = Depends(admin_required)):
    try:
        result = request.app.state.auth_service.crear_comprador_administrativo(
            principal["id_empresa"], principal["id_usuario"], data.correo,
            data.nombre, data.password, data.id_modelo,
        )
    except LookupError as exc:
        raise HTTPException(404, str(exc)) from exc
    except (FileExistsError, pymysql.err.IntegrityError) as exc:
        if getattr(exc, "args", [None])[0] == 1062 or isinstance(exc, FileExistsError):
            raise HTTPException(409, "El correo ya está registrado.") from exc
        raise
    return {**result, "id_empresa": principal["id_empresa"], "correo": data.correo,
            "nombre": data.nombre, "estado": "ACTIVO", "roles": ["USUARIO"],
            "tipo_vehiculo": "SIMULADO"}


@router.patch("/usuarios/{user_id}/estado", summary="Cambiar estado lógico de usuario",
              responses={404: {"description": "Usuario fuera de la empresa o inexistente."}})
async def actualizar_estado_usuario(user_id: int, data: UsuarioEstadoPatch, request: Request,
                                    principal: dict = Depends(admin_required)):
    if user_id <= 0:
        raise HTTPException(422, "El ID debe ser positivo.")
    if user_id == principal["id_usuario"] and data.estado != "ACTIVO":
        raise HTTPException(409, "El administrador autenticado no puede bloquearse a sí mismo.")
    ok = _repo(request).actualizar_estado_usuario(
        user_id, principal["id_empresa"], data.estado, _actor(principal)
    )
    if not ok:
        raise HTTPException(404, "Usuario no encontrado en la empresa.")
    if data.estado != "ACTIVO":
        await request.app.state.connection_manager.cerrar_usuario(user_id)
    return {"id_usuario": user_id, "estado": data.estado}


@router.patch("/usuarios/{user_id}/roles", summary="Reemplazar roles de una cuenta dentro de la empresa",
              responses={404: {"description": "Usuario o rol no encontrado."},
                         409: {"description": "No se puede dejar la empresa sin administrador activo."}})
async def actualizar_roles_usuario(user_id: int, data: UsuarioRolesPatch, request: Request,
                                   principal: dict = Depends(admin_required)):
    if user_id <= 0:
        raise HTTPException(422, "El ID debe ser positivo.")
    try:
        roles = _repo(request).actualizar_roles_usuario(
            user_id, principal["id_empresa"], data.roles, _actor(principal)
        )
    except LookupError as exc:
        raise HTTPException(404, str(exc)) from exc
    except FileExistsError as exc:
        raise HTTPException(409, str(exc)) from exc
    except ValueError as exc:
        raise HTTPException(422, str(exc)) from exc
    if roles is None:
        raise HTTPException(404, "Usuario no encontrado en la empresa.")
    await request.app.state.connection_manager.cerrar_usuario(user_id)
    return {"id_usuario": user_id, "roles": roles, "mensaje": "Roles actualizados; se cerraron sus sesiones WSS."}


@router.get("/asignaciones", summary="Listar asignaciones de la empresa")
def listar_asignaciones(request: Request, principal: dict = Depends(admin_required),
                         estado: str | None = Query(None, pattern="^(ACTIVA|FINALIZADA|REVOCADA)$"),
                         limit: int = Query(50, ge=1, le=100), offset: int = Query(0, ge=0)):
    return _repo(request).listar_asignaciones(principal["id_empresa"], estado, limit, offset)


@router.post("/asignaciones", status_code=status.HTTP_201_CREATED, summary="Asignar unidad a cliente",
             responses={404: {"description": "Unidad o cliente fuera de la empresa."},
                        409: {"description": "Unidad ya asignada."}})
def crear_asignacion(data: AsignacionCreate, request: Request, principal: dict = Depends(admin_required)):
    try:
        assignment_id = _repo(request).crear_asignacion(data.model_dump(), _actor(principal))
    except LookupError as exc:
        raise HTTPException(404, str(exc)) from exc
    except FileExistsError as exc:
        raise HTTPException(409, str(exc)) from exc
    return {"id_asignacion": assignment_id, **data.model_dump(), "estado": "ACTIVA"}


@router.patch("/asignaciones/{assignment_id}", summary="Finalizar o revocar asignación",
              responses={404: {"description": "No existe una asignación activa visible."}})
async def cerrar_asignacion(assignment_id: int, data: AsignacionCerrar, request: Request,
                            principal: dict = Depends(admin_required)):
    if assignment_id <= 0:
        raise HTTPException(422, "El ID debe ser positivo.")
    user_ids = _repo(request).usuarios_asignacion(assignment_id, principal["id_empresa"])
    if not _repo(request).cerrar_asignacion(
        assignment_id, principal["id_empresa"], data.estado, data.motivo, _actor(principal)
    ):
        raise HTTPException(404, "Asignación activa no encontrada en la empresa.")
    for user_id in user_ids:
        await request.app.state.connection_manager.cerrar_usuario(user_id)
    return {"id_asignacion": assignment_id, "estado": data.estado, "mensaje": "Asignación cerrada."}


@router.get("/demos", summary="Listar demos de la empresa")
def listar_demos(request: Request, principal: dict = Depends(admin_required),
                 id_vehiculo: int | None = Query(None, gt=0),
                 limit: int = Query(50, ge=1, le=100), offset: int = Query(0, ge=0)):
    return _repo(request).listar_demos_empresa(
        principal["id_empresa"], id_vehiculo, limit, offset
    )


@router.post("/demos", status_code=status.HTTP_201_CREATED, summary="Crear demo para una unidad propia",
             responses={404: {"description": "Unidad no disponible en la empresa."}})
def crear_demo(data: AdminDemoCreate, request: Request, principal: dict = Depends(admin_required)):
    # Administración opera demos solo en unidades de inventario de la empresa.
    # Los carritos vendidos y sus demos privadas son exclusivos del comprador.
    unit = _repo(request).unidad_en_empresa(
        data.id_vehiculo, principal["id_empresa"]
    )
    if not unit:
        raise HTTPException(404, "Unidad no encontrada en el inventario de la empresa.")
    result = request.app.state.demo_repository.crear_demo(
        data.id_vehiculo, data.nombre, data.descripcion or ""
    )
    demo_id = result.get("id_demo") if isinstance(result, dict) else getattr(result, "id", None)
    if demo_id:
        _repo(request).registrar_evento_auditoria(
            principal["id_empresa"], principal["id_usuario"], "CREAR", "DEMO", int(demo_id)
        )
    return result


@router.get("/demos/{demo_id}", summary="Obtener demo propia", responses={404: {"description": "No encontrada."}})
def obtener_demo(demo_id: int, request: Request, principal: dict = Depends(admin_required)):
    if demo_id <= 0:
        raise HTTPException(422, "El ID debe ser positivo.")
    row = _repo(request).demo_en_empresa(demo_id, principal["id_empresa"])
    if not row:
        raise HTTPException(404, "DEMO no encontrada en la empresa.")
    return row


@router.patch("/demos/{demo_id}", summary="Actualizar demo", responses={404: {"description": "No encontrada."}})
def actualizar_demo(demo_id: int, data: AdminDemoPatch, request: Request,
                    principal: dict = Depends(admin_required)):
    demo = _repo(request).demo_en_empresa(demo_id, principal["id_empresa"])
    if not demo:
        raise HTTPException(404, "DEMO no encontrada en la empresa.")
    values = data.model_dump(exclude_unset=True)
    if not values:
        raise HTTPException(422, "Envía al menos un campo para actualizar.")
    if request.app.state.operacion_service.tiene_demo_activa(demo["id_vehiculo"]):
        raise HTTPException(409, "No se puede editar una DEMO mientras se ejecuta.")
    request.app.state.demo_repository.actualizar_demo(
        demo_id, values.get("nombre", demo["nombre"]),
        values.get("descripcion", demo["descripcion"] or ""),
        values.get("activo", bool(demo["activo"])),
    )
    _repo(request).registrar_evento_auditoria(
        principal["id_empresa"], principal["id_usuario"], "ACTUALIZAR", "DEMO", demo_id
    )
    return obtener_demo(demo_id, request, principal)


@router.delete("/demos/{demo_id}", status_code=status.HTTP_204_NO_CONTENT,
               summary="Dar de baja lógica una demo",
               responses={404: {"description": "No encontrada."}, 409: {"description": "Está ejecutándose."}})
def baja_demo(demo_id: int, request: Request, principal: dict = Depends(admin_required)):
    demo = _repo(request).demo_en_empresa(demo_id, principal["id_empresa"])
    if not demo:
        raise HTTPException(404, "DEMO no encontrada en la empresa.")
    if request.app.state.operacion_service.tiene_demo_activa(demo["id_vehiculo"]):
        raise HTTPException(409, "No se puede dar de baja una DEMO mientras se ejecuta.")
    if not _repo(request).baja_demo(demo_id, principal["id_empresa"], _actor(principal)):
        raise HTTPException(404, "DEMO no encontrada en la empresa.")
    return Response(status_code=204)


@router.get("/demos/{demo_id}/pasos", summary="Listar pasos de una demo propia",
            responses={404: {"description": "DEMO no encontrada."}})
def listar_pasos(demo_id: int, request: Request, principal: dict = Depends(admin_required)):
    if demo_id <= 0:
        raise HTTPException(422, "El ID debe ser positivo.")
    if not _repo(request).demo_en_empresa(demo_id, principal["id_empresa"]):
        raise HTTPException(404, "DEMO no encontrada en la empresa.")
    return _repo(request).listar_pasos_demo(demo_id, principal["id_empresa"])


@router.post("/demos/{demo_id}/pasos", status_code=status.HTTP_201_CREATED,
             summary="Agregar paso ordenado a una demo",
             responses={404: {"description": "DEMO o comando no pertenece a la unidad."},
                        409: {"description": "El orden de paso ya está ocupado."}})
def agregar_paso(demo_id: int, data: AdminPasoCreate, request: Request,
                 principal: dict = Depends(admin_required)):
    demo = _repo(request).demo_en_empresa(demo_id, principal["id_empresa"])
    if not demo:
        raise HTTPException(404, "DEMO no encontrada en la empresa.")
    if not _repo(request).comando_activo_en_vehiculo(data.id_comando, demo["id_vehiculo"]):
        raise HTTPException(404, "Comando activo no pertenece a la unidad de la DEMO.")
    if request.app.state.operacion_service.tiene_demo_activa(demo["id_vehiculo"]):
        raise HTTPException(409, "No se puede editar una DEMO mientras se ejecuta.")
    result = request.app.state.demo_repository.agregar_movimiento_demo(
        demo_id, data.id_comando, data.orden, data.duracion_ms, data.pausa_ms
    )
    _repo(request).registrar_evento_auditoria(
        principal["id_empresa"], principal["id_usuario"], "AGREGAR_PASO", "DEMO", demo_id
    )
    return {"mensaje": "Paso agregado.", "demo_id": demo_id,
            "id_comando": data.id_comando, **data.model_dump()}


@router.patch("/demos/pasos/{step_id}", summary="Actualizar paso de demo",
              responses={404: {"description": "Paso no encontrado o fuera de la empresa."}})
def actualizar_paso(step_id: int, data: AdminPasoPatch, request: Request,
                     principal: dict = Depends(admin_required)):
    if step_id <= 0:
        raise HTTPException(422, "El ID debe ser positivo.")
    step = _repo(request).paso_demo_en_empresa(step_id, principal["id_empresa"])
    if not step:
        raise HTTPException(404, "Paso no encontrado en la empresa.")
    values = data.model_dump(exclude_unset=True)
    if not values:
        raise HTTPException(422, "Envía al menos un campo para actualizar.")
    command_id = values.get("id_comando", step["id_comando"])
    order = values.get("orden", step["orden"])
    duration = values.get("duracion_ms", step["duracion_ms"])
    pause = values.get("pausa_ms", step["pausa_ms"])
    if not _repo(request).comando_activo_en_vehiculo(command_id, step["id_vehiculo"]):
        raise HTTPException(404, "Comando activo no pertenece a la unidad de la DEMO.")
    if request.app.state.operacion_service.tiene_demo_activa(step["id_vehiculo"]):
        raise HTTPException(409, "No se puede editar una DEMO mientras se ejecuta.")
    request.app.state.demo_repository.actualizar_movimiento_demo(
        step_id, command_id, order, duration, pause
    )
    _repo(request).registrar_evento_auditoria(
        principal["id_empresa"], principal["id_usuario"], "ACTUALIZAR_PASO", "DEMO", step["id_demo"]
    )
    return {"id_demo_movimiento": step_id, "id_demo": step["id_demo"],
            "id_comando": command_id, "orden": order,
            "duracion_ms": duration, "pausa_ms": pause}


@router.delete("/demos/pasos/{step_id}", status_code=status.HTTP_204_NO_CONTENT,
               summary="Eliminar paso de una demo",
               responses={404: {"description": "Paso no encontrado."}, 409: {"description": "La demo está ejecutándose."}})
def eliminar_paso(step_id: int, request: Request, principal: dict = Depends(admin_required)):
    if step_id <= 0:
        raise HTTPException(422, "El ID debe ser positivo.")
    step = _repo(request).paso_demo_en_empresa(step_id, principal["id_empresa"])
    if not step:
        raise HTTPException(404, "Paso no encontrado en la empresa.")
    if request.app.state.operacion_service.tiene_demo_activa(step["id_vehiculo"]):
        raise HTTPException(409, "No se puede editar una DEMO mientras se ejecuta.")
    request.app.state.demo_repository.eliminar_movimiento_demo(step_id)
    _repo(request).registrar_evento_auditoria(
        principal["id_empresa"], principal["id_usuario"], "ELIMINAR_PASO", "DEMO", step["id_demo"]
    )
    return Response(status_code=204)


@router.get("/sesiones-invitado", summary="Listar sesiones temporales de la empresa")
def listar_sesiones(request: Request, principal: dict = Depends(admin_required),
                    estado: str | None = Query(None, pattern="^(RESERVADA|ACTIVA|FINALIZADA|EXPIRADA|REVOCADA)$"),
                    limit: int = Query(50, ge=1, le=100), offset: int = Query(0, ge=0)):
    return _repo(request).listar_sesiones_invitado(principal["id_empresa"], estado, limit, offset)


@router.post("/sesiones-invitado", status_code=status.HTTP_201_CREATED,
             summary="Reservar acceso temporal de invitado",
             description="Devuelve el token una sola vez; la base almacena solo su hash.",
             responses={400: {"description": "Comandos incompatibles."},
                        404: {"description": "Unidad o demo no disponible."},
                        409: {"description": "Unidad ya tiene sesión temporal."}})
def crear_sesion(data: SesionInvitadoCreate, request: Request,
                 principal: dict = Depends(admin_required)):
    try:
        return request.app.state.admin_service.crear_sesion_invitado(data.model_dump(), _actor(principal))
    except LookupError as exc:
        raise HTTPException(404, str(exc)) from exc
    except ValueError as exc:
        raise HTTPException(400, str(exc)) from exc


@router.patch("/sesiones-invitado/{session_id}/revocar", summary="Revocar sesión temporal")
async def revocar_sesion(session_id: int, request: Request, principal: dict = Depends(admin_required)):
    if session_id <= 0:
        raise HTTPException(422, "El ID debe ser positivo.")
    session = _repo(request).sesion_invitado_detalle(session_id, principal["id_empresa"])
    if not _repo(request).revocar_sesion_invitado(session_id, principal["id_empresa"], _actor(principal)):
        raise HTTPException(404, "Sesión activa no encontrada en la empresa.")
    if session:
        await request.app.state.operacion_service.detener_seguro(
            int(session["id_vehiculo"]), "SEGURIDAD_ADMIN"
        )
        await request.app.state.connection_manager.cerrar_sesion_invitado(session_id)
    return {"id_sesion": session_id, "estado": "REVOCADA"}


@router.patch("/sesiones-invitado/{session_id}/activar", summary="Activar sesión reservada de invitado",
              responses={404: {"description": "Sesión no reservada, vencida o ajena a la empresa."}})
def activar_sesion(session_id: int, request: Request, principal: dict = Depends(admin_required)):
    if session_id <= 0:
        raise HTTPException(422, "El ID debe ser positivo.")
    if not _repo(request).activar_sesion_invitado(session_id, principal["id_empresa"], _actor(principal)):
        raise HTTPException(404, "Sesión reservada no encontrada, vencida o fuera de la empresa.")
    return {"id_sesion": session_id, "estado": "ACTIVA"}


@router.get("/auditoria", summary="Consultar auditoría de la empresa")
def listar_auditoria(request: Request, principal: dict = Depends(admin_required),
                     entidad: str | None = Query(None, max_length=60),
                     limit: int = Query(50, ge=1, le=100), offset: int = Query(0, ge=0)):
    return _repo(request).listar_auditoria(principal["id_empresa"], entidad, limit, offset)
