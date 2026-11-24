from config.database import DatabaseConnection


class CuentaRepository:
    """Resuelve el alcance de unidades del principal autenticado."""

    def __init__(self, db: DatabaseConnection):
        self._db = db

    def unidades(self, user_id: int, company_id: int, roles: list[str]):
        if "ADMINISTRADOR" in roles:
            sql = """SELECT v.id_vehiculo,v.nombre,v.modelo,v.descripcion,v.microcontrolador,
                            v.activo,i.estado AS estado_inventario,vm.id_modelo
                     FROM inventario_vehiculos i JOIN vehiculos v ON v.id_vehiculo=i.id_vehiculo
                     LEFT JOIN vehiculos_modelos vm ON vm.id_vehiculo=v.id_vehiculo
                     WHERE i.id_empresa=%s AND i.estado='EN_INVENTARIO' AND v.activo=1
                     ORDER BY v.id_vehiculo"""
            params = (company_id,)
        else:
            sql = """SELECT DISTINCT v.id_vehiculo,v.nombre,v.modelo,v.descripcion,
                            v.microcontrolador,v.activo,i.estado AS estado_inventario,
                            vm.id_modelo
                     FROM usuarios_clientes uc
                     JOIN clientes c ON c.id_cliente=uc.id_cliente
                     JOIN asignaciones_vehiculo a ON a.id_cliente=c.id_cliente
                     JOIN inventario_vehiculos i ON i.id_inventario=a.id_inventario
                     JOIN vehiculos v ON v.id_vehiculo=a.id_vehiculo
                     LEFT JOIN vehiculos_modelos vm ON vm.id_vehiculo=v.id_vehiculo
                     WHERE uc.id_usuario=%s AND uc.estado='ACTIVO'
                       AND c.id_empresa=%s AND c.estado='ACTIVO'
                       AND a.estado='ACTIVA'
                       AND (i.estado='EN_INVENTARIO' OR (i.estado='VENDIDO' AND v.microcontrolador='SIMULADO'))
                       AND v.activo=1
                     ORDER BY v.id_vehiculo"""
            params = (user_id, company_id)
        connection = self._db.obtener_conexion()
        try:
            with connection.cursor() as cursor:
                cursor.execute(sql, params)
                return cursor.fetchall()
        finally:
            connection.close()

    def puede_operar(self, user_id: int, company_id: int, roles: list[str], vehicle_id: int) -> bool:
        if "ADMINISTRADOR" in roles:
            sql = """SELECT 1 FROM inventario_vehiculos i
                     JOIN vehiculos v ON v.id_vehiculo=i.id_vehiculo
                     WHERE i.id_empresa=%s AND i.id_vehiculo=%s
                AND i.estado='EN_INVENTARIO' AND v.activo=1
                AND NOT EXISTS (
                  SELECT 1 FROM sesiones_invitado s
                  WHERE s.id_vehiculo=i.id_vehiculo AND s.estado IN ('RESERVADA','ACTIVA')
                    AND s.expira_en>CURRENT_TIMESTAMP
                ) LIMIT 1"""
            params = (company_id, vehicle_id)
        else:
            sql = """SELECT 1 FROM usuarios_clientes uc
                     JOIN clientes c ON c.id_cliente=uc.id_cliente
                     JOIN asignaciones_vehiculo a ON a.id_cliente=c.id_cliente
                     JOIN inventario_vehiculos i ON i.id_inventario=a.id_inventario
                     JOIN vehiculos v ON v.id_vehiculo=a.id_vehiculo
                     WHERE uc.id_usuario=%s AND uc.estado='ACTIVO'
                       AND c.id_empresa=%s AND c.estado='ACTIVO'
                       AND a.estado='ACTIVA'
                       AND (i.estado='EN_INVENTARIO' OR (i.estado='VENDIDO' AND v.microcontrolador='SIMULADO'))
                       AND v.activo=1 AND a.id_vehiculo=%s LIMIT 1"""
            params = (user_id, company_id, vehicle_id)
        connection = self._db.obtener_conexion()
        try:
            with connection.cursor() as cursor:
                cursor.execute(sql, params)
                return cursor.fetchone() is not None
        finally:
            connection.close()
