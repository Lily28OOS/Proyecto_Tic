# app.py
import cv2
import numpy as np
from face_recognition import get_face_descriptor, detect_faces
from database import connect_db, load_faces_from_db

class FaceRecognizer:
    def __init__(self):
        # Conectar a la base de datos
        self.conn, self.c = connect_db()
        # Cargar únicamente rostros de personas activas
        self.face_db = [(name, self.normalize(desc)) for name, desc in load_faces_from_db(self.c)]

    def normalize(self, v):
        norm = np.linalg.norm(v)
        return v / norm if norm > 0 else v

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
            print("[INFO] No se detectaron rostros.")
            return None, None

        x, y, w, h = faces[0]

        # Validar tamaño mínimo del rostro detectado
        MIN_FACE_SIZE = 60
        if w < MIN_FACE_SIZE or h < MIN_FACE_SIZE:
            print("[WARNING] Rostro demasiado pequeño para reconocimiento.")
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
            print("[ERROR] No se pudo obtener descriptor válido del rostro.")
            return None, None

        descriptor = self.normalize(descriptor)
        return self.recognize_face_with_distance(descriptor)

    def close(self):
        self.conn.close()

# Uso de prueba manual
if __name__ == "__main__":
    recognizer = FaceRecognizer()
    img = cv2.imread("test_image.jpg")

    if img is None:
        print("No se pudo cargar la imagen de prueba.")
    else:
        name, dist = recognizer.recognize_from_image(img)
        if name:
            print(f"✅ Rostro reconocido: {name} (distancia {dist:.3f})")
        else:
            print("❌ Rostro no reconocido.")

    recognizer.close()
