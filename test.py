# test.py
import http.server
import socketserver
import socket

# --- HTML embebido para pruebas ---
HTML_PAGE = """<!DOCTYPE html>
<html lang="es">
<head>
  <meta charset="UTF-8">
  <title>Pruebas de Reconocimiento Facial</title>
  <style>
    video, canvas { border: 1px solid black; display: block; margin-bottom: 10px; }
    button { margin-right: 10px; margin-bottom: 10px; }
    input { margin-bottom: 10px; }
  </style>
</head>
<body>
  <h1>Pruebas de Reconocimiento Facial</h1>
  <input id="cedulaInput" type="text" placeholder="Ingrese cédula para acceso" />
  <video id="video" width="640" height="480" autoplay></video>
  <canvas id="canvas" width="640" height="480" style="display:none;"></canvas>
  <div>
    <button id="registerBtn">Registrar Rostro</button>
    <button id="recognizeBtn">Reconocimiento General</button>
    <button id="accessBtn">Verificar Acceso por Cédula</button>
    <button id="stopBtn">Detener Cámara</button>
  </div>
  <pre id="responseBox"></pre>

  <script>
    const video = document.getElementById('video');
    const canvas = document.getElementById('canvas');
    const registerBtn = document.getElementById('registerBtn');
    const recognizeBtn = document.getElementById('recognizeBtn');
    const accessBtn = document.getElementById('accessBtn');
    const stopBtn = document.getElementById('stopBtn');
    const responseBox = document.getElementById('responseBox');
    const cedulaInput = document.getElementById('cedulaInput');
    let stream;

    async function startCamera() {
      if (!stream) {
        try {
          stream = await navigator.mediaDevices.getUserMedia({ video: true });
          video.srcObject = stream;
        } catch (err) {
          alert('No se pudo acceder a la cámara: ' + err);
        }
      }
    }

    async function captureImage() {
      const ctx = canvas.getContext('2d');
      ctx.drawImage(video, 0, 0, canvas.width, canvas.height);
      return new Promise(resolve => {
        canvas.toBlob(blob => resolve(blob), 'image/jpeg');
      });
    }

    async function postImage(url, blob, extraData={}) {
      const formData = new FormData();
      formData.append('file', blob, 'frame.jpg');
      for (const key in extraData) formData.append(key, extraData[key]);
      try {
        const response = await fetch(url, { method: 'POST', body: formData });
        const result = await response.json();
        responseBox.textContent = JSON.stringify(result, null, 2);
      } catch (error) {
        responseBox.textContent = 'Error: ' + error;
      }
    }

    registerBtn.onclick = async () => {
      await startCamera();
      const blob = await captureImage();
      // Datos de prueba para registro
      await postImage('http://localhost:8000/register/', blob, {
        cedula: '123456',
        nombre1: 'Prueba',
        nombre2: '',
        apellido1: 'Usuario',
        apellido2: '',
        correo_prefijo: 'test',
        correo_sufijo: '@mail.com'
      });
    };

    recognizeBtn.onclick = async () => {
      await startCamera();
      const blob = await captureImage();
      await postImage('http://localhost:8000/recognize/', blob);
    };

    accessBtn.onclick = async () => {
      const cedulaIngresada = cedulaInput.value.trim();
      if (!cedulaIngresada) { 
        alert('Ingrese la cédula'); 
        return; 
      }

      await startCamera();
      const blob = await captureImage();
      const formData = new FormData();
      formData.append('file', blob);

      try {
        const response = await fetch('http://localhost:8000/recognize/', { method: 'POST', body: formData });
        const result = await response.json();

        if (result.recognized) {
          if (cedulaIngresada === result.cedula) { 
            responseBox.textContent = '✅ Acceso permitido para ' + result.nombre1 + ' ' + result.apellido1;
          } else {
            responseBox.textContent = '❌ Cédula no coincide con el rostro detectado';
          }
        } else {
          responseBox.textContent = '❌ Rostro no reconocido';
        }
      } catch (error) {
        responseBox.textContent = 'Error: ' + error;
      }
    };

    stopBtn.onclick = () => {
      if (stream) {
        stream.getTracks().forEach(track => track.stop());
        video.srcObject = null;
        stream = null;
      }
    };
  </script>
</body>
</html>
"""

# --- Servidor HTTP para servir la página desde memoria ---
class CustomHandler(http.server.SimpleHTTPRequestHandler):
    def do_GET(self):
        if self.path in ("/", "/index.html"):
            body = HTML_PAGE.encode("utf-8")
            self.send_response(200)
            self.send_header("Content-type", "text/html; charset=utf-8")
            self.send_header("Content-length", str(len(body)))
            self.end_headers()
            self.wfile.write(body)
        else:
            self.send_error(404, "Archivo no encontrado")

def get_local_ip():
    """Obtiene la IP local de la máquina"""
    s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    try:
        s.connect(("8.8.8.8", 80))
        ip = s.getsockname()[0]
    finally:
        s.close()
    return ip

def run_http_server():
    PORT = 8080
    HOST = "0.0.0.0"
    with socketserver.TCPServer((HOST, PORT), CustomHandler) as httpd:
        print(f"Servidor web corriendo en:")
        print(f"  ➜ Localhost:      http://localhost:{PORT}")
        print(f"  ➜ Desde la red:   http://{get_local_ip()}:{PORT}")
        print(f"\nAsegúrate que tu FastAPI esté corriendo en http://localhost:8000")
        print("Presiona Ctrl+C para detener.")
        try:
            httpd.serve_forever()
        except KeyboardInterrupt:
            print("\nServidor detenido.")

if __name__ == "__main__":
    run_http_server()
