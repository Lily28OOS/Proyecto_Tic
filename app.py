# app.py - utilidades para reconocimiento facial
# No ejecutar este archivo directamente; el entrypoint de la aplicación es main.py
import cv2
import numpy as np
from face_recognition import get_face_descriptor, detect_faces
from database import connect_db, load_faces_from_db, close_db

class FaceRecognizer:
    def __init__(self):
        # Conectar a la base de datos
        try:
            self.conn, self.c = connect_db()
        except Exception as e:
            # Si no se puede conectar, lanzar excepción clara
            raise RuntimeError(f"No se pudo conectar a la base de datos: {e}")

        # Cargar únicamente rostros de personas activas
        faces = load_faces_from_db(self.c)
        self.face_db = []
        for name, desc in faces:
            try:
                self.face_db.append((name, self.normalize(desc)))
            except Exception:
                # omitir descriptores inválidos
                continue

    def normalize(self, v):
        norm = np.linalg.norm(v)
        return v / norm if norm > 0 else v

    def refresh(self):
        """Recargar descriptores desde la base de datos (útil si se registraron rostros sin reiniciar)."""
        try:
            faces = load_faces_from_db(self.c)
            self.face_db = []
            for name, desc in faces:
                try:
                    self.face_db.append((name, self.normalize(desc)))
                except Exception:
                    continue
            return True
        except Exception:
            return False

    def resize_image(self, image_bgr, max_width=800):
        """Reduce el tamaño de la imagen si es muy grande, para mejorar el rendimiento."""
        height, width = image_bgr.shape[:2]
        if width > max_width:
            scale = max_width / width
            new_size = (int(width * scale), int(height * scale))
            return cv2.resize(image_bgr, new_size, interpolation=cv2.INTER_AREA)
        return image_bgr

    def recognize_face_with_distance(self, descriptor):
        """Compara el descriptor recibido con los almacenados en la base."""
        recognized_name = None
        min_distance = float('inf')

        for full_name, saved_descriptor in self.face_db:
            distance = np.linalg.norm(saved_descriptor - descriptor)
            if distance < min_distance:
                min_distance = distance
                recognized_name = full_name

        # Umbral de similitud para considerar una coincidencia
        if min_distance < 0.75:
            return recognized_name, min_distance
        return None, None

    def recognize_from_image(self, image_bgr):
        """Detecta y reconoce el rostro en una imagen BGR (OpenCV)."""
        image_bgr = self.resize_image(image_bgr)

        faces = detect_faces(image_bgr)
        if not faces:
            return None, None

        x, y, w, h = faces[0]

        # Validar tamaño mínimo del rostro detectado
        MIN_FACE_SIZE = 60
        if w < MIN_FACE_SIZE or h < MIN_FACE_SIZE:
            return None, None

        # Padding dinámico (20% del tamaño del rostro)
        padding = int(0.2 * max(w, h))
        x = max(0, x - padding)
        y = max(0, y - padding)
        w = min(image_bgr.shape[1] - x, w + 2 * padding)
        h = min(image_bgr.shape[0] - y, h + 2 * padding)

        face_img = image_bgr[y:y+h, x:x+w]
        descriptor = get_face_descriptor(face_img)

        if descriptor is None or len(descriptor) == 0:
            return None, None

        descriptor = self.normalize(descriptor)
        return self.recognize_face_with_distance(descriptor)

    def close(self):
        # Devolver la conexión al pool o cerrarla correctamente
        try:
            close_db(self.conn, self.c)
        except Exception:
            try:
                if self.c:
                    self.c.close()
                if self.conn:
                    self.conn.close()
            except Exception:
                pass
