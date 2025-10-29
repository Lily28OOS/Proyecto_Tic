# main.py
from fastapi import FastAPI, HTTPException, UploadFile, File, Form
from fastapi.middleware.cors import CORSMiddleware
import numpy as np
import cv2
import requests
from io import BytesIO
from PIL import Image
from face_recognition import detect_faces, get_face_descriptor
from database import connect_db, load_faces_from_db
import uvicorn
import re

# --- Lógica de Registro --- #
class FaceRegistrar:
    def __init__(self, cursor, conn, face_db):
        self.c = cursor
        self.conn = conn
        self.face_db = face_db

    def register(self, cedula, descriptor):
        # Buscar usuario existente
        self.c.execute("SELECT id FROM personas WHERE cedula = %s", (cedula,))
        row = self.c.fetchone()
        if not row:
            return False, "Usuario no encontrado. Primero sincronice con la API externa."

        persona_id = row[0]

        # Verificar si el rostro ya está registrado
        for _, existing_descriptor in self.face_db:
            distance = np.linalg.norm(existing_descriptor - descriptor)
            if distance < 0.9:
                return False, "Este rostro ya está registrado."

        try:
            # Insertar codificación facial
            descriptor_list = descriptor.tolist()
            self.c.execute("""
                INSERT INTO codificaciones_faciales (persona_id, codificacion)
                VALUES (%s, %s)
            """, (persona_id, descriptor_list))

            # Actualizar activo = TRUE al vincular rostro
            self.c.execute("UPDATE personas SET activo = TRUE WHERE id = %s", (persona_id,))
            self.conn.commit()

            # Agregar a la base de datos en memoria
            self.c.execute("SELECT nombre, nombre2, apellido1, apellido2, cedula FROM personas WHERE id = %s", (persona_id,))
            nombre1, nombre2, apellido1, apellido2, cedula_db = self.c.fetchone()
            full_name = f"{nombre1} {apellido1} ({cedula_db})"
            self.face_db.append((full_name, self.normalize(descriptor)))

            return True, "Rostro registrado y usuario activado correctamente."
        except Exception as e:
            self.conn.rollback()
            return False, f"Error al registrar rostro: {e}"

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

# --- Endpoints --- #

@app.post("/sync_user/")
async def sync_user(cedula: str = Form(...)):
    api_url = "http://172.16.226.42:3000/administracion/usuario/v1/buscar_por_cedula"
    payload = {"cedula": cedula}

    try:
        response = requests.post(api_url, json=payload)
        response.raise_for_status()
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error al conectar con API externa: {e}")

    data = response.json()
    if not data.get("p_status") or not data.get("p_data", {}).get("p_usuarios"):
        raise HTTPException(status_code=404, detail="Usuario no encontrado en API externa")

    usuario = data["p_data"]["p_usuarios"][0]

    # Separar nombre completo en apellidos y nombres
    partes = usuario["persona"].split()
    apellido1 = partes[0] if len(partes) > 0 else ""
    apellido2 = partes[1] if len(partes) > 1 else ""
    nombre1 = partes[2] if len(partes) > 2 else ""
    nombre2 = " ".join(partes[3:]) if len(partes) > 3 else ""

    # Verificar si ya existe
    c.execute("SELECT id FROM personas WHERE cedula = %s", (usuario["cedula"],))
    row = c.fetchone()
    if row:
        return {"message": "Usuario ya existe en la base de datos", "id": row[0]}

    # Insertar en la DB local con activo = FALSE
    try:
        c.execute("""
            INSERT INTO personas (cedula, nombre, nombre2, apellido1, apellido2, activo)
            VALUES (%s, %s, %s, %s, %s, FALSE) RETURNING id
        """, (
            usuario["cedula"], nombre1, nombre2, apellido1, apellido2
        ))
        persona_id = c.fetchone()[0]
        conn.commit()
    except Exception as e:
        conn.rollback()
        raise HTTPException(status_code=500, detail=f"Error al guardar usuario en DB: {e}")

    return {
        "message": "Usuario sincronizado correctamente",
        "persona_id": persona_id,
        "cedula": usuario["cedula"],
        "nombre1": nombre1,
        "nombre2": nombre2,
        "apellido1": apellido1,
        "apellido2": apellido2,
        "activo": False
    }

@app.post("/register/")
async def register_face(cedula: str = Form(...), file: UploadFile = File(...)):
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

    if descriptor is None:
        raise HTTPException(status_code=400, detail="No se pudo obtener el descriptor del rostro.")

    success, message = face_registrar.register(cedula, descriptor)
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

    if descriptor is None:
        raise HTTPException(status_code=400, detail="No se pudo obtener el descriptor del rostro.")

    name, distance = face_recognizer.recognize(descriptor)
    if not name:
        return {"recognized": False, "message": "Rostro no reconocido."}

    match = re.search(r'\((\d+)\)', name)
    cedula_recognized = match.group(1) if match else None

    c.execute("""
        SELECT nombre, nombre2, apellido1, apellido2, cedula
        FROM personas
        WHERE cedula = %s AND activo = TRUE
    """, (cedula_recognized,))
    row = c.fetchone()

    if not row:
        return {
            "recognized": True,
            "name": name,
            "cedula": cedula_recognized,
            "distance": float(distance),
            "message": "Rostro reconocido pero no hay datos completos o activo en DB"
        }

    nombre1, nombre2, apellido1, apellido2, cedula_db = row

    return {
        "recognized": True,
        "cedula": cedula_db,
        "nombre1": nombre1,
        "nombre2": nombre2,
        "apellido1": apellido1,
        "apellido2": apellido2,
        "distance": float(distance)
    }

if __name__ == "__main__":
    uvicorn.run("main:app", host="0.0.0.0", port=8000, reload=True)
