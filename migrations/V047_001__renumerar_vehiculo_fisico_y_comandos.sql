-- Migración de llaves primarias; conservar un respaldo verificado antes.
-- Version: V047_001
-- Cambia el vehículo físico 5 a 1 y sus 12 id_comando a 1..12.
-- No cambia las reglas de FK. Reasigna las filas hijas mientras ambos padres existen.
-- MySQL hace COMMIT implícito en cada sentencia DDL; ejecutar en orden, sentencia por sentencia.
-- Detener el servicio API antes, evitar escrituras concurrentes y NO reejecutar tras éxito.

USE `vehiculo_iot`;

-- PREVIO: id_vehiculo=1 no existe; el 5 existe; comandos 1..12 están libres.
-- Confirmar que aparecen los doce comandos del vehículo 5, códigos 1..12.
SELECT id_vehiculo, nombre, microcontrolador FROM `vehiculos`
WHERE id_vehiculo IN (1,5);
SELECT id_comando, id_vehiculo, nombre, codigo, mascara FROM `comandos`
WHERE id_vehiculo=5 ORDER BY codigo;
SELECT id_comando FROM `comandos` WHERE id_comando BETWEEN 1 AND 12;

-- Crear temporalmente el padre 1 con los datos del vehículo físico 5.
INSERT INTO `vehiculos`
  (`id_vehiculo`,`nombre`,`modelo`,`descripcion`,`microcontrolador`,`fecha_registro`,`activo`)
SELECT 1,`nombre`,`modelo`,`descripcion`,`microcontrolador`,`fecha_registro`,`activo`
FROM `vehiculos` WHERE `id_vehiculo`=5;

-- Mover referencias directas. Los padres 1 y 5 existen durante este paso;
-- las FKs permanecen con sus UPDATE_RULE originales.
UPDATE `inventario_vehiculos` SET `id_vehiculo`=1 WHERE `id_vehiculo`=5;
UPDATE `asignaciones_vehiculo` SET `id_vehiculo`=1 WHERE `id_vehiculo`=5;
UPDATE `sesiones_invitado` SET `id_vehiculo`=1 WHERE `id_vehiculo`=5;
UPDATE `vehiculos_modelos` SET `id_vehiculo`=1 WHERE `id_vehiculo`=5;
UPDATE `comandos` SET `id_vehiculo`=1 WHERE `id_vehiculo`=5;
UPDATE `demos` SET `id_vehiculo`=1 WHERE `id_vehiculo`=5;
UPDATE `estado_vehiculo` SET `id_vehiculo`=1 WHERE `id_vehiculo`=5;
UPDATE `historial_comandos` SET `id_vehiculo`=1 WHERE `id_vehiculo`=5;

-- Remapear solo las doce PK del carrito físico. Las referencias a id_comando tienen CASCADE.
UPDATE `comandos`
SET `id_comando` = CASE `id_comando`
  WHEN 14 THEN 1 WHEN 15 THEN 2 WHEN 16 THEN 3 WHEN 17 THEN 4
  WHEN 18 THEN 5 WHEN 19 THEN 6 WHEN 20 THEN 7 WHEN 21 THEN 8
  WHEN 22 THEN 9 WHEN 35 THEN 10 WHEN 36 THEN 11 WHEN 37 THEN 12
  ELSE `id_comando` END
WHERE `id_vehiculo`=1 AND `id_comando` IN (14,15,16,17,18,19,20,21,22,35,36,37);

-- Verificar que ninguna tabla conserva referencias al ID 5 antes de quitar el padre antiguo.
SELECT 'inventario_vehiculos' AS tabla, COUNT(*) AS referencias FROM `inventario_vehiculos` WHERE id_vehiculo=5
UNION ALL SELECT 'asignaciones_vehiculo', COUNT(*) FROM `asignaciones_vehiculo` WHERE id_vehiculo=5
UNION ALL SELECT 'sesiones_invitado', COUNT(*) FROM `sesiones_invitado` WHERE id_vehiculo=5
UNION ALL SELECT 'vehiculos_modelos', COUNT(*) FROM `vehiculos_modelos` WHERE id_vehiculo=5
UNION ALL SELECT 'comandos', COUNT(*) FROM `comandos` WHERE id_vehiculo=5
UNION ALL SELECT 'demos', COUNT(*) FROM `demos` WHERE id_vehiculo=5
UNION ALL SELECT 'estado_vehiculo', COUNT(*) FROM `estado_vehiculo` WHERE id_vehiculo=5
UNION ALL SELECT 'historial_comandos', COUNT(*) FROM `historial_comandos` WHERE id_vehiculo=5;

-- Ejecutar solo si la consulta anterior devuelve cero en todas las filas.
DELETE FROM `vehiculos` WHERE `id_vehiculo`=5;

INSERT IGNORE INTO `migraciones_esquema` (`version`, `archivo`, `observaciones`)
VALUES ('V047_001', 'V047_001__renumerar_vehiculo_fisico_y_comandos.sql',
        'Vehículo físico 5 pasa a 1; PK de sus comandos pasan a 1..12; conserva todas las FK y datos.');

-- POST: solo vehículo 1; comandos 1..12; historial/demos/inventario referidos a 1.
SELECT id_vehiculo, nombre, microcontrolador FROM `vehiculos` WHERE id_vehiculo IN (1,5);
SELECT id_comando, id_vehiculo, nombre, codigo, mascara
FROM `comandos` WHERE id_vehiculo=1 ORDER BY codigo;
SELECT TABLE_NAME, CONSTRAINT_NAME, UPDATE_RULE, DELETE_RULE
FROM information_schema.REFERENTIAL_CONSTRAINTS
WHERE CONSTRAINT_SCHEMA=DATABASE()
  AND CONSTRAINT_NAME IN ('fk_inventario_unidad','fk_asignacion_unidad','fk_sesiones_unidad');
