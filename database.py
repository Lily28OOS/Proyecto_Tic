# database.py
import psycopg2
import numpy as np

def connect_db():
    conn = psycopg2.connect(
        dbname="biometria", user="postgres", password="admin", host="localhost", port="5433"
    )
    c = conn.cursor()
    return conn, c

def save_face_descriptor(c, conn, persona_id, descriptor):
    """
    Guarda un descriptor facial normalizado en la base de datos.

    Args:
        c: Cursor de la base de datos.
        conn: Conexión a la base de datos.
        persona_id: ID de la persona en la tabla personas.
        descriptor: Vector numpy con la codificación facial.
    """
    # Normalizar el descriptor (norma 1)
    norm = np.linalg.norm(descriptor)
    if norm > 0:
        descriptor = descriptor / norm
    
    # Convertir a lista de floats para PostgreSQL FLOAT8[]
    desc_list = descriptor.astype(np.float64).tolist()
    
    # Insertar en la tabla codificaciones_faciales
    c.execute(
        "INSERT INTO codificaciones_faciales (persona_id, codificacion) VALUES (%s, %s)",
        (persona_id, desc_list)
    )
    conn.commit()

def load_faces_from_db(c):
    """
    Carga las codificaciones faciales desde la base de datos y las normaliza.

    Args:
        c: Cursor de la base de datos.

    Returns:
        face_db: Lista de tuplas (nombre_completo, descriptor_normalizado)
    """
    c.execute("""
        SELECT p.id, p.nombre, p.correo_electronico, cf.codificacion 
        FROM personas p
        JOIN codificaciones_faciales cf ON p.id = cf.persona_id
    """)
    faces = c.fetchall()
    face_db = []
    for pid, nombre, correo, codificacion in faces:
        full_name = nombre
        desc = np.array(codificacion, dtype=np.float32)
        
        # Normalizar descriptor
        norm = np.linalg.norm(desc)
        if norm > 0:
            desc = desc / norm
        
        face_db.append((full_name, desc))
    return face_db
