# app.py
import cv2
import numpy as np
from PIL import Image, ImageTk
import tkinter as tk
from face_recognition import get_face_descriptor, detect_faces
from database import connect_db, load_faces_from_db
import time
import threading

class FaceRecognitionApp:
    def __init__(self, root, registration_mode=False):
        self.root = root
        self.registration_mode = registration_mode
        self.root.title("Reconocimiento Facial")
        self.root.geometry("800x600")

        # Conexión a la DB y normalización una sola vez
        self.conn, self.c = connect_db()
        self.face_db = [(name, self.normalize(desc)) for name, desc in load_faces_from_db(self.c)]

        # Cámara
        self.cap = cv2.VideoCapture(0)
        if not self.cap.isOpened():
            print("Error: No se pudo abrir la cámara")

        # Interfaz
        self.canvas = tk.Canvas(self.root, width=640, height=480)
        self.canvas.pack()
        self.name_label = tk.Label(self.root, text="Nombre: No reconocido", font=("Arial", 16))
        self.name_label.pack(pady=10)

        # Variables compartidas
        self.lock = threading.Lock()
        self.frame = None
        self.processing_frame = None
        self.detected_face = None
        self.recognized_name = None
        self.recognition_distance = None

        self.running = True
        self.last_recognition_time = 0
        self.processing_face = False  # Variable para controlar si está procesando reconocimiento

        # Hilos
        self.processing_thread = threading.Thread(target=self.processing_loop, daemon=True)
        self.processing_thread.start()
        self.update_frame()

    def normalize(self, v):
        norm = np.linalg.norm(v)
        return v / norm if norm > 0 else v

    def processing_loop(self):
        frame_count = 0
        while self.running:
            with self.lock:
                frame = self.processing_frame.copy() if self.processing_frame is not None else None

            if frame is None:
                time.sleep(0.01)
                continue

            frame_count += 1

            if frame_count % 6 == 0:
                faces = detect_faces(frame)

                if faces:
                    x, y, w, h = faces[0]

                    padding = 10
                    x = max(0, x - padding)
                    y = max(0, y - padding)
                    w = min(frame.shape[1] - x, w + 2 * padding)
                    h = min(frame.shape[0] - y, h + 2 * padding)

                    current_time = time.time()
                    if current_time - self.last_recognition_time > 1.5:
                        self.processing_face = True

                        face_img = frame[y:y+h, x:x+w]
                        descriptor = get_face_descriptor(face_img)
                        descriptor = self.normalize(descriptor)
                        recognized_name, min_distance = self.recognize_face_with_distance(descriptor)

                        with self.lock:
                            self.detected_face = (x, y, w, h)
                            self.recognized_name = recognized_name
                            self.recognition_distance = min_distance

                        self.last_recognition_time = current_time
                        self.processing_face = False
                    else:
                        with self.lock:
                            self.detected_face = (x, y, w, h)
                else:
                    with self.lock:
                        self.detected_face = None
                        self.recognized_name = None
                        self.recognition_distance = None
                        self.processing_face = False

            time.sleep(0.01)

    def recognize_face_with_distance(self, descriptor):
        recognized_name = None
        min_distance = float('inf')

        for full_name, saved_descriptor in self.face_db:
            distance = np.linalg.norm(saved_descriptor - descriptor)
            if distance < min_distance:
                min_distance = distance
                recognized_name = full_name

        if min_distance < 0.75:  # Umbral de reconocimiento
            return recognized_name, min_distance
        else:
            return None, None

    def update_frame(self):
        ret, frame = self.cap.read()
        if not ret:
            self.root.after(10, self.update_frame)
            return

        frame = cv2.flip(frame, 1)

        with self.lock:
            self.frame = frame.copy()
            self.processing_frame = frame.copy()
            detected_face = self.detected_face
            recognized_name = self.recognized_name
            recognition_distance = self.recognition_distance

        if detected_face:
            x, y, w, h = detected_face
            cv2.rectangle(frame, (x, y), (x + w, y + h), (0, 255, 0), 2)
            if recognized_name and recognition_distance is not None:
                parts = recognized_name.strip().split()
                name = f"{parts[0]} {parts[1]}" if len(parts) > 1 else parts[0]
                text = f"{name} ({recognition_distance:.2f})"
                cv2.putText(frame, text, (x, y - 10), cv2.FONT_HERSHEY_SIMPLEX,
                            0.7, (0, 255, 0), 2)
            else:
                cv2.putText(frame, "No reconocido", (x, y - 10), cv2.FONT_HERSHEY_SIMPLEX,
                            0.7, (0, 0, 255), 2)

        if recognized_name:
            parts = recognized_name.strip().split()
            name = f"{parts[0]} {parts[1]}" if len(parts) > 1 else parts[0]
            self.name_label.config(text=f"Nombre: {name}")
        else:
            self.name_label.config(text="Nombre: No reconocido")

        frame_rgb = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
        img = Image.fromarray(frame_rgb)
        imgtk = ImageTk.PhotoImage(image=img)

        self.canvas.imgtk = imgtk
        self.canvas.create_image(0, 0, anchor=tk.NW, image=imgtk)
        self.root.after(15, self.update_frame)

    def quit(self):
        self.running = False
        if self.cap.isOpened():
            self.cap.release()
        self.conn.close()
        self.root.quit()

if __name__ == "__main__":
    root = tk.Tk()
    app = FaceRecognitionApp(root)
    root.protocol("WM_DELETE_WINDOW", app.quit)
    root.mainloop()
