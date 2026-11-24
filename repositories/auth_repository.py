from config.database import DatabaseConnection


class AuthRepository:
    """Acceso parametrizado a usuarios, roles y empresa para autenticación."""

    def __init__(self, db: DatabaseConnection):
        self._db = db

    def _obtener(self, condicion: str, valor: str | int) -> dict | None:
        conexion = self._db.obtener_conexion()
        try:
            with conexion.cursor() as cursor:
                cursor.execute(
                    f"""SELECT u.id_usuario, u.id_empresa, u.correo, u.nombre,
                               u.password_hash, u.estado, e.estado AS estado_empresa
                        FROM usuarios u
                        JOIN empresas e ON e.id_empresa=u.id_empresa
                        WHERE {condicion} = %s
                        LIMIT 1""",
                    (valor,),
                )
                usuario = cursor.fetchone()
                if not usuario:
                    return None
                cursor.execute(
                    """SELECT r.clave
                       FROM usuarios_roles ur
                       JOIN roles r ON r.id_rol = ur.id_rol
                       WHERE ur.id_usuario = %s AND r.activo = 1""",
                    (usuario["id_usuario"],),
                )
                usuario["roles"] = [fila["clave"] for fila in cursor.fetchall()]
                return usuario
        finally:
            conexion.close()

    def obtener_por_correo(self, correo: str) -> dict | None:
        return self._obtener("u.correo", correo)

    def obtener_por_correo_id(self, user_id: int) -> dict | None:
        return self._obtener("u.id_usuario", user_id)

    def token_revocado(self, token_hash: str) -> bool:
        conexion = self._db.obtener_conexion()
        try:
            with conexion.cursor() as cursor:
                cursor.execute(
                    "SELECT 1 FROM tokens_revocados WHERE token_hash=%s AND expira_en>CURRENT_TIMESTAMP LIMIT 1",
                    (token_hash,),
                )
                return cursor.fetchone() is not None
        finally:
            conexion.close()

    def revocar_token(self, token_hash: str, user_id: int, expiration):
        conexion = self._db.obtener_conexion()
        try:
            with conexion.cursor() as cursor:
                cursor.execute("DELETE FROM tokens_revocados WHERE expira_en<=CURRENT_TIMESTAMP")
                cursor.execute(
                    """INSERT INTO tokens_revocados (token_hash,id_usuario,expira_en)
                       VALUES (%s,%s,%s)""", (token_hash, user_id, expiration)
                )
            conexion.commit()
        except Exception:
            conexion.rollback()
            raise
        finally:
            conexion.close()

    def modelos_disponibles_compra(self) -> list[dict]:
        conexion = self._db.obtener_conexion()
        try:
            with conexion.cursor() as cursor:
                cursor.execute(
                    """SELECT m.id_modelo,m.codigo,m.nombre,m.microcontrolador
                       FROM modelos_comerciales m
                       WHERE m.estado='ACTIVO'
                         AND EXISTS (
                           SELECT 1 FROM vehiculos_modelos vm
                           JOIN vehiculos v ON v.id_vehiculo=vm.id_vehiculo
                           JOIN comandos c ON c.id_vehiculo=v.id_vehiculo AND c.activo=1
                           WHERE vm.id_modelo=m.id_modelo AND v.activo=1
                         )
                       ORDER BY m.nombre"""
                )
                return cursor.fetchall()
        finally:
            conexion.close()

    def crear_primer_administrador(self, id_empresa: int, correo: str, nombre: str,
                                   password_hash: str) -> int:
        conexion = self._db.obtener_conexion()
        try:
            conexion.begin()
            with conexion.cursor() as cursor:
                # Serializa bootstrap para la empresa y evita crear dos administradores iniciales.
                cursor.execute(
                    "SELECT id_empresa FROM empresas WHERE id_empresa = %s AND estado = 'ACTIVA' FOR UPDATE",
                    (id_empresa,),
                )
                if not cursor.fetchone():
                    raise LookupError("Empresa activa no encontrada.")
                cursor.execute(
                    """SELECT COUNT(*) AS total
                       FROM usuarios u
                       JOIN usuarios_roles ur ON ur.id_usuario = u.id_usuario
                       JOIN roles r ON r.id_rol = ur.id_rol
                       WHERE u.id_empresa = %s AND u.estado = 'ACTIVO'
                         AND r.clave = 'ADMINISTRADOR' AND r.activo = 1""",
                    (id_empresa,),
                )
                if cursor.fetchone()["total"]:
                    raise FileExistsError("La empresa ya tiene un administrador activo.")
                cursor.execute(
                    """INSERT INTO usuarios
                       (id_empresa, correo, nombre, password_hash, estado)
                       VALUES (%s, %s, %s, %s, 'ACTIVO')""",
                    (id_empresa, correo, nombre, password_hash),
                )
                user_id = cursor.lastrowid
                cursor.execute(
                    "SELECT id_rol FROM roles WHERE clave = 'ADMINISTRADOR' AND activo = 1 LIMIT 1"
                )
                row = cursor.fetchone()
                if not row:
                    raise RuntimeError("No existe el rol ADMINISTRADOR activo.")
                cursor.execute(
                    "INSERT INTO usuarios_roles (id_usuario, id_rol) VALUES (%s, %s)",
                    (user_id, row["id_rol"]),
                )
                cursor.execute(
                    """INSERT INTO auditoria_administracion
                       (id_empresa, id_usuario, accion, entidad, id_entidad, resultado, origen)
                       VALUES (%s, %s, 'BOOTSTRAP_ADMIN', 'USUARIO', %s, 'OK', 'API')""",
                    (id_empresa, user_id, str(user_id)),
                )
            conexion.commit()
            return user_id
        except Exception:
            conexion.rollback()
            raise
        finally:
            conexion.close()

    def registrar_comprador(self, empresa_id: int, correo: str, nombre: str,
                            password_hash: str, model_id: int,
                            actor_id: int | None = None,
                            telefono_contacto: str | None = None) -> dict:
        """Crea en una transacción cuenta, cliente, carrito simulado y propiedad."""
        conexion = self._db.obtener_conexion()
        try:
            conexion.begin()
            with conexion.cursor() as cursor:
                cursor.execute(
                    "SELECT id_empresa FROM empresas WHERE id_empresa=%s AND estado='ACTIVA' FOR UPDATE",
                    (empresa_id,),
                )
                if not cursor.fetchone():
                    raise LookupError("La empresa de registro no está activa.")

                cursor.execute(
                    "SELECT id_modelo,nombre,microcontrolador,estado FROM modelos_comerciales "
                    "WHERE id_modelo=%s FOR UPDATE",
                    (model_id,),
                )
                model = cursor.fetchone()
                if not model or model["estado"] != "ACTIVO":
                    raise LookupError("El modelo seleccionado no está activo.")

                # Copia el catálogo real de capacidades de una unidad plantilla del modelo.
                cursor.execute(
                    """SELECT v.id_vehiculo
                       FROM vehiculos_modelos vm
                       JOIN vehiculos v ON v.id_vehiculo=vm.id_vehiculo
                       WHERE vm.id_modelo=%s AND v.activo=1
                       ORDER BY v.id_vehiculo LIMIT 1 FOR UPDATE""",
                    (model_id,),
                )
                template = cursor.fetchone()
                if not template:
                    raise LookupError("El modelo todavía no tiene una plantilla de comandos.")
                cursor.execute(
                    """SELECT id_comando,nombre,codigo,descripcion,mascara
                       FROM comandos WHERE id_vehiculo=%s AND activo=1 ORDER BY codigo""",
                    (template["id_vehiculo"],),
                )
                template_commands = cursor.fetchall()
                if not template_commands:
                    raise LookupError("El modelo no tiene comandos configurados para simular el carrito.")

                cursor.execute(
                    "INSERT INTO usuarios (id_empresa,correo,nombre,password_hash,estado) "
                    "VALUES (%s,%s,%s,%s,'ACTIVO')",
                    (empresa_id, correo, nombre, password_hash),
                )
                user_id = int(cursor.lastrowid)
                cursor.execute("SELECT id_rol FROM roles WHERE clave='USUARIO' AND activo=1 LIMIT 1")
                role = cursor.fetchone()
                if not role:
                    raise RuntimeError("No existe el rol USUARIO activo.")
                cursor.execute(
                    "INSERT INTO usuarios_roles (id_usuario,id_rol) VALUES (%s,%s)",
                    (user_id, role["id_rol"]),
                )

                cursor.execute(
                    "INSERT INTO clientes (id_empresa,nombre,correo_contacto,telefono_contacto) VALUES (%s,%s,%s,%s)",
                    (empresa_id, nombre, correo, telefono_contacto),
                )
                client_id = int(cursor.lastrowid)
                cursor.execute(
                    "INSERT INTO usuarios_clientes (id_usuario,id_cliente,estado) VALUES (%s,%s,'ACTIVO')",
                    (user_id, client_id),
                )

                vehicle_name = f"Carrito simulado {user_id}"[:80]
                cursor.execute(
                    """INSERT INTO vehiculos (nombre,modelo,descripcion,microcontrolador,activo)
                       VALUES (%s,%s,%s,'SIMULADO',1)""",
                    (vehicle_name, str(model["nombre"])[:80], "Instancia virtual del comprador; sin ESP físico."),
                )
                vehicle_id = int(cursor.lastrowid)
                cursor.execute(
                    "INSERT INTO vehiculos_modelos (id_vehiculo,id_modelo,origen_mapeo) "
                    "VALUES (%s,%s,'MANUAL')",
                    (vehicle_id, model_id),
                )
                cursor.execute(
                    "INSERT INTO inventario_vehiculos (id_empresa,id_vehiculo,estado) "
                    "VALUES (%s,%s,'VENDIDO')",
                    (empresa_id, vehicle_id),
                )
                inventory_id = int(cursor.lastrowid)

                command_map: dict[int, int] = {}
                for command in template_commands:
                    cursor.execute(
                        """INSERT INTO comandos
                           (id_vehiculo,nombre,codigo,descripcion,activo,mascara)
                           VALUES (%s,%s,%s,%s,1,%s)""",
                        (vehicle_id, command["nombre"], command["codigo"],
                         command["descripcion"], command["mascara"]),
                    )
                    command_map[int(command["id_comando"])] = int(cursor.lastrowid)

                # Conserva la semántica del catálogo de comandos del modelo para la unidad virtual.
                for old_command_id, new_command_id in command_map.items():
                    cursor.execute(
                        "SELECT id_catalogo_comando FROM comandos_catalogo WHERE id_comando=%s",
                        (old_command_id,),
                    )
                    for catalog in cursor.fetchall():
                        cursor.execute(
                            "INSERT INTO comandos_catalogo (id_comando,id_catalogo_comando) VALUES (%s,%s)",
                            (new_command_id, catalog["id_catalogo_comando"]),
                        )

                cursor.execute(
                    """INSERT INTO asignaciones_vehiculo
                       (id_inventario,id_vehiculo,id_cliente,estado,motivo)
                       VALUES (%s,%s,%s,'ACTIVA','Compra simulada; carrito virtual')""",
                    (inventory_id, vehicle_id, client_id),
                )
                cursor.execute(
                    """INSERT INTO auditoria_administracion
                       (id_empresa,id_usuario,accion,entidad,id_entidad,resultado,origen)
                       VALUES (%s,%s,'REGISTRO_COMPRADOR','CLIENTE_CARRITO',%s,'OK','API_SIMULACION')""",
                    (empresa_id, actor_id or user_id, str(vehicle_id)),
                )
            conexion.commit()
            return {"id_usuario": user_id, "id_cliente": client_id, "id_vehiculo": vehicle_id}
        except Exception:
            conexion.rollback()
            raise
        finally:
            conexion.close()
