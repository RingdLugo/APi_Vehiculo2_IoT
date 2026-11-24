import logging
import os
import asyncio
import hashlib
import time
from collections import defaultdict, deque

import pymysql
from fastapi import FastAPI, Request, WebSocket, WebSocketDisconnect
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from core.contenedor import Contenedor
from repositories.administracion_repository import AdministracionRepository
from repositories.auth_repository import AuthRepository
from repositories.health_repository import HealthRepository
from routers.administracion_router import router as administracion_router
from routers.auth_router import router as auth_router
from routers.base_controller import BaseController
from routers.comando_router import ComandoController
from repositories.cuenta_repository import CuentaRepository
from repositories.demo_editor_repository import DemoEditorRepository
from repositories.simulacion_repository import SimulacionRepository
from routers.cuenta_router import router as cuenta_router
from routers.demo_router import DemoController
from routers.guest_router import router as guest_router
from routers.health_router import router as health_router
from routers.vehiculo_router import VehiculoController
from routers.ws_router import WebSocketController
from services.administracion_service import AdministracionService
from services.auth_service import AuthService
from services.health_service import HealthService
from services.operacion_service import MovimientoLimitadoError
from ws_manager.eventos import EventoEco

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s: %(message)s")
logger = logging.getLogger("api_vehiculo_iot")


class AplicacionAPI:
    """Construye y configura la aplicación FastAPI."""

    def __init__(self, contenedor: Contenedor | None = None):
        self._c = contenedor or Contenedor()
        self.app = FastAPI(
            title="API Vehículo IoT",
            description=("API desarrollada con FastAPI, Programación Orientada a Objetos, Amazon RDS "
                         "(Stored Procedures) y WebSockets para la gestión de vehículos IoT."),
            version="1.6.0",
        )
        self._request_buckets: dict[tuple[str, str], deque[float]] = defaultdict(deque)
        self.app.state.auth_service = AuthService(AuthRepository(self._c.db))
        self.app.state.auth_repository = AuthRepository(self._c.db)
        self.app.state.health_service = HealthService(HealthRepository(self._c.db))
        self.app.state.admin_repository = AdministracionRepository(self._c.db)
        self.app.state.admin_service = AdministracionService(self.app.state.admin_repository)
        self.app.state.cuenta_repository = CuentaRepository(self._c.db)
        self.app.state.demo_editor_repository = DemoEditorRepository(self._c.db)
        self.app.state.simulacion_repository = getattr(
            self._c, "simulacion_repo", SimulacionRepository(self._c.db)
        )
        self.app.state.demo_repository = self._c.demo_repo
        self.app.state.command_repository = self._c.comando_repo
        self.app.state.state_repository = self._c.estado_repo
        self.app.state.operacion_service = self._c.operacion_service
        self.app.state.vehicle_repository = self._c.vehiculo_repo
        self.app.state.connection_manager = self._c.manager
        self.app.include_router(auth_router)
        self.app.include_router(administracion_router)
        self.app.include_router(guest_router)
        self.app.include_router(cuenta_router)
        self.app.include_router(health_router)
        self.app.middleware("http")(self._proteger_rutas_legacy)
        self.app.middleware("http")(self._limitar_solicitudes_sensibles)
        self._configurar_cors()
        self._registrar_controladores()
        self.app.add_api_websocket_route("/ws/cuenta/vehiculo/{vehicle_id}", self.websocket_cuenta,
                                         name="websocket_cuenta")
        self._registrar_manejadores_errores()
        self.app.add_api_route("/", self.root, methods=["GET"], tags=["General"])
        self._registrar_ciclo_sesiones_invitado()

    def _registrar_ciclo_sesiones_invitado(self) -> None:
        async def cleanup_expired_sessions():
            while True:
                try:
                    expired = await asyncio.to_thread(
                        self.app.state.admin_repository.expirar_sesiones_publicas
                    )
                    for session in expired:
                        vehicle_id = int(session["id_vehiculo"])
                        await self.app.state.operacion_service.detener_seguro(
                            vehicle_id, "SEGURIDAD_EXPIRACION_INVITADO"
                        )
                        await self.app.state.connection_manager.cerrar_sesion_invitado(
                            int(session["id_sesion"])
                        )
                except asyncio.CancelledError:
                    raise
                except Exception:
                    logger.exception("No se pudieron limpiar las sesiones temporales vencidas")
                await asyncio.sleep(5)

        @self.app.on_event("startup")
        async def start_guest_session_cleanup():
            self.app.state.guest_cleanup_task = asyncio.create_task(cleanup_expired_sessions())

        @self.app.on_event("shutdown")
        async def stop_guest_session_cleanup():
            task = getattr(self.app.state, "guest_cleanup_task", None)
            if task:
                task.cancel()
                try:
                    await task
                except asyncio.CancelledError:
                    pass

    async def _limitar_solicitudes_sensibles(self, request: Request, call_next):
        """Límites básicos por IP para credenciales, alta y reservas públicas."""
        limits = {
            ("POST", "/auth/token"): (15, 60),
            ("POST", "/auth/registro-comprador"): (5, 60),
            ("POST", "/guest/sesiones"): (5, 60),
        }
        rule = limits.get((request.method.upper(), request.url.path.rstrip("/")))
        route_path = request.url.path.rstrip("/")
        if request.method.upper() == "POST" and route_path.endswith("/simulacion/ejecutar"):
            rule = (50, 10)
        elif request.method.upper() == "PUT" and route_path.endswith("/simulacion"):
            rule = (20, 60)
        if rule:
            maximum, period = rule
            host = request.client.host if request.client else "unknown"
            bucket = self._request_buckets[(request.url.path, host)]
            now = time.monotonic()
            while bucket and now - bucket[0] >= period:
                bucket.popleft()
            if len(bucket) >= maximum:
                return JSONResponse(status_code=429, content={
                    "detail": "Demasiadas solicitudes; vuelve a intentarlo más tarde."
                }, headers={"Retry-After": str(period)})
            bucket.append(now)
        return await call_next(request)

    async def _proteger_rutas_legacy(self, request: Request, call_next):
        """Mantiene rutas REST anteriores, pero aplica ahora identidad y alcance de empresa/unidad."""
        if request.method.upper() == "OPTIONS":
            return await call_next(request)
        path = request.url.path.rstrip("/")
        if not any(path == prefix or path.startswith(prefix + "/")
                   for prefix in ("/vehiculos", "/comandos", "/demos")):
            return await call_next(request)

        authorization = request.headers.get("authorization", "")
        scheme, _, token = authorization.partition(" ")
        if scheme.lower() != "bearer" or not token:
            return JSONResponse(status_code=401, content={"detail": "Se requiere autenticación Bearer."},
                                headers={"WWW-Authenticate": "Bearer"})
        principal = await asyncio.to_thread(self.app.state.auth_service.autenticar_token, token)
        if not principal:
            return JSONResponse(status_code=401, content={"detail": "La sesión no es válida o venció."},
                                headers={"WWW-Authenticate": "Bearer"})
        roles = set(principal.get("roles", []))
        admin = "ADMINISTRADOR" in roles
        if not admin and "USUARIO" not in roles:
            return JSONResponse(status_code=403, content={"detail": "El rol no permite acceso a estas rutas."})
        method = request.method.upper()
        parts = [part for part in path.split("/") if part]

        async def require_vehicle(vehicle_id: int):
            allowed = await asyncio.to_thread(
                self.app.state.cuenta_repository.puede_operar,
                principal["id_usuario"], principal["id_empresa"], list(roles), vehicle_id,
            )
            if not allowed:
                return JSONResponse(status_code=404, content={"detail": "Vehículo no disponible para esta cuenta."})
            return None

        def forbidden():
            return JSONResponse(status_code=403, content={"detail": "La operación requiere rol administrador."})

        if parts[0] == "vehiculos":
            if len(parts) == 1:
                return forbidden()
            try: vehicle_id = int(parts[1])
            except ValueError: return JSONResponse(status_code=404, content={"detail": "Vehículo no disponible."})
            if method == "GET":
                error = await require_vehicle(vehicle_id)
                return error or await call_next(request)
            if method == "POST" and len(parts) >= 3 and parts[2] in {"movimiento", "mensaje", "demo"}:
                if parts[2] == "mensaje" and not admin: return forbidden()
                error = await require_vehicle(vehicle_id)
                return error or await call_next(request)
            if admin and method == "POST" and len(parts) >= 3 and parts[2] in {"actualizar", "eliminar"}:
                error = await require_vehicle(vehicle_id)
                return error or await call_next(request)
            return forbidden()

        if parts[0] == "comandos":
            if method != "GET" or len(parts) < 3 or parts[1] != "vehiculo":
                return forbidden()
            try: vehicle_id = int(parts[2])
            except ValueError: return JSONResponse(status_code=404, content={"detail": "Vehículo no disponible."})
            error = await require_vehicle(vehicle_id)
            return error or await call_next(request)

        if parts[0] == "demos":
            if method != "GET" or len(parts) < 3 or parts[1] != "vehiculo":
                return forbidden()
            try: vehicle_id = int(parts[2])
            except ValueError: return JSONResponse(status_code=404, content={"detail": "Vehículo no disponible."})
            error = await require_vehicle(vehicle_id)
            return error or await call_next(request)

        return forbidden()

    def _configurar_cors(self) -> None:
        origenes = [o.strip() for o in os.getenv(
            "CORS_ORIGINS", "https://controlwish.duckdns.org"
        ).split(",") if o.strip()]
        self.app.add_middleware(
            CORSMiddleware,
            allow_origins=origenes,
            allow_credentials=origenes != ["*"],
            allow_methods=["*"],
            allow_headers=["*"],
        )

    def _registrar_controladores(self) -> None:
        c = self._c
        controladores: list[BaseController] = [
            VehiculoController(c.vehiculo_repo, c.comando_repo, c.estado_repo, c.demo_repo,
                               c.operacion_service, c.eliminacion_service),
            ComandoController(c.comando_repo, c.manager, c.eliminacion_service),
            DemoController(c.demo_repo, c.manager, c.eliminacion_service),
            WebSocketController(c.vehiculo_repo, c.manager),
        ]
        for controlador in controladores:
            controlador.registrar(self.app)

    def _registrar_manejadores_errores(self) -> None:
        self.app.add_exception_handler(pymysql.err.IntegrityError, self._integridad_handler)
        self.app.add_exception_handler(pymysql.MySQLError, self._mysql_handler)

    async def websocket_cuenta(self, websocket: WebSocket, vehicle_id: int):
        """Canal WSS autenticado para usuarios, administradores e invitados temporales.

        El navegador envía la credencial en el primer mensaje para no incluirla en la URL.
        Revalida sesión, asignación y permisos durante toda la conexión.
        """
        if vehicle_id <= 0:
            await websocket.close(code=1008)
            return
        await websocket.accept()
        conectado = False
        try:
            auth_message = await asyncio.wait_for(websocket.receive_json(), timeout=10)
            principal = None
            guest = False
            if isinstance(auth_message, dict) and auth_message.get("access_token"):
                principal = await asyncio.to_thread(
                    self.app.state.auth_service.autenticar_token, auth_message["access_token"]
                )
                if not principal:
                    await websocket.close(code=1008)
                    return
                if not set(principal.get("roles", [])).intersection({"ADMINISTRADOR", "USUARIO"}):
                    await websocket.close(code=1008)
                    return
                permitted = await asyncio.to_thread(
                    self.app.state.cuenta_repository.puede_operar,
                    principal["id_usuario"], principal["id_empresa"], principal["roles"], vehicle_id,
                )
            elif isinstance(auth_message, dict) and auth_message.get("guest_token"):
                token_hash = hashlib.sha256(auth_message["guest_token"].encode()).hexdigest()
                session = await asyncio.to_thread(
                    self.app.state.admin_repository.sesion_invitado_por_token, token_hash
                )
                permitted = bool(session and int(session["id_vehiculo"]) == vehicle_id)
                guest = True
            else:
                await websocket.close(code=1008)
                return
            if not permitted:
                await websocket.close(code=1008)
                return
            vehicle = await asyncio.to_thread(self._c.vehiculo_repo.obtener_por_id, vehicle_id)
            if not vehicle or not vehicle.esta_activo():
                await websocket.close(code=1008)
                return

            event_filter = None
            initial_state = None
            if guest:
                allowed_commands = set(session["comandos_permitidos"])
                stop_id = await asyncio.to_thread(
                    self.app.state.admin_repository.comando_detener_id, vehicle_id
                )
                if stop_id is not None:
                    allowed_commands.add(stop_id)
                allowed_demo = int(session["id_demo"]) if session.get("id_demo") is not None else None
                def event_filter(event: dict) -> bool:
                    if event.get("tipo") == "movimiento_individual":
                        return int(event.get("comando_id") or 0) in allowed_commands
                    if str(event.get("tipo", "")).startswith("demo_"):
                        return allowed_demo is not None and int(event.get("demo_id") or 0) == allowed_demo
                    return False
                initial_state = {"mensaje": "Acceso temporal autorizado"}
            if guest and self._c.manager.conexiones_invitado(int(session["id_sesion"])) > 0:
                await websocket.close(code=1013, reason="La sesión temporal ya está conectada en otro navegador")
                return
            await self._c.manager.connect(vehicle_id, websocket, already_accepted=True,
                                          event_filter=event_filter, initial_state=initial_state,
                                          connection_kind="browser",
                                          user_id=principal["id_usuario"] if principal else None,
                                          guest_session_id=int(session["id_sesion"]) if guest else None)
            conectado = True
            while True:
                try:
                    text = await asyncio.wait_for(websocket.receive_text(), timeout=10)
                except asyncio.TimeoutError:
                    # Revalida vencimiento, revocación y asignación mientras el socket sigue abierto.
                    if guest:
                        current = await asyncio.to_thread(
                            self.app.state.admin_repository.sesion_invitado_por_token, token_hash
                        )
                        still_allowed = bool(current and int(current["id_vehiculo"]) == vehicle_id)
                    else:
                        current = await asyncio.to_thread(
                            self.app.state.auth_service.autenticar_token, auth_message["access_token"]
                        )
                        still_allowed = bool(current and set(current.get("roles", [])).intersection(
                            {"ADMINISTRADOR", "USUARIO"}))
                        if still_allowed:
                            still_allowed = await asyncio.to_thread(
                                self.app.state.cuenta_repository.puede_operar,
                                current["id_usuario"], current["id_empresa"], current["roles"], vehicle_id,
                            )
                    if not still_allowed:
                        await websocket.close(code=1008)
                        return
                    continue
                # Revalidar también al recibir actividad evita que un cliente mantenga
                # abierto un socket revocado enviando mensajes para impedir el timeout.
                if guest:
                    current = await asyncio.to_thread(
                        self.app.state.admin_repository.sesion_invitado_por_token, token_hash
                    )
                    still_allowed = bool(current and int(current["id_vehiculo"]) == vehicle_id)
                else:
                    current = await asyncio.to_thread(
                        self.app.state.auth_service.autenticar_token, auth_message["access_token"]
                    )
                    still_allowed = bool(current and set(current.get("roles", [])).intersection(
                        {"ADMINISTRADOR", "USUARIO"}))
                    if still_allowed:
                        still_allowed = await asyncio.to_thread(
                            self.app.state.cuenta_repository.puede_operar,
                            current["id_usuario"], current["id_empresa"], current["roles"], vehicle_id,
                        )
                if not still_allowed:
                    await websocket.close(code=1008)
                    return
                # El canal de control web es de salida; texto arbitrario no se interpreta como orden.
                if not guest:
                    await self._c.manager.enviar_a_cliente(websocket, EventoEco(vehicle_id, text))
        except (asyncio.TimeoutError, WebSocketDisconnect):
            return
        except Exception:
            logger.exception("Falló la autorización WSS del vehículo %s", vehicle_id)
            try:
                await websocket.close(code=1011)
            except Exception:
                pass
        finally:
            if conectado:
                self._c.manager.disconnect(vehicle_id, websocket)
                if guest and self._c.manager.conexiones_invitado(int(session["id_sesion"])) == 0:
                    closed = await asyncio.to_thread(
                        self.app.state.admin_repository.finalizar_sesion_publica,
                        int(session["id_sesion"]), token_hash, "FINALIZADA",
                    )
                    if closed:
                        await self.app.state.operacion_service.detener_seguro(
                            vehicle_id, "SEGURIDAD_DESCONEXION_INVITADO"
                        )

    @staticmethod
    async def _integridad_handler(request: Request, exc: pymysql.err.IntegrityError):
        return JSONResponse(status_code=409, content={
            "detail": "La operación viola una restricción de la base de datos "
                      "(dato duplicado o referencia inválida)."})

    @staticmethod
    async def _mysql_handler(request: Request, exc: pymysql.MySQLError):
        codigo = exc.args[0] if exc.args and isinstance(exc.args[0], int) else None
        if codigo == 1644 and len(exc.args) > 1:
            return JSONResponse(status_code=400, content={"detail": str(exc.args[1])})
        if codigo in (1305, 1054):
            logger.error("Base de datos desactualizada: %s", exc)
            return JSONResponse(status_code=500, content={"detail": (
                f"El esquema de la base de datos no es compatible: "
                f"{exc.args[1] if len(exc.args) > 1 else exc}. "
                "Verifica que RDS tenga la columna comandos.mascara y los procedimientos "
                "almacenados requeridos.")})
        logger.error("Error de base de datos: %s", exc)
        return JSONResponse(status_code=500,
                            content={"detail": "Error interno en el servidor de base de datos."})

    @staticmethod
    def root():
        return {
            "mensaje": "API FastAPI de Vehículos IoT disponible",
            "documentacion": "/docs",
            "websocket_endpoint": "/ws/cuenta/vehiculo/{vehicle_id}",
            "websocket_device_endpoint": "/ws/vehiculo/{vehiculo_id} (requiere token de dispositivo)",
        }


app = AplicacionAPI().app
