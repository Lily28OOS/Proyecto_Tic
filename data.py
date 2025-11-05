#recibir los datos de la api del sga
import requests
from typing import Tuple, Any
import sys
import json
import argparse

DEFAULT_URL = "http://localhost:3000/administracion/usuario/v1/buscar_por_idpersonal"

def buscar_por_idpersonal(idpersonal: str, url: str = DEFAULT_URL, timeout: int = 10) -> Tuple[int, Any]:
    """
    Llama al endpoint de búsqueda por idPersonal.
    Envía JSON {"idPersonal": idpersonal} por POST y devuelve (status_code, json o text).
    """
    payload = {"idPersonal": idpersonal}
    headers = {"Content-Type": "application/json"}
    try:
        resp = requests.post(url, json=payload, headers=headers, timeout=timeout)
        content_type = resp.headers.get("Content-Type", "")
        if "application/json" in content_type:
            return resp.status_code, resp.json()
        return resp.status_code, resp.text
    except requests.RequestException as e:
        return 0, {"error": str(e)}

def pretty_print_response(status: int, data: Any) -> None:
    if status == 0:
        print("Error de conexión:", data)
        return
    print(f"HTTP status: {status}")
    if isinstance(data, (dict, list)):
        print(json.dumps(data, indent=2, ensure_ascii=False))
    else:
        print(data)

def extract_id_from_text(text: str) -> str:
    text = text.strip()
    # intentar parsear JSON si el usuario pegó un objeto
    try:
        obj = json.loads(text)
        return str(obj.get("idpersonal") or obj.get("idPersonal") or obj.get("id_personal"))
    except Exception:
        # si es solo un número o string, devolver tal cual
        return text

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Llamar buscar_por_idpersonal")
    parser.add_argument("idpersonal", nargs="?", help="idPersonal (ej: 81427)")
    parser.add_argument("--url", "-u", help="URL del endpoint", default=DEFAULT_URL)
    args = parser.parse_args()

    id_val = None
    # 1) argumento en línea de comandos
    if args.idpersonal:
        id_val = extract_id_from_text(args.idpersonal)
    else:
        # 2) entrada por pipe (stdin)
        try:
            if not sys.stdin.isatty():
                stdin = sys.stdin.read()
                if stdin.strip():
                    id_val = extract_id_from_text(stdin)
        except Exception:
            pass

    # 3) prompt interactivo si aún no hay id
    if not id_val:
        try:
            raw = input("Ingrese idPersonal (ej: 81427) o pegue JSON {\"idpersonal\":81427}: ").strip()
            if raw:
                id_val = extract_id_from_text(raw)
        except KeyboardInterrupt:
            print("\nCancelado.")
            sys.exit(1)

    if not id_val:
        print("Uso:\n  python data.py 81427\n  echo '{\"idpersonal\":81427}' | python data.py\n  python data.py --url http://host:3000/... 81427")
        sys.exit(1)

    status, data = buscar_por_idpersonal(id_val, url=args.url)
    pretty_print_response(status, data)