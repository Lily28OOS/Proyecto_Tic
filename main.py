# main.py
from fastapi import FastAPI, HTTPException, UploadFile, File, Form
from fastapi.middleware.cors import CORSMiddleware
import numpy as np
from io import BytesIO
from PIL import Image
import uvicorn
import threading

from face_recognition import extract_face_descriptor
from database import (
    connect_db,
    close_db,
    load_faces_from_db,
    get_person_by_cedula,
    save_face_descriptor
)

# ============================================================
# CONFIGURACIÓN GLOBAL
# ============================================================

THRESHOLD_RECOGNITION = 0.40   # estricto
THRESHOLD_REGISTER = 0.30      # más estricto

app = FastAPI(title="API Reconocimiento Facial - UTM")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Base facial en memoria
# Estructura: [(persona_id, cedula, embedding)]
face_db = []
face_db_lock = threading.Lock()

# ============================================================
# STARTUP / SHUTDOWN
# ============================================================

@app.on_event("startup")
async def startup():
    global face_db
    conn, c = None, None

    try:
        conn, c = connect_db()
        rows = load_faces_from_db(c)

        loaded = []
        for persona_id, cedula, emb in rows:
            if emb is not None:
                loaded.append((persona_id, cedula, emb))

        with face_db_lock:
            face_db = loaded

        print(f"[INFO] Rostros cargados en memoria: {len(face_db)}")

    except Exception as e:
        print(f"[ERROR] Error en startup: {e}")

    finally:
        close_db(conn, c)


@app.on_event("shutdown")
async def shutdown():
    print("[INFO] API detenida correctamente")

# ============================================================
# UTILIDADES BIOMÉTRICAS
# ============================================================

def compare_embeddings(e1, e2) -> float:
    return np.linalg.norm(e1 - e2)


def distance_to_confidence(dist: float, threshold: float) -> float:
    """
    Convierte distancia a una confianza aproximada (0-1)
    """
    score = max(0.0, 1.0 - (dist / threshold))
    return round(score, 3)

# ============================================================
# ENDPOINT: REGISTRO FACIAL
# ============================================================

@app.post("/register/")
async def register_face(
    cedula: str = Form(...),
    file: UploadFile = File(...)
):
    content = await file.read()

    try:
        img = Image.open(BytesIO(content)).convert("RGB")
        frame = np.array(img)[:, :, ::-1]  # RGB → BGR
    except Exception:
        raise HTTPException(status_code=400, detail="Imagen inválida")

    descriptor = extract_face_descriptor(frame)
    if descriptor is None:
        raise HTTPException(status_code=400, detail="No se pudo extraer rostro")

    # Verificar duplicados
    with face_db_lock:
        for _, _, existing in face_db:
            if compare_embeddings(existing, descriptor) < THRESHOLD_REGISTER:
                raise HTTPException(
                    status_code=409,
                    detail="Rostro ya registrado"
                )

    conn, c = None, None
    try:
        conn, c = connect_db()
        persona = get_person_by_cedula(c, cedula)

        if not persona:
            raise HTTPException(
                status_code=404,
                detail="Persona no encontrada en la base institucional"
            )

        ok = save_face_descriptor(c, conn, persona["id"], descriptor)
        if not ok:
            raise HTTPException(status_code=500, detail="Error al guardar descriptor")

        with face_db_lock:
            face_db.append((persona["id"], cedula, descriptor))

        return {
            "success": True,
            "persona_id": persona["id"],
            "cedula": cedula
        }

    finally:
        close_db(conn, c)

# ============================================================
# ENDPOINT: RECONOCIMIENTO FACIAL
# ============================================================

@app.post("/recognize/")
async def recognize_face(file: UploadFile = File(...)):
    content = await file.read()

    try:
        img = Image.open(BytesIO(content)).convert("RGB")
        frame = np.array(img)[:, :, ::-1]
    except Exception:
        raise HTTPException(status_code=400, detail="Imagen inválida")

    descriptor = extract_face_descriptor(frame)
    if descriptor is None:
        raise HTTPException(status_code=400, detail="No se detectó rostro")

    best_match = None
    best_dist = float("inf")

    with face_db_lock:
        for pid, cedula, existing in face_db:
            dist = compare_embeddings(existing, descriptor)
            if dist < best_dist:
                best_match = (pid, cedula)
                best_dist = dist

    if best_match is None or best_dist >= THRESHOLD_RECOGNITION:
        return {
            "recognized": False,
            "confidence": 0.0
        }

    confidence = distance_to_confidence(best_dist, THRESHOLD_RECOGNITION)

    conn, c = None, None
    try:
        conn, c = connect_db()
        c.execute(
            "SELECT nombre, apellido1 FROM personas WHERE cedula = %s AND activo = TRUE",
            (best_match[1],)
        )
        row = c.fetchone()

        return {
            "recognized": True,
            "cedula": best_match[1],
            "nombre": row["nombre"] if row else None,
            "apellido": row["apellido1"] if row else None,
            "distance": round(float(best_dist), 4),
            "confidence": confidence
        }

    finally:
        close_db(conn, c)

# ============================================================
# MAIN
# ============================================================

if __name__ == "__main__":
    uvicorn.run(
        "main:app",
        host="0.0.0.0",
        port=8000,
        reload=True
    )
