import re
import unicodedata


_MASCARAS_POR_NOMBRE = {
    "avanzar": 0x0001,
    "adelante": 0x0001,
    "mover el vehiculo hacia adelante": 0x0001,
    "retroceder": 0x0002,
    "reversa": 0x0002,
    "mover el vehiculo hacia atras": 0x0002,
    "izquierda": 0x0040,
    "girar izquierda": 0x0040,
    "girar a la izquierda": 0x0040,
    "girar hacia la izquierda": 0x0040,
    "derecha": 0x0080,
    "girar derecha": 0x0080,
    "girar a la derecha": 0x0080,
    "girar hacia la derecha": 0x0080,
    "pala izquierda": 0x0004,
    "pala hacia la izquierda": 0x0004,
    "izquierda pala": 0x0004,
    "pala derecha": 0x0008,
    "pala hacia la derecha": 0x0008,
    "derecha pala": 0x0008,
    "subir pala": 0x0010,
    "subir brazo": 0x0010,
    "brazo arriba": 0x0010,
    "bajar pala": 0x0020,
    "bajar brazo": 0x0020,
    "brazo abajo": 0x0020,
    "sonido": 0x0100,
    "activar sonido": 0x0100,
    "sonido encendido": 0x0100,
    "modo": 0x0200,
    "mode": 0x0200,
    "activar modo": 0x0200,
    "activar mode": 0x0200,
    "modo activado": 0x0200,
    "mode activado": 0x0200,
    "led": 0x0400,
    "encender led": 0x0400,
    "prender led": 0x0400,
    "luz encendida": 0x0400,
    "luz prendida": 0x0400,
    "detener": 0x0000,
    "parar": 0x0000,
    "apagar todo": 0x0000,
    "detener todo": 0x0000,
}


def mascara_automatica(nombre: str) -> int:
    """Obtiene la máscara de salida conocida por nombre; desconocidos no activan salidas."""
    normalizado = unicodedata.normalize("NFKD", nombre)
    normalizado = "".join(caracter for caracter in normalizado if not unicodedata.combining(caracter))
    normalizado = re.sub(r"[^a-z0-9]+", " ", normalizado.lower()).strip()
    return _MASCARAS_POR_NOMBRE.get(normalizado, 0)
