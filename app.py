# app.py
import cv2
import numpy as np
from PIL import Image, ImageTk
import tkinter as tk
from face_recognition import get_face_descriptor, detect_faces
from database import connect_db, load_faces_from_db

class FaceRecognitionApp:
    def __init__(self, root):
        self.root = root
        self.root.title("Reconocimiento Facial")
        self.root.geometry("800x600")

        self.conn, self.c = connect_db()
        self.face_db = load_faces_from_db(self.c)

        self.cap = cv2.VideoCapture(0)
        self.canvas = tk.Canvas(self.root, width=640, height=480)
        self.canvas.pack()

        self.name_label = tk.Label(self.root, text="Nombre: No reconocido", font=("Arial", 16))
        self.name_label.pack(pady=10)

        self.face_cascade = cv2.CascadeClassifier(cv2.data.haarcascades + 'haarcascade_frontalface_default.xml')

        # Iniciar bucle de reconocimiento continuo
        self.update_frame()

    def update_frame(self):
        ret, frame = self.cap.read()
        if not ret:
            return

        frame = cv2.flip(frame, 1)
        faces = detect_faces(frame, self.face_cascade)

        if faces:
            x, y, w, h = faces[0]
            face_img = frame[y:y+h, x:x+w]
            descriptor = get_face_descriptor(face_img)
            self.recognize_face(descriptor)

            # Dibujar un rectángulo alrededor del rostro detectado
            cv2.rectangle(frame, (x, y), (x+w, y+h), (0, 255, 0), 2)
        else:
            self.name_label.config(text="Nombre: No reconocido")

        # Mostrar frame en canvas
        frame_rgb = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
        img = Image.fromarray(frame_rgb)
        imgtk = ImageTk.PhotoImage(image=img)
        self.canvas.imgtk = imgtk
        self.canvas.create_image(0, 0, anchor=tk.NW, image=imgtk)

        # Repetir cada 200 ms (puedes ajustar para mejor rendimiento)
        self.root.after(200, self.update_frame)

    def recognize_face(self, descriptor):
        recognized_name = None
        min_distance = float('inf')

        for full_name, saved_descriptor in self.face_db:
            distance = np.linalg.norm(saved_descriptor - descriptor)
            if distance < min_distance:
                min_distance = distance
                recognized_name = full_name

        if recognized_name is not None and min_distance < 0.9:
            parts = recognized_name.strip().split()
            first_name = parts[0] if len(parts) > 0 else ""
            first_surname = parts[1] if len(parts) > 1 else ""
            display_name = f"{first_name} {first_surname}".strip()
            self.name_label.config(text=f"Nombre: {display_name}")
        else:
            self.name_label.config(text="Nombre: No reconocido")

    def quit(self):
        self.cap.release()
        self.conn.close()
        self.root.quit()
