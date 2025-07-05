# seleccion.py
import tkinter as tk
from app import FaceRecognitionApp

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
        self.root.destroy()
        root = tk.Tk()
        app = FaceRecognitionApp(root, registration_mode=True)
        root.mainloop()

    def open_verification(self):
        self.root.destroy()
        root = tk.Tk()
        app = FaceRecognitionApp(root, registration_mode=False)
        root.mainloop()

if __name__ == "__main__":
    SelectionWindow()
