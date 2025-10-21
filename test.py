# Antes de ejecutar el test, asegúrate de que el servidor FastAPI esté corriendo.
# debes ejecutar primero: python main.py
# Luego, en otra terminal, ejecuta este script de prueba.

import cv2
import requests

API_URL = "http://localhost:8000/recognize/"

cap = cv2.VideoCapture(0)

while True:
    ret, frame = cap.read()
    if not ret:
        break

    # Mostrar la imagen en tiempo real
    cv2.imshow('Presiona Q para salir', frame)

    # Enviar frame cada cierto tiempo o con una tecla
    key = cv2.waitKey(1)
    if key == ord('s'):  # Presiona 's' para enviar imagen
        _, img_encoded = cv2.imencode('.jpg', frame)
        files = {'file': ('frame.jpg', img_encoded.tobytes(), 'image/jpeg')}
        response = requests.post(API_URL, files=files)
        print(response.json())

    elif key == ord('q'):
        break

cap.release()
cv2.destroyAllWindows()
