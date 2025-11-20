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
import json
import re
import hnswlib
import os

# --- Helpers mínimos (español) --- #
def _get_id_from_row(row):
    if not row:
        return None
    if isinstance(row, dict):
        return row.get("id")
    try:
        return row[0]
    except Exception:
        return None

def _person_fields_from_row(row):
    if not row:
        return (None, None, None, None, None)
    if isinstance(row, dict):
        return (row.get("nombre"), row.get("nombre2"), row.get("apellido1"), row.get("apellido2"), row.get("cedula"))
    vals = list(row)
    vals += [None] * (5 - len(vals))
    return tuple(vals[:5])

# --- Registro y reconocimiento mínimos --- #
THRESHOLD = 0.75

class FaceRegistrar:
    def __init__(self, cursor, conn, face_db):
        self.c = cursor
        self.conn = conn
        self.face_db = face_db

    def _normalize(self, v):
        a = np.array(v, dtype=float)
        n = np.linalg.norm(a)
        return a / n if n > 0 else a

    def register(self, cedula, descriptor):
        self.c.execute("SELECT id FROM personas WHERE cedula = %s", (cedula,))
        persona_id = _get_id_from_row(self.c.fetchone())
        if not persona_id:
            return False, "Usuario no encontrado (sincronice primero)."

        desc = self._normalize(descriptor)
        for _, existing in self.face_db:
            try:
                if np.linalg.norm(existing - desc) < THRESHOLD:
                    return False, "Rostro ya registrado."
            except Exception:
                continue

        try:
            self.c.execute(
                "INSERT INTO codificaciones_faciales (persona_id, codificacion) VALUES (%s, %s)",
                (persona_id, desc.tolist()),
            )
            self.c.execute("UPDATE personas SET activo = TRUE WHERE id = %s", (persona_id,))
            self.conn.commit()
            # actualizar memoria
            self.c.execute("SELECT nombre, nombre2, apellido1, apellido2, cedula FROM personas WHERE id = %s", (persona_id,))
            info = self.c.fetchone()
            nombre1, _, apellido1, _, cedula_db = _person_fields_from_row(info)
            display = f"{nombre1 or ''} {apellido1 or ''} ({cedula_db or ''})".strip()
            self.face_db.append((display, desc))
            return True, {"persona_id": persona_id}
        except Exception as e:
            self.conn.rollback()
            return False, f"Error al guardar descriptor: {e}"

class FaceRecognizer:
    def __init__(self, face_db):
        normalized = []
        for name, desc in face_db:
            a = np.array(desc, dtype=float)
            n = np.linalg.norm(a)
            if n > 0:
                a = a / n
            normalized.append((name, a))
        self.face_db = normalized

    def recognize(self, descriptor):
        d = np.array(descriptor, dtype=float)
        n = np.linalg.norm(d)
        if n > 0:
            d = d / n
        best, best_dist = None, float("inf")
        for name, existing in self.face_db:
            try:
                dist = np.linalg.norm(existing - d)
            except Exception:
                continue
            if dist < best_dist:
                best, best_dist = name, dist
        if best is not None and best_dist < THRESHOLD:
            return best, float(best_dist)
        return None, None

# ANN (hnswlib) - integración mínima en este archivo
ANN_INDEX_PATH = "face_index.bin"
ann = None
_ann_next_id = 0

# --- App --- #
app = FastAPI(title="Face Recognition API")
app.add_middleware(CORSMiddleware, allow_origins=["*"], allow_credentials=True, allow_methods=["*"], allow_headers=["*"])

conn, c = None, None
face_db = []
face_registrar = None
face_recognizer = None

@app.on_event("startup")
async def startup():
    global conn, c, face_db, face_registrar, face_recognizer
    conn, c = connect_db()
    raw = load_faces_from_db(c)  # [(name, descriptor), ...]
    cleaned = []
    for name, desc in raw:
        try:
            a = np.array(desc, dtype=float)
            n = np.linalg.norm(a)
            if n > 0:
                a = a / n
            cleaned.append((name, a))
        except Exception:
            continue
    face_db = cleaned
    face_registrar = FaceRegistrar(c, conn, face_db)
    face_recognizer = FaceRecognizer(face_db)
    global ann, _ann_next_id
    # detectar dimensión del embedding (fallback 512)
    dim = 512
    if face_db and len(face_db[0]) > 1:
        try:
            dim = int(face_db[0][1].shape[0])
        except Exception:
            dim = 512
    try:
        ann = hnswlib.Index(space='l2', dim=dim)
        if os.path.exists(ANN_INDEX_PATH):
            ann.load_index(ANN_INDEX_PATH)
            ann.set_ef(50)
            _ann_next_id = ann.get_current_count()
        else:
            max_elements = max(1000, len(face_db) * 2)
            ann.init_index(max_elements=max_elements, ef_construction=200, M=48)
            if face_db:
                ids = list(range(len(face_db)))
                vecs = [np.array(v, dtype=np.float32) for _, v in face_db]
                ann.add_items(np.vstack(vecs), ids)
                ann.set_ef(50)
                try:
                    ann.save_index(ANN_INDEX_PATH)
                except Exception:
                    pass
            _ann_next_id = ann.get_current_count()
    except Exception:
        ann = None
        _ann_next_id = len(face_db)

@app.on_event("shutdown")
async def shutdown():
    global conn, c
    try:
        if c: c.close()
    except Exception:
        pass
    try:
        if conn: conn.close()
    except Exception:
        pass

@app.post("/sync_user/")
async def sync_user(idpersonal: str = Form(...)):
    api_url = "http://localhost:3000/administracion/usuario/v1/buscar_por_idpersonal"
    try:
        r = requests.post(api_url, json={"idPersonal": idpersonal}, timeout=10)
        r.raise_for_status()
        data = r.json()
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error al llamar API externa: {e}")

    usuarios = data.get("p_data", {}).get("p_usuarios") or []
    if not usuarios:
        raise HTTPException(status_code=404, detail="Usuario no encontrado en API externa")
    usuario = usuarios[0]
    cedula = usuario.get("cedula")
    if not cedula:
        raise HTTPException(status_code=400, detail="La respuesta no contiene 'cedula'")

    # extraer nombres simples
    nombres = usuario.get("nombres") or ""
    apellidos = usuario.get("apellidos") or ""
    n1 = nombres.split()[0] if nombres else ""
    n2 = " ".join(nombres.split()[1:]) if len(nombres.split()) > 1 else ""
    a1 = apellidos.split()[0] if apellidos else ""
    a2 = " ".join(apellidos.split()[1:]) if len(apellidos.split()) > 1 else ""

    c.execute("SELECT id FROM personas WHERE cedula = %s", (cedula,))
    if _get_id_from_row(c.fetchone()):
        # actualizar metadata si existe
        try:
            c.execute("INSERT INTO persona_metadata (persona_id, metadata) VALUES (%s, %s) ON CONFLICT (persona_id) DO UPDATE SET metadata = EXCLUDED.metadata", (_get_id_from_row(c.fetchone()), json.dumps(usuario, ensure_ascii=False)))
            conn.commit()
        except Exception:
            conn.rollback()
        return {"message": "Usuario ya existe"}

    try:
        c.execute("INSERT INTO personas (cedula, nombre, nombre2, apellido1, apellido2, activo) VALUES (%s,%s,%s,%s,%s,FALSE) RETURNING id", (cedula, n1, n2, a1, a2))
        new_id = _get_id_from_row(c.fetchone())
        if not new_id:
            c.execute("SELECT id FROM personas WHERE cedula = %s", (cedula,))
            new_id = _get_id_from_row(c.fetchone())
        try:
            c.execute("INSERT INTO persona_metadata (persona_id, metadata) VALUES (%s, %s) ON CONFLICT (persona_id) DO UPDATE SET metadata = EXCLUDED.metadata", (new_id, json.dumps(usuario, ensure_ascii=False)))
        except Exception:
            conn.rollback()
        conn.commit()
    except Exception as e:
        conn.rollback()
        raise HTTPException(status_code=500, detail=f"Error guardando en DB: {e}")

    return {"message": "Sincronizado", "persona_id": new_id, "cedula": cedula}

@app.post("/register/")
async def register_face(cedula: str = Form(...), file: UploadFile = File(...)):
    if not face_registrar:
        raise HTTPException(status_code=500, detail="Servicio no inicializado")
    content = await file.read()
    try:
        img = Image.open(BytesIO(content)).convert("RGB")
        img_np = np.array(img)[:, :, ::-1]  # RGB -> BGR
    except Exception:
        raise HTTPException(status_code=400, detail="Imagen inválida")
    faces = detect_faces(img_np)
    if not faces:
        raise HTTPException(status_code=400, detail="No se detectó rostro")
    x, y, w, h = faces[0]
    face_img = img_np[y:y+h, x:x+w]
    desc = get_face_descriptor(face_img)
    if desc is None:
        raise HTTPException(status_code=500, detail="No se pudo calcular descriptor")
    success, payload = face_registrar.register(cedula, desc)
    if not success:
        raise HTTPException(status_code=400, detail=payload)
    return payload

@app.post("/recognize/")
async def recognize_face(file: UploadFile = File(...)):
    if not face_recognizer:
        raise HTTPException(status_code=500, detail="Servicio no inicializado")
    content = await file.read()
    try:
        img = Image.open(BytesIO(content)).convert("RGB")
        img_np = np.array(img)[:, :, ::-1]
    except Exception:
        raise HTTPException(status_code=400, detail="Imagen inválida")
    faces = detect_faces(img_np)
    if not faces:
        raise HTTPException(status_code=400, detail="No se detectó rostro")
    x, y, w, h = faces[0]
    face_img = img_np[y:y+h, x:x+w]
    desc = get_face_descriptor(face_img)
    if desc is None:
        raise HTTPException(status_code=500, detail="No se pudo calcular descriptor")
    name, dist = face_recognizer.recognize(desc)
    if not name:
        return {"recognized": False}
    m = re.search(r"\((\d+)\)", name)
    ced = m.group(1) if m else None
    c.execute("SELECT nombre, nombre2, apellido1, apellido2, cedula FROM personas WHERE cedula = %s AND activo = TRUE", (ced,))
    info = c.fetchone()
    if not _get_id_from_row(info) and not ced:
        return {"recognized": True, "name": name, "distance": float(dist)}
    n1, n2, a1, a2, ced_db = _person_fields_from_row(info)
    return {"recognized": True, "cedula": ced_db, "nombre1": n1, "apellido1": a1, "distance": float(dist)}

if __name__ == "__main__":
    uvicorn.run("main:app", host="0.0.0.0", port=8000, reload=True)
