# database.py
import psycopg2
import numpy as np

# Conectar a la base de datos PostgreSQL (con contraseña root)
def connect_db():
    conn = psycopg2.connect(
        dbname="biometria", user="postgres", password="admin", host="localhost", port="5432"
    )
    c = conn.cursor()
    return conn, c

# Cargar todos los rostros de la base de datos
def load_faces_from_db(c):
    c.execute("""
        SELECT p.id, p.nombre, p.correo_electronico, cf.codificacion 
        FROM personas p
        JOIN codificaciones_faciales cf ON p.id = cf.persona_id
    """)
    faces = c.fetchall()
    face_db = []
    for pid, nombre, correo, codificacion in faces:
        full_name = nombre
        # Convertir el arreglo de FLOAT8 a un numpy array
        desc = np.array(codificacion, dtype=np.float64)
        face_db.append((full_name, desc))
    return face_db
