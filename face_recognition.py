# face_recognition.py
import cv2
import numpy as np
from deepface import DeepFace
from retinaface import RetinaFace
import time
import threading

print("[INFO] Cargando modelo ArcFace...")
try:
    model = DeepFace.build_model("ArcFace")
    print("[INFO] Modelo ArcFace cargado.")
except Exception as e:
    print(f"[WARN] No se pudo cargar modelo ArcFace: {e}")
    model = None

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
    """
    Recibe:
      - imagen numpy BGR (cv2.imread) o RGB,
      - o ruta a archivo (str),
      - o bytes de imagen.
    Devuelve descriptor numpy normalizado (float32) o None si falla.
    """
    try:
        if model is None:
            print("[ERROR] Modelo ArcFace no disponible")
            return None

        # Determinar si image es ndarray (imagen en memoria) o path/bytes
        is_ndarray = isinstance(image, (np.ndarray, ))
        is_path = isinstance(image, str)
        is_bytes = isinstance(image, (bytes, bytearray))

        img_arg = None
        # preparar imagen para DeepFace: DeepFace puede aceptar img=ndarray o img_path=str
        if is_ndarray:
            # intentar convertir a RGB (DeepFace espera RGB)
            try:
                img_rgb = cv2.cvtColor(image, cv2.COLOR_BGR2RGB)
            except Exception:
                img_rgb = image
            img_arg = {"img": img_rgb}
        elif is_path:
            img_arg = {"img_path": image}
        elif is_bytes:
            # intentar decodificar bytes a ndarray
            nparr = np.frombuffer(image, np.uint8)
            img_np = cv2.imdecode(nparr, cv2.IMREAD_COLOR)
            try:
                img_rgb = cv2.cvtColor(img_np, cv2.COLOR_BGR2RGB)
            except Exception:
                img_rgb = img_np
            img_arg = {"img": img_rgb}
        else:
            # fallback: intentar tratar como path
            img_arg = {"img_path": image}

        # llamar DeepFace.represent probando firmas distintas si hace falta
        rep = None
        try:
            rep = DeepFace.represent(model=model, enforce_detection=False, detector_backend="skip", **img_arg)
        except TypeError:
            # versión que no acepta 'model' como keyword o acepta distinta firma
            try:
                if is_ndarray or is_bytes:
                    rep = DeepFace.represent(img=img_arg.get("img"), model_name="ArcFace", enforce_detection=False, detector_backend="skip")
                else:
                    rep = DeepFace.represent(img_path=img_arg.get("img_path"), model_name="ArcFace", enforce_detection=False, detector_backend="skip")
            except Exception as e2:
                print(f"[ERROR] DeepFace.represent fallback error: {e2}")
                rep = None
        except Exception as e:
            print(f"[ERROR] DeepFace.represent error: {e}")
            rep = None

        if not rep:
            print("[ERROR] DeepFace.represent devolvió None o lista vacía")
            return None

        # extraer embedding soportando varias estructuras
        embedding = None
        try:
            if isinstance(rep, dict) and "embedding" in rep:
                embedding = rep["embedding"]
            elif isinstance(rep, list):
                first = rep[0]
                if isinstance(first, dict) and "embedding" in first:
                    embedding = first["embedding"]
                elif isinstance(first, (list, np.ndarray, float, int)):
                    # rep puede ser directamente una lista/vector
                    if isinstance(first, (list, np.ndarray)):
                        embedding = first
                    else:
                        # rep es lista de números
                        embedding = rep
            elif isinstance(rep, (list, np.ndarray)):
                embedding = rep
        except Exception:
            embedding = None

        if embedding is None:
            print("[ERROR] No se pudo extraer embedding de la salida de DeepFace")
            return None

        emb = np.array(embedding, dtype=np.float32)
        norm = np.linalg.norm(emb)
        if norm <= 0:
            print("[ERROR] Embedding con norma 0")
            return None
        emb_norm = emb / norm
        return emb_norm
    except Exception as e:
        print(f"[Error get_face_descriptor] {e}")
        return None

# Instancia global
_detector_instance = MixedFaceDetector()

def detect_faces(frame):
    return _detector_instance.detect_faces(frame)
