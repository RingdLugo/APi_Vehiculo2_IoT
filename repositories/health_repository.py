from config.database import DatabaseConnection


class HealthRepository:
    """Comprueba acceso de lectura a la base sin exponer detalles de conexión."""

    def __init__(self, database: DatabaseConnection):
        self._database = database

    def database_available(self) -> bool:
        connection = None
        try:
            connection = self._database.obtener_conexion()
            with connection.cursor() as cursor:
                cursor.execute("SELECT 1 AS disponible")
                return cursor.fetchone()["disponible"] == 1
        except Exception:
            return False
        finally:
            if connection is not None:
                connection.close()
