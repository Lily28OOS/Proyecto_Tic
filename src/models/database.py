# database.py
import logging
import requests
import psycopg2
import psycopg2.extras
import psycopg2.pool
import numpy as np
from typing import Optional, Tuple, List, Dict, Any

from src.config.settings import db_config, api_config

# =====================================================
# CONFIGURACIÓN DB (importada desde settings)
# =====================================================
DB_NAME = db_config.DB_NAME
DB_USER = db_config.DB_USER
DB_PASS = db_config.DB_PASS
DB_HOST = db_config.DB_HOST
DB_PORT = db_config.DB_PORT

POOL_MINCONN = db_config.POOL_MINCONN
POOL_MAXCONN = db_config.POOL_MAXCONN

# =====================================================
# CONFIG API EXTERNA
# =====================================================
API_PERSONA_URL = api_config.PERSONA_URL

# =====================================================
# LOGGER
# =====================================================
logger = logging.getLogger("database")
if not logger.handlers:
    handler = logging.StreamHandler()
    handler.setFormatter(logging.Formatter("%(asctime)s %(levelname)s %(message)s"))
    logger.addHandler(handler)
logger.setLevel(logging.INFO)

# =====================================================
# POOL
# =====================================================
_POOL: Optional[psycopg2.pool.SimpleConnectionPool] = None


def init_pool() -> None:
    global _POOL
    if _POOL:
        return
    _POOL = psycopg2.pool.SimpleConnectionPool(
        POOL_MINCONN,
        POOL_MAXCONN,
        dbname=DB_NAME,
        user=DB_USER,
        password=DB_PASS,
        host=DB_HOST,
        port=DB_PORT
    )
    logger.info("Pool DB inicializado")


def connect_db() -> Tuple[Any, Any]:
    if not _POOL:
        init_pool()
    conn = _POOL.getconn()
    cur = conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)
    return conn, cur


def close_db(conn, cur) -> None:
    if cur:
        cur.close()
    if conn and _POOL:
        _POOL.putconn(conn)


# =====================================================
# PERSONAS
# =====================================================
def get_person_by_cedula(c, cedula: str) -> Optional[Dict]:
    c.execute(
        "SELECT * FROM personas WHERE cedula = %s ",
        (cedula,)
    )
    row = c.fetchone()
    return dict(row) if row else None


def insert_person(c, conn, data: Dict) -> Optional[int]:
    try:
        c.execute(
            """
            INSERT INTO personas
            (cedula, tipo_persona, nombre, nombre2, apellido1, apellido2)
            VALUES (%s, %s, %s, %s, %s, %s)
            RETURNING id
            """,
            (
                data.get("cedula"),
                data.get("tipo_persona", "INSTITUCIONAL"),
                data.get("nombre"),
                data.get("nombre2"),
                data.get("apellido1"),
                data.get("apellido2"),
            )
        )
        pid = c.fetchone()["id"]
        conn.commit()
        return pid
    except Exception:
        conn.rollback()
        logger.exception("Error insertando persona")
        return None


# =====================================================
# API EXTERNA → METADATA
# =====================================================
def fetch_person_metadata(idpersonal: str) -> Optional[Dict]:
    try:
        resp = requests.post(
            API_PERSONA_URL,
            json={"idpersonal": idpersonal},
            timeout=10
        )
        resp.raise_for_status()
        data = resp.json()
        usuarios = data.get("p_data", {}).get("p_usuarios")
        return usuarios[0] if usuarios else None
    except Exception as e:
        logger.error(f"Error API externa: {e}")
        return None


def upsert_person_metadata(c, conn, persona_id: int, metadata: Dict) -> bool:
    try:
        c.execute(
            """
            INSERT INTO persona_metadata (persona_id, metadata)
            VALUES (%s, %s)
            ON CONFLICT (persona_id)
            DO UPDATE SET
                metadata = EXCLUDED.metadata,
                fecha_actualizacion = CURRENT_TIMESTAMP
            """,
            (persona_id, psycopg2.extras.Json(metadata))
        )
        conn.commit()
        return True
    except Exception:
        conn.rollback()
        logger.exception("Error guardando metadata")
        return False


# =====================================================
# CODIFICACIONES FACIALES
# =====================================================
def save_face_descriptor(
    c, conn,
    persona_id: int,
    descriptor: np.ndarray,
    modelo: str = "facenet",
    version_modelo: str = "1.0"
) -> bool:
    try:
        emb = np.asarray(descriptor, dtype=np.float32)
        emb /= np.linalg.norm(emb)

        c.execute(
            """
            INSERT INTO codificaciones_faciales
            (persona_id, codificacion, modelo, version_modelo)
            VALUES (%s, %s, %s, %s)
            """,
            (
                persona_id,
                psycopg2.extras.Json(emb.tolist()),
                modelo,
                version_modelo
            )
        )
        conn.commit()
        return True
    except Exception:
        conn.rollback()
        logger.exception("Error guardando descriptor")
        return False


def load_faces_from_db(c) -> List[Tuple[int, str, np.ndarray]]:
    c.execute(
        """
        SELECT
            p.id AS persona_id,
            p.cedula,
            cf.codificacion
        FROM personas p
        JOIN codificaciones_faciales cf ON p.id = cf.persona_id
        WHERE p.activo = TRUE AND cf.activo = TRUE
        """
    )

    rows = []
    for r in c.fetchall():
        emb = np.array(r["codificacion"], dtype=np.float32)
        emb /= np.linalg.norm(emb)
        rows.append((r["persona_id"], r["cedula"], emb))

    logger.info("Rostros cargados: %d", len(rows))
    return rows
