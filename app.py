# app.py
import cv2
import numpy as np
from PIL import Image, ImageTk
import tkinter as tk
from face_recognition import get_face_descriptor, detect_faces
from database import connect_db, load_faces_from_db
from interface import show_registration_form

class FaceRecognitionApp:
    def __init__(self, root):
        self.root = root
        self.root.title("Reconocimiento Facial")
        self.root.geometry("800x600")

        self.conn, self.c = connect_db()
        self.face_db = load_faces_from_db(self.c)
        self.registration_form_open = False

        self.cap = cv2.VideoCapture(0)
        self.canvas = tk.Canvas(self.root, width=640, height=480)
        self.canvas.pack()

        self.name_label = tk.Label(self.root, text="Nombre: No reconocido", font=("Arial", 16))
        self.name_label.pack()

        self.face_cascade = cv2.CascadeClassifier(cv2.data.haarcascades + 'haarcascade_frontalface_default.xml')
        self.photo = None
        self.detecting = False  # Nueva bandera para controlar el retraso

        self.update_frame()

    def update_frame(self):
        ret, frame = self.cap.read()
        if ret:
            self.detect_faces(frame)
            frame_rgb = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
            frame_image = Image.fromarray(frame_rgb)
            self.photo = ImageTk.PhotoImage(image=frame_image)
            self.canvas.create_image(0, 0, anchor=tk.NW, image=self.photo)
            self.root.after(10, self.update_frame)
        else:
            print("Error al acceder a la cámara.")

    def detect_faces(self, frame):
        if self.detecting:  # Si ya se está detectando, no hacer nada
            return

        faces = detect_faces(frame, self.face_cascade)

        if len(faces) > 0:
            faces = sorted(faces, key=lambda face: self.distance_to_center(face, frame.shape))
            x, y, w, h = faces[0]
            face = frame[y:y+h, x:x+w]
            descriptor = get_face_descriptor(face)

            self.detecting = True  # Establecer que estamos en un periodo de espera

            # Iniciar el temporizador de x segundos
            self.root.after(1000, self.recognize_face, descriptor, face)

            # Dibuja un rectángulo en la cara detectada
            cv2.rectangle(frame, (x, y), (x + w, y + h), (0, 0, 255), 2)

    def recognize_face(self, descriptor, face_image):
        recognized_name = None
        min_distance = float('inf')

        # Compara el rostro detectado con los rostros en la base de datos
        for name, saved_descriptor in self.face_db:
            distance = np.linalg.norm(saved_descriptor - descriptor)
            if distance < min_distance:
                min_distance = distance
                recognized_name = name

        if recognized_name is not None and min_distance < 0.9:
            self.name_label.config(text=f"Nombre: {recognized_name}")
        else:
            self.name_label.config(text="Nombre: No reconocido")
            show_registration_form(self.root, descriptor, face_image, self.face_db, self.c, self.conn)

        self.detecting = False  # Finaliza el periodo de detección

    def distance_to_center(self, face, frame_shape):
        x, y, w, h = face
        face_center = (x + w // 2, y + h // 2)
        frame_center = (frame_shape[1] // 2, frame_shape[0] // 2)
        return np.linalg.norm(np.array(face_center) - np.array(frame_center))

    def quit(self):
        self.cap.release()
        self.conn.close()
        self.root.quit()
