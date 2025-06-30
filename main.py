# main.py
import tkinter as tk
from app import FaceRecognitionApp

# Crear la ventana principal de Tkinter
root = tk.Tk()
app = FaceRecognitionApp(root)
root.mainloop()
