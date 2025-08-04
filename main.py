# main.py
from fastapi import FastAPI, HTTPException, UploadFile, File, Form
from fastapi.middleware.cors import CORSMiddleware
import numpy as np
import cv2
from io import BytesIO
from PIL import Image
from face_recognition import detect_faces, get_face_descriptor
from database import connect_db, load_faces_from_db
import uvicorn

# --- Lógica de Registro --- #
class FaceRegistrar:
    def __init__(self, cursor, conn, face_db):
        self.c = cursor
        self.conn = conn
        self.face_db = face_db

    def register(self, cedula, nombre1, nombre2, apellido1, apellido2, correo_prefijo, correo_sufijo, descriptor):
        correo = correo_prefijo + correo_sufijo
        for _, existing_descriptor in self.face_db:
            distance = np.linalg.norm(existing_descriptor - descriptor)
            if distance < 0.9:
                return False, "Este rostro ya está registrado."

        try:
            self.c.execute("""
                INSERT INTO personas (cedula, nombre, nombre2, apellido1, apellido2, correo_electronico)
                VALUES (%s, %s, %s, %s, %s, %s) RETURNING id
            """, (cedula, nombre1, nombre2, apellido1, apellido2, correo))
            persona_id = self.c.fetchone()[0]

            descriptor_list = descriptor.tolist()
            self.c.execute("""
                INSERT INTO codificaciones_faciales (persona_id, codificacion)
                VALUES (%s, %s)
            """, (persona_id, descriptor_list))
            self.conn.commit()

            full_name = f"{nombre1} {apellido1}"
            self.face_db.append((full_name, self.normalize(descriptor)))
            return True, "Rostro registrado exitosamente."
        except Exception as e:
            return False, f"Error al registrar: {e}"

    def normalize(self, v):
        norm = np.linalg.norm(v)
        return v / norm if norm > 0 else v

# --- Lógica de Reconocimiento --- #
class FaceRecognizer:
    def __init__(self, face_db):
        self.face_db = [(name, self.normalize(desc)) for name, desc in face_db]

    def normalize(self, v):
        norm = np.linalg.norm(v)
        return v / norm if norm > 0 else v

    def recognize(self, descriptor):
        descriptor = self.normalize(descriptor)
        recognized_name = None
        min_distance = float("inf")

        for full_name, saved_descriptor in self.face_db:
            distance = np.linalg.norm(saved_descriptor - descriptor)
            if distance < min_distance:
                min_distance = distance
                recognized_name = full_name

        if min_distance < 0.75:
            return recognized_name, min_distance
        return None, None

# --- FastAPI App --- #
app = FastAPI(title="Face Recognition API")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Conexión y carga inicial
conn, c = connect_db()
face_db = load_faces_from_db(c)

face_registrar = FaceRegistrar(c, conn, face_db)
face_recognizer = FaceRecognizer(face_db)

@app.post("/register/")
async def register_face(
    cedula: str = Form(...),
    nombre1: str = Form(...),
    nombre2: str = Form(""),
    apellido1: str = Form(...),
    apellido2: str = Form(""),
    correo_prefijo: str = Form(...),
    correo_sufijo: str = Form(...),
    file: UploadFile = File(...)
):
    contents = await file.read()
    image = Image.open(BytesIO(contents)).convert("RGB")
    frame = np.array(image)
    frame = cv2.cvtColor(frame, cv2.COLOR_RGB2BGR)

    faces = detect_faces(frame)
    if not faces:
        raise HTTPException(status_code=400, detail="No se detectó ningún rostro en la imagen.")

    x, y, w, h = faces[0]
    face_img = frame[y:y+h, x:x+w]

    descriptor = get_face_descriptor(face_img)

    success, message = face_registrar.register(
        cedula, nombre1, nombre2, apellido1, apellido2,
        correo_prefijo, correo_sufijo, descriptor
    )
    if not success:
        raise HTTPException(status_code=400, detail=message)

    return {"message": message}

@app.post("/recognize/")
async def recognize_face(file: UploadFile = File(...)):
    contents = await file.read()
    image = Image.open(BytesIO(contents)).convert("RGB")
    frame = np.array(image)
    frame = cv2.cvtColor(frame, cv2.COLOR_RGB2BGR)

    faces = detect_faces(frame)
    if not faces:
        raise HTTPException(status_code=400, detail="No se detectó ningún rostro en la imagen.")

    x, y, w, h = faces[0]
    face_img = frame[y:y+h, x:x+w]

    descriptor = get_face_descriptor(face_img)
    name, distance = face_recognizer.recognize(descriptor)

    if name:
        return {"recognized": True, "name": name, "distance": distance}
    return {"recognized": False, "message": "Rostro no reconocido."}

if __name__ == "__main__":
    uvicorn.run("main:app", host="0.0.0.0", port=8000, reload=True)

