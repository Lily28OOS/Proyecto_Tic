# Proyecto_Tic

## Descripción

Proyecto_Tic es una API web desarrollada con FastAPI para el registro y reconocimiento facial de personas. Permite registrar usuarios mediante el envío de una imagen y sus datos personales, y posteriormente reconocerlos a partir de una foto. Utiliza técnicas de reconocimiento facial con OpenCV y NumPy, y almacena la información en una base de datos.

## Características

- Registro de usuarios con foto y datos personales.
- Reconocimiento facial a partir de imágenes.
- API RESTful documentada automáticamente.
- Soporte para CORS.
- Base de datos para almacenar usuarios y descriptores faciales.
- Soporte para DeepFace, RetinaFace y Haarcascade para la detección y reconocimiento facial.

## Tecnologías utilizadas

- Python 3.8+
- FastAPI
- Uvicorn
- OpenCV
- NumPy
- Pillow
- PostgreSQL
- DeepFace
- RetinaFace
- Haarcascade (OpenCV)
- face_recognition (módulo propio o externo)
- Visual Studio Code

## Instalación

1. **Clona el repositorio:**
- git clone https://github.com/Lily28OOS/Proyecto_Tic.git cd Proyecto_Tic-master
2. **Crea un entorno virtual (opcional pero recomendado):**
- python -m venv venv venv\Scripts\activate
3. **Instala las dependencias:**
- pip install -r requirements.txt
4. **Configura la base de datos:**
- Edita el archivo `database.py` para poner tus credenciales y parámetros de conexión.
- Asegúrate de tener la base de datos y las tablas necesarias creadas.

## Uso

1. **Inicia el servidor:**
- python main.py
2. **Accede a la documentación interactiva:**
- [http://localhost:8000/docs](http://localhost:8000/docs) (Swagger UI)
- [http://localhost:8000/redoc](http://localhost:8000/redoc) (ReDoc)

3. **Prueba los endpoints:**
- `/register/` para registrar un usuario (requiere imagen y datos).
- `/recognize/` para reconocer un usuario a partir de una imagen.

4. **Interfaz HTML (opcional):**
- Abre el archivo `test.html` en tu navegador para probar la API desde un formulario web.

## Estructura del proyecto
Proyecto_Tic-master/ 
│ 
├── main.py # Archivo principal de la API 
├── database.py # Conexión y funciones de base de datos 
├── face_recognition.py # Funciones de reconocimiento facial 
├── test.py # Interfaz de prueba (opcional) 
├── requirements.txt # Dependencias del proyecto 
└── README.md

## Notas

- Asegúrate de tener instaladas las dependencias y la base de datos configurada antes de ejecutar el proyecto.
- Puedes modificar los umbrales de reconocimiento facial en `main.py` según tus necesidades.
- Si tienes problemas con las dependencias, revisa la versión de Python y los paquetes instalados.

## Créditos

Desarrollado por Delgado Benavides y Farias Palma.  
Basado en FastAPI y tecnologías de código abierto.

## Licencia

Este proyecto está bajo la licencia .