# src/config/settings.py
"""
Configuración centralizada del proyecto.
Todas las variables de entorno y configuraciones se definen aquí.
"""
import os
from typing import Optional


class DatabaseConfig:
    """Configuración de la base de datos PostgreSQL."""
    
    DB_NAME: str = os.getenv("DB_NAME", "biometria")
    DB_USER: str = os.getenv("DB_USER", "postgres")
    DB_PASS: str = os.getenv("DB_PASS", "admin")
    DB_HOST: str = os.getenv("DB_HOST", "localhost")
    DB_PORT: int = int(os.getenv("DB_PORT", "5432"))
    
    POOL_MINCONN: int = int(os.getenv("DB_POOL_MIN", "1"))
    POOL_MAXCONN: int = int(os.getenv("DB_POOL_MAX", "10"))


class APIConfig:
    """Configuración de APIs externas."""
    
    PERSONA_URL: str = "http://172.16.226.42:3000/administracion/usuario/v1/buscar_por_idpersonal"


class RecognitionConfig:
    """Configuración para reconocimiento facial."""
    
    # Umbrales de reconocimiento
    THRESHOLD_RECOGNITION: float = 0.90  # Para reconocimiento (más estricto)
    THRESHOLD_REGISTER: float = 0.50     # Para registro (más permisivo)
    MATCH_THRESHOLD: float = 0.65        # Umbral para coincidencia de rostros
    
    # Configuración de imágenes
    MAX_IMAGE_WIDTH: int = 800


class AppConfig:
    """Configuración general de la aplicación."""
    
    TITLE: str = "API Reconocimiento Facial - UTM"
    VERSION: str = "1.0.0"
    DEBUG: bool = os.getenv("DEBUG", "False").lower() == "true"
    
    # CORS
    CORS_ORIGINS: list = ["*"]


# Instancias de configuración
db_config = DatabaseConfig()
api_config = APIConfig()
recognition_config = RecognitionConfig()
app_config = AppConfig()
