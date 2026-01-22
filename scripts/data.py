import os
import json
import random
import requests
import psycopg2
from psycopg2 import pool
from datetime import datetime

# Configuración desde variables de entorno
DB_NAME = os.getenv("DB_NAME", "biometria")
DB_USER = os.getenv("DB_USER", "postgres")
DB_PASS = os.getenv("DB_PASS", "admin")
DB_HOST = os.getenv("DB_HOST", "localhost")
DB_PORT = int(os.getenv("DB_PORT", "5433"))
POOL_MINCONN = int(os.getenv("DB_POOL_MIN", "1"))
POOL_MAXCONN = int(os.getenv("DB_POOL_MAX", "5"))

DEFAULT_URL = "http://172.16.226.42:3000/administracion/usuario/v1/buscar_por_idpersonal"
RANDOM_IDS = ["81427", "12345", "56789", "99887", "44112"]

# Pool de conexiones
db_pool = psycopg2.pool.SimpleConnectionPool(
    POOL_MINCONN,
    POOL_MAXCONN,
    dbname=DB_NAME,
    user=DB_USER,
    password=DB_PASS,
    host=DB_HOST,
    port=DB_PORT
)

# ============================================
# Funciones
# ============================================

def fetch_by_id(idpersonal: str, url: str = DEFAULT_URL, timeout: int = 10):
    payload = {"idPersonal": idpersonal, "idpersonal": idpersonal}
    headers = {"Content-Type": "application/json"}
    try:
        print(f"Consultando API con idpersonal={idpersonal} ...")
        resp = requests.post(url, json=payload, headers=headers, timeout=timeout)
        resp.raise_for_status()
        return resp.json()
    except requests.RequestException as e:
        print(f"Error en la API: {e}")
        return None

def create_table():
    """Crea la tabla usuarios_temporal si no existe."""
    conn = db_pool.getconn()
    try:
        cur = conn.cursor()
        cur.execute("""
            CREATE TABLE IF NOT EXISTS usuarios_temporal (
                id SERIAL PRIMARY KEY,
                idpersonal BIGINT NOT NULL,
                cedula VARCHAR(50) NOT NULL,
                persona TEXT NOT NULL,
                ubicacion TEXT,
                correo_personal_institucional TEXT,
                correo_personal_alternativo TEXT,
                created_at TIMESTAMP DEFAULT NOW()
            );
        """)
        conn.commit()
        cur.close()
        print("Tabla usuarios_temporal lista.")
    finally:
        db_pool.putconn(conn)

def save_user(user):
    """Guarda un usuario en la tabla separando cada campo."""
    conn = db_pool.getconn()
    try:
        cur = conn.cursor()
        idpersonal = int(user.get("idpersonal") or 0)
        cedula = user.get("cedula")
        persona = user.get("persona")
        ubicacion = user.get("ubicacion")
        correo1 = user.get("correo_personal_institucional")
        correo2 = user.get("correo_personal_alternativo")

        # Validación mínima
        if not cedula or not persona:
            print(f"Registro con idpersonal={idpersonal} inválido, se omite.")
            return

        cur.execute("""
            INSERT INTO usuarios_temporal
            (idpersonal, cedula, persona, ubicacion, correo_personal_institucional, correo_personal_alternativo)
            VALUES (%s, %s, %s, %s, %s, %s)
        """, (idpersonal, cedula, persona, ubicacion, correo1, correo2))

        conn.commit()
        cur.close()
    finally:
        db_pool.putconn(conn)

# ============================================
# Script principal
# ============================================

def main():
    # Seleccionar ID al azar
    id_val = random.choice(RANDOM_IDS)
    print(f"ID aleatorio seleccionado: {id_val}")

    # Consultar API
    data = fetch_by_id(id_val)
    if not data:
        print("No se obtuvo respuesta de la API.")
        return

    usuarios = data.get("p_data", {}).get("p_usuarios") or []

    if not usuarios:
        print("La API no devolvió usuarios.")
        return

    # Mostrar primer usuario como ejemplo
    primer_usuario = usuarios[0]
    print("\n===== Ejemplo de usuario =====")
    print(json.dumps(primer_usuario, indent=2, ensure_ascii=False))
    print("==============================")

    # Crear tabla si no existe
    create_table()

    # Guardar todos los usuarios
    print("Guardando usuarios en la base de datos...")
    for u in usuarios:
        save_user(u)
    print(f"{len(usuarios)} usuarios guardados en usuarios_temporal.")

if __name__ == "__main__":
    main()
