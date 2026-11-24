import asyncio
import logging
from typing import Callable, Dict, List

from fastapi import WebSocket

from repositories.estado_historial_repository import EstadoHistorialRepository
from ws_manager.eventos import Evento, EventoConexion, EventoConsulta

logger = logging.getLogger(__name__)


class ConnectionManager:

    def __init__(self, estado_repo: EstadoHistorialRepository):
        self.__estado_repo = estado_repo
        self.__conexiones: Dict[int, List[WebSocket]] = {}
        self.__filtros: Dict[WebSocket, Callable[[dict], bool] | None] = {}
        self.__tipos_conexion: Dict[WebSocket, str] = {}
        self.__usuarios: Dict[WebSocket, int] = {}
        self.__sesiones_invitado: Dict[WebSocket, int] = {}

    async def connect(self, vehiculo_id: int, websocket: WebSocket, *, already_accepted: bool = False,
                      event_filter: Callable[[dict], bool] | None = None,
                      initial_state: dict | None = None,
                      connection_kind: str = "device", user_id: int | None = None,
                      guest_session_id: int | None = None):
        if not already_accepted:
            await websocket.accept()
        self.__conexiones.setdefault(vehiculo_id, []).append(websocket)
        self.__filtros[websocket] = event_filter
        self.__tipos_conexion[websocket] = connection_kind
        if user_id is not None:
            self.__usuarios[websocket] = int(user_id)
        if guest_session_id is not None:
            self.__sesiones_invitado[websocket] = int(guest_session_id)

        if initial_state is None:
            try:
                ultimo = await asyncio.to_thread(self.__estado_repo.obtener_estado, vehiculo_id)
                estado = ultimo.a_diccionario() if ultimo else {"mensaje": "Sin estado previo registrado"}
            except Exception:
                logger.exception("No se pudo consultar el estado inicial del vehículo %s", vehiculo_id)
                estado = {"mensaje": "Error al consultar estado inicial"}
        else:
            estado = initial_state

        await self.enviar_a_cliente(websocket, EventoConexion(vehiculo_id, estado))

    def disconnect(self, vehiculo_id: int, websocket: WebSocket):
        conexiones = self.__conexiones.get(vehiculo_id)
        if not conexiones:
            return
        if websocket in conexiones:
            conexiones.remove(websocket)
        self.__filtros.pop(websocket, None)
        self.__tipos_conexion.pop(websocket, None)
        self.__usuarios.pop(websocket, None)
        self.__sesiones_invitado.pop(websocket, None)
        if not conexiones:
            del self.__conexiones[vehiculo_id]

    def total_conexiones(self, vehiculo_id: int) -> int:
        """Cuántos clientes (navegadores, ESP...) escuchan a ese vehículo."""
        return len(self.__conexiones.get(vehiculo_id, []))

    def total_navegadores(self, vehiculo_id: int) -> int:
        """Número de sesiones WSS abiertas por navegadores para la unidad."""
        return sum(self.__tipos_conexion.get(socket) == "browser"
                   for socket in self.__conexiones.get(vehiculo_id, []))

    def total_dispositivos(self, vehiculo_id: int) -> int:
        """Número de ESP/dispositivos autenticados por WSS para esta unidad."""
        return sum(self.__tipos_conexion.get(socket) == "device"
                   for socket in self.__conexiones.get(vehiculo_id, []))

    def conexiones_invitado(self, session_id: int) -> int:
        return sum(session_id == self.__sesiones_invitado.get(socket)
                   for sockets in self.__conexiones.values() for socket in sockets)

    async def cerrar_usuario(self, user_id: int, code: int = 1008) -> None:
        sockets = [socket for socket, owner in self.__usuarios.items() if owner == int(user_id)]
        await self.__cerrar_sockets(sockets, code)

    async def cerrar_sesion_invitado(self, session_id: int, code: int = 1008) -> None:
        sockets = [socket for socket, current in self.__sesiones_invitado.items()
                   if current == int(session_id)]
        await self.__cerrar_sockets(sockets, code)

    async def __cerrar_sockets(self, sockets: list[WebSocket], code: int) -> None:
        for socket in sockets:
            for vehicle_id, connected in list(self.__conexiones.items()):
                if socket not in connected:
                    continue
                self.disconnect(vehicle_id, socket)
                try:
                    await socket.close(code=code, reason="Permiso revocado o sesión finalizada")
                except Exception:
                    logger.debug("El socket ya estaba cerrado")
                break

    async def enviar_a_cliente(self, websocket: WebSocket, evento: Evento):
        await websocket.send_json(evento.a_diccionario())

    async def broadcast_to_vehicle(self, evento: Evento):
        """Envía el evento a todos los clientes de ese vehículo (y solo a ellos)."""
        conexiones = list(self.__conexiones.get(evento.vehiculo_id, []))
        if not conexiones:
            return

        carga = evento.a_diccionario()
        destinos = [c for c in conexiones if self.__filtros.get(c) is None
                    or self.__filtros[c](carga)]
        resultados = await asyncio.gather(
            *(c.send_json(carga) for c in destinos), return_exceptions=True
        )
        for conexion, resultado in zip(destinos, resultados):
            if isinstance(resultado, Exception):
                self.disconnect(evento.vehiculo_id, conexion)

    async def broadcast_simulation_to_user(self, vehicle_id: int, user_id: int, payload: dict):
        """Evento virtual privado: solo a la sesión web del dueño, nunca al ESP ni a otros usuarios."""
        destinations = [socket for socket in self.__conexiones.get(int(vehicle_id), [])
                        if self.__tipos_conexion.get(socket) == "browser"
                        and self.__usuarios.get(socket) == int(user_id)]
        results = await asyncio.gather(
            *(socket.send_json(payload) for socket in destinations), return_exceptions=True
        )
        for socket, result in zip(destinations, results):
            if isinstance(result, Exception):
                self.disconnect(int(vehicle_id), socket)

    async def notificar_consulta(self, vehiculo_id: int, recurso: str, datos):
        await self.broadcast_to_vehicle(EventoConsulta(vehiculo_id, recurso, datos))
