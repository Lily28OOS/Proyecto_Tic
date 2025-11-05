# database.py
import os
import json
import logging
import psycopg2
import psycopg2.extras
import psycopg2.pool
import numpy as np
from typing import Tuple, List, Any, Optional, Dict

# Configuración desde variables de entorno (evitar credenciales hardcodeadas)
DB_NAME = os.getenv("DB_NAME", "biometria")
DB_USER = os.getenv("DB_USER", "postgres")
DB_PASS = os.getenv("DB_PASS", "admin")
DB_HOST = os.getenv("DB_HOST", "localhost")
DB_PORT = int(os.getenv("DB_PORT", "5433"))
POOL_MINCONN = int(os.getenv("DB_POOL_MIN", "1"))
POOL_MAXCONN = int(os.getenv("DB_POOL_MAX", "5"))

# Logger mínimo
logger = logging.getLogger("database")
if not logger.handlers:
    handler = logging.StreamHandler()
    handler.setFormatter(logging.Formatter("%(asctime)s %(levelname)s %(message)s"))
    logger.addHandler(handler)
logger.setLevel(logging.INFO)

# Pool global (inicializar con init_pool)
_POOL: Optional[psycopg2.pool.SimpleConnectionPool] = None

def init_pool(minconn: int = POOL_MINCONN, maxconn: int = POOL_MAXCONN) -> None:
    """Inicializa el pool de conexiones. Llamar en startup de la app."""
    global _POOL
    if _POOL is not None:
        return
    try:
        _POOL = psycopg2.pool.SimpleConnectionPool(
            minconn,
            maxconn,
            dbname=DB_NAME,
            user=DB_USER,
            password=DB_PASS,
            host=DB_HOST,
            port=DB_PORT,
        )
        logger.info("Pool de conexiones inicializado (%d-%d)", minconn, maxconn)
    except Exception:
        logger.exception("Error inicializando pool de conexiones")
        raise

def close_pool() -> None:
    """Cierra todas las conexiones del pool."""
    global _POOL
    if _POOL:
        try:
            _POOL.closeall()
            logger.info("Pool de conexiones cerrado")
        except Exception:
            logger.exception("Error cerrando pool")
        finally:
            _POOL = None

def get_conn_from_pool():
    """
    Obtiene una conexión del pool y un cursor RealDictCursor.
    Retorna (conn, cursor). Si no hay pool, crea una conexión directa.
    """
    global _POOL
    if _POOL:
        conn = _POOL.getconn()
        c = conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)
        # marcar en la conexión que proviene del pool para put_conn saberlo
        setattr(conn, "_from_pool", True)
        return conn, c
    # fallback: conexión directa
    conn = psycopg2.connect(
        dbname=DB_NAME, user=DB_USER, password=DB_PASS, host=DB_HOST, port=DB_PORT
    )
    c = conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)
    setattr(conn, "_from_pool", False)
    return conn, c

def put_conn(conn) -> None:
    """Devuelve la conexión al pool o la cierra si no proviene del pool."""
    global _POOL
    try:
        if conn is None:
            return
        from_pool = getattr(conn, "_from_pool", False)
        if from_pool and _POOL:
            _POOL.putconn(conn)
        else:
            conn.close()
    except Exception:
        logger.exception("Error devolviendo/cerrando conexión")

def connect_db() -> Tuple[psycopg2.extensions.connection, psycopg2.extensions.cursor]:
    """
    Compatibilidad: devuelve (conn, cursor). Si el pool está inicializado, obtiene del pool.
    Caller debe usar put_conn(conn) para liberar o conn.close() si no se usa pool.
    """
    return get_conn_from_pool()

def close_db(conn: Optional[psycopg2.extensions.connection], c: Optional[psycopg2.extensions.cursor]) -> None:
    """Cerrar cursor y devolver/cerrar conexión de forma segura."""
    try:
        if c:
            c.close()
    except Exception:
        logger.exception("Error cerrando cursor")
    try:
        if conn:
            put_conn(conn)
    except Exception:
        logger.exception("Error cerrando conexión")

def ensure_tables_exist(c, conn) -> None:
    """
    Crear tablas necesarias si no existen.
    - personas: tabla principal de usuarios (id, cedula, nombres, apellidos, activo)
    - codificaciones_faciales: descriptores faciales en JSONB
    - persona_metadata: metadata completa de la API externa (JSONB)
    """
    try:
        c.execute(
            """
            CREATE TABLE IF NOT EXISTS personas (
                id SERIAL PRIMARY KEY,
                cedula TEXT UNIQUE,
                nombre TEXT,
                nombre2 TEXT,
                apellido1 TEXT,
                apellido2 TEXT,
                activo BOOLEAN DEFAULT FALSE,
                created_at TIMESTAMP DEFAULT NOW()
            )
            """
        )
        c.execute(
            """
            CREATE TABLE IF NOT EXISTS codificaciones_faciales (
                id SERIAL PRIMARY KEY,
                persona_id INTEGER NOT NULL REFERENCES personas(id) ON DELETE CASCADE,
                codificacion JSONB,
                created_at TIMESTAMP DEFAULT NOW()
            )
            """
        )
        c.execute(
            """
            CREATE TABLE IF NOT EXISTS persona_metadata (
                persona_id INTEGER PRIMARY KEY REFERENCES personas(id) ON DELETE CASCADE,
                metadata JSONB
            )
            """
        )
        c.execute("CREATE INDEX IF NOT EXISTS idx_personas_cedula ON personas(cedula)")
        conn.commit()
        logger.info("Tablas verificadas/creadas correctamente")
    except Exception:
        conn.rollback()
        logger.exception("Error creando tablas")
        raise

def get_person_by_cedula(c, cedula: str) -> Optional[Dict[str, Any]]:
    """Devuelve fila de persona (dict) por cédula o None si no existe."""
    c.execute("SELECT * FROM personas WHERE cedula = %s", (cedula,))
    row = c.fetchone()
    return dict(row) if row else None

def insert_person(c, conn, cedula: str, nombre: str = None, nombre2: str = None, apellido1: str = None, apellido2: str = None, activo: bool = False) -> Optional[int]:
    """
    Inserta una persona y retorna su id. Si ya existe devuelve su id existente.
    """
    existing = get_person_by_cedula(c, cedula)
    if existing:
        return int(existing.get("id"))
    try:
        c.execute(
            """
            INSERT INTO personas (cedula, nombre, nombre2, apellido1, apellido2, activo)
            VALUES (%s, %s, %s, %s, %s, %s)
            RETURNING id
            """,
            (cedula, nombre, nombre2, apellido1, apellido2, activo),
        )
        row = c.fetchone()
        pid = int(row.get("id")) if row and row.get("id") is not None else None
        if not pid:
            # fallback: buscar por cédula
            c.execute("SELECT id FROM personas WHERE cedula = %s", (cedula,))
            r2 = c.fetchone()
            pid = int(r2.get("id")) if r2 and r2.get("id") is not None else None
        conn.commit()
        return pid
    except Exception:
        conn.rollback()
        logger.exception("Error insertando persona")
        return None

def upsert_person_metadata(c, conn, persona_id: int, metadata: Any) -> bool:
    """Inserta o actualiza metadata JSON para una persona."""
    try:
        c.execute(
            """
            INSERT INTO persona_metadata (persona_id, metadata)
            VALUES (%s, %s)
            ON CONFLICT (persona_id) DO UPDATE SET metadata = EXCLUDED.metadata
            """,
            (persona_id, psycopg2.extras.Json(metadata)),
        )
        conn.commit()
        return True
    except Exception:
        conn.rollback()
        logger.exception("Error guardando metadata")
        return False

def save_face_descriptor(c, conn, persona_id: int, descriptor: Any) -> bool:
    """
    Guarda un descriptor facial normalizado (como JSON) en la base de datos.
    descriptor puede ser numpy array o lista de floats.
    Retorna True si OK, False si error.
    """
    try:
        arr = np.array(descriptor, dtype=float)
        norm = np.linalg.norm(arr)
        if norm > 0:
            arr = arr / norm
        desc_list: List[float] = arr.astype(float).tolist()
        c.execute(
            "INSERT INTO codificaciones_faciales (persona_id, codificacion) VALUES (%s, %s)",
            (persona_id, psycopg2.extras.Json(desc_list)),
        )
        conn.commit()
        return True
    except Exception:
        conn.rollback()
        logger.exception("Error guardando descriptor facial")
        return False

def load_faces_from_db(c) -> List[Tuple[str, np.ndarray]]:
    """
    Carga las codificaciones faciales de las personas activas en la base de datos.
    Devuelve lista de tuplas (display_name, numpy_array_descriptor).
    """
    c.execute(
        """
        SELECT p.id AS persona_id, p.nombre, p.cedula, cf.codificacion
        FROM personas p
        JOIN codificaciones_faciales cf ON p.id = cf.persona_id
        WHERE p.activo = TRUE
        """
    )
    rows = c.fetchall()
    face_db: List[Tuple[str, np.ndarray]] = []
    for row in rows:
        pid = row.get("persona_id")
        nombre = row.get("nombre") or ""
        cedula = row.get("cedula") or ""
        codificacion = row.get("codificacion")
        if isinstance(codificacion, str):
            try:
                codificacion = json.loads(codificacion)
            except Exception:
                pass
        try:
            desc = np.array(codificacion, dtype=float)
        except Exception:
            logger.warning("Codificación inválida para persona_id=%s, se omite", pid)
            continue
        norm = np.linalg.norm(desc)
        if norm > 0:
            desc = desc / norm
        display_name = f"{nombre} ({cedula})" if nombre or cedula else str(pid)
        face_db.append((display_name, desc))
    return face_db
