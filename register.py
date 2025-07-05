# register.py
import cv2
import numpy as np
import tkinter as tk
from tkinter import messagebox
from PIL import Image, ImageTk
from face_recognition import detect_faces, get_face_descriptor


def show_registration_form(root, descriptor, face_image, face_db, c, conn):
    if hasattr(root, 'registration_form_open') and root.registration_form_open:
        return

    root.registration_form_open = True

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
        correo_sufijo = email_suffix_var.get()
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
