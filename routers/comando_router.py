import asyncio

from fastapi import HTTPException, status

from core.mascaras import mascara_automatica
from repositories.comando_repository import ComandoRepository
from routers.base_controller import BaseController
from services.eliminacion_service import EliminacionService
from schemas.gestion_schema import ComandoActualizar, ComandoCrear, MascaraRequest
from ws_manager.manager import ConnectionManager


class ComandoController(BaseController):

    def __init__(self, comando_repo: ComandoRepository, manager: ConnectionManager,
                 eliminacion_service: EliminacionService):
        self._comando_repo = comando_repo
        self._manager = manager
        self._eliminacion = eliminacion_service
        super().__init__(prefix="/comandos", tags=["Comandos"])

    def _registrar_rutas(self) -> None:
        r = self._ruta
        r("/vehiculo/{vehiculo_id}", self.obtener_comandos, "GET", "Listar comandos de un vehículo",
          "También se avisa por WebSocket. **SP:** `sp_obtener_comandos_vehiculo`")
        r("/", self.crear_comando, "POST", "Crear comando",
          "Asigna automáticamente una máscara según el nombre; nombres desconocidos usan máscara 0. "
          "Puede enviarse `mascara` para definir una salida explícita. **SP:** `sp_crear_comando`",
          status_code=status.HTTP_201_CREATED)
        r("/{comando_id}/actualizar", self.actualizar_comando, "POST", "Actualizar comando",
          "Recalcula automáticamente la máscara según el nombre, salvo que se envíe `mascara` "
          "explícitamente. **SP:** `sp_actualizar_comando`")
        r("/{comando_id}/eliminar", self.eliminar_comando, "POST", "Eliminar comando",
          "**SP:** `sp_eliminar_comando`")
        r("/vehiculo/{vehiculo_id}/detalle", self.obtener_detalle, "GET",
          "Listar comandos con su máscara de salida",
          "Incluye la columna `mascara` que se envía a la ESP. **SP:** `sp_obtener_comandos_detalle`")
        r("/{comando_id}/mascara", self.asignar_mascara, "POST", "Asignar máscara de salida a un comando",
          "Define qué salidas de los 74HC595 activa el comando. **SP:** `sp_actualizar_mascara_comando`",
          responses={404: {"description": "Comando no encontrado."}})

    async def obtener_comandos(self, vehiculo_id: int):
        comandos = self._serializar(
            await asyncio.to_thread(self._comando_repo.obtener_por_vehiculo, vehiculo_id))
        await self._manager.notificar_consulta(vehiculo_id, "comandos", comandos)
        return comandos

    def crear_comando(self, data: ComandoCrear):
        return self._comando_repo.crear_con_mascara(
            data.vehiculo_id, data.nombre, data.codigo, data.descripcion,
            data.mascara if data.mascara is not None else mascara_automatica(data.nombre))

    def actualizar_comando(self, comando_id: int, data: ComandoActualizar):
        resultado = self._comando_repo.actualizar(
            comando_id, data.nombre, data.codigo, data.descripcion, data.activo
        )
        mascara = data.mascara if data.mascara is not None else mascara_automatica(data.nombre)
        if not self._comando_repo.actualizar_mascara(comando_id, mascara):
            raise HTTPException(status_code=404, detail="Comando no encontrado")
        return {**resultado, "mascara": mascara}

    def eliminar_comando(self, comando_id: int):
        return self._eliminacion.eliminar(self._comando_repo, comando_id)

    def obtener_detalle(self, vehiculo_id: int):
        return self._serializar(self._comando_repo.obtener_detalle_por_vehiculo(vehiculo_id))

    def asignar_mascara(self, comando_id: int, data: MascaraRequest):
        if not self._comando_repo.actualizar_mascara(comando_id, data.mascara):
            raise HTTPException(status_code=404, detail="Comando no encontrado")
        return {"mensaje": "Máscara actualizada exitosamente",
                "comando_id": comando_id, "mascara": data.mascara}
