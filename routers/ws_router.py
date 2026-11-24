import asyncio
import hmac
import logging
import os

from fastapi import WebSocket, WebSocketDisconnect

from repositories.vehiculo_repository import VehiculoRepository
from routers.base_controller import BaseController
from ws_manager.eventos import EventoEco
from ws_manager.manager import ConnectionManager

logger = logging.getLogger(__name__)


class WebSocketController(BaseController):
    """Canal WebSocket para monitorear un vehículo en tiempo real."""

    def __init__(self, vehiculo_repo: VehiculoRepository, manager: ConnectionManager):
        self._vehiculo_repo = vehiculo_repo
        self._manager = manager
        super().__init__(prefix="", tags=["WebSocket"])

    def _registrar_rutas(self) -> None:
        self._router.add_api_websocket_route("/ws/vehiculo/{vehiculo_id}", self.websocket_vehiculo)

    async def websocket_vehiculo(self, websocket: WebSocket, vehiculo_id: int):
        """WSS autenticado de dispositivo; requiere IOT_DEVICE_TOKEN_<id> en el primer JSON."""
        # Credencial distinta por unidad: el token de un dispositivo no abre otro vehículo.
        configured_token = os.getenv(f"IOT_DEVICE_TOKEN_{vehiculo_id}", "")
        if not configured_token:
            await websocket.close(code=1011, reason="Autenticación de dispositivo no configurada")
            return
        await websocket.accept()
        try:
            payload = await asyncio.wait_for(websocket.receive_json(), timeout=8)
        except (asyncio.TimeoutError, WebSocketDisconnect, ValueError):
            await websocket.close(code=1008, reason="Autenticación requerida")
            return
        supplied_token = payload.get("device_token") if isinstance(payload, dict) else None
        if not isinstance(supplied_token, str) or not hmac.compare_digest(supplied_token, configured_token):
            await websocket.close(code=1008, reason="Dispositivo no autorizado")
            return
        try:
            vehiculo = await asyncio.to_thread(self._vehiculo_repo.obtener_por_id, vehiculo_id)
        except Exception:
            logger.exception("No se pudo validar el vehículo %s en el WebSocket", vehiculo_id)
            await websocket.close(code=1011)
            return
        if not vehiculo or not vehiculo.esta_activo():
            await websocket.close(code=1008)
            return
        if str(vehiculo.obtener("microcontrolador", "")).upper() == "SIMULADO":
            await websocket.close(code=1008, reason="Los carritos simulados no aceptan conexiones de hardware")
            return

        await self._manager.connect(vehiculo_id, websocket, already_accepted=True, connection_kind="device")
        try:
            while True:
                texto = await websocket.receive_text()
                # No registrar el contenido: los mensajes podrían contener información sensible.
                await self._manager.enviar_a_cliente(websocket, EventoEco(vehiculo_id, texto))
        except WebSocketDisconnect:
            pass
        finally:
            self._manager.disconnect(vehiculo_id, websocket)
