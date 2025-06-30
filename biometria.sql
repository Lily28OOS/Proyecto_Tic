-- Database: biometria

 SELECT * FROM pg_stat_activity WHERE datname = 'biometria';

-- DROP DATABASE IF EXISTS biometria;

DO
$$
BEGIN
    IF NOT EXISTS (SELECT FROM pg_database WHERE datname = 'biometria') THEN
        CREATE DATABASE biometria
        WITH
        OWNER = postgres
        ENCODING = 'UTF8'
        LC_COLLATE = 'Spanish_Colombia.1252'
        LC_CTYPE = 'Spanish_Colombia.1252'
        TABLESPACE = pg_default
        CONNECTION LIMIT = -1
        IS_TEMPLATE = False;
    END IF;
END
$$;
	
-- Crear tabla: personas
CREATE TABLE IF NOT EXISTS personas (
    id SERIAL PRIMARY KEY,
    nombre VARCHAR(100) NOT NULL,
    correo_electronico VARCHAR(100) UNIQUE,
    fecha_creacion TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- Crear tabla: codificaciones_faciales
CREATE TABLE IF NOT EXISTS codificaciones_faciales (
    id SERIAL PRIMARY KEY,
    persona_id INTEGER REFERENCES personas(id) ON DELETE CASCADE,
    codificacion FLOAT8[] NOT NULL,
    fecha_creacion TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- Crear tabla: eventos_reconocimiento
CREATE TABLE IF NOT EXISTS eventos_reconocimiento (
    id SERIAL PRIMARY KEY,
    persona_id INTEGER REFERENCES personas(id),
    confianza FLOAT,
    fecha_evento TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    imagen BYTEA,
    ubicacion VARCHAR(255)
);

-- Crear tabla: rostros_desconocidos
CREATE TABLE IF NOT EXISTS rostros_desconocidos (
    id SERIAL PRIMARY KEY,
    codificacion FLOAT8[] NOT NULL,
    imagen BYTEA,
    fecha_evento TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- Alterar la tabla personas para agregar cédula, nombres y apellidos con las restricciones
ALTER TABLE personas
ADD COLUMN cedula VARCHAR(10) CHECK (cedula ~ '^\d{1,10}$') NOT NULL,
ADD COLUMN nombre2 VARCHAR(25),
ADD COLUMN apellido1 VARCHAR(25),
ADD COLUMN apellido2 VARCHAR(25);

-- Modificar las columnas existentes para ajustarse a las restricciones
ALTER TABLE personas
ALTER COLUMN nombre SET DATA TYPE VARCHAR(25),
ALTER COLUMN nombre SET NOT NULL,
ALTER COLUMN apellido1 SET DATA TYPE VARCHAR(25),
ALTER COLUMN apellido1 SET NOT NULL,
ALTER COLUMN apellido2 SET DATA TYPE VARCHAR(25),
ALTER COLUMN apellido2 SET NOT NULL;

SELECT * from codificaciones_faciales;
SELECT * FROM personas;
