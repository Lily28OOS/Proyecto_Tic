# test.py
import http.server
import socketserver
import socket

# ============================================================
# CONFIGURACIÓN
# ============================================================
API_BASE = "http://localhost:8000"   # FastAPI
VIDEO_WIDTH = 720
VIDEO_HEIGHT = 650
PORT = 8080                         #  HTML

# ============================================================
# HTML DE PRUEBAS
# ============================================================
HTML_PAGE = f"""<!DOCTYPE html>
<html lang="es">
<head>
  <meta charset="UTF-8">
  <title>Pruebas de Reconocimiento Facial</title>
  <style>
    body {{ font-family: Arial, sans-serif; }}
    video, canvas {{ border: 1px solid #333; display: block; margin-bottom: 10px; }}
    button {{ margin-right: 10px; margin-bottom: 10px; padding: 8px 12px; }}
    input {{ margin-bottom: 10px; padding: 6px; width: 260px; }}
    pre {{ background: #f4f4f4; padding: 10px; min-height: 120px; }}
  </style>
</head>
<body>

<h1>Pruebas de Reconocimiento Facial</h1>

<input id="cedulaInput" type="text" placeholder="Ingrese cédula registrada" />

<video id="video" width="{VIDEO_WIDTH}" height="{VIDEO_HEIGHT}" autoplay></video>
<canvas id="canvas" width="{VIDEO_WIDTH}" height="{VIDEO_HEIGHT}" style="display:none;"></canvas>

<div>
  <button id="cameraBtn">Activar Cámara</button>
  <button id="mirrorBtn">Modo Espejo: OFF</button>
</div>

<div>
  <button id="registerBtn">Registrar Rostro</button>
  <button id="recognizeBtn">Reconocer Rostro</button>
  <button id="accessBtn">Verificar Acceso</button>
  <button id="realtimeBtn">Reconocimiento en Tiempo Real</button>
</div>

<pre id="responseBox">Esperando acción...</pre>

<script>
const API_BASE = "{API_BASE}";
const video = document.getElementById("video");
const canvas = document.getElementById("canvas");
const ctx = canvas.getContext("2d");
const responseBox = document.getElementById("responseBox");
const cedulaInput = document.getElementById("cedulaInput");
const cameraBtn = document.getElementById("cameraBtn");

let stream = null;
let mirrorMode = false;
let realtimeActive = false;
let realtimeInterval = null;
let startTime = 0;

// ============================================================
// CÁMARA
// ============================================================
async function startCamera() {{
  if (!stream) {{
    try {{
      stream = await navigator.mediaDevices.getUserMedia({{ video: true }});
      video.srcObject = stream;
      cameraBtn.textContent = "Detener Cámara";
    }} catch (err) {{
      alert("No se pudo acceder a la cámara");
    }}
  }}
}}

function stopCamera() {{
  if (stream) {{
    stream.getTracks().forEach(t => t.stop());
    video.srcObject = null;
    stream = null;
    cameraBtn.textContent = "Activar Cámara";
  }}
}}

cameraBtn.onclick = () => stream ? stopCamera() : startCamera();

// ============================================================
// CAPTURA DE IMAGEN
// ============================================================
async function captureImage() {{
  ctx.save();
  if (mirrorMode) {{
    ctx.translate(canvas.width, 0);
    ctx.scale(-1, 1);
  }}
  ctx.drawImage(video, 0, 0, canvas.width, canvas.height);
  ctx.restore();

  return new Promise(resolve => {{
    canvas.toBlob(blob => resolve(blob), "image/jpeg", 0.95);
  }});
}}

// ============================================================
// POST A LA API
// ============================================================
async function postImage(url, blob, extraData={{}}) {{
  if (!blob) {{
    responseBox.textContent =
      "❌ No se pudo capturar la imagen";

    return null;
  }}

  const formData = new FormData();

  formData.append(
    "file",
    blob,
    "face.jpg"
  );

  for (const k in extraData) {{
    formData.append(
      k,
      extraData[k]
    );
  }}

  try {{
    const res = await fetch(
      url,
      {{
        method: "POST",
        body: formData
      }}
    );

    const data =
      await res.json();

    if (!res.ok) {{
      responseBox.textContent =
        "❌ Error (" +
        res.status +
        "):\\n" +
        JSON.stringify(
          data,
          null,
          2
        );

      return null;
    }}

    return data;

  }} catch (err) {{
    responseBox.textContent =
      "❌ Error de conexión con la API\\n\\n" +
      "Tipo: " +
      err.name +
      "\\n" +
      "Mensaje: " +
      err.message;

    console.error(
      "Error API:",
      err
    );

    return null;
  }}
}}

// ============================================================
// RECONOCIMIENTO EN TIEMPO REAL
// ============================================================
async function startRealtimeRecognition() {{
  await startCamera();

  realtimeInterval = setInterval(async () => {{
    if (!stream) return;

    startTime = performance.now();
    const blob = await captureImage();
    const result = await postImage(`${{API_BASE}}/face/recognize/`, blob);

    if (!result) return;

    if (result.recognized) {{
      responseBox.textContent =
        "🟢 ROSTRO RECONOCIDO\\n" +
        `Cédula: ${{result.person.cedula}}\\n` +
        `Nombre: ${{result.person.nombre}} ${{result.person.apellido1}}\\n` +
        `Distancia: ${{result.distance}}` + getTimer();
    }} else {{
      responseBox.textContent = "🔴 Rostro no reconocido" + getTimer();
    }}
  }}, 1000);
}}

function stopRealtimeRecognition() {{
  clearInterval(realtimeInterval);
  realtimeInterval = null;
  realtimeActive = false;
  document.getElementById("realtimeBtn").textContent =
    "Reconocimiento en Tiempo Real";
}}

function startTimer(message) {{
  startTime = performance.now();
  responseBox.textContent = message;
}}

function getTimer() {{
  const elapsed = performance.now() - startTime;
  return `\\n⏱ Tiempo: ${{elapsed.toFixed(0)}} ms (${{(elapsed / 1000).toFixed(2)}} s)`;
}}

// ============================================================
// BOTONES
// ============================================================

document.getElementById("registerBtn").onclick = async () => {{
  startTimer("⏳ Registrando rostro, espere por favor...");
  const cedula = cedulaInput.value.trim();
  if (!cedula) {{
    alert("Ingrese una cédula válida");
    return;
  }}

  await startCamera();
  const blob = await captureImage();
  const res = await postImage(`${{API_BASE}}/face/register/`, blob, {{ cedula }});

  if (res) {{
    responseBox.textContent = "✅ Rostro registrado correctamente" + getTimer();
  }}
}};

document.getElementById("recognizeBtn").onclick = async () => {{
  startTimer("⏳ Reconociendo rostro, espere por favor...");
  await startCamera();
  const blob = await captureImage();
  const res = await postImage(`${{API_BASE}}/face/recognize/`, blob);

  if (res) {{
        if (res.recognized && res.person) {{
            responseBox.textContent =
                "🟢 ROSTRO RECONOCIDO\\n" +
                "Cédula: " + res.person.cedula + "\\n" +
                "Nombres: " + res.person.nombre + "\\n" +
                "Apellidos: " + res.person.apellido1 + " " + res.person.apellido2 + "\\n" +
                "Distancia: " + res.distance.toFixed(4) + "\\n" +
                getTimer();
        }} else {{
            responseBox.textContent =
                "🔴 Rostro no reconocido\\n" +
                "Distancia: " + (res.distance ?? "N/A") + "\\n" +
                getTimer();
        }}
    }}
}};

document.getElementById("accessBtn").onclick = async () => {{
  startTimer("⏳ Verificando identidad y prueba de vida...");

  const cedulaIngresada =
    cedulaInput.value.trim();

  if (!cedulaIngresada) {{
    alert("Ingrese la cédula");
    return;
  }}

  // ==========================================
  // ACTIVAR CÁMARA
  // ==========================================

  await startCamera();

  if (!stream) {{
    responseBox.textContent =
      "❌ No se pudo activar la cámara";
    return;
  }}

  // ==========================================
  // CAPTURAR FRAMES PARA LIVENESS
  // ==========================================

  const totalFrames = 5;
  const frames = [];

  responseBox.textContent =
    "🛡️ Comprobando que sea una persona real...\\n\\n" +
    "📷 Preparando prueba de vida...";

  for (let i = 0; i < totalFrames; i++) {{

    await new Promise(resolve =>
      setTimeout(resolve, 100)
    );

    const blob =
      await captureImage();

    if (!blob) {{
      responseBox.textContent =
        "❌ No se pudo capturar el frame " +
        (i + 1) +
        "/" +
        totalFrames;

      return;
    }}

    frames.push(blob);

    responseBox.textContent =
      "🛡️ Comprobando que sea una persona real...\\n\\n" +
      "📷 Capturando: " +
      (i + 1) +
      "/" +
      totalFrames;
  }}

  // ==========================================
  // ENVIAR TODOS LOS FRAMES
  // ==========================================

  responseBox.textContent =
    "🛡️ Analizando prueba de vida...\\n\\n" +
    "⏳ Espere un momento...";

  const formData =
    new FormData();

  frames.forEach(
    (blob, index) => {{
      formData.append(
        "frames",
        blob,
        `frame_${{index}}.jpg`
      );
    }}
  );

  let livenessResult;

  try {{

    const res =
      await fetch(
        `${{API_BASE}}/face/liveness`,
        {{
          method: "POST",
          body: formData
        }}
      );

    livenessResult =
      await res.json();

    if (!res.ok) {{
      responseBox.textContent =
        "❌ Error en prueba de vida (" +
        res.status +
        "):\\n" +
        JSON.stringify(
          livenessResult,
          null,
          2
        );

      return;
    }}

  }} catch (err) {{

    responseBox.textContent =
      "❌ Error de conexión con la API\\n\\n" +
      "Tipo: " +
      err.name +
      "\\n" +
      "Mensaje: " +
      err.message;

    console.error(
      "Error Liveness:",
      err
    );

    return;
  }}

  console.log(
    "[LIVENESS] Resultado:",
    livenessResult
  );

  // ==========================================
  // RESULTADO LIVENESS
  // ==========================================

  if (
    !livenessResult.success ||
    !livenessResult.live
  ) {{

    responseBox.textContent =
      "❌ ACCESO DENEGADO\\n\\n" +
      "⚠️ No se pudo confirmar que sea una persona real.\\n\\n" +
      "📊 Liveness score: " +
      (livenessResult.score ?? 0).toFixed(4) +
      "\\n" +
      "📷 Frames analizados: " +
      (livenessResult.framesAnalyzed ?? 0) +
      "/" +
      totalFrames;

    return;
  }}

  // ==========================================
  // LIVENESS APROBADO
  // ==========================================

  responseBox.textContent =
    "🟢 Persona real detectada.\\n\\n" +
    "🛡️ Prueba de vida: APROBADA\\n" +
    "📊 Score: " +
    livenessResult.score.toFixed(4) +
    "\\n" +
    "📷 Frames analizados: " +
    livenessResult.framesAnalyzed +
    "/" +
    totalFrames +
    "\\n\\n" +
    "🔍 Reconociendo rostro...";

  // ==========================================
  // RECONOCIMIENTO FACIAL
  // ==========================================

  const ultimoBlob =
    frames[frames.length - 1];

  const recognitionResult =
    await postImage(
      `${{API_BASE}}/face/recognize`,
      ultimoBlob
    );

  if (!recognitionResult) {{
    return;
  }}

  if (
    !recognitionResult.success ||
    !recognitionResult.recognized ||
    !recognitionResult.person
  ) {{

    responseBox.textContent =
      "❌ ACCESO DENEGADO\\n\\n" +
      "Rostro no reconocido.\\n" +
      "Distancia: " +
      (
        recognitionResult.distance ??
        "N/A"
      ) +
      getTimer();

    return;
  }}

  const persona =
    recognitionResult.person;

  // ==========================================
  // COMPARAR CÉDULA
  // ==========================================

  if (
    persona.cedula !==
    cedulaIngresada
  ) {{

    responseBox.textContent =
      "❌ ACCESO DENEGADO\\n\\n" +
      "⚠️ La cédula no coincide con el rostro.\\n\\n" +
      "Cédula ingresada: " +
      cedulaIngresada +
      "\\n" +
      "Cédula del rostro: " +
      persona.cedula +
      "\\n\\n" +
      "Distancia: " +
      recognitionResult.distance.toFixed(4) +
      getTimer();

    return;
  }}

  // ==========================================
  // ACCESO PERMITIDO
  // ==========================================

  responseBox.textContent =
    "✅ ACCESO PERMITIDO\\n\\n" +
    "👤 Persona: " +
    persona.nombre +
    " " +
    persona.apellido1 +
    " " +
    (persona.apellido2 ?? "") +
    "\\n" +
    "🪪 Cédula: " +
    persona.cedula +
    "\\n" +
    "🛡️ Prueba de vida: APROBADA\\n" +
    "📷 Frames analizados: " +
    livenessResult.framesAnalyzed +
    "/" +
    totalFrames +
    "\\n" +
    "📊 Liveness score: " +
    livenessResult.score.toFixed(4) +
    "\\n" +
    "🔐 Rostro: RECONOCIDO\\n" +
    "📏 Distancia: " +
    recognitionResult.distance.toFixed(4) +
    getTimer();
}};

document.getElementById("realtimeBtn").onclick = async () => {{
  if (!realtimeActive) {{
    realtimeActive = true;
    document.getElementById("realtimeBtn").textContent =
      "Detener Reconocimiento";
    await startRealtimeRecognition();
  }} else {{
    stopRealtimeRecognition();
  }}
}};

document.getElementById("mirrorBtn").onclick = () => {{
  mirrorMode = !mirrorMode;
  video.style.transform = mirrorMode ? "scaleX(-1)" : "scaleX(1)";
  document.getElementById("mirrorBtn").textContent =
    mirrorMode ? "Modo Espejo: ON" : "Modo Espejo: OFF";
}};
</script>

</body>
</html>
"""

# ============================================================
# SERVIDOR HTTP SIMPLE
# ============================================================
class CustomHandler(http.server.SimpleHTTPRequestHandler):
    def do_GET(self):
        if self.path in ("/", "/index.html"):
            body = HTML_PAGE.encode("utf-8")
            self.send_response(200)
            self.send_header("Content-Type", "text/html; charset=utf-8")
            self.send_header("Content-Length", str(len(body)))
            self.end_headers()
            self.wfile.write(body)
        else:
            self.send_error(404, "Archivo no encontrado")


def get_local_ip():
    s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    try:
        s.connect(("8.8.8.8", 80))
        return s.getsockname()[0]
    finally:
        s.close()


def run_http_server():
    with socketserver.TCPServer(("0.0.0.0", PORT), CustomHandler) as httpd:
        print("Servidor de pruebas iniciado:")
        print(f" ➜ Local: http://localhost:{PORT}")
        print(f" ➜ Red:   http://{get_local_ip()}:{PORT}")
        print("FastAPI debe estar activo en http://localhost:8000")
        print("Ctrl+C para detener.")
        httpd.serve_forever()


if __name__ == "__main__":
    run_http_server()
