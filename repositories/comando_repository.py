from core.mascaras import mascara_automatica
from models.entidades import Comando
from repositories.base_repository import RepositorioCRUD


class ComandoRepository(RepositorioCRUD):
    @property
    def entidad(self) -> str:
        return "comando"

    def construir(self, fila: dict) -> Comando:
        return Comando(fila)

    def obtener_por_vehiculo(self, vehiculo_id: int) -> list[Comando]:
        """sp_obtener_comandos_vehiculo"""
        return self._listar("sp_obtener_comandos_vehiculo", (vehiculo_id,))

    def obtener_detalle_por_vehiculo(self, vehiculo_id: int) -> list[Comando]:
        """sp_obtener_comandos_detalle (incluye la máscara de salida del hardware)."""
        comandos = self._listar("sp_obtener_comandos_detalle", (vehiculo_id,))
        completos = []
        for comando in comandos:
            if comando.mascara is None:
                mascara = mascara_automatica(comando.nombre)
                if not self.actualizar_mascara(comando.id, mascara):
                    raise RuntimeError(
                        f"No se pudo guardar la máscara automática del comando {comando.id}."
                    )
                completos.append(Comando({**comando.a_diccionario(), "mascara": mascara}))
            else:
                completos.append(comando)
        return completos

    def actualizar_mascara(self, comando_id: int, mascara: int) -> bool:
        """sp_actualizar_mascara_comando. Devuelve False si el comando no existe."""
        fila = self._escribir("sp_actualizar_mascara_comando", (comando_id, mascara), devolver=True)
        return bool(fila and fila.get("existe"))

    def crear_con_mascara(self, vehiculo_id: int, nombre: str, codigo: int,
                          descripcion: str, mascara: int):
        """Crea el comando y le asigna su máscara.

        El comando recién creado se ubica por (vehículo, código), que es único,
        sin depender de lo que devuelva sp_crear_comando.
        """
        resultado = self.crear(vehiculo_id, nombre, codigo, descripcion)
        nuevo = next((c for c in self.obtener_detalle_por_vehiculo(vehiculo_id)
                      if c.codigo == codigo), None)
        if nuevo is None or not self.actualizar_mascara(nuevo.id, mascara):
            raise RuntimeError("El comando se creó pero no se pudo asignar su máscara. "
                               "Asígnala con POST /comandos/{id}/mascara.")
        if isinstance(resultado, dict):
            resultado = {**resultado, "mascara": mascara}
        return resultado

    def crear(self, vehiculo_id: int, nombre: str, codigo: int, descripcion: str):
        """sp_crear_comando"""
        return self._escribir("sp_crear_comando", (vehiculo_id, nombre, codigo, descripcion), devolver=True)

    def actualizar(self, comando_id: int, nombre: str, codigo: int, descripcion: str, activo: bool):
        """sp_actualizar_comando"""
        self._escribir("sp_actualizar_comando", (comando_id, nombre, codigo, descripcion, activo))
        return {"mensaje": "Comando actualizado exitosamente"}

    def eliminar(self, identificador: int) -> dict:
        """sp_eliminar_comando"""
        self._escribir("sp_eliminar_comando", (identificador,))
        return {"mensaje": "Comando eliminado exitosamente"}
