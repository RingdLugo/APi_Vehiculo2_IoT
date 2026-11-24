-- Reversión de V047_001. Requiere que los IDs originales 5 y 14..22,35..37 sigan libres.
-- Ejecutar sentencia por sentencia; no ejecutarla si nuevas filas ocupan esos IDs.

USE `vehiculo_iot`;

-- PREVIO: ID 1 es el carrito físico; ID 5 está libre; sus comandos tienen IDs 1..12.
SELECT id_vehiculo, nombre, microcontrolador FROM `vehiculos` WHERE id_vehiculo IN (1,5);
SELECT id_comando, id_vehiculo, nombre, codigo FROM `comandos`
WHERE id_vehiculo=1 ORDER BY codigo;

-- Crear temporalmente el padre 5 con los datos actuales del vehículo 1.
INSERT INTO `vehiculos`
  (`id_vehiculo`,`nombre`,`modelo`,`descripcion`,`microcontrolador`,`fecha_registro`,`activo`)
SELECT 5,`nombre`,`modelo`,`descripcion`,`microcontrolador`,`fecha_registro`,`activo`
FROM `vehiculos` WHERE `id_vehiculo`=1;

UPDATE `inventario_vehiculos` SET `id_vehiculo`=5 WHERE `id_vehiculo`=1;
UPDATE `asignaciones_vehiculo` SET `id_vehiculo`=5 WHERE `id_vehiculo`=1;
UPDATE `sesiones_invitado` SET `id_vehiculo`=5 WHERE `id_vehiculo`=1;
UPDATE `vehiculos_modelos` SET `id_vehiculo`=5 WHERE `id_vehiculo`=1;
UPDATE `comandos` SET `id_vehiculo`=5 WHERE `id_vehiculo`=1;
UPDATE `demos` SET `id_vehiculo`=5 WHERE `id_vehiculo`=1;
UPDATE `estado_vehiculo` SET `id_vehiculo`=5 WHERE `id_vehiculo`=1;
UPDATE `historial_comandos` SET `id_vehiculo`=5 WHERE `id_vehiculo`=1;

UPDATE `comandos`
SET `id_comando` = CASE `id_comando`
  WHEN 1 THEN 14 WHEN 2 THEN 15 WHEN 3 THEN 16 WHEN 4 THEN 17
  WHEN 5 THEN 18 WHEN 6 THEN 19 WHEN 7 THEN 20 WHEN 8 THEN 21
  WHEN 9 THEN 22 WHEN 10 THEN 35 WHEN 11 THEN 36 WHEN 12 THEN 37
  ELSE `id_comando` END
WHERE `id_vehiculo`=5 AND `id_comando` BETWEEN 1 AND 12;

SELECT 'inventario_vehiculos' AS tabla, COUNT(*) AS referencias FROM `inventario_vehiculos` WHERE id_vehiculo=1
UNION ALL SELECT 'asignaciones_vehiculo', COUNT(*) FROM `asignaciones_vehiculo` WHERE id_vehiculo=1
UNION ALL SELECT 'sesiones_invitado', COUNT(*) FROM `sesiones_invitado` WHERE id_vehiculo=1
UNION ALL SELECT 'vehiculos_modelos', COUNT(*) FROM `vehiculos_modelos` WHERE id_vehiculo=1
UNION ALL SELECT 'comandos', COUNT(*) FROM `comandos` WHERE id_vehiculo=1
UNION ALL SELECT 'demos', COUNT(*) FROM `demos` WHERE id_vehiculo=1
UNION ALL SELECT 'estado_vehiculo', COUNT(*) FROM `estado_vehiculo` WHERE id_vehiculo=1
UNION ALL SELECT 'historial_comandos', COUNT(*) FROM `historial_comandos` WHERE id_vehiculo=1;

-- Ejecutar solo si la consulta anterior devuelve cero en todas las filas.
DELETE FROM `vehiculos` WHERE `id_vehiculo`=1;
DELETE FROM `migraciones_esquema` WHERE `version`='V047_001';

SELECT id_vehiculo, nombre, microcontrolador FROM `vehiculos` WHERE id_vehiculo IN (1,5);
SELECT id_comando, id_vehiculo, nombre, codigo, mascara
FROM `comandos` WHERE id_vehiculo=5 ORDER BY codigo;
