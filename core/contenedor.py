from config.database import DatabaseConnection
from repositories.comando_repository import ComandoRepository
from repositories.demo_repository import DemoRepository
from repositories.estado_historial_repository import EstadoHistorialRepository
from repositories.vehiculo_repository import VehiculoRepository
from services.eliminacion_service import EliminacionService
from services.operacion_service import OperacionService
from ws_manager.manager import ConnectionManager


class Contenedor:

    def __init__(self):
        self.db = DatabaseConnection()

        self.vehiculo_repo = VehiculoRepository(self.db)
        self.comando_repo = ComandoRepository(self.db)
        self.demo_repo = DemoRepository(self.db)
        self.estado_repo = EstadoHistorialRepository(self.db)

        self.manager = ConnectionManager(self.estado_repo)
        self.eliminacion_service = EliminacionService()
        self.operacion_service = OperacionService(
            vehiculo_repo=self.vehiculo_repo,
            comando_repo=self.comando_repo,
            demo_repo=self.demo_repo,
            estado_repo=self.estado_repo,
            manager=self.manager,
        )
