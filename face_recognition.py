# face_recognition.py
import cv2
import numpy as np
from deepface import DeepFace
from PIL import Image, ImageTk

# Función para obtener el descriptor del rostro usando ArcFace
def get_face_descriptor(image):
    result = DeepFace.represent(image, model_name="ArcFace", enforce_detection=False)
    descriptor = result[0]["embedding"]
    return np.array(descriptor)

# Detección de rostro usando OpenCV
def detect_faces(frame, face_cascade):
    gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)
    faces = face_cascade.detectMultiScale(gray, scaleFactor=1.1, minNeighbors=5)
    return faces
