# Fases 7–10: administración comercial, DEMOs y roles

## Alcance implementado

La aplicación conserva las rutas y módulos anteriores de Control y Monitoreo, y agrega la administración comercial bajo `/admin`, operaciones de cuenta bajo `/cuenta`, catálogo/sesiones de invitado bajo `/guest`, autenticación en `/auth` y WSS autenticado de navegador en `/ws/cuenta/vehiculo/{vehicle_id}`. La definición pública de contratos se genera desde las rutas registradas; Swagger es `/docs` y OpenAPI `/openapi.json`.

El registro de comprador crea en una transacción una cuenta, un cliente, un carrito virtual ligado a un modelo comercial, su catálogo de comandos y una asignación. Una unidad virtual no se presenta como hardware conectado: el tablero muestra conectividad WSS del navegador cuando se observa y la salida física queda «Sin verificar».

## Matriz de reutilización y contrato

| Función | API/ruta | Resultado |
|---|---|---|
| Modelos comerciales | `/admin/modelos` y `/admin/modelos/{model_id}` | CRUD administrativo con baja lógica |
| Unidades e inventario | `/admin/unidades` y `/admin/unidades/{vehicle_id}` | Alta, consulta, edición y baja lógica; marca de exhibición separada |
| Clientes/compradores | `/admin/clientes` y `/admin/clientes/{client_id}` | CRUD administrativo con filtros y paginación |
| Usuarios/roles | `/admin/usuarios`, `/admin/usuarios/{user_id}/estado`, `/admin/roles` | consulta, cambio de estado y roles; el alcance se vuelve a comprobar en API |
| Asignaciones | `/admin/asignaciones` y `/admin/asignaciones/{assignment_id}` | crear y cerrar; conservar histórico; reasignar cerrando y creando una nueva |
| DEMOs públicas | `/admin/demos`, `/admin/demos/{demo_id}`, `/admin/demos/{demo_id}/pasos`, `/admin/demos/pasos/{step_id}` | gestión administrativa de demos y pasos ordenados |
| DEMOs del comprador | `/cuenta/vehiculos/{vehicle_id}/demos` y rutas hijas `/pasos` | alta y edición de demos propias, con comandos compatibles con el modelo |
| Sesiones de invitado | `/admin/sesiones-invitado`, activar/revocar; `/guest/catalogo`, `/guest/sesiones`, `/guest/sesiones/actual` | exposición agregada, reserva exclusiva temporal y cierre |
| Auditoría | `/admin/auditoria` | consulta de eventos administrativos |
| Estado/historial/comandos | rutas existentes y `/cuenta/vehiculos/{id}/...` | se conservan contratos anteriores de Control/Monitoreo; las rutas de cuenta validan propiedad |
| Salud | `/health` (ver contrato publicado) | estado del servicio; RDS solo se reporta comprobado si el backend consultó la conexión |

Los GET con listados aceptan filtros y `limit`/`offset` donde están declarados. Los cuerpos, restricciones, ejemplos y respuestas 401/403/404/409/422 se consultan en Swagger generado. No se debe anunciar en el frontend una ruta distinta de la que figure en OpenAPI.

## Autorización

- Administrador: valida empresa, rol y unidad para cada operación comercial.
- Comprador: las rutas `/cuenta` validan asignación activa y propiedad de cada DEMO antes de leer o escribir.
- Invitado: usa un token temporal aleatorio; la base conserva su hash, la reserva es exclusiva, dura diez minutos y solo habilita la lista de comandos de exhibición. El servidor limita la frecuencia y cantidad de movimientos públicos.
- Cierre de sesión de cuenta: `POST /auth/logout` revoca el token actual y cierra las conexiones de navegador de esa cuenta.
- WSS de navegador: `/ws/cuenta/vehiculo/{vehicle_id}` valida token o sesión temporal antes de aceptar operaciones y eventos.
- El endpoint histórico `/ws/vehiculo/{vehiculo_id}` se conserva para compatibilidad con dispositivos instalados. No debe usarse para una sesión del navegador ni considerarse protegido por roles; el control por token se aplica al endpoint `/ws/cuenta/...`. Para proteger también el canal dispositivo se requiere una credencial por dispositivo y actualización coordinada del firmware antes de cerrar la ruta antigua.

Los indicadores del dashboard separan API, sesión WSS de navegador y RDS. «Sesión WSS activa» no demuestra que el microcontrolador esté en línea ni confirma que una salida física haya actuado.

## Demos

Las demos privadas del comprador conservan sus pasos en `demo_movimientos`; se validan en servidor contra el vehículo, el modelo y sus capacidades. El editor permite reordenar y quitar pasos, limita cada paso a 10 segundos, cada secuencia a 20 pasos y el total a 60 segundos. Guardar reemplaza la secuencia de forma transaccional. Cancelar descarta el borrador del navegador. La ejecución conserva las rutas de Control y la cancelación usa la operación DETENER existente; una respuesta API/WSS no se presenta como confirmación física del hardware.

## Migraciones requeridas antes de desplegar este código

Orden para una copia de prueba: verificar que V043 está aplicada y sus tablas/llaves corresponden al inventario real; aplicar `V044_001__unidades_exhibicion.sql`; aplicar `V044_003__limites_sesion_invitado.sql`; aplicar `V045_001__revocacion_tokens_sesion.sql`. Ejecutar verificaciones y revisar conteos, llaves, lecturas de historial y demos. Los scripts de esta entrega están también en `D:\iotAlis\api_vehiculo_2\migrations` para copiarlos junto con la API.

Los scripts contienen DDL, que en MySQL puede confirmar implícitamente una transacción. La reversión no es un `ROLLBACK`: se documenta en `R044_001__unidades_exhibicion.sql`, `R044_003__limites_sesion_invitado.sql` y `R045_001__revocacion_tokens_sesion.sql`; revisar sus SELECT de impacto, guardar copia y revertir solo cuando el API ya no dependa de esas columnas/tablas. No ejecutar en producción sin copia verificable y una prueba aislada aprobada.

## Comprobación y despliegue

En este cambio se comprobó sintaxis Python y se inspeccionaron los contratos OpenAPI localmente. No se ejecutaron altas, asignaciones ni comandos contra la instancia RDS productiva y no se hizo despliegue. Antes de liberar, ejecutar desde Swagger/Postman en ambiente de prueba: login/logout; rol sin acceso; comprador con y sin asignación; lectura y escritura cruzada de DEMOs; edición y orden de pasos; dos solicitudes simultáneas de invitado para una unidad; expiración/revocación con DETENER; y regresión de `/vehiculos`, comandos, estado, historial, DEMO y salud.

Guardar fecha, commit/versión de API, versión de MySQL, respaldo, conteos y respuestas de las verificaciones; capturar las consultas SQL antes/después. Al aprobar la prueba, desplegar API y frontend compatibles en la misma ventana y verificar `/openapi.json`, salud, Control, Monitoreo y Administración.
