# seleccion.py
import tkinter as tk
from register import show_registration_form
from app import FaceRecognitionApp
import cv2
from database import connect_db, load_faces_from_db

class SelectionWindow:
    def __init__(self):
        self.root = tk.Tk()
        self.root.title("Seleccionar opción")
        self.root.geometry("300x150")

        btn_register = tk.Button(self.root, text="Registro", width=20, command=self.open_registration)
        btn_verify = tk.Button(self.root, text="Verificación", width=20, command=self.open_verification)

        btn_register.pack(pady=20)
        btn_verify.pack(pady=10)

        self.root.mainloop()

    def open_registration(self):
        # Capturar una cara desde la cámara y luego abrir el formulario para registrar
        cap = cv2.VideoCapture(0)
        ret, frame = cap.read()
        cap.release()

        if ret:
            # Convertir imagen y descriptor para enviar al formulario
            # Aquí puedes usar tu función para obtener el descriptor facial
            from face_recognition import get_face_descriptor, detect_faces
            face_cascade = cv2.CascadeClassifier(cv2.data.haarcascades + 'haarcascade_frontalface_default.xml')
            faces = detect_faces(frame, face_cascade)

            if len(faces) == 0:
                tk.messagebox.showerror("Error", "No se detectó ningún rostro. Inténtalo de nuevo.")
                return

            x, y, w, h = faces[0]
            face_img = frame[y:y+h, x:x+w]

            descriptor = get_face_descriptor(face_img)

            # Cargar base de datos
            conn, c = connect_db()
            face_db = load_faces_from_db(c)

            # Mostrar formulario de registro
            show_registration_form(self.root, descriptor, face_img, face_db, c, conn)

        else:
            tk.messagebox.showerror("Error", "No se pudo acceder a la cámara.")

    def open_verification(self):
        self.root.destroy()
        root = tk.Tk()
        app = FaceRecognitionApp(root)
        root.mainloop()

if __name__ == "__main__":
    SelectionWindow()
