import json
import logging

from config.database import DatabaseConnection

logger = logging.getLogger(__name__)


class AdministracionRepository:
    """Consultas SQL parametrizadas para recursos administrativos por empresa."""

    def __init__(self, db: DatabaseConnection):
        self._db = db

    def _leer(self, sql: str, params: tuple = (), uno: bool = False):
        cn = self._db.obtener_conexion()
        try:
            with cn.cursor() as cur:
                cur.execute(sql, params)
                return cur.fetchone() if uno else cur.fetchall()
        finally:
            cn.close()

    @staticmethod
    def _auditar(cur, empresa_id: int, user_id: int, accion: str,
                 entidad: str, entity_id: int, resultado: str = "OK",
                 metadatos: dict | None = None):
        cur.execute(
            """INSERT INTO auditoria_administracion
               (id_empresa, id_usuario, accion, entidad, id_entidad, resultado, origen, metadatos)
               VALUES (%s, %s, %s, %s, %s, %s, 'API_ADMIN', %s)""",
            (empresa_id, user_id, accion, entidad, str(entity_id), resultado,
             json.dumps(metadatos, separators=(",", ":")) if metadatos is not None else None),
        )

    def _escribir(self, sql: str, params: tuple = (), *, audit: tuple | None = None,
                  fetch: bool = False):
        cn = self._db.obtener_conexion()
        try:
            cn.begin()
            with cn.cursor() as cur:
                cur.execute(sql, params)
                result = cur.fetchone() if fetch else None
                entity_id = result.get("id") if fetch and result else cur.lastrowid
                if audit:
                    self._auditar(cur, *audit, entity_id)
            cn.commit()
            return result if fetch else entity_id
        except Exception:
            cn.rollback()
            logger.exception("Error ejecutando consulta administrativa")
            raise
        finally:
            cn.close()

    # Modelos comerciales (catálogo compartido, solo rol ADMINISTRADOR).
    def listar_modelos(self, q: str | None, estado: str | None, limit: int, offset: int):
        q_like = f"%{q}%" if q else None
        return self._leer(
            """SELECT id_modelo, codigo, marca, nombre, microcontrolador, estado,
                      creado_en, fecha_baja
               FROM modelos_comerciales
               WHERE (%s IS NULL OR codigo LIKE %s OR marca LIKE %s OR nombre LIKE %s)
                 AND (%s IS NULL OR estado = %s)
               ORDER BY id_modelo LIMIT %s OFFSET %s""",
            (q, q_like, q_like, q_like, estado, estado, limit, offset),
        )

    def metricas_dashboard(self, empresa_id: int) -> dict:
        return self._leer(
            """SELECT
                 (SELECT COUNT(*) FROM modelos_comerciales WHERE estado='ACTIVO') AS modelos_activos,
                 (SELECT COUNT(*) FROM inventario_vehiculos i
                    JOIN vehiculos v ON v.id_vehiculo=i.id_vehiculo
                   WHERE i.id_empresa=%s AND i.estado<>'BAJA' AND v.activo=1) AS unidades_totales,
                 (SELECT COUNT(*) FROM inventario_vehiculos i
                    JOIN vehiculos v ON v.id_vehiculo=i.id_vehiculo
                   WHERE i.id_empresa=%s AND v.activo=1
                     AND (i.estado='VENDIDO' OR EXISTS (
                       SELECT 1 FROM asignaciones_vehiculo a
                        WHERE a.id_vehiculo=i.id_vehiculo AND a.estado='ACTIVA'
                     ))) AS unidades_vendidas_asignadas,
                 (SELECT COUNT(*) FROM inventario_vehiculos i
                    JOIN vehiculos v ON v.id_vehiculo=i.id_vehiculo
                   WHERE i.id_empresa=%s AND i.estado='EN_INVENTARIO'
                     AND i.disponible_demo=1 AND v.activo=1
                     AND NOT EXISTS (
                       SELECT 1 FROM sesiones_invitado s
                        WHERE s.id_vehiculo=v.id_vehiculo AND s.estado IN ('RESERVADA','ACTIVA')
                          AND s.expira_en>CURRENT_TIMESTAMP
                     )
                     AND NOT EXISTS (
                       SELECT 1 FROM asignaciones_vehiculo a
                        WHERE a.id_vehiculo=i.id_vehiculo AND a.estado='ACTIVA'
                     ) AND EXISTS (
                       SELECT 1 FROM demos d JOIN demo_movimientos dm ON dm.id_demo=d.id_demo
                       JOIN comandos c ON c.id_comando=dm.id_comando
                        WHERE d.id_vehiculo=v.id_vehiculo AND d.activo=1
                        GROUP BY d.id_demo
                        HAVING SUM(dm.duracion_ms+dm.pausa_ms)<=60000
                          AND SUM(dm.duracion_ms>10000 OR dm.pausa_ms>10000)=0
                          AND SUM(UPPER(c.nombre) NOT IN ('AVANZAR','RETROCEDER','GIRAR_IZQUIERDA','GIRAR_DERECHA'))=0
                          AND SUM(c.activo=0)=0
                          AND SUM(NOT EXISTS (
                            SELECT 1 FROM comandos_catalogo cx
                            JOIN vehiculos_modelos vm ON vm.id_vehiculo=v.id_vehiculo
                            JOIN capacidades_modelo cap ON cap.id_catalogo_comando=cx.id_catalogo_comando
                              AND cap.id_modelo=vm.id_modelo AND cap.habilitada=1
                            WHERE cx.id_comando=c.id_comando
                          ))=0
                     )) AS unidades_disponibles_prueba,
                 (SELECT COUNT(*) FROM clientes c
                   WHERE c.id_empresa=%s AND c.estado='ACTIVO') AS clientes_activos,
                 (SELECT COUNT(DISTINCT d.id_demo) FROM demos d
                    JOIN inventario_vehiculos i ON i.id_vehiculo=d.id_vehiculo
                    JOIN vehiculos v ON v.id_vehiculo=d.id_vehiculo
                   WHERE i.id_empresa=%s AND d.activo=1 AND v.activo=1
                     AND (i.estado='EN_INVENTARIO' OR
                          (i.estado='VENDIDO' AND v.microcontrolador='SIMULADO'))) AS demos_activas""",
            (empresa_id, empresa_id, empresa_id, empresa_id, empresa_id), uno=True,
        )

    def unidades_observables_wss(self, empresa_id: int) -> list[dict]:
        return self._leer(
            """SELECT DISTINCT i.id_vehiculo
               FROM inventario_vehiculos i
               JOIN vehiculos v ON v.id_vehiculo=i.id_vehiculo
               WHERE i.id_empresa=%s AND v.activo=1
                 AND (i.estado='EN_INVENTARIO' OR
                      (i.estado='VENDIDO' AND v.microcontrolador='SIMULADO'))""",
            (empresa_id,),
        )

    def obtener_modelo(self, model_id: int):
        return self._leer(
            "SELECT id_modelo, codigo, marca, nombre, microcontrolador, estado, creado_en, fecha_baja "
            "FROM modelos_comerciales WHERE id_modelo = %s", (model_id,), uno=True
        )

    def crear_modelo(self, data: dict, actor: dict):
        return self._escribir(
            """INSERT INTO modelos_comerciales
               (codigo, marca, nombre, microcontrolador) VALUES (%s, %s, %s, %s)""",
            (data["codigo"], data["marca"], data["nombre"], data.get("microcontrolador")),
            audit=(actor["id_empresa"], actor["id_usuario"], "CREAR", "MODELO"),
        )

    def actualizar_modelo(self, model_id: int, data: dict, actor: dict):
        allowed = {"marca", "nombre", "microcontrolador", "estado"}
        fields = [(key, value) for key, value in data.items() if key in allowed]
        if not fields:
            return False
        assignments = [f"{key} = %s" for key, _ in fields]
        params = [value for _, value in fields]
        if data.get("estado") == "BAJA":
            assignments.append("fecha_baja = COALESCE(fecha_baja, CURRENT_TIMESTAMP)")
        elif "estado" in data:
            assignments.append("fecha_baja = NULL")
        params.append(model_id)
        cn = self._db.obtener_conexion()
        try:
            cn.begin()
            with cn.cursor() as cur:
                cur.execute(
                    f"UPDATE modelos_comerciales SET {', '.join(assignments)} WHERE id_modelo = %s",
                    tuple(params),
                )
                if cur.rowcount == 0:
                    cur.execute("SELECT 1 FROM modelos_comerciales WHERE id_modelo=%s", (model_id,))
                    if not cur.fetchone():
                        cn.rollback()
                        return False
                self._auditar(cur, actor["id_empresa"], actor["id_usuario"],
                              "ACTUALIZAR", "MODELO", model_id)
            cn.commit()
            return True
        except Exception:
            cn.rollback()
            raise
        finally:
            cn.close()

    def baja_modelo(self, model_id: int, actor: dict):
        return self.actualizar_modelo(model_id, {"estado": "BAJA"}, actor)

    # Unidades: el alcance de empresa se deriva del token, nunca del JSON.
    def listar_unidades(self, empresa_id: int, q: str | None, activo: bool | None,
                        limit: int, offset: int):
        q_like = f"%{q}%" if q else None
        return self._leer(
            """SELECT v.id_vehiculo, v.nombre, v.modelo, v.descripcion,
                      v.microcontrolador, v.activo, i.id_inventario, i.estado AS estado_inventario,
                      i.desde, i.disponible_demo, vm.id_modelo,
                      m.codigo AS codigo_modelo, m.nombre AS nombre_modelo,
                      owner.nombre AS propietario,
                      CASE WHEN v.activo=0 OR i.estado IN ('BAJA','MANTENIMIENTO') THEN 'INACTIVO'
                           WHEN i.estado='VENDIDO' OR assignment.id_asignacion IS NOT NULL THEN 'VENDIDO/ASIGNADO'
                           WHEN i.disponible_demo=1 THEN 'EXHIBICION'
                           ELSE 'DISPONIBLE' END AS estado_comercial,
                      CASE WHEN EXISTS (SELECT 1 FROM sesiones_invitado s
                                        WHERE s.id_vehiculo=v.id_vehiculo
                                          AND s.estado IN ('RESERVADA','ACTIVA')
                                          AND s.expira_en>CURRENT_TIMESTAMP)
                           THEN 'RESERVA DE INVITADO' ELSE 'SIN SESION DE INVITADO' END AS estado_sesion,
                      'Sin verificar' AS conectividad
               FROM inventario_vehiculos i
               JOIN vehiculos v ON v.id_vehiculo = i.id_vehiculo
               LEFT JOIN vehiculos_modelos vm ON vm.id_vehiculo = v.id_vehiculo
               LEFT JOIN modelos_comerciales m ON m.id_modelo = vm.id_modelo
               LEFT JOIN asignaciones_vehiculo assignment
                 ON assignment.id_vehiculo=v.id_vehiculo AND assignment.estado='ACTIVA'
               LEFT JOIN clientes owner ON owner.id_cliente=assignment.id_cliente
               WHERE i.id_empresa = %s
                 AND (%s IS NULL OR v.nombre LIKE %s OR v.modelo LIKE %s)
                 AND (%s IS NULL OR v.activo = %s)
               ORDER BY v.id_vehiculo LIMIT %s OFFSET %s""",
            (empresa_id, q, q_like, q_like, activo, activo, limit, offset),
        )

    def catalogo_publico_invitado(self) -> list[dict]:
        """Modelos y capacidades agregadas; nunca devuelve IDs ni datos de inventario."""
        return self._leer(
            """SELECT m.id_modelo,m.codigo,m.nombre,m.marca,
                      COUNT(DISTINCT CASE WHEN i.estado='EN_INVENTARIO' AND v.activo=1
                        AND i.disponible_demo=1 AND assignment.id_asignacion IS NULL
                        AND active_session.id_sesion IS NULL AND EXISTS (
                          SELECT 1 FROM demos d JOIN demo_movimientos dm ON dm.id_demo=d.id_demo
                          JOIN comandos c ON c.id_comando=dm.id_comando
                          WHERE d.id_vehiculo=v.id_vehiculo AND d.activo=1
                          GROUP BY d.id_demo
                            HAVING SUM(dm.duracion_ms+dm.pausa_ms)<=60000
                              AND SUM(dm.duracion_ms>10000 OR dm.pausa_ms>10000)=0
                              AND SUM(UPPER(c.nombre) NOT IN ('AVANZAR','RETROCEDER','GIRAR_IZQUIERDA','GIRAR_DERECHA'))=0
                              AND SUM(c.activo=0)=0
                              AND SUM(NOT EXISTS (
                                SELECT 1 FROM comandos_catalogo cx
                                JOIN capacidades_modelo mx ON mx.id_catalogo_comando=cx.id_catalogo_comando
                                WHERE cx.id_comando=c.id_comando AND mx.id_modelo=vm.id_modelo
                                  AND mx.habilitada=1
                              ))=0
                        ) THEN v.id_vehiculo END) AS unidades_disponibles,
                      GROUP_CONCAT(DISTINCT cc.nombre ORDER BY cc.nombre SEPARATOR ',') AS capacidades
               FROM modelos_comerciales m
               LEFT JOIN vehiculos_modelos vm ON vm.id_modelo=m.id_modelo
               LEFT JOIN vehiculos v ON v.id_vehiculo=vm.id_vehiculo
               LEFT JOIN inventario_vehiculos i ON i.id_vehiculo=v.id_vehiculo
               LEFT JOIN asignaciones_vehiculo assignment
                 ON assignment.id_vehiculo=v.id_vehiculo AND assignment.estado='ACTIVA'
               LEFT JOIN (SELECT id_vehiculo,MIN(id_sesion) id_sesion FROM sesiones_invitado
                          WHERE estado IN ('RESERVADA','ACTIVA') AND expira_en>CURRENT_TIMESTAMP
                          GROUP BY id_vehiculo) active_session ON active_session.id_vehiculo=v.id_vehiculo
               LEFT JOIN capacidades_modelo cap ON cap.id_modelo=m.id_modelo AND cap.habilitada=1
               LEFT JOIN catalogo_comandos cc ON cc.id_catalogo_comando=cap.id_catalogo_comando
                    AND cc.estado='ACTIVO'
               WHERE m.estado='ACTIVO'
               GROUP BY m.id_modelo,m.codigo,m.nombre,m.marca
               ORDER BY m.nombre"""
        )

    def reservar_sesion_publica(self, model_id: int, demo_id: int | None,
                                token_hash: str, duration_minutes: int = 10):
        """Reserva una unidad de exhibición y autoriza solo comandos de desplazamiento básicos."""
        allowed_names = ("AVANZAR", "RETROCEDER", "GIRAR_IZQUIERDA", "GIRAR_DERECHA")
        cn = self._db.obtener_conexion()
        try:
            cn.begin()
            with cn.cursor() as cur:
                cur.execute(
                    """SELECT v.id_vehiculo,i.id_empresa FROM inventario_vehiculos i
                       JOIN vehiculos v ON v.id_vehiculo=i.id_vehiculo
                       JOIN vehiculos_modelos vm ON vm.id_vehiculo=v.id_vehiculo
                       JOIN modelos_comerciales m ON m.id_modelo=vm.id_modelo
                       LEFT JOIN asignaciones_vehiculo a ON a.id_vehiculo=v.id_vehiculo AND a.estado='ACTIVA'
                       LEFT JOIN sesiones_invitado s ON s.id_vehiculo=v.id_vehiculo
                         AND s.estado IN ('RESERVADA','ACTIVA') AND s.expira_en>CURRENT_TIMESTAMP
                       WHERE vm.id_modelo=%s AND m.estado='ACTIVO' AND i.disponible_demo=1
                         AND i.estado='EN_INVENTARIO' AND v.activo=1
                         AND a.id_asignacion IS NULL AND s.id_sesion IS NULL
                       ORDER BY v.id_vehiculo LIMIT 1 FOR UPDATE""",
                    (model_id,),
                )
                unit = cur.fetchone()
                if not unit:
                    raise LookupError("No hay una unidad de exhibición disponible para ese modelo.")
                vehicle_id = int(unit["id_vehiculo"])
                if demo_id is None:
                    cur.execute(
                        """SELECT d.id_demo FROM demos d JOIN demo_movimientos dm ON dm.id_demo=d.id_demo
                           WHERE d.id_vehiculo=%s AND d.activo=1 GROUP BY d.id_demo
                           ORDER BY d.id_demo LIMIT 1""", (vehicle_id,)
                    )
                    demo_row = cur.fetchone()
                    if not demo_row:
                        raise LookupError("La unidad no tiene una DEMO de exhibición configurada.")
                    demo_id = int(demo_row["id_demo"])
                cur.execute(
                      """SELECT dm.id_comando,dm.duracion_ms,dm.pausa_ms,c.nombre,cap.duracion_max_ms
                       FROM demo_movimientos dm JOIN demos d ON d.id_demo=dm.id_demo
                       JOIN comandos c ON c.id_comando=dm.id_comando
                         JOIN comandos_catalogo cm ON cm.id_comando=c.id_comando
                         JOIN vehiculos_modelos vm ON vm.id_vehiculo=c.id_vehiculo
                         JOIN capacidades_modelo cap ON cap.id_modelo=vm.id_modelo
                           AND cap.id_catalogo_comando=cm.id_catalogo_comando AND cap.habilitada=1
                       WHERE d.id_demo=%s AND d.id_vehiculo=%s AND d.activo=1
                           AND c.activo=1
                         ORDER BY dm.orden""", (demo_id, vehicle_id)
                )
                steps = cur.fetchall()
                if not steps:
                    raise LookupError("DEMO de exhibición no disponible.")
                if len(steps) > 20 or sum(int(s["duracion_ms"]) + int(s["pausa_ms"]) for s in steps) > 60_000:
                    raise ValueError("La DEMO de exhibición supera los límites de duración o cantidad de pasos.")
                if any(int(s["duracion_ms"]) > 10_000 or int(s["pausa_ms"]) > 10_000
                       or (s["duracion_max_ms"] is not None and int(s["duracion_ms"]) > int(s["duracion_max_ms"]))
                       for s in steps):
                    raise ValueError("La DEMO de exhibición supera la duración permitida por paso o modelo.")
                allowed_upper = {name.upper() for name in allowed_names}
                if any(str(step["nombre"]).upper() not in allowed_upper for step in steps):
                    raise ValueError("La DEMO contiene comandos fuera del catálogo público permitido.")
                marks = ",".join(["%s"] * len(allowed_names))
                cur.execute(
                    f"""SELECT DISTINCT c.id_comando FROM comandos c
                       JOIN vehiculos_modelos vm ON vm.id_vehiculo=c.id_vehiculo
                       JOIN comandos_catalogo ccx ON ccx.id_comando=c.id_comando
                       JOIN capacidades_modelo cap ON cap.id_modelo=vm.id_modelo
                         AND cap.id_catalogo_comando=ccx.id_catalogo_comando AND cap.habilitada=1
                       WHERE c.id_vehiculo=%s AND c.activo=1 AND UPPER(c.nombre) IN ({marks})""",
                    (vehicle_id, *allowed_names),
                )
                permitted = sorted(int(row["id_comando"]) for row in cur.fetchall())
                step_ids = {int(step["id_comando"]) for step in steps}
                if not permitted or not step_ids.issubset(set(permitted)):
                    raise ValueError("La DEMO no coincide con las capacidades habilitadas del modelo.")
                cur.execute(
                    """INSERT INTO sesiones_invitado
                       (token_hash,id_vehiculo,id_demo,autorizado_por,estado,inicio,expira_en,comandos_permitidos)
                       VALUES (%s,%s,%s,NULL,'ACTIVA',CURRENT_TIMESTAMP,
                         DATE_ADD(CURRENT_TIMESTAMP, INTERVAL %s MINUTE),%s)""",
                    (token_hash, vehicle_id, demo_id, duration_minutes, json.dumps(permitted)),
                )
                session_id = cur.lastrowid
                cur.execute("SELECT expira_en FROM sesiones_invitado WHERE id_sesion=%s", (session_id,))
                expiration = cur.fetchone()["expira_en"]
                cur.execute(
                    """INSERT INTO auditoria_administracion
                       (id_empresa,id_usuario,accion,entidad,id_entidad,resultado,origen,metadatos)
                       VALUES (%s,NULL,'RESERVAR','SESION_INVITADO',%s,'OK','API_GUEST',
                         JSON_OBJECT('unidad',%s,'actor','INVITADO'))""",
                    (unit["id_empresa"], str(session_id), vehicle_id),
                )
            cn.commit()
            return {"id_sesion": session_id, "id_vehiculo": vehicle_id,
                    "id_demo": demo_id, "expira_en": expiration,
                    "comandos_permitidos": permitted}
        except Exception:
            cn.rollback()
            raise
        finally:
            cn.close()

    def finalizar_sesion_publica(self, session_id: int, token_hash: str | None = None,
                                 final_state: str = "FINALIZADA") -> dict | None:
        cn = self._db.obtener_conexion()
        try:
            cn.begin()
            with cn.cursor() as cur:
                where = "id_sesion=%s AND estado IN ('RESERVADA','ACTIVA')"
                params: tuple = (session_id,)
                if token_hash:
                    where += " AND token_hash=%s"
                    params += (token_hash,)
                cur.execute(
                    """SELECT s.id_vehiculo,i.id_empresa,s.autorizado_por
                       FROM sesiones_invitado s JOIN inventario_vehiculos i ON i.id_vehiculo=s.id_vehiculo
                       WHERE s.id_sesion=%s AND s.estado IN ('RESERVADA','ACTIVA')
                         AND (%s IS NULL OR s.token_hash=%s) FOR UPDATE""",
                    (session_id, token_hash, token_hash),
                )
                row = cur.fetchone()
                if not row:
                    cn.rollback()
                    return None
                cur.execute(
                    f"UPDATE sesiones_invitado SET estado=%s,finalizada_en=CURRENT_TIMESTAMP WHERE {where}",
                    (final_state, *params),
                )
                cur.execute(
                    """INSERT INTO auditoria_administracion
                       (id_empresa,id_usuario,accion,entidad,id_entidad,resultado,origen,metadatos)
                       VALUES (%s,%s,%s,'SESION_INVITADO',%s,'OK','API_GUEST',JSON_OBJECT('unidad',%s))""",
                    (row["id_empresa"], row["autorizado_por"], final_state,
                     str(session_id), row["id_vehiculo"]),
                )
            cn.commit()
            return {"id_sesion": session_id, "id_vehiculo": int(row["id_vehiculo"]),
                    "estado": final_state}
        except Exception:
            cn.rollback()
            raise
        finally:
            cn.close()

    def expirar_sesiones_publicas(self) -> list[dict]:
        cn = self._db.obtener_conexion()
        try:
            cn.begin()
            with cn.cursor() as cur:
                cur.execute(
                    """SELECT s.id_sesion,s.id_vehiculo,s.autorizado_por,i.id_empresa
                       FROM sesiones_invitado s JOIN inventario_vehiculos i ON i.id_vehiculo=s.id_vehiculo
                       WHERE s.estado IN ('RESERVADA','ACTIVA')
                         AND s.expira_en<=CURRENT_TIMESTAMP FOR UPDATE"""
                )
                rows = cur.fetchall()
                if rows:
                    ids = [int(row["id_sesion"]) for row in rows]
                    cur.executemany(
                        "UPDATE sesiones_invitado SET estado='EXPIRADA',finalizada_en=CURRENT_TIMESTAMP WHERE id_sesion=%s",
                        [(session_id,) for session_id in ids],
                    )
                    cur.executemany(
                        """INSERT INTO auditoria_administracion
                           (id_empresa,id_usuario,accion,entidad,id_entidad,resultado,origen,metadatos)
                           VALUES (%s,%s,'EXPIRAR','SESION_INVITADO',%s,'OK','API_SEGURIDAD',JSON_OBJECT('unidad',%s))""",
                        [(row["id_empresa"], row["autorizado_por"], str(row["id_sesion"]), row["id_vehiculo"])
                         for row in rows],
                    )
            cn.commit()
            return rows
        except Exception:
            cn.rollback()
            raise
        finally:
            cn.close()

    def usuarios_asignacion(self, assignment_id: int, company_id: int) -> list[int]:
        rows = self._leer(
            """SELECT DISTINCT uc.id_usuario FROM asignaciones_vehiculo a
               JOIN inventario_vehiculos i ON i.id_inventario=a.id_inventario
               JOIN usuarios_clientes uc ON uc.id_cliente=a.id_cliente AND uc.estado='ACTIVO'
               WHERE a.id_asignacion=%s AND i.id_empresa=%s AND a.estado='ACTIVA'""",
            (assignment_id, company_id),
        )
        return [int(row["id_usuario"]) for row in rows]

    def unidad_en_empresa(self, vehicle_id: int, empresa_id: int, lock: bool = False,
                          include_simulated_sold: bool = False):
        suffix = " FOR UPDATE" if lock else ""
        return self._leer(
            """SELECT v.id_vehiculo, v.nombre, v.modelo, v.descripcion,
                      v.microcontrolador, v.activo, i.id_empresa, i.id_inventario,
                      i.estado AS estado_inventario, i.disponible_demo, vm.id_modelo
               FROM inventario_vehiculos i
               JOIN vehiculos v ON v.id_vehiculo = i.id_vehiculo
               LEFT JOIN vehiculos_modelos vm ON vm.id_vehiculo = v.id_vehiculo
               WHERE v.id_vehiculo = %s AND i.id_empresa = %s
                 AND (i.estado = 'EN_INVENTARIO' OR
                      (%s = 1 AND i.estado = 'VENDIDO' AND v.microcontrolador = 'SIMULADO'))""" + suffix,
            (vehicle_id, empresa_id, int(include_simulated_sold)), uno=True,
        )

    def crear_unidad(self, data: dict, actor: dict):
        cn = self._db.obtener_conexion()
        try:
            cn.begin()
            with cn.cursor() as cur:
                cur.execute("SELECT nombre, microcontrolador, estado FROM modelos_comerciales WHERE id_modelo=%s FOR UPDATE",
                            (data["id_modelo"],))
                model = cur.fetchone()
                if not model or model["estado"] != "ACTIVO":
                    raise LookupError("Modelo activo no encontrado.")
                cur.execute(
                    """INSERT INTO vehiculos (nombre, modelo, descripcion, microcontrolador, activo)
                       VALUES (%s, %s, %s, %s, 1)""",
                    (data["nombre"], model["nombre"], data.get("descripcion"),
                     data.get("microcontrolador") or model["microcontrolador"]),
                )
                vehicle_id = cur.lastrowid
                cur.execute(
                    "INSERT INTO vehiculos_modelos (id_vehiculo,id_modelo,origen_mapeo) VALUES (%s,%s,'MANUAL')",
                    (vehicle_id, data["id_modelo"]),
                )
                cur.execute(
                    "INSERT INTO inventario_vehiculos (id_empresa,id_vehiculo,estado) VALUES (%s,%s,'EN_INVENTARIO')",
                    (actor["id_empresa"], vehicle_id),
                )
                self._auditar(cur, actor["id_empresa"], actor["id_usuario"],
                              "CREAR", "VEHICULO", vehicle_id)
            cn.commit()
            return vehicle_id
        except Exception:
            cn.rollback()
            raise
        finally:
            cn.close()

    def actualizar_unidad(self, vehicle_id: int, data: dict, actor: dict):
        cn = self._db.obtener_conexion()
        try:
            cn.begin()
            with cn.cursor() as cur:
                cur.execute(
                    """SELECT i.id_inventario FROM inventario_vehiculos i
                       WHERE i.id_vehiculo=%s AND i.id_empresa=%s
                         AND i.estado='EN_INVENTARIO' FOR UPDATE""",
                    (vehicle_id, actor["id_empresa"]),
                )
                if not cur.fetchone():
                    cn.rollback()
                    return False
                updates = {k: data[k] for k in ("nombre", "descripcion", "activo") if k in data}
                if updates:
                    sets = ", ".join(f"{key}=%s" for key in updates)
                    cur.execute(f"UPDATE vehiculos SET {sets} WHERE id_vehiculo=%s",
                                (*updates.values(), vehicle_id))
                if "id_modelo" in data:
                    cur.execute("SELECT id_modelo FROM vehiculos_modelos WHERE id_vehiculo=%s FOR UPDATE",
                                (vehicle_id,))
                    current_model = cur.fetchone()
                    if current_model and int(current_model["id_modelo"]) != int(data["id_modelo"]):
                        cur.execute("SELECT 1 FROM asignaciones_vehiculo WHERE id_vehiculo=%s AND estado='ACTIVA' LIMIT 1",
                                    (vehicle_id,))
                        if cur.fetchone():
                            raise FileExistsError("No se puede cambiar el modelo comercial de una unidad asignada.")
                    cur.execute("SELECT nombre,microcontrolador,estado FROM modelos_comerciales WHERE id_modelo=%s FOR UPDATE",
                                (data["id_modelo"],))
                    model = cur.fetchone()
                    if not model or model["estado"] != "ACTIVO":
                        raise LookupError("Modelo activo no encontrado.")
                    cur.execute(
                        """INSERT INTO vehiculos_modelos (id_vehiculo,id_modelo,origen_mapeo)
                           VALUES (%s,%s,'MANUAL') ON DUPLICATE KEY UPDATE id_modelo=VALUES(id_modelo),
                           asignado_en=CURRENT_TIMESTAMP, origen_mapeo='MANUAL'""",
                        (vehicle_id, data["id_modelo"]),
                    )
                    cur.execute("UPDATE vehiculos SET modelo=%s, microcontrolador=%s WHERE id_vehiculo=%s",
                                (model["nombre"], model["microcontrolador"], vehicle_id))
                if "disponible_demo" in data:
                    if data["disponible_demo"]:
                        cur.execute(
                            """SELECT 1 FROM asignaciones_vehiculo
                               WHERE id_vehiculo=%s AND estado='ACTIVA' LIMIT 1""", (vehicle_id,)
                        )
                        if cur.fetchone():
                            raise FileExistsError("Una unidad asignada no se puede marcar para exhibición pública.")
                    cur.execute(
                        """SELECT id_sesion FROM sesiones_invitado WHERE id_vehiculo=%s
                           AND estado IN ('RESERVADA','ACTIVA') AND expira_en>CURRENT_TIMESTAMP LIMIT 1""",
                        (vehicle_id,),
                    )
                    if cur.fetchone():
                        raise FileExistsError("Finaliza la sesión de invitado antes de cambiar su disponibilidad pública.")
                    cur.execute(
                        "UPDATE inventario_vehiculos SET disponible_demo=%s WHERE id_vehiculo=%s AND id_empresa=%s",
                        (int(data["disponible_demo"]), vehicle_id, actor["id_empresa"]),
                    )
                self._auditar(cur, actor["id_empresa"], actor["id_usuario"],
                              "ACTUALIZAR", "VEHICULO", vehicle_id)
            cn.commit()
            return True
        except Exception:
            cn.rollback()
            raise
        finally:
            cn.close()

    def baja_unidad(self, vehicle_id: int, actor: dict):
        cn = self._db.obtener_conexion()
        try:
            cn.begin()
            with cn.cursor() as cur:
                cur.execute(
                    """SELECT id_inventario FROM inventario_vehiculos
                       WHERE id_vehiculo=%s AND id_empresa=%s AND estado='EN_INVENTARIO' FOR UPDATE""",
                    (vehicle_id, actor["id_empresa"]),
                )
                inv = cur.fetchone()
                if not inv:
                    cn.rollback()
                    return False
                cur.execute("SELECT 1 FROM asignaciones_vehiculo WHERE id_vehiculo=%s AND estado='ACTIVA' LIMIT 1",
                            (vehicle_id,))
                if cur.fetchone():
                    raise FileExistsError("No se puede dar de baja una unidad con asignación activa.")
                cur.execute("SELECT 1 FROM sesiones_invitado WHERE id_vehiculo=%s AND estado IN ('RESERVADA','ACTIVA') LIMIT 1",
                            (vehicle_id,))
                if cur.fetchone():
                    raise FileExistsError("No se puede dar de baja una unidad con sesión de invitado abierta.")
                cur.execute("UPDATE vehiculos SET activo=0 WHERE id_vehiculo=%s", (vehicle_id,))
                cur.execute(
                    "UPDATE inventario_vehiculos SET estado='BAJA', hasta=CURRENT_TIMESTAMP WHERE id_inventario=%s",
                    (inv["id_inventario"],),
                )
                self._auditar(cur, actor["id_empresa"], actor["id_usuario"], "BAJA", "VEHICULO", vehicle_id)
            cn.commit()
            return True
        except Exception:
            cn.rollback()
            raise
        finally:
            cn.close()

    # Clientes y asignaciones, siempre limitados a la empresa autenticada.
    def listar_clientes(self, empresa_id: int, q: str | None, estado: str | None,
                        limit: int, offset: int):
        q_like = f"%{q}%" if q else None
        return self._leer(
            """SELECT c.id_cliente,c.id_empresa,c.nombre,c.correo_contacto,c.telefono_contacto,
                      c.estado,c.fecha_alta,c.fecha_baja,
                      (SELECT MIN(uc.id_usuario) FROM usuarios_clientes uc
                       WHERE uc.id_cliente=c.id_cliente AND uc.estado='ACTIVO') AS id_usuario,
                      (SELECT MAX(v.id_vehiculo) FROM usuarios_clientes uc
                       JOIN asignaciones_vehiculo av ON av.id_cliente=uc.id_cliente AND av.estado='ACTIVA'
                       JOIN inventario_vehiculos iv ON iv.id_inventario=av.id_inventario
                       JOIN vehiculos v ON v.id_vehiculo=iv.id_vehiculo AND v.microcontrolador='SIMULADO'
                       WHERE uc.id_cliente=c.id_cliente AND uc.estado='ACTIVO') AS id_vehiculo,
                      CASE WHEN (SELECT MAX(v.id_vehiculo) FROM usuarios_clientes uc
                         JOIN asignaciones_vehiculo av ON av.id_cliente=uc.id_cliente AND av.estado='ACTIVA'
                         JOIN inventario_vehiculos iv ON iv.id_inventario=av.id_inventario
                         JOIN vehiculos v ON v.id_vehiculo=iv.id_vehiculo AND v.microcontrolador='SIMULADO'
                         WHERE uc.id_cliente=c.id_cliente AND uc.estado='ACTIVO') IS NOT NULL
                        THEN 'SIMULADO' ELSE NULL END AS tipo_vehiculo
               FROM clientes c WHERE c.id_empresa=%s
                 AND (%s IS NULL OR c.nombre LIKE %s OR c.correo_contacto LIKE %s)
                 AND (%s IS NULL OR c.estado=%s)
               ORDER BY c.id_cliente LIMIT %s OFFSET %s""",
            (empresa_id, q, q_like, q_like, estado, estado, limit, offset),
        )

    def obtener_cliente(self, client_id: int, empresa_id: int):
        return self._leer("SELECT id_cliente,id_empresa,nombre,correo_contacto,telefono_contacto,estado,fecha_alta,fecha_baja "
                           "FROM clientes WHERE id_cliente=%s AND id_empresa=%s",
                           (client_id, empresa_id), uno=True)

    def crear_cliente(self, data: dict, actor: dict):
        return self._escribir(
            """INSERT INTO clientes (id_empresa,nombre,correo_contacto,telefono_contacto)
               VALUES (%s,%s,%s,%s)""",
            (actor["id_empresa"], data["nombre"], data.get("correo_contacto"), data.get("telefono_contacto")),
            audit=(actor["id_empresa"], actor["id_usuario"], "CREAR", "CLIENTE"),
        )

    def actualizar_cliente(self, client_id: int, empresa_id: int, data: dict, actor: dict):
        allowed = {"nombre", "correo_contacto", "telefono_contacto", "estado"}
        fields = [(key, value) for key, value in data.items() if key in allowed]
        if not fields:
            return False
        cn = self._db.obtener_conexion()
        try:
            cn.begin()
            with cn.cursor() as cur:
                cur.execute("SELECT id_cliente FROM clientes WHERE id_cliente=%s AND id_empresa=%s FOR UPDATE",
                            (client_id, empresa_id))
                if not cur.fetchone():
                    cn.rollback()
                    return False
                if data.get("estado") == "BAJA":
                    cur.execute("SELECT 1 FROM asignaciones_vehiculo WHERE id_cliente=%s AND estado='ACTIVA' LIMIT 1",
                                (client_id,))
                    if cur.fetchone():
                        raise FileExistsError("No se puede dar de baja un cliente con unidades asignadas.")
                sets = [f"{key}=%s" for key, _ in fields]
                values = [value for _, value in fields]
                if data.get("estado") == "BAJA":
                    sets.append("fecha_baja=COALESCE(fecha_baja,CURRENT_TIMESTAMP)")
                elif "estado" in data:
                    sets.append("fecha_baja=NULL")
                cur.execute(f"UPDATE clientes SET {', '.join(sets)} WHERE id_cliente=%s AND id_empresa=%s",
                            (*values, client_id, empresa_id))
                self._auditar(cur, empresa_id, actor["id_usuario"], "ACTUALIZAR", "CLIENTE", client_id)
            cn.commit()
            return True
        except Exception:
            cn.rollback()
            raise
        finally:
            cn.close()

    def baja_cliente(self, client_id: int, company_id: int, actor: dict):
        return self.actualizar_cliente(client_id, company_id, {"estado": "BAJA"}, actor)

    def listar_roles(self):
        return self._leer("SELECT id_rol,clave,nombre,descripcion,activo FROM roles WHERE activo=1 ORDER BY id_rol")

    def listar_usuarios(self, empresa_id: int, estado: str | None, limit: int, offset: int):
        return self._leer(
            """SELECT u.id_usuario,u.id_empresa,u.correo,u.nombre,u.estado,u.fecha_alta,
                      u.fecha_baja,GROUP_CONCAT(DISTINCT r.clave ORDER BY r.clave) AS roles,
                      GROUP_CONCAT(DISTINCT uc.id_cliente ORDER BY uc.id_cliente) AS clientes,
                      MAX(v.id_vehiculo) AS id_vehiculo,
                      MAX(v.microcontrolador) AS tipo_carrito
               FROM usuarios u
               LEFT JOIN usuarios_roles ur ON ur.id_usuario=u.id_usuario
               LEFT JOIN roles r ON r.id_rol=ur.id_rol AND r.activo=1
               LEFT JOIN usuarios_clientes uc ON uc.id_usuario=u.id_usuario AND uc.estado='ACTIVO'
               LEFT JOIN asignaciones_vehiculo av ON av.id_cliente=uc.id_cliente AND av.estado='ACTIVA'
               LEFT JOIN inventario_vehiculos iv ON iv.id_inventario=av.id_inventario
               LEFT JOIN vehiculos v ON v.id_vehiculo=iv.id_vehiculo AND v.microcontrolador='SIMULADO'
               WHERE u.id_empresa=%s AND (%s IS NULL OR u.estado=%s)
               GROUP BY u.id_usuario,u.id_empresa,u.correo,u.nombre,u.estado,u.fecha_alta,u.fecha_baja
               ORDER BY u.id_usuario LIMIT %s OFFSET %s""",
            (empresa_id, estado, estado, limit, offset),
        )

    def crear_usuario(self, data: dict, actor: dict, password_hash: str):
        cn = self._db.obtener_conexion()
        try:
            cn.begin()
            with cn.cursor() as cur:
                if data.get("id_cliente") is not None:
                    cur.execute("SELECT id_cliente FROM clientes WHERE id_cliente=%s AND id_empresa=%s AND estado='ACTIVO' FOR UPDATE",
                                (data["id_cliente"], actor["id_empresa"]))
                    if not cur.fetchone():
                        raise LookupError("Cliente activo no encontrado en la empresa.")
                cur.execute(
                    """INSERT INTO usuarios (id_empresa,correo,nombre,password_hash,estado)
                       VALUES (%s,%s,%s,%s,'ACTIVO')""",
                    (actor["id_empresa"], data["correo"], data["nombre"], password_hash),
                )
                user_id = cur.lastrowid
                cur.execute("SELECT id_rol FROM roles WHERE clave='USUARIO' AND activo=1 LIMIT 1")
                role = cur.fetchone()
                if not role:
                    raise RuntimeError("No existe el rol USUARIO activo.")
                cur.execute("INSERT INTO usuarios_roles (id_usuario,id_rol,asignado_por) VALUES (%s,%s,%s)",
                            (user_id, role["id_rol"], actor["id_usuario"]))
                if data.get("id_cliente") is not None:
                    cur.execute("INSERT INTO usuarios_clientes (id_usuario,id_cliente) VALUES (%s,%s)",
                                (user_id, data["id_cliente"]))
                self._auditar(cur, actor["id_empresa"], actor["id_usuario"], "CREAR", "USUARIO", user_id)
            cn.commit()
            return user_id
        except Exception:
            cn.rollback()
            raise
        finally:
            cn.close()

    def actualizar_estado_usuario(self, user_id: int, company_id: int, estado: str, actor: dict):
        cn = self._db.obtener_conexion()
        try:
            cn.begin()
            with cn.cursor() as cur:
                cur.execute(
                    """UPDATE usuarios SET estado=%s,
                         fecha_baja=CASE WHEN %s='BAJA' THEN COALESCE(fecha_baja,CURRENT_TIMESTAMP) ELSE NULL END
                       WHERE id_usuario=%s AND id_empresa=%s""",
                    (estado, estado, user_id, company_id),
                )
                if cur.rowcount == 0:
                    cur.execute("SELECT 1 FROM usuarios WHERE id_usuario=%s AND id_empresa=%s", (user_id, company_id))
                    if not cur.fetchone():
                        cn.rollback()
                        return False
                self._auditar(cur, company_id, actor["id_usuario"], estado, "USUARIO", user_id)
            cn.commit()
            return True
        except Exception:
            cn.rollback()
            raise
        finally:
            cn.close()

    def actualizar_roles_usuario(self, user_id: int, company_id: int,
                                 role_keys: list[str], actor: dict):
        """Reemplaza roles dentro de la empresa; el rol Invitado nunca se asigna a una cuenta permanente."""
        normalized = sorted(set(role_keys))
        if not normalized or not set(normalized).issubset({"ADMINISTRADOR", "USUARIO"}):
            raise ValueError("La cuenta requiere al menos un rol de administrador o usuario.")
        cn = self._db.obtener_conexion()
        try:
            cn.begin()
            with cn.cursor() as cur:
                cur.execute("SELECT id_usuario,estado FROM usuarios WHERE id_usuario=%s AND id_empresa=%s FOR UPDATE",
                            (user_id, company_id))
                target = cur.fetchone()
                if not target:
                    cn.rollback()
                    return None
                if int(user_id) == int(actor["id_usuario"]) and "ADMINISTRADOR" not in normalized:
                    raise FileExistsError("No puedes quitarte tu propio rol de administrador.")
                marks = ",".join(["%s"] * len(normalized))
                cur.execute(f"SELECT id_rol,clave FROM roles WHERE activo=1 AND clave IN ({marks})", tuple(normalized))
                role_rows = cur.fetchall()
                if {row["clave"] for row in role_rows} != set(normalized):
                    raise LookupError("Uno o más roles no están disponibles.")
                cur.execute(
                    """SELECT GROUP_CONCAT(r.clave ORDER BY r.clave) AS roles
                       FROM usuarios_roles ur JOIN roles r ON r.id_rol=ur.id_rol
                       WHERE ur.id_usuario=%s""", (user_id,)
                )
                old_value = cur.fetchone()["roles"] or ""
                old_roles = sorted(value for value in old_value.split(",") if value)
                if "ADMINISTRADOR" in old_roles and "ADMINISTRADOR" not in normalized and target["estado"] == "ACTIVO":
                    cur.execute(
                        """SELECT COUNT(*) AS total FROM usuarios u
                           JOIN usuarios_roles ur ON ur.id_usuario=u.id_usuario
                           JOIN roles r ON r.id_rol=ur.id_rol
                           WHERE u.id_empresa=%s AND u.estado='ACTIVO' AND r.clave='ADMINISTRADOR'
                             AND r.activo=1 AND u.id_usuario<>%s""", (company_id, user_id)
                    )
                    if int(cur.fetchone()["total"]) == 0:
                        raise FileExistsError("La empresa debe conservar al menos un administrador activo.")
                cur.execute("DELETE FROM usuarios_roles WHERE id_usuario=%s", (user_id,))
                cur.executemany(
                    "INSERT INTO usuarios_roles (id_usuario,id_rol,asignado_por) VALUES (%s,%s,%s)",
                    [(user_id, int(row["id_rol"]), actor["id_usuario"]) for row in role_rows],
                )
                self._auditar(cur, company_id, actor["id_usuario"], "CAMBIAR_ROLES", "USUARIO", user_id,
                              metadatos={"roles_anteriores": old_roles, "roles_nuevos": normalized})
            cn.commit()
            return normalized
        except Exception:
            cn.rollback()
            raise
        finally:
            cn.close()

    def listar_asignaciones(self, empresa_id: int, estado: str | None, limit: int, offset: int):
        return self._leer(
            """SELECT a.id_asignacion,a.id_vehiculo,a.id_cliente,a.id_inventario,a.estado,
                      a.inicio,a.fin,a.motivo,v.nombre AS vehiculo,c.nombre AS cliente
               FROM asignaciones_vehiculo a
               JOIN inventario_vehiculos i ON i.id_inventario=a.id_inventario
               JOIN vehiculos v ON v.id_vehiculo=a.id_vehiculo
               JOIN clientes c ON c.id_cliente=a.id_cliente
               WHERE i.id_empresa=%s AND (%s IS NULL OR a.estado=%s)
               ORDER BY a.id_asignacion DESC LIMIT %s OFFSET %s""",
            (empresa_id, estado, estado, limit, offset),
        )

    def crear_asignacion(self, data: dict, actor: dict):
        cn = self._db.obtener_conexion()
        try:
            cn.begin()
            with cn.cursor() as cur:
                cur.execute(
                    """SELECT id_inventario FROM inventario_vehiculos
                       WHERE id_vehiculo=%s AND id_empresa=%s AND estado='EN_INVENTARIO' FOR UPDATE""",
                    (data["id_vehiculo"], actor["id_empresa"]),
                )
                inv = cur.fetchone()
                if not inv:
                    raise LookupError("Unidad no disponible en el inventario de la empresa.")
                cur.execute("SELECT id_cliente FROM clientes WHERE id_cliente=%s AND id_empresa=%s AND estado='ACTIVO' FOR UPDATE",
                            (data["id_cliente"], actor["id_empresa"]))
                if not cur.fetchone():
                    raise LookupError("Cliente activo no encontrado en la empresa.")
                cur.execute("SELECT 1 FROM asignaciones_vehiculo WHERE id_vehiculo=%s AND estado='ACTIVA' LIMIT 1 FOR UPDATE",
                            (data["id_vehiculo"],))
                if cur.fetchone():
                    raise FileExistsError("La unidad ya tiene una asignación activa.")
                cur.execute(
                    """INSERT INTO asignaciones_vehiculo
                       (id_inventario,id_vehiculo,id_cliente,motivo)
                       VALUES (%s,%s,%s,%s)""",
                    (inv["id_inventario"], data["id_vehiculo"], data["id_cliente"], data.get("motivo")),
                )
                assignment_id = cur.lastrowid
                self._auditar(cur, actor["id_empresa"], actor["id_usuario"],
                              "ASIGNAR", "VEHICULO_CLIENTE", assignment_id)
            cn.commit()
            return assignment_id
        except Exception:
            cn.rollback()
            raise
        finally:
            cn.close()

    def cerrar_asignacion(self, assignment_id: int, empresa_id: int, estado: str,
                          motivo: str | None, actor: dict):
        cn = self._db.obtener_conexion()
        try:
            cn.begin()
            with cn.cursor() as cur:
                cur.execute(
                    """UPDATE asignaciones_vehiculo a
                       JOIN inventario_vehiculos i ON i.id_inventario=a.id_inventario
                       SET a.estado=%s, a.fin=CURRENT_TIMESTAMP, a.motivo=COALESCE(%s,a.motivo)
                       WHERE a.id_asignacion=%s AND i.id_empresa=%s AND a.estado='ACTIVA'""",
                    (estado, motivo, assignment_id, empresa_id),
                )
                if cur.rowcount != 1:
                    cn.rollback()
                    return False
                self._auditar(cur, empresa_id, actor["id_usuario"], estado,
                              "ASIGNACION", assignment_id)
            cn.commit()
            return True
        except Exception:
            cn.rollback()
            raise
        finally:
            cn.close()

    def sesion_invitado_detalle(self, session_id: int, empresa_id: int):
        return self._leer(
            """SELECT s.id_sesion,s.id_vehiculo,s.autorizado_por,s.estado
               FROM sesiones_invitado s JOIN inventario_vehiculos i ON i.id_vehiculo=s.id_vehiculo
               WHERE s.id_sesion=%s AND i.id_empresa=%s""", (session_id, empresa_id), uno=True
        )

    # Sesiones temporales: se persiste únicamente SHA-256 del token de alta entropía.
    def crear_sesion_invitado(self, data: dict, actor: dict, token_hash: str):
        vehicle_id = data["id_vehiculo"]
        command_ids = sorted(set(data["comandos_permitidos"]))
        if len(command_ids) != len(data["comandos_permitidos"]):
            raise ValueError("La lista de comandos contiene duplicados.")
        cn = self._db.obtener_conexion()
        try:
            cn.begin()
            with cn.cursor() as cur:
                cur.execute(
                    """SELECT i.id_vehiculo FROM inventario_vehiculos i
                       WHERE i.id_vehiculo=%s AND i.id_empresa=%s
                         AND i.estado='EN_INVENTARIO' FOR UPDATE""",
                    (vehicle_id, actor["id_empresa"]),
                )
                if not cur.fetchone():
                    raise LookupError("Unidad no disponible en el inventario de la empresa.")
                # Libera la exclusividad de sesiones cuyo TTL terminó sin depender de
                # una tarea programada externa. La transición conserva la fila histórica.
                cur.execute(
                    """UPDATE sesiones_invitado
                       SET estado='EXPIRADA', finalizada_en=CURRENT_TIMESTAMP
                       WHERE id_vehiculo=%s AND estado IN ('RESERVADA','ACTIVA')
                         AND expira_en<=CURRENT_TIMESTAMP""",
                    (vehicle_id,),
                )
                if data.get("id_demo") is not None:
                    cur.execute("SELECT 1 FROM demos WHERE id_demo=%s AND id_vehiculo=%s AND activo=1",
                                (data["id_demo"], vehicle_id))
                    if not cur.fetchone():
                        raise LookupError("DEMO activa no encontrada para esa unidad.")
                marks = ",".join(["%s"] * len(command_ids))
                cur.execute(
                    f"""SELECT c.id_comando
                        FROM comandos c
                        JOIN vehiculos_modelos vm ON vm.id_vehiculo=c.id_vehiculo
                        JOIN comandos_catalogo cc ON cc.id_comando=c.id_comando
                        JOIN capacidades_modelo cap
                          ON cap.id_modelo=vm.id_modelo
                         AND cap.id_catalogo_comando=cc.id_catalogo_comando
                        WHERE c.id_vehiculo=%s AND c.activo=1 AND cap.habilitada=1
                          AND c.id_comando IN ({marks})""",
                    (vehicle_id, *command_ids),
                )
                allowed = {row["id_comando"] for row in cur.fetchall()}
                if allowed != set(command_ids):
                    raise ValueError("Uno o más comandos no pertenecen o no están habilitados para la unidad.")
                cur.execute(
                    """INSERT INTO sesiones_invitado
                       (token_hash,id_vehiculo,id_demo,autorizado_por,estado,inicio,expira_en,
                        comandos_permitidos)
                       VALUES (%s,%s,%s,%s,'RESERVADA',CURRENT_TIMESTAMP,
                         DATE_ADD(CURRENT_TIMESTAMP, INTERVAL %s MINUTE),%s)""",
                    (token_hash, vehicle_id, data.get("id_demo"), actor["id_usuario"],
                     data["duracion_minutos"], json.dumps(command_ids)),
                )
                session_id = cur.lastrowid
                cur.execute("SELECT expira_en FROM sesiones_invitado WHERE id_sesion=%s", (session_id,))
                expiration = cur.fetchone()["expira_en"]
                self._auditar(cur, actor["id_empresa"], actor["id_usuario"],
                              "RESERVAR", "SESION_INVITADO", session_id)
            cn.commit()
            return {"id_sesion": session_id, "expira_en": expiration}
        except Exception:
            cn.rollback()
            raise
        finally:
            cn.close()

    def listar_sesiones_invitado(self, empresa_id: int, estado: str | None,
                                limit: int, offset: int):
        return self._leer(
            """SELECT s.id_sesion,s.id_vehiculo,s.id_demo,s.autorizado_por,s.estado,
                      s.inicio,s.expira_en,s.finalizada_en,s.comandos_permitidos
               FROM sesiones_invitado s
               JOIN inventario_vehiculos i ON i.id_vehiculo=s.id_vehiculo
               WHERE i.id_empresa=%s AND i.estado IN ('EN_INVENTARIO','MANTENIMIENTO')
                 AND (%s IS NULL OR s.estado=%s)
               ORDER BY s.id_sesion DESC LIMIT %s OFFSET %s""",
            (empresa_id, estado, estado, limit, offset),
        )

    def listar_demos_empresa(self, empresa_id: int, vehicle_id: int | None,
                             limit: int, offset: int):
        return self._leer(
            """SELECT d.id_demo,d.id_vehiculo,d.nombre,d.descripcion,d.activo,
                      COUNT(dm.id_demo_movimiento) AS total_pasos
               FROM demos d
               JOIN inventario_vehiculos i ON i.id_vehiculo=d.id_vehiculo
                 AND i.id_empresa=%s
               LEFT JOIN demo_movimientos dm ON dm.id_demo=d.id_demo
               WHERE i.estado='EN_INVENTARIO'
                 AND (%s IS NULL OR d.id_vehiculo=%s)
               GROUP BY d.id_demo,d.id_vehiculo,d.nombre,d.descripcion,d.activo
               ORDER BY d.id_demo LIMIT %s OFFSET %s""",
            (empresa_id, vehicle_id, vehicle_id, limit, offset),
        )

    def demo_en_empresa(self, demo_id: int, empresa_id: int):
        return self._leer(
            """SELECT d.id_demo,d.id_vehiculo,d.nombre,d.descripcion,d.activo
               FROM demos d JOIN inventario_vehiculos i ON i.id_vehiculo=d.id_vehiculo
               WHERE d.id_demo=%s AND i.id_empresa=%s AND i.estado='EN_INVENTARIO'
               LIMIT 1""",
            (demo_id, empresa_id), uno=True,
        )

    def listar_pasos_demo(self, demo_id: int, empresa_id: int):
        return self._leer(
            """SELECT dm.id_demo_movimiento,dm.id_demo,dm.id_comando,c.nombre AS comando,
                      c.codigo,dm.orden,dm.duracion_ms,dm.pausa_ms
               FROM demo_movimientos dm
               JOIN demos d ON d.id_demo=dm.id_demo
               JOIN inventario_vehiculos i ON i.id_vehiculo=d.id_vehiculo
               JOIN comandos c ON c.id_comando=dm.id_comando
               WHERE dm.id_demo=%s AND i.id_empresa=%s AND i.estado='EN_INVENTARIO'
               ORDER BY dm.orden""",
            (demo_id, empresa_id),
        )

    def paso_demo_en_empresa(self, step_id: int, empresa_id: int):
        return self._leer(
            """SELECT dm.id_demo_movimiento,dm.id_demo,dm.id_comando,dm.orden,
                      dm.duracion_ms,dm.pausa_ms,d.id_vehiculo
               FROM demo_movimientos dm
               JOIN demos d ON d.id_demo=dm.id_demo
               JOIN inventario_vehiculos i ON i.id_vehiculo=d.id_vehiculo
               WHERE dm.id_demo_movimiento=%s AND i.id_empresa=%s
                 AND i.estado='EN_INVENTARIO'""",
            (step_id, empresa_id), uno=True,
        )

    def comando_activo_en_vehiculo(self, command_id: int, vehicle_id: int):
        return self._leer(
            "SELECT id_comando FROM comandos WHERE id_comando=%s AND id_vehiculo=%s AND activo=1",
            (command_id, vehicle_id), uno=True,
        )

    def baja_demo(self, demo_id: int, empresa_id: int, actor: dict):
        cn = self._db.obtener_conexion()
        try:
            cn.begin()
            with cn.cursor() as cur:
                cur.execute(
                    """UPDATE demos d JOIN inventario_vehiculos i ON i.id_vehiculo=d.id_vehiculo
                       SET d.activo=0 WHERE d.id_demo=%s AND i.id_empresa=%s
                         AND i.estado='EN_INVENTARIO'""",
                    (demo_id, empresa_id),
                )
                if cur.rowcount == 0:
                    cur.execute(
                        """SELECT d.id_demo FROM demos d JOIN inventario_vehiculos i
                           ON i.id_vehiculo=d.id_vehiculo
                       WHERE d.id_demo=%s AND i.id_empresa=%s AND i.estado='EN_INVENTARIO'""",
                        (demo_id, empresa_id),
                    )
                    if not cur.fetchone():
                        cn.rollback()
                        return False
                self._auditar(cur, empresa_id, actor["id_usuario"], "BAJA", "DEMO", demo_id)
            cn.commit()
            return True
        except Exception:
            cn.rollback()
            raise
        finally:
            cn.close()

    def registrar_evento_auditoria(self, empresa_id: int, user_id: int,
                                   accion: str, entidad: str, entity_id: int):
        self._escribir(
            """INSERT INTO auditoria_administracion
               (id_empresa,id_usuario,accion,entidad,id_entidad,resultado,origen)
               VALUES (%s,%s,%s,%s,%s,'OK','API_ADMIN')""",
            (empresa_id, user_id, accion, entidad, str(entity_id)),
        )

    def revocar_sesion_invitado(self, session_id: int, empresa_id: int, actor: dict):
        cn = self._db.obtener_conexion()
        try:
            cn.begin()
            with cn.cursor() as cur:
                cur.execute(
                    """UPDATE sesiones_invitado s
                       JOIN inventario_vehiculos i ON i.id_vehiculo=s.id_vehiculo
                       SET s.estado='REVOCADA',s.finalizada_en=CURRENT_TIMESTAMP
                       WHERE s.id_sesion=%s AND i.id_empresa=%s
                         AND s.estado IN ('RESERVADA','ACTIVA')""",
                    (session_id, empresa_id),
                )
                if cur.rowcount != 1:
                    cn.rollback()
                    return False
                self._auditar(cur, empresa_id, actor["id_usuario"],
                              "REVOCAR", "SESION_INVITADO", session_id)
            cn.commit()
            return True
        except Exception:
            cn.rollback()
            raise
        finally:
            cn.close()

    def activar_sesion_invitado(self, session_id: int, empresa_id: int, actor: dict):
        cn = self._db.obtener_conexion()
        try:
            cn.begin()
            with cn.cursor() as cur:
                cur.execute(
                    """UPDATE sesiones_invitado s
                       JOIN inventario_vehiculos i ON i.id_vehiculo=s.id_vehiculo
                       SET s.estado='ACTIVA'
                       WHERE s.id_sesion=%s AND i.id_empresa=%s
                         AND s.estado='RESERVADA' AND s.expira_en>CURRENT_TIMESTAMP""",
                    (session_id, empresa_id),
                )
                if cur.rowcount != 1:
                    cn.rollback()
                    return False
                self._auditar(cur, empresa_id, actor["id_usuario"],
                              "ACTIVAR", "SESION_INVITADO", session_id)
            cn.commit()
            return True
        except Exception:
            cn.rollback()
            raise
        finally:
            cn.close()

    def invitado_puede_ejecutar(self, token_hash: str, vehicle_id: int, command_id: int) -> bool | None:
        row = self._leer(
            """SELECT s.id_sesion,s.comandos_permitidos,s.autorizado_por
               FROM sesiones_invitado s
               JOIN inventario_vehiculos i ON i.id_vehiculo=s.id_vehiculo
               JOIN vehiculos v ON v.id_vehiculo=s.id_vehiculo
               WHERE s.token_hash=%s AND s.id_vehiculo=%s AND s.estado='ACTIVA'
                 AND s.expira_en>CURRENT_TIMESTAMP AND i.estado='EN_INVENTARIO'
                 AND i.vehiculo_en_inventario=s.id_vehiculo AND v.activo=1 LIMIT 1""",
            (token_hash, vehicle_id), uno=True,
        )
        if not row:
            return None
        allowed = row["comandos_permitidos"]
        if isinstance(allowed, str):
            allowed = json.loads(allowed)
        if int(command_id) in {int(item) for item in allowed}:
            if row["autorizado_por"] is not None:
                return True
            cn = self._db.obtener_conexion()
            try:
                with cn.cursor() as cur:
                    cur.execute(
                        """UPDATE sesiones_invitado SET comandos_usados=comandos_usados+1,
                             ultimo_comando_en=CURRENT_TIMESTAMP(3)
                           WHERE id_sesion=%s AND token_hash=%s AND id_vehiculo=%s
                             AND estado='ACTIVA' AND expira_en>CURRENT_TIMESTAMP
                             AND comandos_usados<80
                             AND (ultimo_comando_en IS NULL OR ultimo_comando_en <=
                                  DATE_SUB(CURRENT_TIMESTAMP(3), INTERVAL 250000 MICROSECOND))""",
                        (row["id_sesion"], token_hash, vehicle_id),
                    )
                    if cur.rowcount == 1:
                        cn.commit()
                        return True
                cn.rollback()
            finally:
                cn.close()
            still_active = self._leer(
                "SELECT 1 FROM sesiones_invitado WHERE id_sesion=%s AND token_hash=%s "
                "AND estado='ACTIVA' AND expira_en>CURRENT_TIMESTAMP",
                (row["id_sesion"], token_hash), uno=True,
            )
            return False if still_active else None
        # DETENER se conserva como permiso de seguridad aunque la lista de invitado sea limitada.
        stop = self._leer(
            """SELECT 1 FROM comandos WHERE id_comando=%s AND id_vehiculo=%s
               AND activo=1 AND UPPER(nombre)='DETENER' LIMIT 1""",
            (command_id, vehicle_id), uno=True,
        )
        return stop is not None

    def comando_detener_id(self, vehicle_id: int) -> int | None:
        row = self._leer(
            """SELECT id_comando FROM comandos
               WHERE id_vehiculo=%s AND activo=1 AND UPPER(nombre)='DETENER' LIMIT 1""",
            (vehicle_id,), uno=True,
        )
        return int(row["id_comando"]) if row else None

    def sesion_invitado_por_token(self, token_hash: str):
        row = self._leer(
            """SELECT s.id_sesion,s.id_vehiculo,s.id_demo,s.estado,s.expira_en,
                      s.comandos_permitidos
               FROM sesiones_invitado s
               JOIN inventario_vehiculos i ON i.id_vehiculo=s.id_vehiculo
               JOIN vehiculos v ON v.id_vehiculo=s.id_vehiculo
               WHERE s.token_hash=%s AND s.estado='ACTIVA'
                 AND s.expira_en>CURRENT_TIMESTAMP AND i.estado='EN_INVENTARIO'
                 AND i.vehiculo_en_inventario=s.id_vehiculo AND v.activo=1 LIMIT 1""",
            (token_hash,), uno=True,
        )
        if row:
            allowed = row["comandos_permitidos"]
            if isinstance(allowed, str):
                allowed = json.loads(allowed)
            row["comandos_permitidos"] = [int(item) for item in allowed]
        return row

    # Auditoría de solo lectura desde la API; las filas se crean en cada operación.
    def listar_auditoria(self, empresa_id: int, entidad: str | None,
                         limit: int, offset: int):
        return self._leer(
            """SELECT id_auditoria,id_empresa,id_usuario,accion,entidad,id_entidad,
                      resultado,origen,ocurrido_en
               FROM auditoria_administracion
               WHERE id_empresa=%s AND (%s IS NULL OR entidad=%s)
               ORDER BY ocurrido_en DESC,id_auditoria DESC LIMIT %s OFFSET %s""",
            (empresa_id, entidad, entidad, limit, offset),
        )
