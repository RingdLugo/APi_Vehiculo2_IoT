import hashlib
import secrets

from repositories.administracion_repository import AdministracionRepository


class AdministracionService:
    """Reglas de aplicación de Administración IoT; repositorio parametriza SQL."""

    def __init__(self, repository: AdministracionRepository):
        self._repo = repository

    def crear_sesion_invitado(self, data: dict, actor: dict):
        raw_token = secrets.token_urlsafe(32)
        token_hash = hashlib.sha256(raw_token.encode()).hexdigest()
        session = self._repo.crear_sesion_invitado(data, actor, token_hash)
        return {**session, "token_invitado": raw_token}

    def solicitar_sesion_publica(self, model_id: int, demo_id: int | None = None):
        raw_token = secrets.token_urlsafe(32)
        token_hash = hashlib.sha256(raw_token.encode()).hexdigest()
        session = self._repo.reservar_sesion_publica(model_id, demo_id, token_hash, 10)
        return {**session, "token_invitado": raw_token, "duracion_minutos": 10}

