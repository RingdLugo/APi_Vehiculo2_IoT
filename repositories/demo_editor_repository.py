import json

from config.database import DatabaseConnection


class DemoEditorRepository:
    """Edición transaccional de secuencias privadas; valida dueño y capacidad en RDS."""

    MAX_PASOS = 20
    MAX_PASO_MS = 10_000
    MAX_TOTAL_MS = 60_000

    def __init__(self, db: DatabaseConnection):
        self._db = db

    def es_propietario(self, demo_id: int, vehicle_id: int, user_id: int) -> bool:
        cn = self._db.obtener_conexion()
        try:
            with cn.cursor() as cur:
                cur.execute(
                    """SELECT 1 FROM demos d JOIN permisos_demos p ON p.id_demo=d.id_demo
                       WHERE d.id_demo=%s AND d.id_vehiculo=%s AND d.activo=1
                         AND p.id_usuario=%s AND p.estado='ACTIVO'
                         AND (p.vigente_hasta IS NULL OR p.vigente_hasta>CURRENT_TIMESTAMP)
                       LIMIT 1""", (demo_id, vehicle_id, user_id)
                )
                return cur.fetchone() is not None
        finally:
            cn.close()

    def crear_demo_privada(self, vehicle_id: int, user_id: int, company_id: int,
                           name: str, description: str, allow_admin: bool = False):
        cn = self._db.obtener_conexion()
        try:
            cn.begin()
            with cn.cursor() as cur:
                if allow_admin:
                    cur.execute(
                        """SELECT 1 FROM inventario_vehiculos i
                           JOIN vehiculos v ON v.id_vehiculo=i.id_vehiculo
                           WHERE i.id_empresa=%s AND i.id_vehiculo=%s
                             AND i.estado='EN_INVENTARIO' AND v.activo=1
                             AND v.microcontrolador='SIMULADO' FOR UPDATE""",
                        (company_id, vehicle_id),
                    )
                else:
                    cur.execute(
                        """SELECT 1 FROM usuarios_clientes uc
                           JOIN clientes c ON c.id_cliente=uc.id_cliente
                           JOIN asignaciones_vehiculo a ON a.id_cliente=c.id_cliente
                           JOIN inventario_vehiculos i ON i.id_inventario=a.id_inventario
                           JOIN vehiculos v ON v.id_vehiculo=a.id_vehiculo
                           WHERE uc.id_usuario=%s AND uc.estado='ACTIVO' AND c.id_empresa=%s
                             AND c.estado='ACTIVO' AND a.id_vehiculo=%s AND a.estado='ACTIVA'
                             AND (i.estado='EN_INVENTARIO' OR
                                  (i.estado='VENDIDO' AND v.microcontrolador='SIMULADO')) AND v.activo=1
                           FOR UPDATE""", (user_id, company_id, vehicle_id)
                    )
                if not cur.fetchone():
                    raise LookupError("Solo el comprador asignado puede crear una DEMO para su carrito.")
                cur.execute("INSERT INTO demos (id_vehiculo,nombre,descripcion,activo) VALUES (%s,%s,%s,1)",
                            (vehicle_id, name, description or None))
                demo_id = cur.lastrowid
                cur.execute("INSERT INTO permisos_demos (id_demo,id_usuario) VALUES (%s,%s)",
                            (demo_id, user_id))
                cur.execute(
                    """INSERT INTO auditoria_administracion
                       (id_empresa,id_usuario,accion,entidad,id_entidad,resultado,origen,metadatos)
                       VALUES (%s,%s,'CREAR','DEMO',%s,'OK','API_CUENTA',JSON_OBJECT('tipo','PRIVADA'))""",
                    (company_id, user_id, str(demo_id)),
                )
            cn.commit()
            return {"id_demo": demo_id, "id_vehiculo": vehicle_id, "nombre": name,
                    "descripcion": description, "activo": 1, "tipo": "PRIVADA"}
        except Exception:
            cn.rollback()
            raise
        finally:
            cn.close()

    def guardar_demo_privada(self, demo_id: int, vehicle_id: int, user_id: int, company_id: int,
                             name: str, description: str, steps: list[dict]):
        if len(steps) > self.MAX_PASOS:
            raise ValueError(f"La DEMO admite hasta {self.MAX_PASOS} pasos.")
        total_ms = sum(int(s["duracion_ms"]) + int(s.get("pausa_ms", 0)) for s in steps)
        if total_ms > self.MAX_TOTAL_MS:
            raise ValueError(f"La duración total no puede superar {self.MAX_TOTAL_MS // 1000} segundos.")
        if any(int(s["duracion_ms"]) > self.MAX_PASO_MS for s in steps):
            raise ValueError(f"Cada paso admite hasta {self.MAX_PASO_MS // 1000} segundos.")
        cn = self._db.obtener_conexion()
        try:
            cn.begin()
            with cn.cursor() as cur:
                cur.execute(
                    """SELECT d.id_demo FROM demos d JOIN permisos_demos p ON p.id_demo=d.id_demo
                       JOIN inventario_vehiculos i ON i.id_vehiculo=d.id_vehiculo
                       JOIN vehiculos_modelos vm ON vm.id_vehiculo=d.id_vehiculo
                       WHERE d.id_demo=%s AND d.id_vehiculo=%s AND d.activo=1
                         AND i.id_empresa=%s
                         AND p.id_usuario=%s AND p.estado='ACTIVO'
                         AND (p.vigente_hasta IS NULL OR p.vigente_hasta>CURRENT_TIMESTAMP)
                       FOR UPDATE""", (demo_id, vehicle_id, company_id, user_id)
                )
                if not cur.fetchone():
                    raise LookupError("DEMO privada no encontrada para esta cuenta.")
                cur.execute("SELECT 1 FROM demos WHERE id_demo=%s AND id_vehiculo=%s FOR UPDATE",
                            (demo_id, vehicle_id))
                if not cur.fetchone():
                    raise LookupError("DEMO no disponible para esta unidad.")
                if steps:
                    ids = [int(step["id_comando"]) for step in steps]
                    marks = ",".join(["%s"] * len(ids))
                    cur.execute(
                        f"""SELECT c.id_comando FROM comandos c
                           JOIN vehiculos_modelos vm ON vm.id_vehiculo=c.id_vehiculo
                           JOIN comandos_catalogo x ON x.id_comando=c.id_comando
                           JOIN capacidades_modelo cap ON cap.id_modelo=vm.id_modelo
                             AND cap.id_catalogo_comando=x.id_catalogo_comando
                           WHERE c.id_vehiculo=%s AND c.activo=1 AND cap.habilitada=1
                             AND c.id_comando IN ({marks})""",
                        (vehicle_id, *ids),
                    )
                    allowed = {int(row["id_comando"]) for row in cur.fetchall()}
                    if allowed != set(ids):
                        raise ValueError("Cada comando debe pertenecer a la unidad y estar habilitado en su modelo.")
                    cur.execute(
                        f"""SELECT c.id_comando,cap.duracion_max_ms FROM comandos c
                           JOIN comandos_catalogo bridge ON bridge.id_comando=c.id_comando
                           JOIN capacidades_modelo cap ON cap.id_catalogo_comando=bridge.id_catalogo_comando
                           JOIN vehiculos_modelos vm ON vm.id_modelo=cap.id_modelo
                           WHERE vm.id_vehiculo=%s AND c.id_vehiculo=vm.id_vehiculo
                             AND cap.habilitada=1 AND c.activo=1
                             AND c.id_comando IN ({marks})""",
                        (vehicle_id, *ids),
                    )
                    maximums = {int(row["id_comando"]): row["duracion_max_ms"] for row in cur.fetchall()}
                    for step in steps:
                        ceiling = maximums.get(int(step["id_comando"]))
                        if ceiling is not None and int(step["duracion_ms"]) > int(ceiling):
                            raise ValueError("La duración supera el máximo definido para la capacidad del modelo.")
                cur.execute("UPDATE demos SET nombre=%s,descripcion=%s WHERE id_demo=%s AND id_vehiculo=%s",
                            (name, description or None, demo_id, vehicle_id))
                cur.execute("DELETE FROM demo_movimientos WHERE id_demo=%s", (demo_id,))
                cur.executemany(
                    """INSERT INTO demo_movimientos (id_demo,id_comando,orden,duracion_ms,pausa_ms)
                       VALUES (%s,%s,%s,%s,%s)""",
                    [(demo_id, int(step["id_comando"]), index, int(step["duracion_ms"]),
                      int(step.get("pausa_ms", 0))) for index, step in enumerate(steps, start=1)],
                ) if steps else None
                cur.execute(
                    """INSERT INTO auditoria_administracion
                       (id_empresa,id_usuario,accion,entidad,id_entidad,resultado,origen,metadatos)
                       VALUES (%s,%s,'ACTUALIZAR_SECUENCIA','DEMO',%s,'OK','API_CUENTA',%s)""",
                    (company_id, user_id, str(demo_id),
                     json.dumps({"total_pasos": len(steps), "duracion_total_ms": total_ms}, separators=(",", ":"))),
                )
            cn.commit()
            return {"id_demo": demo_id, "id_vehiculo": vehicle_id, "nombre": name,
                    "descripcion": description, "tipo": "PRIVADA", "total_pasos": len(steps),
                    "duracion_total_ms": total_ms,
                    "pasos": [{**step, "orden": index} for index, step in enumerate(steps, start=1)]}
        except Exception:
            cn.rollback()
            raise
        finally:
            cn.close()
