# face_recognition.py
import cv2
import numpy as np
from deepface import DeepFace
from retinaface import RetinaFace
import time
import threading

print("[INFO] Cargando modelo ArcFace...")
model = DeepFace.build_model("ArcFace")
print("[INFO] Modelo cargado.")

class MixedFaceDetector:
    def __init__(self):
        self._last_detection = None
        self._last_detection_time = 0
        self.cache_time = 1.0  # segundos para cachear detecciones
        self.frame_count = 0
        self.lock = threading.Lock()

        # Detector rápido Haar Cascade
        self.face_cascade = cv2.CascadeClassifier(cv2.data.haarcascades + "haarcascade_frontalface_default.xml")
        if self.face_cascade.empty():
            raise IOError("No se pudo cargar haarcascade_frontalface_default.xml")

        self._retinaface_thread = None
        self._retinaface_result = None
        self._retinaface_running = False

    def _detect_retinaface_async(self, frame):
        """Función que corre RetinaFace en segundo plano"""
        try:
            height, width = frame.shape[:2]
            top_portion_height = int(height * 0.6)
            top_frame = frame[0:top_portion_height, :]

            new_width = 320
            new_height = int(new_width * top_portion_height / width)
            small_frame = cv2.resize(top_frame, (new_width, new_height))
            img_rgb = cv2.cvtColor(small_frame, cv2.COLOR_BGR2RGB)

            faces = RetinaFace.detect_faces(img_rgb)
            boxes = []
            if isinstance(faces, dict):
                for key, face in faces.items():
                    x1, y1, x2, y2 = face['facial_area']
                    scale_x = width / new_width
                    scale_y = top_portion_height / new_height

                    x1 = int(x1 * scale_x)
                    y1 = int(y1 * scale_y)
                    x2 = int(x2 * scale_x)
                    y2 = int(y2 * scale_y)

                    boxes.append((x1, y1, x2 - x1, y2 - y1))
            with self.lock:
                self._retinaface_result = boxes
                self._retinaface_running = False
                self._last_detection = boxes
                self._last_detection_time = time.time()
            print(f"[INFO] RetinaFace async: detectadas {len(boxes)} caras.")
        except Exception as e:
            print(f"[ERROR] RetinaFace async detection: {e}")
            with self.lock:
                self._retinaface_running = False

    def detect_faces(self, frame):
        current_time = time.time()
        with self.lock:
            cache_valid = (self._last_detection is not None) and ((current_time - self._last_detection_time) < self.cache_time)

        if cache_valid:
            # Retornar cache inmediatamente
            return self._last_detection

        self.frame_count += 1
        start = time.time()

        # Siempre detectar rápido con Haar Cascade y devolverlo rápido
        gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)
        faces = self.face_cascade.detectMultiScale(gray, scaleFactor=1.1, minNeighbors=5, minSize=(40, 40))
        boxes = [(x, y, w, h) for (x, y, w, h) in faces]
        method = "Haar Cascade"

        elapsed = time.time() - start
        print(f"[INFO] detect_faces ({method}): tiempo = {elapsed:.3f}s, faces detectadas: {len(boxes)}")

        # Lanzar RetinaFace async solo si no está ya corriendo
        with self.lock:
            if not self._retinaface_running:
                self._retinaface_running = True
                frame_copy = frame.copy()
                self._retinaface_thread = threading.Thread(target=self._detect_retinaface_async, args=(frame_copy,))
                self._retinaface_thread.daemon = True
                self._retinaface_thread.start()

            # Actualizar cache con detección rápida para respuestas rápidas
            self._last_detection = boxes
            self._last_detection_time = current_time

        return boxes

def get_face_descriptor(image):
    try:
        start = time.time()
        result = DeepFace.represent(
            img_path=image,
            model_name="ArcFace",
            detector_backend="skip",
            enforce_detection=False
        )
        embedding = result[0]['embedding']
        embedding = np.array(embedding)
        embedding_norm = embedding / np.linalg.norm(embedding)
        elapsed = time.time() - start
        print(f"[INFO] get_face_descriptor: tiempo de extracción = {elapsed:.3f} segundos")
        return embedding_norm
    except Exception as e:
        print(f"[Error get_face_descriptor] {e}")
        return np.zeros(512)

# Instancia global
_detector_instance = MixedFaceDetector()

def detect_faces(frame):
    return _detector_instance.detect_faces(frame)
