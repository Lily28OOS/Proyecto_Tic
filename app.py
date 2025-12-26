# app.py - utilidades para reconocimiento facial
# No ejecutar este archivo directamente; el entrypoint es main.py

import cv2
import numpy as np
from face_recognition import extract_face_descriptor
from database import connect_db, load_faces_from_db, close_db

class FaceRecognizer:
    def __init__(self):
        """
        Inicializa el reconocedor facial:
        - Conecta a la base de datos
        - Carga los embeddings faciales en memoria
        """
        try:
            self.conn, self.c = connect_db()
        except Exception as e:
            raise RuntimeError(f"No se pudo conectar a la base de datos: {e}")

        self.face_db = []
        self._load_faces()

        # Umbral estricto (ArcFace + embeddings normalizados)
        # Valores típicos:
        # 0.6 - muy estricto
        # 0.65 - estricto (recomendado)
        # 0.75 - permisivo
        self.MATCH_THRESHOLD = 0.65

    # ============================================================
    # UTILIDADES
    # ============================================================

    def normalize(self, v):
        """Normaliza un vector."""
        norm = np.linalg.norm(v)
        return v / norm if norm > 0 else None

    def resize_image(self, image_bgr, max_width=800):
        """Reduce el tamaño de la imagen si es muy grande."""
        h, w = image_bgr.shape[:2]
        if w > max_width:
            scale = max_width / w
            new_size = (int(w * scale), int(h * scale))
            return cv2.resize(image_bgr, new_size, interpolation=cv2.INTER_AREA)
        return image_bgr

    # ============================================================
    # CARGA Y ACTUALIZACIÓN DE EMBEDDINGS
    # ============================================================

    def _load_faces(self):
        """Carga los embeddings desde la base de datos."""
        try:
            faces = load_faces_from_db(self.c)
            self.face_db.clear()

            for name, desc in faces:
                try:
                    emb = self.normalize(np.array(desc, dtype=np.float32))
                    if emb is not None:
                        self.face_db.append((name, emb))
                except Exception:
                    continue
        except Exception as e:
            print(f"[ERROR] Cargando rostros desde DB: {e}")

    def refresh(self):
        """
        Recarga los embeddings desde la base de datos
        sin reiniciar la aplicación.
        """
        try:
            self._load_faces()
            return True
        except Exception:
            return False

    # ============================================================
    # RECONOCIMIENTO FACIAL
    # ============================================================

    def _compare_embeddings(self, descriptor):
        """
        Compara el embedding recibido con los almacenados.
        Devuelve (nombre, distancia) o (None, None).
        """
        best_match = None
        min_distance = float("inf")

        for name, stored_emb in self.face_db:
            distance = np.linalg.norm(stored_emb - descriptor)
            if distance < min_distance:
                min_distance = distance
                best_match = name

        if min_distance < self.MATCH_THRESHOLD:
            return best_match, min_distance

        return None, None

    def recognize_from_image(self, image_bgr):
        """
        Pipeline completo de reconocimiento:
        1. Redimensiona imagen
        2. Detecta rostro con RetinaFace
        3. Extrae embedding con ArcFace
        4. Compara contra la base de datos

        Devuelve:
        - (nombre, distancia) si hay coincidencia
        - (None, None) si no se reconoce
        """
        if image_bgr is None:
            return None, None

        image_bgr = self.resize_image(image_bgr)

        # Extraer embedding directamente (detección + reconocimiento)
        descriptor = extract_face_descriptor(image_bgr)
        if descriptor is None:
            return None, None

        descriptor = self.normalize(descriptor)
        if descriptor is None:
            return None, None

        return self._compare_embeddings(descriptor)

    # ============================================================
    # CIERRE DE RECURSOS
    # ============================================================

    def close(self):
        """Cierra correctamente la conexión a la base de datos."""
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
