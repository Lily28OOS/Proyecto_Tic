# face_recognition.py
import cv2
import numpy as np
from deepface import DeepFace
from retinaface import RetinaFace

# ============================================================
# CONFIGURACIÓN GENERAL
# ============================================================

MIN_FACE_SIZE = 50                # píxeles mínimos del rostro
MIN_RETINAFACE_SCORE = 0.60       # score mínimo de detección
MIN_LAPLACIAN_VAR = 20.0          # nitidez mínima aceptable

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
# MEJORA DE CALIDAD DE IMAGEN (PREPROCESAMIENTO)
# ============================================================

def enhance_image_quality(frame):
    """
    Mejora iluminación, contraste y reduce ruido.
    Ideal para cámaras web o celulares.
    """
    try:
        if frame is None:
            return None

        # Convertir a YCrCb
        ycrcb = cv2.cvtColor(frame, cv2.COLOR_BGR2YCrCb)
        y, cr, cb = cv2.split(ycrcb)

        # Ecualización adaptativa (CLAHE)
        clahe = cv2.createCLAHE(clipLimit=2.0, tileGridSize=(8, 8))
        y_eq = clahe.apply(y)

        # Reconstruir imagen
        ycrcb_eq = cv2.merge((y_eq, cr, cb))
        enhanced = cv2.cvtColor(ycrcb_eq, cv2.COLOR_YCrCb2BGR)

        # Suavizado ligero
        enhanced = cv2.GaussianBlur(enhanced, (3, 3), 0)

        return enhanced

    except Exception as e:
        print(f"[ERROR] enhance_image_quality: {e}")
        return frame


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
# DETECCIÓN FACIAL CON RETINAFACE
# ============================================================

def detect_face_retina(frame):
    try:
        if frame is None:
            return None

        # Reducir tamaño SOLO para detección (mejora RetinaFace)
        h, w = frame.shape[:2]
        scale = 640 / max(h, w)
        resized = cv2.resize(frame, (int(w * scale), int(h * scale)))

        img_rgb = cv2.cvtColor(resized, cv2.COLOR_BGR2RGB)
        faces = RetinaFace.detect_faces(img_rgb)

        if not isinstance(faces, dict) or len(faces) == 0:
            return None

        best_face = max(faces.values(), key=lambda x: x.get("score", 0))
        score = best_face.get("score", 0)

        if score < 0.55:  # más tolerante
            return None

        x1, y1, x2, y2 = best_face["facial_area"]

        # Reescalar coordenadas al frame original
        inv = 1 / scale
        x1, y1, x2, y2 = map(lambda v: int(v * inv), (x1, y1, x2, y2))

        face = frame[y1:y2, x1:x2]

        if face.size == 0:
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
# PIPELINE PRINCIPAL (REGISTRO / RECONOCIMIENTO)
# ============================================================

def extract_face_descriptor(frame):
    """
    Pipeline REALISTA:
    - Registro: permisivo
    - Reconocimiento: estricto (se controla afuera)
    """

    enhanced = enhance_image_quality(frame)
    face = detect_face_retina(enhanced)

    if face is None:
        return None

    return get_face_embedding(face)
