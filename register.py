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
        ret, frame = cap.read()
        cap.release()
        if not ret:
            return {'success': False, 'message': 'No se pudo acceder a la cámara'}

        faces = detect_faces(frame)
        if len(faces) == 0:
            return {'success': False, 'message': 'No se detectó ningún rostro'}

        x, y, w, h = faces[0]
        face_img = frame[y:y+h, x:x+w]
        descriptor = get_face_descriptor(face_img)

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
            # Convertir descriptor a JSON para PostgreSQL
            descriptor_json = Json(descriptor.tolist())

            # Insertar persona
            self.c.execute("""
                INSERT INTO personas (cedula, nombre, nombre2, apellido1, apellido2, estado)
                VALUES (%s, %s, %s, %s, %s, 'activo') RETURNING id
            """, (cedula, nombre1, nombre2, apellido1, apellido2))
            persona_id = self.c.fetchone()[0]

            # Insertar codificación facial
            self.c.execute("""
                INSERT INTO codificaciones_faciales (persona_id, codificacion)
                VALUES (%s, %s)
            """, (persona_id, descriptor_json))

            # Confirmar cambios
            self.conn.commit()

            # Actualizar la base de datos en memoria
            self.face_db.append((f"{nombre1} {apellido1}", descriptor))

            return {'success': True, 'message': 'Registro guardado correctamente', 'persona_id': persona_id}
        except Exception as e:
            self.conn.rollback()
            return {'success': False, 'message': f'Error al guardar en DB: {str(e)}'}
