# register.py
import cv2
import numpy as np
from psycopg2.extras import Json
from face_recognition import detect_faces, get_face_descriptor


class FaceRegister:
    """
    Módulo encargado del enrolamiento biométrico facial.
    Responsable de:
    - Capturar imagen desde cámara
    - Detectar rostro
    - Generar descriptor facial
    - Verificar duplicados
    - Registrar persona y codificación facial en la base de datos
    """

    FACE_DUPLICATE_THRESHOLD = 0.9

    def __init__(self, cursor, connection, face_db, camera_index=0):
        """
        :param cursor: cursor activo de PostgreSQL
        :param connection: conexión a la base de datos
        :param face_db: lista en memoria [(identificador, descriptor numpy)]
        :param camera_index: índice de cámara (default 0)
        """
        self.cursor = cursor
        self.connection = connection
        self.face_db = face_db
        self.camera_index = camera_index

    # ------------------------------------------------------------------
    # CAPTURA Y PROCESAMIENTO FACIAL
    # ------------------------------------------------------------------
    def capture_face_descriptor(self):
        """
        Captura una imagen desde la cámara y obtiene el descriptor facial.
        :return: dict con success, descriptor o mensaje de error
        """
        cap = cv2.VideoCapture(self.camera_index)
        try:
            ret, frame = cap.read()
        finally:
            cap.release()

        if not ret or frame is None:
            return {'success': False, 'message': 'No se pudo acceder a la cámara'}

        faces = detect_faces(frame)
        if not faces:
            return {'success': False, 'message': 'No se detectó ningún rostro'}

        x, y, w, h = faces[0]
        face_img = frame[y:y + h, x:x + w]

        descriptor = get_face_descriptor(face_img)
        if descriptor is None:
            return {'success': False, 'message': 'No se pudo generar el descriptor facial'}

        descriptor = self._normalize(descriptor)

        if self._is_duplicate(descriptor):
            return {'success': False, 'message': 'El rostro ya se encuentra registrado'}

        return {
            'success': True,
            'descriptor': descriptor,
            'face_image': face_img
        }

    # ------------------------------------------------------------------
    # REGISTRO EN BASE DE DATOS
    # ------------------------------------------------------------------
    def register_person(self, cedula, nombre1, nombre2, apellido1, apellido2, descriptor):
        """
        Registra una persona y su codificación facial en la base de datos.
        """
        try:
            descriptor = self._normalize(descriptor)
            descriptor_json = Json(descriptor.tolist())

            # Insertar persona
            self.cursor.execute("""
                INSERT INTO personas (cedula, nombre, nombre2, apellido1, apellido2, activo)
                VALUES (%s, %s, %s, %s, %s, FALSE)
                RETURNING id
            """, (cedula, nombre1, nombre2, apellido1, apellido2))

            row = self.cursor.fetchone()
            if not row:
                raise Exception("No se pudo obtener el ID de la persona")

            persona_id = row[0]

            # Insertar codificación facial
            self.cursor.execute("""
                INSERT INTO codificaciones_faciales (persona_id, codificacion)
                VALUES (%s, %s)
            """, (persona_id, descriptor_json))

            self.connection.commit()

            # Actualizar base en memoria
            etiqueta = f"{nombre1} {apellido1} ({cedula})"
            self.face_db.append((etiqueta, descriptor))

            return {
                'success': True,
                'message': 'Persona registrada correctamente',
                'persona_id': persona_id
            }

        except Exception as e:
            self.connection.rollback()
            return {
                'success': False,
                'message': f'Error al registrar persona: {str(e)}'
            }

    # ------------------------------------------------------------------
    # MÉTODOS AUXILIARES
    # ------------------------------------------------------------------
    def _normalize(self, vector):
        vector = np.array(vector, dtype=float)
        norm = np.linalg.norm(vector)
        return vector / norm if norm > 0 else vector

    def _is_duplicate(self, descriptor):
        for _, existing in self.face_db:
            distance = np.linalg.norm(existing - descriptor)
            if distance < self.FACE_DUPLICATE_THRESHOLD:
                return True
        return False
