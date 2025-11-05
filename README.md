# Proyecto_Tic

## Descripción
API web (FastAPI) para registro y reconocimiento facial. Permite sincronizar usuarios desde una API externa (por idPersonal), guardar la metadata recibida, registrar descriptores faciales y reconocer personas por imagen.

## Características
- Sincronización desde API externa (buscar por idPersonal) y guardado de metadata.
- Registro de usuarios y descriptores faciales (tabla `codificaciones_faciales`).
- Reconocimiento facial usando DeepFace / RetinaFace / Haarcascade (según configuración).
- Documentación automática (Swagger / ReDoc).
- Soporte CORS básico.
- Base de datos PostgreSQL con tablas creadas automáticamente.

## Requisitos previos (importante)
1. Instalar CMake (requisito para algunas dependencias nativas):
   - Descarga: https://cmake.org/download/
   - En Windows con Chocolatey (PowerShell como administrador):  
     choco install cmake -y
   - Asegúrate de que `cmake` esté en el PATH antes de instalar dependencias Python.

2. Tener PostgreSQL accesible y crear la base de datos (por ejemplo `biometria`) o ajustar variables de entorno para tu DB.

## Tecnologías
- Python 3.8+
- FastAPI, Uvicorn
- OpenCV, NumPy, Pillow
- PostgreSQL (psycopg2)
- DeepFace / RetinaFace / Haarcascade (según uso)
- Módulo local `face_recognition.py`

## Instalación (Windows)
1. Clonar repositorio:
   - git clone https://github.com/Lily28OOS/Proyecto_Tic.git
   - cd Proyecto_Tic-master

2. Crear y activar entorno virtual:
   - python -m venv .venv
   - .venv\Scripts\activate

3. Instalar dependencias:
   - pip install -r requirements.txt

4. Configurar conexión a la BD (opcional por variables de entorno):
   - DB_NAME, DB_USER, DB_PASS, DB_HOST, DB_PORT, DB_POOL_MIN, DB_POOL_MAX
   - Ejemplo (PowerShell):
     $env:DB_NAME="biometria"; $env:DB_USER="postgres"; $env:DB_PASS="admin"; $env:DB_HOST="localhost"; $env:DB_PORT="5433"

5. Ejecutar la aplicación (inicializará tablas si es necesario):
   - uvicorn main:app --reload
   - o: python main.py

## Uso (endpoints principales)
- Sincronizar usuario desde API externa (recibe idPersonal):
  - POST /sync_user/ form-data: idpersonal=81427
  - Ejemplo curl (PowerShell):
    curl -X POST "http://localhost:8000/sync_user/" -F "idpersonal=81427"

- Registrar descriptor facial (upload imagen + cedula):
  - POST /register/ form-data: cedula=01020304, file=@foto.jpg
  - Ejemplo:
    curl -X POST "http://localhost:8000/register/" -F "cedula=01020304" -F "file=@C:\ruta\foto.jpg"

- Reconocer rostro:
  - POST /recognize/ form-data: file=@foto.jpg
  - Ejemplo:
    curl -X POST "http://localhost:8000/recognize/" -F "file=@C:\ruta\foto.jpg"

- Documentación:
  - http://localhost:8000/docs
  - http://localhost:8000/redoc

## Estructura del proyecto
Proyecto_Tic
├── .venv
├── app.py
├── database.py
├── face_recognition.py
├── main.py         # entrypoint principal (FastAPI)
├── register.py
├── README.md
├── requirements.txt
└── ...

## Notas importantes
- El campo `idPersonal` de la API externa no es la cédula; la API externa debe devolver la `cedula` en la respuesta para crear la persona local. El flujo es: sync (/sync_user) por idPersonal → guarda metadata y `cedula` → luego register/recognize usan la `cedula` local.
- Asegúrate de que las funciones detect_faces() y get_face_descriptor() en `face_recognition.py` devuelvan formatos compatibles (listas o numpy arrays).
- En producción revisa CORS y límites de subida de archivos, y configura el pool de conexiones según la carga.

## Créditos
Delgado Benavides y Farias Palma.

## Licencia
MIT