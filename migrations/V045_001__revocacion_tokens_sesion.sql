-- Fase 8.1: invalidación de tokens de usuario al cerrar sesión.
-- Aplicar primero en copia de prueba y registrar el respaldo/resultado.
-- No cambia usuarios, IDs de vehículos ni datos de control/historial.
USE vehiculo_iot;

SELECT DATABASE() AS base_activa, VERSION() AS version_mysql;
SELECT TABLE_NAME FROM information_schema.TABLES
WHERE TABLE_SCHEMA=DATABASE() AND TABLE_NAME='tokens_revocados';

-- Ejecutar solo si la consulta anterior no devolvió filas.
CREATE TABLE tokens_revocados (
  token_hash CHAR(64) CHARACTER SET ascii COLLATE ascii_bin NOT NULL,
  id_usuario BIGINT UNSIGNED NOT NULL,
  revocado_en TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
  expira_en TIMESTAMP NOT NULL,
  PRIMARY KEY (token_hash),
  KEY ix_tokens_revocados_usuario (id_usuario, expira_en),
  KEY ix_tokens_revocados_expiracion (expira_en),
  CONSTRAINT fk_tokens_revocados_usuario FOREIGN KEY (id_usuario)
    REFERENCES usuarios (id_usuario) ON DELETE RESTRICT ON UPDATE CASCADE
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_0900_ai_ci;

SELECT TABLE_NAME, ENGINE FROM information_schema.TABLES
WHERE TABLE_SCHEMA=DATABASE() AND TABLE_NAME='tokens_revocados';
