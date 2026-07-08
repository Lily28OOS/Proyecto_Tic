# register.py
import numpy as np
from psycopg2.extras import Json
from face_recognition import extract_face_descriptor


class FaceRegister:
    """
    Módulo encargado del enrolamiento biométrico facial.

    Responsabilidades:
    - Extraer descriptor facial usando pipeline oficial
    - Verificar duplicados
    - Registrar codificación facial
    - Activar persona
    """

    FACE_DUPLICATE_THRESHOLD = 0.50

    def __init__(self, cursor, connection, face_db):
        """
        :param cursor: cursor PostgreSQL
        :param connection: conexión activa
        :param face_db: [(persona_id, embedding)]
        """
        self.cursor = cursor
        self.connection = connection
        self.face_db = face_db

    # ---------------------------------------------------------
    # REGISTRO BIOMÉTRICO
    # ---------------------------------------------------------
    def register_face(
        self,
        persona_id: int,
        frame: np.ndarray,
        modelo: str,
        version_modelo: str = None
    ):
        try:
            # 1️ Extraer descriptor (pipeline único)
            descriptor = extract_face_descriptor(frame)

            if descriptor is None:
                return {
                    "success": False,
                    "message": "No se detectó un rostro válido"
                }

            # 2️ Verificar duplicados
            if self._is_duplicate(descriptor):
                return {
                    "success": False,
                    "message": "El rostro ya se encuentra registrado"
                }

            descriptor_json = Json(descriptor.tolist())

            # 3️ Guardar codificación facial
            self.cursor.execute("""
                INSERT INTO codificaciones_faciales
                (persona_id, codificacion, modelo, version_modelo)
                VALUES (%s, %s, %s, %s)
            """, (
                persona_id,
                descriptor_json,
                modelo,
                version_modelo
            ))

            # 4️ Activar persona
            self.cursor.execute("""
                UPDATE personas
                SET activo = TRUE
                WHERE id = %s
            """, (persona_id,))

            self.connection.commit()

            # 5️ Cache en memoria
            self.face_db.append((persona_id, descriptor))

            return {
                "success": True,
                "persona_id": persona_id
            }

        except Exception as e:
            self.connection.rollback()
            return {
                "success": False,
                "message": f"Error al registrar rostro: {str(e)}"
            }

    # ---------------------------------------------------------
    # UTILIDADES
    # ---------------------------------------------------------
    def _is_duplicate(self, descriptor):
        for _, existing in self.face_db:
            dist = np.linalg.norm(existing - descriptor)
            if dist < self.FACE_DUPLICATE_THRESHOLD:
                return True
        return False
