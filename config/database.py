import os

import pymysql
from dotenv import load_dotenv

load_dotenv()


class DatabaseConnection:

    def __init__(self):
        self.__host = os.getenv("DB_HOST")
        self.__port = int(os.getenv("DB_PORT", "3306"))
        self.__database = os.getenv("DB_NAME")
        self.__user = os.getenv("DB_USER")
        self.__password = os.getenv("DB_PASSWORD")

    def __validar_configuracion(self) -> None:
        requeridos = {
            "DB_HOST": self.__host,
            "DB_NAME": self.__database,
            "DB_USER": self.__user,
            "DB_PASSWORD": self.__password,
        }
        faltantes = [nombre for nombre, valor in requeridos.items() if not valor]
        if faltantes:
            raise ValueError(f"Faltan variables de configuración: {', '.join(faltantes)}")

    def obtener_conexion(self):
        """Abre y devuelve una conexión con MySQL."""
        self.__validar_configuracion()
        return pymysql.connect(
            host=self.__host,
            port=self.__port,
            database=self.__database,
            user=self.__user,
            password=self.__password,
            connect_timeout=10,
            cursorclass=pymysql.cursors.DictCursor,
        )
