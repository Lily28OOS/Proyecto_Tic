# face_recognition.py
import cv2
import numpy as np
from deepface import DeepFace
from retinaface import RetinaFace
import time

print("[INFO] Cargando modelo ArcFace...")
model = DeepFace.build_model("ArcFace")
print("[INFO] Modelo cargado.")

# Variables para cache de detecciones simples
_last_detection = None
_last_detection_time = 0

def preprocess_face(img, target_size=(112, 112)):
    if img.ndim == 2:
        img = cv2.cvtColor(img, cv2.COLOR_GRAY2BGR)
    elif img.shape[2] == 4:
        img = cv2.cvtColor(img, cv2.COLOR_BGRA2BGR)

    img = cv2.resize(img, target_size)
    img_rgb = cv2.cvtColor(img, cv2.COLOR_BGR2RGB)
    img_rgb = img_rgb.astype('float32') / 255.0
    img_rgb = np.expand_dims(img_rgb, axis=0)
    return img_rgb

def get_face_descriptor(image):
    try:
        start = time.time()
        # DeepFace.represent puede aceptar numpy array directamente
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

def detect_faces(frame, use_cache=True, cache_time=1.0):
    global _last_detection, _last_detection_time

    current_time = time.time()
    if use_cache and _last_detection is not None and (current_time - _last_detection_time) < cache_time:
        # Retorna cache para evitar repetir detección si no pasó suficiente tiempo
        return _last_detection

    start = time.time()
    # Reducir resolución para acelerar
    small_frame = cv2.resize(frame, (160, 120))
    img_rgb = cv2.cvtColor(small_frame, cv2.COLOR_BGR2RGB)

    faces = RetinaFace.detect_faces(img_rgb)

    boxes = []
    if isinstance(faces, dict):
        for key, face in faces.items():
            x1, y1, x2, y2 = face['facial_area']
            # Ajustar coordenadas a tamaño original
            scale_x = frame.shape[1] / 160
            scale_y = frame.shape[0] / 120
            x1 = int(x1 * scale_x)
            y1 = int(y1 * scale_y)
            x2 = int(x2 * scale_x)
            y2 = int(y2 * scale_y)
            boxes.append((x1, y1, x2 - x1, y2 - y1))

    elapsed = time.time() - start
    print(f"[INFO] detect_faces: tiempo de detección = {elapsed:.3f} segundos, Faces detectadas: {len(boxes)}")

    _last_detection = boxes
    _last_detection_time = current_time
    return boxes
