import json

from config.database import DatabaseConnection


class SimulacionRepository:
    def __init__(self, db: DatabaseConnection):
        self._db = db

    def obtener_configuracion(self, user_id: int, vehicle_id: int):
        connection = self._db.obtener_conexion()
        try:
            with connection.cursor() as cursor:
                cursor.execute(
                    "SELECT movimientos, asignaciones FROM configuracion_simulacion "
                    "WHERE id_usuario=%s AND id_vehiculo=%s LIMIT 1",
                    (user_id, vehicle_id),
                )
                row = cursor.fetchone()
                if not row:
                    return {"configurado": False, "movimientos": [], "asignaciones": {}}
                return {"movimientos": self._decode(row["movimientos"]),
                        "asignaciones": self._decode(row["asignaciones"]), "configurado": True}
        finally:
            connection.close()

    def guardar_configuracion(self, user_id: int, vehicle_id: int, movements, bindings):
        connection = self._db.obtener_conexion()
        try:
            with connection.cursor() as cursor:
                cursor.execute(
                    "INSERT INTO configuracion_simulacion "
                    "(id_usuario,id_vehiculo,movimientos,asignaciones) VALUES (%s,%s,%s,%s) "
                    "ON DUPLICATE KEY UPDATE movimientos=VALUES(movimientos), "
                    "asignaciones=VALUES(asignaciones), actualizado_en=CURRENT_TIMESTAMP",
                    (user_id, vehicle_id, json.dumps(movements, ensure_ascii=False),
                     json.dumps(bindings, ensure_ascii=False)),
                )
            connection.commit()
        except Exception:
            connection.rollback()
            raise
        finally:
            connection.close()

    @staticmethod
    def _decode(value):
        if isinstance(value, (dict, list)):
            return value
        if isinstance(value, bytes):
            value = value.decode("utf-8")
        return json.loads(value or "{}")
