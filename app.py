# app.py
import cv2
import numpy as np
from PIL import Image, ImageTk
import tkinter as tk
from tkinter import messagebox
from face_recognition import get_face_descriptor, detect_faces
from database import connect_db, load_faces_from_db
from register import show_registration_form

class FaceRecognitionApp:
    def __init__(self, root, registration_mode=False):
        self.root = root
        self.root.title("Reconocimiento Facial")
        self.root.geometry("800x600")

        self.conn, self.c = connect_db()
        self.face_db = load_faces_from_db(self.c)
        self.registration_form_open = False
        self.registration_mode = registration_mode

        self.cap = cv2.VideoCapture(0)
        self.canvas = tk.Canvas(self.root, width=640, height=480)
        self.canvas.pack()

        self.name_label = tk.Label(self.root, text="Nombre: No reconocido", font=("Arial", 16))
        self.name_label.pack()

        self.face_cascade = cv2.CascadeClassifier(cv2.data.haarcascades + 'haarcascade_frontalface_default.xml')
        self.photo = None

        # Botón para capturar la foto manualmente
        self.capture_button = tk.Button(self.root, text="Tomar foto", command=self.capture_image)
        self.capture_button.pack(pady=10)

        # Iniciar solo el bucle de visualización (sin reconocimiento)
        self.update_frame()

    def update_frame(self):
        ret, frame = self.cap.read()
        if not ret:
            return

        frame = cv2.flip(frame, 1)

        # Dibujar silueta tenue
        overlay = frame.copy()
        center_x, center_y = frame.shape[1] // 2, frame.shape[0] // 2
        axes_length = (150, 200)
        color = (128, 128, 128)
        thickness = 2
        alpha = 0.3

        cv2.ellipse(overlay, (center_x, center_y), axes_length, 0, 0, 360, color, thickness)
        cv2.addWeighted(overlay, alpha, frame, 1 - alpha, 0, frame)

        # Mostrar en canvas
        frame_rgb = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
        img = Image.fromarray(frame_rgb)
        imgtk = ImageTk.PhotoImage(image=img)
        self.canvas.imgtk = imgtk
        self.canvas.create_image(0, 0, anchor=tk.NW, image=imgtk)

        # Repetir cada 15 ms
        self.root.after(15, self.update_frame)

    def capture_image(self):
        ret, frame = self.cap.read()
        if not ret:
            messagebox.showerror("Error", "No se pudo acceder a la cámara.")
            return

        frame = cv2.flip(frame, 1)

        faces = detect_faces(frame, self.face_cascade)

        if not faces:
            messagebox.showwarning("Advertencia", "No se detectó ningún rostro.")
            return

        # Seleccionar la cara más grande
        faces = sorted(faces, key=lambda f: f[2] * f[3], reverse=True)
        x, y, w, h = faces[0]
        face_img = frame[y:y+h, x:x+w]
        descriptor = get_face_descriptor(face_img)

        # Actualizar imagen en canvas (opcional, muestra la imagen capturada)
        frame_rgb = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
        img = Image.fromarray(frame_rgb)
        imgtk = ImageTk.PhotoImage(img)
        self.canvas.imgtk = imgtk
        self.canvas.create_image(0, 0, anchor=tk.NW, image=imgtk)

        # Verificar si el rostro es reconocido
        self.recognize_face(descriptor, face_img)

    def recognize_face(self, descriptor, face_image):
        recognized_name = None
        min_distance = float('inf')

        for name, saved_descriptor in self.face_db:
            distance = np.linalg.norm(saved_descriptor - descriptor)
            if distance < min_distance:
                min_distance = distance
                recognized_name = name

        if recognized_name is not None and min_distance < 0.9:
            self.name_label.config(text=f"Nombre: {recognized_name}")
        else:
            self.name_label.config(text="Nombre: No reconocido")
            if self.registration_mode:
                show_registration_form(self.root, descriptor, face_image, self.face_db, self.c, self.conn)

    def quit(self):
        self.cap.release()
        self.conn.close()
        self.root.quit()
