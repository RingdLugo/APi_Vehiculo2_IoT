# Seguridad y evaluación cruzada (P01–P17)

**Versión del API:** 1.6.0  
**Fecha de revisión:** 2026-11-22  
**Estado de ejecución:** se hizo revisión del código y se recopilaron comprobaciones técnicas del navegador/API. Las pruebas colaborativas P01–P17 continúan **No ejecutado** hasta completar sus criterios y guardar evidencia; no se anotan resultados supuestos.

## Evidencia técnica recopilada

Estas comprobaciones ayudan a acotar fallos, pero no sustituyen los escenarios P01–P17:

| Comprobación | Resultado observado | Alcance |
|---|---|---|
| Preflight `OPTIONS /cuenta/vehiculos/5/movimiento` desde `https://controlwish.duckdns.org` | HTTP 200; CORS permitió el origen, `POST`, `authorization` y `content-type`. | Verifica preflight, no el movimiento autenticado. |
| `POST /cuenta/vehiculos/5/movimiento` sin credenciales | HTTP 401 con `Access-Control-Allow-Origin` correcto. | Confirma rechazo sin autenticación y CORS en esa respuesta. No ejecutó comando. |
| `GET /cuenta/vehiculos/5/comandos` desde la sesión del navegador | HTTP 200; se recibió el catálogo de 13 comandos. | Confirma lectura autorizada del catálogo en esa sesión; no prueba aislamiento entre compradores. |
| POST autenticado de movimiento, primera ejecución | HTTP 500 por argumento `estado_salida` no admitido por `EventoMovimientoIndividual`. | Se corrigió el constructor y se publicó el archivo actualizado; la alumna confirmó que el control volvió a funcionar. Falta adjuntar evidencia de persistencia, WSS e historial para completar P06/P07/P08. |

La ausencia de `Access-Control-Allow-Origin` en aquella respuesta 500 era consecuencia de la excepción no controlada. No se tomó como diagnóstico de CORS: el preflight y el POST sin credenciales sí devolvieron los encabezados esperados.

## Roles y reglas de acceso

- **Administrador:** administra modelos, inventario de la empresa, compradores, asignaciones, demos de exhibición, sesiones invitadas y auditoría. Puede operar unidades aún disponibles en inventario. No puede consultar ni operar carritos vendidos ni demos privadas del comprador.
- **Usuario/comprador:** solo puede consultar y operar vehículos con asignación activa vinculada a su cuenta. Las rutas de recurso fuera de su alcance responden 404 para no revelar si existe un vehículo ajeno. Los cambios de rol, revocación y permisos se validan en FastAPI, aunque se altere la petición desde DevTools/Postman.
- **Invitado:** usa catálogo público y una sesión temporal que reserva en exclusiva una unidad de exhibición. La sesión se vence o se revoca en backend y limita comandos y frecuencia.
- **Dispositivo:** `/ws/vehiculo/{vehiculo_id}` requiere `IOT_DEVICE_TOKEN_<id>` en el primer mensaje JSON. El token se compara en tiempo constante, es distinto por vehículo y no se registra. La ESP8266 debe enviar `{"device_token":"…"}` y considerar WSS activo solo al recibir `conexion_establecida`.
- **DETENER:** cancela DEMO antes de emitir el comando prioritario y no queda sujeto al límite ordinario de movimientos. La respuesta confirma la orden del servidor; la ejecución física solo se confirma con telemetría real.

Configurar en el servidor `CORS_ORIGINS=https://controlwish.duckdns.org` y una clave aleatoria por unidad, por ejemplo `IOT_DEVICE_TOKEN_1` para el carrito físico renumerado. Cargar la misma clave en el portal local del firmware. No guardar claves en el repositorio, capturas o auditoría. El frontend web usa `/ws/cuenta/vehiculo/{id}` con token de cuenta o invitado; ese endpoint revalida permisos y vigencia periódicamente y al cerrar sesión se desconecta.

El backend comprueba credenciales Bearer, estado/expiración y revocación contra RDS; `POST /auth/logout` revoca el token y cierra los sockets del usuario. Límites HTTP por IP: login 15/minuto, registro de comprador 5/minuto y reserva pública 5/minuto. Los movimientos individuales tienen un máximo de 50 por unidad cada 10 segundos (por proceso) y las sesiones invitadas tienen sus propios límites de tiempo/comandos/frecuencia. Estos contadores están en memoria del proceso y se reinician con el servicio; en más de una instancia deben reemplazarse por un limitador compartido. Las rutas ejecutan consultas SQL parametrizadas. TLS/WSS, CORS y acceso RDS deben verificarse también en el despliegue, no solo leyendo el código.

## Matriz de pruebas

Estados admitidos: **Correcto**, **Incorrecto** o **No ejecutado**. Completa evidencia con captura, fecha/hora, identidad de prueba y respuesta HTTP/WSS. Sustituye el estado solo después de ejecutar la comprobación.

| ID | Prueba y criterio observable | Estado inicial | Evidencia / resultado real |
|---|---|---|---|
| P01 | Login Admin válido; `/auth/me` informa rol y empresa esperados. Sin token, ruta protegida devuelve 401. | No ejecutado | |
| P02 | Admin crea modelo/unidad disponible; fila y claves persisten en RDS sin alterar IDs existentes. | No ejecutado | |
| P03 | Admin registra comprador; cuenta, cliente y carrito virtual quedan relacionados. | No ejecutado | |
| P04 | Admin asigna unidad; comprador obtiene únicamente su recurso asignado. | No ejecutado | |
| P05 | Comprador A intenta consultar IDs, estados, demos e historial de B por REST y URL manipulada; obtiene 404/403 y ningún dato de B. | No ejecutado | |
| P06 | Comprador opera su unidad; movimiento persiste y se refleja en la API y monitoreo. | No ejecutado | |
| P07 | WSS autorizado por sesión de cuenta/dispositivo recibe eventos; token ausente/incorrecto o token de otro vehículo se rechaza. | No ejecutado | |
| P08 | Monitoreo concilia REST tras WSS y muestra último movimiento y hasta diez movimientos individuales con fecha/hora. | No ejecutado | |
| P09 | Comprador crea/guarda demo privada; después de recargar continúa asociada al mismo comprador y vehículo. | No ejecutado | |
| P10 | Inicia demo y ejecuta DETENER; la demo se cancela y el comando prioritario se emite. Confirmar efecto físico por telemetría. | No ejecutado | |
| P11 | Invitado consulta catálogo, reserva demo limitada y no puede operar fuera de comandos/tiempo permitidos. | No ejecutado | |
| P12 | Invitado intenta `/admin/...`; recibe 401 sin identidad o 403 con rol insuficiente. | No ejecutado | |
| P13 | A intenta operar unidad/demo de B por REST y WSS; no recibe información ni controla el recurso. | No ejecutado | |
| P14 | Dos sesiones invitadas reservan simultáneamente una misma unidad; solo una obtiene reserva, la otra recibe 409. | No ejecutado | |
| P15 | Interrumpir WSS de forma controlada; verificar indicadores API/RDS/WSS por separado, reconectar y reconciliar con REST sin perder historial. | No ejecutado | |
| P16 | Verificar CONTROL, MONITOREO y ADMINISTRACIÓN en móvil vertical/horizontal, tablet y escritorio; adjuntar capturas sin cortes ni desbordamiento. | No ejecutado | |
| P17 | Revisar auditoría de altas/bajas, roles, asignación, demo y sesión temporal: fecha, actor, acción, recurso y resultado; confirmar ausencia de contraseñas/tokens. | No ejecutado | |

Consulta segura para revisar eventos sin traer metadatos ni credenciales:

```sql
SELECT ocurrido_en, id_usuario, accion, entidad, id_entidad, resultado, origen
FROM auditoria_administracion
WHERE id_empresa = 1
ORDER BY ocurrido_en DESC, id_auditoria DESC
LIMIT 100;
```

## Presentación en equipo de tres

Cada alumno presenta su propia instancia. En cada ronda el evaluador registra P01–P17 en la plataforma anfitriona y conserva su evidencia:

| Ronda | Administrador/anfitrión | Usuario/comprador | Invitado |
|---|---|---|---|
| A | A | B | C |
| B | B | C | A |
| C | C | A | B |

## Recuperación y límites

No se ejecutaron aquí operaciones contra la instancia productiva ni la base RDS. Antes de probar datos reales, usar cuentas y vehículos de prueba, verificar que el respaldo pueda restaurarse y evitar DDL durante la evaluación. El WSS físico antiguo deja de aceptar conexiones anónimas: el firmware tiene que compilarse y configurarse con el token propio de la unidad antes de volver a conectar. Las restricciones de frecuencia en memoria del proceso se reinician al reiniciar el API; la exclusividad de sesiones invitadas sí se basa en el estado persistido en RDS.

**Sesiones de soporte Admin:** no se implementa acceso de soporte a carritos vendidos. El Admin solo opera unidades disponibles de inventario; no debe presentarse como que tiene consentimiento o una sesión de soporte autorizada.
