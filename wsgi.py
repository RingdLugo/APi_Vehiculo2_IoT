from main import app
from waitress import serve

if __name__ == "__main__":
    print("Iniciando servidor de producción con Waitress en puerto 80...")
    serve(app, host="127.0.0.1", port=80)