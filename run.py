"""
Punto de entrada principal del proyecto.
Ejecuta la aplicación FastAPI.
"""
import uvicorn
import sys
from pathlib import Path

# Agregar el directorio raíz al path para permitir imports absolutos
root_path = Path(__file__).parent
sys.path.insert(0, str(root_path))

if __name__ == "__main__":
    uvicorn.run(
        "src.api.main:app",
        host="0.0.0.0",
        port=8000,
        reload=True
    )
