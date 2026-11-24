# Fase 4 — Contratos implementados y validación

La referencia ejecutable de contratos es OpenAPI en `/openapi.json` y Swagger UI en `/docs`. En este repositorio se agregan rutas administrativas y de autenticación sin cambiar la forma de respuesta de las rutas antiguas usadas por Control y Monitoreo.

## Matriz de operaciones

| Recurso/función | Rutas nuevas o ampliadas | Operaciones | Alcance y controles |
|---|---|---|---|
| Registro/Autenticación | `/auth/bootstrap-admin`, `/auth/registro-comprador`, `/auth/modelos`, `/auth/token`, `/auth/me` | POST, POST, GET, POST, GET | Alta atómica de comprador/cliente/carrito virtual; catálogo de modelos disponibles; bootstrap, login y bearer de 30 min. |
| Modelos comerciales | `/admin/modelos`, `/admin/modelos/{model_id}` | GET, POST, GET, PATCH, DELETE | Administrador; catálogo compartido; DELETE es baja lógica. |
| Unidades | `/admin/unidades`, `/admin/unidades/{vehicle_id}` | GET, POST, GET, PATCH, DELETE | Administrador; empresa del token; inventario propio; baja lógica valida asignaciones/sesiones. |
| Comprador/cliente | `/admin/clientes`, `/admin/clientes/{client_id}` | GET, POST, GET, PATCH, DELETE | Crear comprador registra cuenta `USUARIO`, cliente y carrito `SIMULADO` con comandos propios; exige modelo activo. |
| Usuarios/roles | `/admin/roles`, `/admin/usuarios`, `/admin/usuarios/{user_id}/estado` | GET, GET, POST, PATCH | Alta de usuario comprador requiere modelo y crea carrito virtual; rol no se toma del JSON. |
| Asignaciones | `/admin/asignaciones`, `/admin/asignaciones/{assignment_id}` | GET, POST, PATCH | Comprueba unidad y cliente dentro de la empresa; duplicados/estados incompatibles son 409. |
| Demos/pasos | `/admin/demos`, `/admin/demos/{demo_id}`, `/admin/demos/{demo_id}/pasos`, `/admin/demos/pasos/{step_id}` | GET, POST, PATCH, DELETE | Reutiliza `demos`, `demo_movimientos` y procedimientos existentes; comprueba dueño y comandos de la unidad. |
| DEMOs de comprador | `/cuenta/vehiculos/{id}/demos`, `/cuenta/vehiculos/{id}/demos/{demo_id}/pasos` | POST, POST | Crea DEMOs y pasos solo para carritos autorizados; el comando debe pertenecer a esa unidad. |
| Invitados | `/admin/sesiones-invitado`, `/admin/sesiones-invitado/{session_id}/activar`, `/admin/sesiones-invitado/{session_id}/revocar`, `/guest/vehiculos/{vehicle_id}/movimiento` | GET, POST, PATCH, PATCH, POST | Token aleatorio devuelto una vez y persistido como SHA-256; vigencia, unidad y comandos permitidos se validan en servidor. |
| Auditoría | `/admin/auditoria` | GET | Solo lectura, restringida a empresa y paginada; cambios administrativos escriben sus eventos. |
| Salud | `/health` | GET | Prueba API y ejecuta `SELECT 1` desde backend para estado RDS; el detalle del error no se publica. |
| Dashboard Admin | `/admin/dashboard` | GET | Métricas de modelos, unidades, clientes, DEMOs y sesiones navegador-servidor WSS. No indica conexión física ESP. |
| Control/Monitoreo legado | Rutas existentes `/vehiculos`, `/comandos`, `/demos` | Se conserva contrato | Middleware valida Bearer, rol y alcance de unidad sin cambiar las respuestas exitosas consumidas por Control/Monitoreo. |
| WSS de cuenta | `/ws/cuenta/vehiculo/{id}` | WSS | Primer mensaje JSON con Bearer o token de invitado; se valida permiso de vehículo. |
| WSS dispositivo | `/ws/vehiculo/{id}` | WSS | Requiere el token secreto por vehículo en el primer JSON; firmware y servidor deben configurarse con el mismo secreto. |

## Ejemplos para Swagger

Los valores son ficticios. No publiques tokens reales en Swagger, capturas o repositorios.

`POST /auth/registro-comprador` crea de forma atómica una cuenta `USUARIO`, la ficha de cliente, un carrito virtual marcado `SIMULADO`, sus comandos y la asignación. El registro no representa un pago ni un ESP físico. `GET /auth/modelos` devuelve solo modelos activos con una unidad plantilla que tenga comandos configurados.

```json
{"nombre":"Compradora de prueba","correo":"compradora@example.test","password":"Cambiar-Esta-Clave-123!","id_modelo":1}
```

La respuesta incluye `id_vehiculo` y un `access_token`. Usa ese ID en rutas de cuenta y WSS; no supongas que tendrá un valor fijo. Para una DEMO propia: crea con `POST /cuenta/vehiculos/{id_vehiculo}/demos` y agrega pasos ordenados con `POST /cuenta/vehiculos/{id_vehiculo}/demos/{demo_id}/pasos`.

`POST /auth/bootstrap-admin`, header `X-Bootstrap-Key: <secreto-configurado>`:

```json
{
  "id_empresa": 1,
  "correo": "admin@example.test",
  "nombre": "Administración de prueba",
  "password": "Cambiar-Esta-Clave-123!"
}
```

`POST /auth/token`:

```json
{"correo":"admin@example.test","password":"Cambiar-Esta-Clave-123!"}
```

Luego introduce `Bearer <access_token>` en **Authorize** de Swagger. Las rutas `/admin/*` requieren `ADMINISTRADOR`; 401 es falta/token inválido y 403 es rol insuficiente. La empresa se deriva del token, no del body.

`GET /health` devuelve `api`, `rds` (`disponible` o `no disponible`) y `verificado_en`. La respuesta indica que el servidor contestó y si pudo ejecutar una lectura simple en RDS.

`GET /admin/dashboard` requiere Bearer de administrador y devuelve métricas reales de la empresa. `unidades_con_sesion_wss` cuenta sockets de navegador observados por la API; no debe interpretarse como presencia del ESP físico. Las rutas listadas aceptan `limit` 1–100 y `offset` >= 0; filtros declarados por ruta son `q`, `estado`, `activo`, `id_vehiculo` y `entidad`.

La configuración local se documenta en `.env.example`; debe copiarse a `.env` y reemplazar cada marcador por valores privados. `AUTH_SECRET` firma tokens por 30 minutos y `BOOTSTRAP_ADMIN_KEY` permite únicamente el alta inicial; ambos deben ser secretos distintos y no deben quedar en Git.

`POST /admin/unidades`:

```json
{"nombre":"Unidad de demostración","descripcion":"Unidad de prueba","microcontrolador":"ESP32","id_modelo":1}
```

`POST /admin/asignaciones`:

```json
{"id_vehiculo":5,"id_cliente":1,"motivo":"Prueba autorizada"}
```

`POST /admin/demos` y `POST /admin/demos/{demo_id}/pasos`:

```json
{"id_vehiculo":5,"nombre":"Recorrido de prueba","descripcion":"Secuencia corta"}
```

```json
{"id_comando":14,"orden":1,"duracion_ms":1000,"pausa_ms":500}
```

IDs y orden deben ser positivos; duración y pausa tienen máximo de 3,600,000 ms. Cada operación valida la empresa de la unidad y que los comandos estén activos y sean de esa unidad.

`POST /admin/sesiones-invitado`:

```json
{"id_vehiculo":5,"id_demo":null,"duracion_minutos":15,"comandos_permitidos":[14,22]}
```

La respuesta entrega `token_invitado` una sola vez. Activa mediante `PATCH /admin/sesiones-invitado/{session_id}/activar`; el invitado envía `POST /guest/vehiculos/5/movimiento`, header `X-Guest-Token: <token>` y cuerpo `{"comando_id":14}`. El servidor rechaza tokens vencidos/inactivos con 401 y comandos fuera del permiso con 403.

## Estados y paginación

- `200`: consulta o modificación con cuerpo.
- `201`: creado; `204`: baja lógica sin cuerpo.
- `400`: transición o regla de negocio inválida; `401`: no autenticado.
- `403`: rol/permisos insuficientes; `404`: ID inexistente o fuera del ámbito de empresa.
- `409`: duplicado, unidad ocupada o estado incompatible; `422`: esquema/parámetro no válido.

Las listas administrativas aceptan `limit` entre 1 y 100 y `offset` desde cero, además de filtros declarados en Swagger. Los SQL usan parámetros; los nombres de columna dinámicos provienen de allowlists.

## Evidencia y límites de las pruebas

- La compilación sintáctica de Python y la comprobación sintáctica de los módulos JavaScript se ejecutaron localmente. La importación de FastAPI/OpenAPI no se pudo ejecutar en este entorno porque no tiene instalado `pymysql` (dependencia del proyecto); no equivale a prueba integral de RDS.
- Las pruebas de escritura desde Swagger/Postman deben hacerse con cuentas y una copia aislada. Este cambio no ejecuta mutaciones en RDS.
- Las rutas REST legadas exigen bearer y validan ámbito. WSS de cuenta revalida token/propiedad; WSS del dispositivo compara el token de esa unidad en tiempo constante y no registra credenciales.
