# app.py
import cv2
import numpy as np
from PIL import Image, ImageTk
import tkinter as tk
from face_recognition import get_face_descriptor, detect_faces
from database import connect_db, load_faces_from_db
import time

class FaceRecognitionApp:
    def __init__(self, root, registration_mode=False):
        self.root = root
        self.registration_mode = registration_mode
        self.root.title("Reconocimiento Facial")
        self.root.geometry("800x600")

        # Conexión a la DB
        self.conn, self.c = connect_db()
        self.face_db = load_faces_from_db(self.c)  # [(nombre, np.array(descriptor)), ...]

        # Abrir cámara
        self.cap = cv2.VideoCapture(0)
        if not self.cap.isOpened():
            print("Error: No se pudo abrir la cámara")

        # Interfaz
        self.canvas = tk.Canvas(self.root, width=640, height=480)
        self.canvas.pack()
        self.name_label = tk.Label(self.root, text="Nombre: No reconocido", font=("Arial", 16))
        self.name_label.pack(pady=10)

        self.last_recognition_time = 0
        self.last_recognized_name = None

        # Iniciar loop
        self.update_frame()

    def normalize(self, v):
        norm = np.linalg.norm(v)
        return v / norm if norm > 0 else v

    def update_frame(self):
        ret, frame = self.cap.read()
        if not ret:
            print("No se pudo leer frame")
            self.root.after(500, self.update_frame)
            return

        frame = cv2.flip(frame, 1)
        small_frame = cv2.resize(frame, (320, 240))  # Reducir para acelerar detección
        scale_factor = frame.shape[1] / 320

        faces = detect_faces(small_frame)  # Usamos RetinaFace aquí

        if faces is not None and len(faces) > 0:
            # Escalamos la primera cara detectada (puedes hacer para varias si quieres)
            x, y, w, h = [int(coord * scale_factor) for coord in faces[0]]

            # Padding para recorte cómodo
            padding = 10
            x = max(0, x - padding)
            y = max(0, y - padding)
            w = min(frame.shape[1] - x, w + 2 * padding)
            h = min(frame.shape[0] - y, h + 2 * padding)

            face_img = frame[y:y+h, x:x+w]

            current_time = time.time()
            if current_time - self.last_recognition_time > 3:  # cada 3 segundos
                descriptor = get_face_descriptor(face_img)
                descriptor = self.normalize(descriptor)
                self.recognize_face(descriptor)
                self.last_recognition_time = current_time

            # Dibujar rectángulo
            cv2.rectangle(frame, (x, y), (x+w, y+h), (0, 255, 0), 2)
        else:
            self.name_label.config(text="Nombre: No reconocido")
            self.last_recognized_name = None

        # Mostrar en Tkinter
        frame_rgb = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
        img = Image.fromarray(frame_rgb)
        imgtk = ImageTk.PhotoImage(image=img)
        self.canvas.imgtk = imgtk
        self.canvas.create_image(0, 0, anchor=tk.NW, image=imgtk)

        self.root.after(500, self.update_frame)

    def recognize_face(self, descriptor):
        recognized_name = None
        min_distance = float('inf')

        for full_name, saved_descriptor in self.face_db:
            saved_descriptor = self.normalize(saved_descriptor)
            distance = np.linalg.norm(saved_descriptor - descriptor)
            if distance < min_distance:
                min_distance = distance
                recognized_name = full_name

        if recognized_name is not None and min_distance < 1.2:
            if recognized_name != self.last_recognized_name:
                parts = recognized_name.strip().split()
                first_name = parts[0] if len(parts) > 0 else ""
                first_surname = parts[1] if len(parts) > 1 else ""
                display_name = f"{first_name} {first_surname}".strip()
                self.name_label.config(text=f"Nombre: {display_name}")
                self.last_recognized_name = recognized_name
        else:
            self.name_label.config(text="Nombre: No reconocido")
            self.last_recognized_name = None

    def quit(self):
        if self.cap.isOpened():
            self.cap.release()
        self.conn.close()
        self.root.quit()


if __name__ == "__main__":
    root = tk.Tk()
    app = FaceRecognitionApp(root)
    root.protocol("WM_DELETE_WINDOW", app.quit)
    root.mainloop()
