# database.py
import psycopg2
import numpy as np

def connect_db():
    """
    Establece la conexión con la base de datos PostgreSQL.
    """
    conn = psycopg2.connect(
        dbname="biometria",
        user="postgres",
        password="admin",
        host="localhost",
        port="5433"
    )
    c = conn.cursor()
    return conn, c


def save_face_descriptor(c, conn, persona_id, descriptor):
    """
    Guarda un descriptor facial normalizado en la base de datos.
    """
    # Normalizar el descriptor (norma 1)
    norm = np.linalg.norm(descriptor)
    if norm > 0:
        descriptor = descriptor / norm

    desc_list = descriptor.astype(np.float64).tolist()

    # Insertar en la tabla codificaciones_faciales
    c.execute("""
        INSERT INTO codificaciones_faciales (persona_id, codificacion)
        VALUES (%s, %s)
    """, (persona_id, desc_list))
    conn.commit()


def load_faces_from_db(c):
    """
    Carga las codificaciones faciales de las personas activas en la base de datos.
    """
    c.execute("""
        SELECT p.id, p.nombre, p.cedula, cf.codificacion
        FROM personas p
        JOIN codificaciones_faciales cf ON p.id = cf.persona_id
        WHERE p.activo = TRUE
    """)
    faces = c.fetchall()

    face_db = []
    for pid, nombre, cedula, codificacion in faces:
        full_name = f"{nombre} ({cedula})"
        desc = np.array(codificacion, dtype=np.float32)

        # Normalizar descriptor
        norm = np.linalg.norm(desc)
        if norm > 0:
            desc = desc / norm

        face_db.append((full_name, desc))

    return face_db
