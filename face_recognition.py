# face_recognition.py
import cv2
import numpy as np
from deepface import DeepFace
from retinaface import RetinaFace

# Función para obtener el descriptor del rostro usando ArcFace
def get_face_descriptor(image):
    result = DeepFace.represent(image, model_name="ArcFace", enforce_detection=False)
    descriptor = result[0]["embedding"]
    return np.array(descriptor)

# Detección de rostro usando RetinaFace
def detect_faces(frame):
    img_rgb = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
    faces = RetinaFace.detect_faces(img_rgb)

    boxes = []
    if faces:
        for key, face in faces.items():
            x1, y1, x2, y2 = face['facial_area']
            boxes.append((x1, y1, x2 - x1, y2 - y1))  # (x, y, w, h)
    return boxes
