#recibir los datos de la api del sga
import requests
from typing import Tuple, Any

DEFAULT_URL = "http://172.16.226.42:3000/administracion/usuario/v1/buscar_por_cedula"

def buscar_por_cedula(cedula: str, url: str = DEFAULT_URL, timeout: int = 10) -> Tuple[int, Any]:
    """
    Llama al endpoint de búsqueda por cédula.
    Envía JSON {"cedula": cedula} por POST y devuelve (status_code, json o text).
    """
    payload = {"cedula": cedula}
    headers = {"Content-Type": "application/json"}
    try:
        resp = requests.post(url, json=payload, headers=headers, timeout=timeout)
        content_type = resp.headers.get("Content-Type", "")
        if "application/json" in content_type:
            return resp.status_code, resp.json()
        return resp.status_code, resp.text
    except requests.RequestException as e:
        return 0, {"error": str(e)}

if __name__ == "__main__":
    # Ejemplo de uso
    cedula_ej = "1314314244"
    status, data = buscar_por_cedula(cedula_ej)
    print("status:", status)
    print("data:", data)