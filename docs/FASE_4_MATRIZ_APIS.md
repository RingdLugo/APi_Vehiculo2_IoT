# Fase 4 — Inventario de contratos FastAPI

Esta matriz describe las rutas implementadas en el código de `api_vehiculo_2`. La lista autoritativa publicada es `/openapi.json`; no representa un conteo fijo de procedimientos almacenados. CONTROL y MONITOREO conservan sus rutas REST y eventos WSS.

## Matriz por función

| Función | Estado | Rutas relevantes | Observaciones |
|---|---|---|---|
| Salud | Nueva | `GET /health` | API responde y RDS se verifica desde backend con `SELECT 1`; no expone credenciales. |
| Login, perfil y registro de comprador | Existentes | `POST /auth/token`, `GET /auth/me`, `GET /auth/modelos`, `POST /auth/registro-comprador` | Crea cuenta de comprador y carrito virtual `SIMULADO`; no representa hardware ni una venta/pago real. |
| Bootstrap inicial | Existente | `POST /auth/bootstrap-admin` | Solo con `X-Bootstrap-Key`, empresa existente y sin administrador vigente. |
| Modelos comerciales | Existente | `GET/POST /admin/modelos`, `GET/PATCH/DELETE /admin/modelos/{model_id}` | CRUD con baja lógica, búsqueda y paginación. |
| Unidades e inventario | Existente | `GET/POST /admin/unidades`, `GET/PATCH/DELETE /admin/unidades/{vehicle_id}` | El alcance se obtiene del token; la unidad física conserva su ID. Baja lógica valida estados y relaciones. |
| Compradores y carritos | Existente | `GET/POST /admin/clientes`, `GET/PATCH/DELETE /admin/clientes/{client_id}` | El alta crea en una transacción cliente, usuario y carrito virtual con ID propio; nunca asigna una unidad física. |
| Usuarios y roles | Existente | `GET /admin/roles`, `GET/POST /admin/usuarios`, `PATCH /admin/usuarios/{user_id}/estado` | Crear cuenta de comprador exige modelo activo y también genera el carrito virtual. |
| Asignaciones | Existente | `GET/POST /admin/asignaciones`, `PATCH /admin/asignaciones/{assignment_id}` | Valida cliente y unidad de la empresa, estado y asignación exclusiva. |
| Demos y pasos | Existente y ampliada | `GET/POST /admin/demos`, `GET/PATCH/DELETE /admin/demos/{demo_id}`, `/admin/demos/{demo_id}/pasos`, `/admin/demos/pasos/{step_id}` | Admin puede consultar/gestionar también demos del carrito virtual vendido. Los comandos se validan contra la unidad. |
| DEMOs del comprador | Existente | `/cuenta/vehiculos/{vehicle_id}/demos` y sus rutas de pasos | Rutas limitadas a vehículos autorizados por la cuenta. |
| Sesiones de invitado | Existente | `GET/POST /admin/sesiones-invitado`, `PATCH .../{session_id}/activar`, `PATCH .../{session_id}/revocar`, `GET /guest/sesion`, `POST /guest/vehiculos/{vehicle_id}/movimiento` | El secreto se muestra al crear y se guarda como hash; el servidor aplica vigencia, unidad y comandos permitidos. |
| Auditoría | Existente | `GET /admin/auditoria` | Solo lectura y restringida a la empresa autenticada; las mutaciones administrativas registran eventos. |
| CONTROL, MONITOREO y comandos | Existente; middleware reforzado | `/vehiculos/*`, `/comandos/*`, `/demos/*` | Las respuestas existentes se conservan. Rutas REST requieren Bearer y el middleware valida rol/alcance de unidad. |
| WSS de cuenta | Existente | `/ws/cuenta/vehiculo/{vehicle_id}` | Requiere primer mensaje JSON con `access_token` o `guest_token`; verifica permiso de unidad. El dashboard cuenta sólo sesiones marcadas como navegador y no telemetría física del ESP. |
| WSS de dispositivo | Actualizado | `/ws/vehiculo/{vehiculo_id}` | Requiere `IOT_DEVICE_TOKEN_<id>` por unidad en el primer JSON; el firmware debe aprovisionarse con el mismo secreto. Un token no habilita otras unidades. |
| Dashboard de Administración | Nuevo | `GET /admin/dashboard` | Solo Admin. Métricas salen de RDS; sesiones WSS cuentan conexiones autenticadas del navegador y no prueban que el ESP esté conectado. |

## Seguridad y errores

- Rutas administrativas exigen Bearer válido y rol `ADMINISTRADOR`; el `id_empresa` siempre se deriva del token.
- Las rutas de cuenta y legado verifican la propiedad/asignación en el backend. Los filtros del navegador no otorgan acceso.
- `401` identidad faltante o inválida; `403` rol insuficiente; `404` recurso inexistente/fuera del ámbito; `409` conflicto de integridad/estado; `422` parámetros o cuerpo inválidos. Algunas rutas devuelven `400` para transición de negocio inválida.
- Los SQL de repositorios usan parámetros para valores; las listas de campos dinámicos se limitan a allowlists.
- Las bajas administrativas son lógicas. No se borran unidades ni se reinician identificadores.

## Compatibilidad y comprobación

La app usa un solo `HttpClient`, conserva el cliente WSS global y sincroniza el estado/historial de Control y Monitoreo mediante REST tras eventos/reconexiones. Swagger se genera desde rutas implementadas y sus esquemas Pydantic.

La compilación sintáctica local no sustituye la generación de `/openapi.json` ni las pruebas de integración desde Swagger/Postman. Las escrituras deben probarse con una copia de la base; no se debe usar `/admin/*` contra producción para una prueba destructiva. Una publicación final requiere validar con credenciales de prueba que altas, edición, asignaciones, acceso cruzado denegado, demos, pasos, health, historial y rutas legadas respondan como se documenta.
