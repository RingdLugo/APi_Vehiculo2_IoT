-- Reversion de V044_001__unidades_exhibicion.sql
-- Ejecutar solo si la API ya no depende de disponible_demo y se desactivaron
-- las unidades de exhibicion. Este DDL produce commit implicito en MySQL.
USE vehiculo_iot;

SELECT COUNT(*) AS unidades_a_revisar
FROM inventario_vehiculos
WHERE disponible_demo = 1;

-- Revisa el conteo anterior y exporta sus valores antes de revertir.
ALTER TABLE inventario_vehiculos
  DROP CHECK chk_inventario_disponible_demo,
  DROP INDEX ix_inventario_demo_estado,
  DROP COLUMN disponible_demo;

SELECT COLUMN_NAME
FROM information_schema.COLUMNS
WHERE TABLE_SCHEMA = DATABASE()
  AND TABLE_NAME = 'inventario_vehiculos'
  AND COLUMN_NAME = 'disponible_demo';
