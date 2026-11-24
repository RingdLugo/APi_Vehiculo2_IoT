-- Reversión de V045_001. DDL en MySQL realiza commit implícito.
-- Solo ejecutar cuando la API ya no lea esta tabla.
USE vehiculo_iot;
SELECT COUNT(*) AS tokens_revocados_a_descartar FROM tokens_revocados;
DROP TABLE tokens_revocados;
