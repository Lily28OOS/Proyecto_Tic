import requests
import json
import argparse
import os
import sys
import time
import random

DEFAULT_URL = os.getenv(
    "SGA_URL",
    "http://172.16.226.42:3000/administracion/usuario/v1/buscar_por_idpersonal",
)

# Lista de IDs disponibles para elegir uno al azar
RANDOM_IDS = ["81427", "12345", "56789", "99887", "44112"]

def fetch_by_id(idpersonal: str, url: str = DEFAULT_URL, timeout: int = 10):
    payload = {"idPersonal": idpersonal, "idpersonal": idpersonal}
    headers = {"Content-Type": "application/json"}
    try:
        print(f"Estado: Enviando solicitud a {url} con idpersonal={idpersonal} ...")
        resp = requests.post(url, json=payload, headers=headers, timeout=timeout)
    except requests.RequestException as e:
        print(f"Estado: Error de conexión -> {e}")
        return None, str(e)
    print(f"Estado: Respuesta recibida (HTTP {resp.status_code})")
    try:
        return resp.json(), None
    except Exception:
        return resp.text, None

def find_matches(data, idpersonal: str):
    matches = []
    id_str = str(idpersonal)
    usuarios = []
    if isinstance(data, dict):
        usuarios = data.get("p_data", {}).get("p_usuarios") or []
    if not isinstance(usuarios, list):
        return matches
    for u in usuarios:
        if not isinstance(u, dict):
            continue
        for k in ("idpersonal", "idPersonal", "id_personal"):
            v = u.get(k)
            if v is None:
                continue
            if str(v) == id_str:
                matches.append(u)
                break
    return matches

def main():
    parser = argparse.ArgumentParser(description="Buscar usuario por idPersonal y mostrar datos")
    parser.add_argument("idpersonal", nargs="?", help="idPersonal (ej: 81427)")
    parser.add_argument("--url", "-u", help="URL del endpoint", default=DEFAULT_URL)
    parser.add_argument("--timeout", "-t", type=int, default=10, help="Timeout en segundos")
    args = parser.parse_args()

    # Si no hay ID → escoger uno al azar
    id_val = args.idpersonal
    if not id_val:
        id_val = random.choice(RANDOM_IDS)
        print(f"No se proporcionó idPersonal. Usando uno al azar: {id_val}")

    data, err = fetch_by_id(id_val, url=args.url, timeout=args.timeout)
    if err:
        print("Error:", err)
        sys.exit(1)

    if isinstance(data, (str, bytes)):
        print("Respuesta no JSON de la API:")
        print(data)
        sys.exit(0)

    matches = find_matches(data, id_val)
    if not matches:
        print(f"No se encontró usuario con idPersonal = {id_val}")
        usuarios = data.get("p_data", {}).get("p_usuarios") or []
        if usuarios:
            print(f"La API devolvió {len(usuarios)} registro(es). Puedes revisar la respuesta completa con --debug.")
        sys.exit(0)

    for i, u in enumerate(matches, 1):
        print(f"--- Usuario {i} ---")
        print(json.dumps(u, indent=2, ensure_ascii=False))

if __name__ == "__main__":
    main()
