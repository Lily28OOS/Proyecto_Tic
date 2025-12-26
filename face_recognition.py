# face_recognition.py

import cv2
import numpy as np
from deepface import DeepFace
from retinaface import RetinaFace

# ============================================================
# CONFIGURACIÓN GENERAL (UMBRAL ESTRICTO)
# ============================================================

MIN_FACE_SIZE = 90               # píxeles mínimos (ancho o alto)
MIN_RETINAFACE_SCORE = 0.95      # detección MUY estricta
MIN_LAPLACIAN_VAR = 100.0        # nitidez mínima (blur detection)

# Nota:
# Para ArcFace con embeddings normalizados:
# - SAME PERSON  : cosine similarity >= 0.70
# - DIFFERENT    : < 0.70
# Este umbral se aplicará en el módulo de comparación / BD

# ============================================================
# CARGA DEL MODELO ARCFACE (UNA SOLA VEZ)
# ============================================================

print("[INFO] Cargando modelo ArcFace...")
try:
    ARC_MODEL = DeepFace.build_model("ArcFace")
    print("[INFO] Modelo ArcFace cargado correctamente.")
except Exception as e:
    print(f"[ERROR] No se pudo cargar ArcFace: {e}")
    ARC_MODEL = None


# ============================================================
# UTILIDAD: MEDIR NITIDEZ DEL ROSTRO
# ============================================================

def is_face_sharp(face_img):
    """
    Evalúa si el rostro está borroso usando Laplacian.
    """
    gray = cv2.cvtColor(face_img, cv2.COLOR_BGR2GRAY)
    variance = cv2.Laplacian(gray, cv2.CV_64F).var()
    return variance >= MIN_LAPLACIAN_VAR


# ============================================================
# DETECCIÓN FACIAL CON RETINAFACE (OPTIMIZADA + FILTROS)
# ============================================================

def detect_face_retina(frame, target_width=320):
    """
    Detecta un solo rostro usando RetinaFace.
    Aplica filtros estrictos de calidad.
    Devuelve rostro recortado (BGR) o None.
    """
    try:
        if frame is None:
            return None

        img_rgb = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)

        h, w = img_rgb.shape[:2]
        ratio = target_width / w
        resized = cv2.resize(img_rgb, (target_width, int(h * ratio)))

        faces = RetinaFace.detect_faces(resized)
        if not isinstance(faces, dict) or len(faces) == 0:
            return None

        # Seleccionar rostro con mayor score
        best_face = max(
            faces.values(),
            key=lambda x: x.get("score", 0)
        )

        score = best_face.get("score", 0)
        if score < MIN_RETINAFACE_SCORE:
            return None

        x1, y1, x2, y2 = best_face["facial_area"]

        # Escalar coordenadas al tamaño original
        scale_x = w / resized.shape[1]
        scale_y = h / resized.shape[0]

        x1 = int(x1 * scale_x)
        x2 = int(x2 * scale_x)
        y1 = int(y1 * scale_y)
        y2 = int(y2 * scale_y)

        face = frame[y1:y2, x1:x2]
        if face.size == 0:
            return None

        fh, fw = face.shape[:2]
        if fh < MIN_FACE_SIZE or fw < MIN_FACE_SIZE:
            return None

        if not is_face_sharp(face):
            return None

        return face

    except Exception as e:
        print(f"[ERROR] detect_face_retina: {e}")
        return None


# ============================================================
# EXTRACCIÓN DE EMBEDDING FACIAL (ARCFACE)
# ============================================================

def get_face_embedding(face_img):
    """
    Recibe imagen de rostro (BGR).
    Devuelve embedding normalizado (np.ndarray) o None.
    """
    try:
        if ARC_MODEL is None or face_img is None:
            return None

        face_rgb = cv2.cvtColor(face_img, cv2.COLOR_BGR2RGB)

        rep = DeepFace.represent(
            img=face_rgb,
            model=ARC_MODEL,
            enforce_detection=False,
            detector_backend="skip"
        )

        if not rep or not isinstance(rep, list):
            return None

        embedding = rep[0].get("embedding")
        if embedding is None:
            return None

        emb = np.array(embedding, dtype=np.float32)
        norm = np.linalg.norm(emb)
        if norm == 0:
            return None

        return emb / norm

    except Exception as e:
        print(f"[ERROR] get_face_embedding: {e}")
        return None


# ============================================================
# PIPELINE PRINCIPAL (FASTAPI / BACKEND)
# ============================================================

def extract_face_descriptor(frame):
    """
    Pipeline completo y estricto:
    1. Detecta rostro válido
    2. Verifica calidad
    3. Extrae embedding ArcFace

    Retorna embedding normalizado o None
    """
    face = detect_face_retina(frame)
    if face is None:
        return None

    return get_face_embedding(face)
