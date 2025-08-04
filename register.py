# register.py
import cv2
import numpy as np
from PIL import Image, ImageTk
import tkinter as tk
from tkinter import messagebox
from face_recognition import detect_faces, get_face_descriptor
from registerform import show_registration_form

class FaceRegister:
    def __init__(self, root, face_db, c, conn):
        self.root = root
        self.face_db = face_db
        self.c = c
        self.conn = conn

        self.cap = cv2.VideoCapture(0)
        self.canvas = tk.Canvas(root, width=640, height=480)
        self.canvas.pack()

        self.face_cascade = cv2.CascadeClassifier(cv2.data.haarcascades + 'haarcascade_frontalface_default.xml')

        self.capture_button = tk.Button(root, text="Tomar foto", command=self.capture_image)
        self.capture_button.pack(pady=10)

        self.cancel_button = tk.Button(root, text="Cancelar", command=self.cancel)
        self.cancel_button.pack(pady=5)

        self.name_label = tk.Label(root, text="Ajusta tu rostro dentro de la silueta y presiona 'Tomar foto'", font=("Arial", 14))
        self.name_label.pack(pady=5)

        self.update_frame()

    def update_frame(self):
        ret, frame = self.cap.read()
        if not ret:
            return

        frame = cv2.flip(frame, 1)

        overlay = frame.copy()
        center_x, center_y = frame.shape[1] // 2, frame.shape[0] // 2
        axes_length = (150, 200)
        color = (128, 128, 128)
        thickness = 2
        alpha = 0.3

        cv2.ellipse(overlay, (center_x, center_y), axes_length, 0, 0, 360, color, thickness)
        cv2.addWeighted(overlay, alpha, frame, 1 - alpha, 0, frame)

        frame_rgb = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
        img = Image.fromarray(frame_rgb)
        imgtk = ImageTk.PhotoImage(image=img)
        self.canvas.imgtk = imgtk
        self.canvas.create_image(0, 0, anchor=tk.NW, image=imgtk)

        self.root.after(15, self.update_frame)

    def show_save_result(self, success, message):
        if success:
            messagebox.showinfo("Éxito", message)
        else:
            messagebox.showerror("Error", message)

    def capture_image(self):
        ret, frame = self.cap.read()
        if not ret:
            messagebox.showerror("Error", "No se pudo acceder a la cámara.")
            return

        frame = cv2.flip(frame, 1)
        faces = detect_faces(frame)

        if len(faces) == 0:
            messagebox.showwarning("Advertencia", "No se detectó ningún rostro.")
            return

        x, y, w, h = faces[0]
        face_img = frame[y:y+h, x:x+w]
        descriptor = get_face_descriptor(face_img)

        # Verificar duplicado
        for _, existing_descriptor in self.face_db:
            distance = np.linalg.norm(existing_descriptor - descriptor)
            if distance < 0.9:
                messagebox.showinfo("Ya registrado", "Este rostro ya está registrado en el sistema.")
                return

        self.cap.release()
        # Pasar callback show_save_result para mostrar resultado después de guardar
        show_registration_form(self.root, descriptor, face_img, self.face_db, self.c, self.conn)

    def cancel(self):
        self.cap.release()
        self.root.destroy()

        # Importar aquí para evitar el ciclo
        from selection import SelectionWindow
        SelectionWindow()
