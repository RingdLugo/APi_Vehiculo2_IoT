import logging

from repositories.base_repository import RepositorioCRUD

logger = logging.getLogger(__name__)


class EliminacionService:

    def eliminar(self, repositorio: RepositorioCRUD, identificador: int) -> dict:
        if not isinstance(repositorio, RepositorioCRUD):
            raise TypeError("Se requiere un repositorio que implemente RepositorioCRUD.")
        logger.info("Eliminando %s con id %s", repositorio.entidad, identificador)
        return repositorio.eliminar(identificador)
