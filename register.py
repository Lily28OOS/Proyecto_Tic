# register.py
import cv2
import numpy as np
import tkinter as tk
from tkinter import messagebox
from PIL import Image, ImageTk
from face_recognition import detect_faces, get_face_descriptor

# Función para mostrar el formulario de registro de un nuevo rostro
def show_registration_form(root, descriptor, face_image, face_db, c, conn):
    if hasattr(root, 'registration_form_open') and root.registration_form_open:
        return  # Si la ventana ya está abierta, no hacer nada

    root.registration_form_open = True
    # Lista de sufijos de correo más comunes
    email_suffixes = [
        "@utm.edu.ec",
        "@gmail.com",
        "@yahoo.com",
        "@hotmail.com",
        "@outlook.com",
        "@aol.com"
    ]

    def save_data():
        nombre1 = entry_nombre1.get()
        nombre2 = entry_nombre2.get()
        apellido1 = entry_apellido1.get()
        apellido2 = entry_apellido2.get()
        cedula = entry_cedula.get()
        correo_prefijo = entry_correo_prefijo.get()
        correo_sufijo = email_suffix_var.get()  # Sufijo seleccionado

        correo_completo = correo_prefijo + correo_sufijo

        if nombre1 and apellido1 and cedula and correo_prefijo:
            descriptor_list = descriptor.tolist()

            c.execute("""
                INSERT INTO personas (cedula, nombre, nombre2, apellido1, apellido2, correo_electronico) 
                VALUES (%s, %s, %s, %s, %s, %s) RETURNING id
            """, (cedula, nombre1, nombre2, apellido1, apellido2, correo_completo))
            persona_id = c.fetchone()[0]

            c.execute("""
                INSERT INTO codificaciones_faciales (persona_id, codificacion) 
                VALUES (%s, %s)
            """, (persona_id, descriptor_list))
            conn.commit()
            top.destroy()
            root.registration_form_open = False

    def cancel():
        top.destroy()
        root.registration_form_open = False

    top = tk.Toplevel(root)
    top.title("Registrar nuevo rostro")

    tk.Label(top, text="Cédula").grid(row=0, column=0)
    tk.Label(top, text="Nombre 1").grid(row=1, column=0)
    tk.Label(top, text="Nombre 2").grid(row=2, column=0)
    tk.Label(top, text="Apellido 1").grid(row=3, column=0)
    tk.Label(top, text="Apellido 2").grid(row=4, column=0)
    tk.Label(top, text="Correo").grid(row=6, column=0)

    entry_cedula = tk.Entry(top)
    entry_nombre1 = tk.Entry(top)
    entry_nombre2 = tk.Entry(top)
    entry_apellido1 = tk.Entry(top)
    entry_apellido2 = tk.Entry(top)
    entry_correo_prefijo = tk.Entry(top)

    entry_cedula.grid(row=0, column=1)
    entry_nombre1.grid(row=1, column=1)
    entry_nombre2.grid(row=2, column=1)
    entry_apellido1.grid(row=3, column=1)
    entry_apellido2.grid(row=4, column=1)
    entry_correo_prefijo.grid(row=6, column=1)

    email_suffix_var = tk.StringVar()
    email_suffix_var.set("@utm.edu.ec")
    suffix_combobox = tk.OptionMenu(top, email_suffix_var, *email_suffixes)
    suffix_combobox.grid(row=6, column=2)

    face_rgb = cv2.cvtColor(face_image, cv2.COLOR_BGR2RGB)
    face_pil = Image.fromarray(cv2.resize(face_rgb, (160, 160)))
    face_photo = ImageTk.PhotoImage(face_pil)
    image_label = tk.Label(top, image=face_photo)
    image_label.image = face_photo
    image_label.grid(row=0, column=2, rowspan=6, padx=10, pady=10)

    tk.Button(top, text="Guardar", command=save_data).grid(row=7, column=1)
    tk.Button(top, text="Cancelar", command=cancel).grid(row=7, column=2)


class FaceCaptureForRegistration:
    def __init__(self, root, face_db, c, conn):
        self.root = root
        self.face_db = face_db
        self.c = c
        self.conn = conn
        self.cap = cv2.VideoCapture(0)
        self.canvas = tk.Canvas(root, width=640, height=480)
        self.canvas.pack()

        self.countdown_label = tk.Label(root, text="", font=("Arial", 18))
        self.countdown_label.pack(pady=10)

        self.countdown = 5  # segundos para capturar
        self.capturing = False

        self.update_frame()
        self.update_countdown()

    def update_frame(self):
        ret, frame = self.cap.read()
        if ret:
            frame = cv2.flip(frame, 1)

            overlay = frame.copy()

            center_x, center_y = frame.shape[1] // 2, frame.shape[0] // 2
            axes_length = (150, 200)
            color = (0, 255, 0)
            thickness = 2

            # Dibujar óvalo guía
            cv2.ellipse(overlay, (center_x, center_y), axes_length, 0, 0, 360, color, thickness)

            alpha = 0.3
            cv2.addWeighted(overlay, alpha, frame, 1 - alpha, 0, frame)

            frame_rgb = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
            img = Image.fromarray(frame_rgb)
            imgtk = ImageTk.PhotoImage(img)

            self.canvas.imgtk = imgtk
            self.canvas.create_image(0, 0, anchor=tk.NW, image=imgtk)

        if not self.capturing:
            self.root.after(15, self.update_frame)

    def update_countdown(self):
        if self.countdown > 0:
            self.countdown_label.config(text=f"Foto en {self.countdown} segundos. Mantente quieto dentro de la silueta.")
            self.countdown -= 1
            self.root.after(1000, self.update_countdown)
        else:
            self.countdown_label.config(text="Capturando...")
            self.capturing = True
            self.capture_image()

    def capture_image(self):
        ret, frame = self.cap.read()
        if not ret:
            messagebox.showerror("Error", "No se pudo acceder a la cámara.")
            self.cap.release()
            self.root.destroy()
            return

        frame = cv2.flip(frame, 1)

        faces = detect_faces(frame, cv2.CascadeClassifier(cv2.data.haarcascades + 'haarcascade_frontalface_default.xml'))

        if len(faces) == 0:
            messagebox.showwarning("Advertencia", "No se detectó ningún rostro. Intenta de nuevo.")
            self.capturing = False
            self.countdown = 5
            self.update_countdown()
            self.update_frame()
            return

        faces = sorted(faces, key=lambda f: f[2] * f[3], reverse=True)
        x, y, w, h = faces[0]
        face_img = frame[y:y + h, x:x + w]

        descriptor = get_face_descriptor(face_img)

        self.cap.release()
        self.root.destroy()

        root_form = tk.Tk()
        root_form.title("Formulario de Registro")
        show_registration_form(root_form, descriptor, face_img, self.face_db, self.c, self.conn)
        root_form.mainloop()


def start_face_capture_for_registration(root, face_db, c, conn):
    capture_win = tk.Toplevel(root)
    capture_win.title("Captura de rostro para registro")
    FaceCaptureForRegistration(capture_win, face_db, c, conn)
