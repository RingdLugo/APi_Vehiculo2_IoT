import base64
import hashlib
import hmac
import json
import os
import secrets
import time
from datetime import datetime, timezone

from repositories.auth_repository import AuthRepository


class AuthService:
    """Autenticación con PBKDF2 y tokens HMAC firmados, sin secretos embebidos."""

    ITERATIONS = 310_000
    TOKEN_TTL_SECONDS = 30 * 60

    def __init__(self, repository: AuthRepository):
        self._repository = repository

    @staticmethod
    def hash_password(password: str) -> str:
        salt = secrets.token_bytes(16)
        digest = hashlib.pbkdf2_hmac("sha256", password.encode(), salt, AuthService.ITERATIONS)
        return "pbkdf2_sha256${}${}${}".format(
            AuthService.ITERATIONS,
            base64.urlsafe_b64encode(salt).decode().rstrip("="),
            base64.urlsafe_b64encode(digest).decode().rstrip("="),
        )

    @staticmethod
    def verify_password(password: str, encoded: str) -> bool:
        try:
            scheme, iterations, salt_text, digest_text = encoded.split("$", 3)
            if scheme != "pbkdf2_sha256":
                return False
            salt = base64.urlsafe_b64decode(salt_text + "=" * (-len(salt_text) % 4))
            expected = base64.urlsafe_b64decode(digest_text + "=" * (-len(digest_text) % 4))
            actual = hashlib.pbkdf2_hmac("sha256", password.encode(), salt, int(iterations))
            return hmac.compare_digest(actual, expected)
        except (ValueError, TypeError):
            return False

    @staticmethod
    def _secret() -> bytes:
        secret = os.getenv("AUTH_SECRET", "")
        if len(secret) < 32:
            raise RuntimeError("AUTH_SECRET debe contener al menos 32 caracteres aleatorios.")
        return secret.encode()

    @staticmethod
    def _b64(data: bytes) -> str:
        return base64.urlsafe_b64encode(data).decode().rstrip("=")

    @staticmethod
    def _unb64(data: str) -> bytes:
        return base64.urlsafe_b64decode(data + "=" * (-len(data) % 4))

    def iniciar_sesion(self, correo: str, password: str) -> dict | None:
        user = self._repository.obtener_por_correo(correo)
        if (not user or user["estado"] != "ACTIVO" or user["estado_empresa"] != "ACTIVA"
                or not self.verify_password(password, user["password_hash"])):
            return None
        return self._crear_token(user)

    def registrar_comprador(self, empresa_id: int, correo: str, nombre: str,
                            password: str, model_id: int) -> dict:
        # Verifica la configuración antes de confirmar una cuenta en la base.
        self._secret()
        password_hash = self.hash_password(password)
        created = self._repository.registrar_comprador(
            empresa_id, correo, nombre, password_hash, model_id
        )
        user = self._repository.obtener_por_correo_id(created["id_usuario"])
        if not user:
            raise RuntimeError("No se pudo recuperar la cuenta recién creada.")
        return {**created, "correo": user["correo"], "nombre": user["nombre"],
                **self._crear_token(user)}

    def crear_comprador_administrativo(self, empresa_id: int, actor_id: int,
                                       correo: str, nombre: str, password: str,
                                       model_id: int,
                                       telefono_contacto: str | None = None) -> dict:
        """Da de alta comprador, cuenta y carrito virtual sin iniciar la sesión del comprador."""
        return self._repository.registrar_comprador(
            empresa_id, correo, nombre, self.hash_password(password), model_id,
            actor_id=actor_id, telefono_contacto=telefono_contacto,
        )

    def _crear_token(self, user: dict) -> dict:
        now = int(time.time())
        claims = {
            "sub": int(user["id_usuario"]),
            "iat": now,
            "exp": now + self.TOKEN_TTL_SECONDS,
            "iss": "api-vehiculo-iot",
        }
        body = self._b64(json.dumps(claims, separators=(",", ":")).encode())
        signature = self._b64(hmac.new(self._secret(), body.encode(), hashlib.sha256).digest())
        return {"access_token": f"{body}.{signature}", "token_type": "bearer",
                "expires_in": self.TOKEN_TTL_SECONDS}

    def autenticar_token(self, token: str) -> dict | None:
        try:
            body, signature = token.split(".", 1)
            expected = self._b64(hmac.new(self._secret(), body.encode(), hashlib.sha256).digest())
            if not hmac.compare_digest(signature, expected):
                return None
            claims = json.loads(self._unb64(body))
            if (claims.get("iss") != "api-vehiculo-iot"
                    or int(claims.get("exp", 0)) <= int(time.time())):
                return None
            if self._repository.token_revocado(hashlib.sha256(token.encode()).hexdigest()):
                return None
            user = self._repository.obtener_por_correo_id(int(claims["sub"]))
            if not user or user["estado"] != "ACTIVO" or user["estado_empresa"] != "ACTIVA":
                return None
            return {"id_usuario": int(user["id_usuario"]),
                    "id_empresa": int(user["id_empresa"]),
                    "correo": user["correo"], "nombre": user["nombre"],
                    "roles": user["roles"]}
        except (ValueError, KeyError, TypeError, json.JSONDecodeError, RuntimeError):
            return None

    def revocar_token(self, token: str, user_id: int) -> None:
        body, signature = token.split(".", 1)
        expected = self._b64(hmac.new(self._secret(), body.encode(), hashlib.sha256).digest())
        if not hmac.compare_digest(signature, expected):
            raise ValueError("Token inválido.")
        claims = json.loads(self._unb64(body))
        if int(claims.get("sub", 0)) != int(user_id):
            raise ValueError("Token no corresponde a la sesión autenticada.")
        expires = int(claims.get("exp", 0))
        if expires <= int(time.time()):
            return
        self._repository.revocar_token(
            hashlib.sha256(token.encode()).hexdigest(), user_id,
            datetime.fromtimestamp(expires, timezone.utc).replace(tzinfo=None),
        )

    def bootstrap_admin(self, id_empresa: int, correo: str, nombre: str, password: str,
                        bootstrap_key: str | None) -> int:
        expected = os.getenv("BOOTSTRAP_ADMIN_KEY", "")
        if not expected:
            raise PermissionError("El bootstrap inicial está deshabilitado en este entorno.")
        if not bootstrap_key or not hmac.compare_digest(bootstrap_key, expected):
            raise PermissionError("Clave de bootstrap inválida.")
        password_hash = self.hash_password(password)
        return self._repository.crear_primer_administrador(
            id_empresa, correo, nombre, password_hash
        )
