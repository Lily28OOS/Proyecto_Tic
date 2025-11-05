# register.py
import cv2
import numpy as np
from face_recognition import detect_faces, get_face_descriptor
from psycopg2.extras import Json

class FaceRegister:
    def __init__(self, c, conn, face_db):
        """
        c: cursor de la DB
        conn: conexión a la DB
        face_db: lista de tuplas (nombre_completo, descriptor numpy array)
        """
        self.c = c
        self.conn = conn
        self.face_db = face_db

    def capture_image(self):
        """
        Captura una imagen desde la cámara, detecta el rostro y genera el descriptor facial.
        Retorna un diccionario con éxito y datos o error.
        """
        cap = cv2.VideoCapture(0)
        try:
            ret, frame = cap.read()
        finally:
            cap.release()
        if not ret or frame is None:
            return {'success': False, 'message': 'No se pudo acceder a la cámara'}

        faces = detect_faces(frame)
        if len(faces) == 0:
            return {'success': False, 'message': 'No se detectó ningún rostro'}

        x, y, w, h = faces[0]
        face_img = frame[y:y+h, x:x+w]
        descriptor = get_face_descriptor(face_img)
        if descriptor is None:
            return {'success': False, 'message': 'No se pudo calcular descriptor facial'}

        # normalizar descriptor
        descriptor = self._normalize(descriptor)

        # Verificar si el descriptor ya está registrado (umbral 0.9)
        for _, existing_descriptor in self.face_db:
            distance = np.linalg.norm(existing_descriptor - descriptor)
            if distance < 0.9:
                return {'success': False, 'message': 'Este rostro ya está registrado'}

        return {
            'success': True,
            'descriptor': descriptor,
            'face_image': face_img
        }

    def register_person(self, cedula, nombre1, nombre2, apellido1, apellido2, descriptor):
        """
        Guarda los datos personales y el descriptor facial en la base de datos.
        descriptor debe ser un numpy array.
        Retorna diccionario con éxito o error.
        """
        try:
            # normalizar antes de guardar y convertir a lista
            if isinstance(descriptor, np.ndarray):
                desc_arr = descriptor.astype(float)
            else:
                desc_arr = np.array(descriptor, dtype=float)
            norm = np.linalg.norm(desc_arr)
            desc_norm = (desc_arr / norm).tolist() if norm > 0 else desc_arr.tolist()

            # Convertir descriptor a JSON para PostgreSQL
            descriptor_json = Json(desc_norm)

            # Insertar persona (usar columna 'activo' para consistencia con main.py)
            self.c.execute("""
                INSERT INTO personas (cedula, nombre, nombre2, apellido1, apellido2, activo)
                VALUES (%s, %s, %s, %s, %s, FALSE) RETURNING id
            """, (cedula, nombre1, nombre2, apellido1, apellido2))

            # leer el id de forma robusta (dict o tupla)
            persona_row = self.c.fetchone()
            if not persona_row:
                # fallback: buscar por cédula
                self.c.execute("SELECT id FROM personas WHERE cedula = %s", (cedula,))
                persona_row = self.c.fetchone()
            if isinstance(persona_row, dict):
                persona_id = persona_row.get("id")
            else:
                persona_id = persona_row[0] if persona_row else None

            if not persona_id:
                raise Exception("No se obtuvo persona_id tras INSERT")

            # Insertar codificación facial (asegurar tabla codificaciones_faciales existe)
            self.c.execute("""
                INSERT INTO codificaciones_faciales (persona_id, codificacion)
                VALUES (%s, %s)
            """, (persona_id, descriptor_json))

            # Confirmar cambios
            self.conn.commit()

            # Actualizar la base de datos en memoria con descriptor normalizado (numpy array)
            self.face_db.append((f"{nombre1} {apellido1} ({cedula})", np.array(desc_norm, dtype=float)))

            return {'success': True, 'message': 'Registro guardado correctamente', 'persona_id': persona_id}
        except Exception as e:
            self.conn.rollback()
            return {'success': False, 'message': f'Error al guardar en DB: {str(e)}'}

    def _normalize(self, v):
        v = np.array(v, dtype=float)
        norm = np.linalg.norm(v)
        return v / norm if norm > 0 else v
