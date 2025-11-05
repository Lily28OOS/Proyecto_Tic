-- ---------------- Base de datos ---------------- --
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
        IS_TEMPLATE = FALSE;
    END IF;
END
$$;

-- ---------------- Tablas ---------------- --

-- Tabla personas
CREATE TABLE IF NOT EXISTS personas (
    id SERIAL PRIMARY KEY,
    cedula VARCHAR(10) NOT NULL UNIQUE CHECK (cedula ~ '^[0-9]{10}$'),
    nombre VARCHAR(25) NOT NULL,
    nombre2 VARCHAR(25),
    apellido1 VARCHAR(25) NOT NULL,
    apellido2 VARCHAR(25) NOT NULL,
    activo BOOLEAN NOT NULL DEFAULT FALSE,
    fecha_creacion TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- Tabla codificaciones_faciales
CREATE TABLE IF NOT EXISTS codificaciones_faciales (
    id SERIAL PRIMARY KEY,
    persona_id INTEGER NOT NULL REFERENCES personas(id) ON DELETE CASCADE,
    codificacion FLOAT8[] NOT NULL,
    fecha_creacion TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- Trigger para activar persona al registrar rostro
CREATE OR REPLACE FUNCTION fn_activar_persona_al_registrar_rostro()
RETURNS TRIGGER AS
$$
BEGIN
    UPDATE personas
    SET activo = TRUE
    WHERE id = NEW.persona_id;
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

DROP TRIGGER IF EXISTS trg_activar_persona_al_registrar_rostro ON codificaciones_faciales;

CREATE TRIGGER trg_activar_persona_al_registrar_rostro
AFTER INSERT ON codificaciones_faciales
FOR EACH ROW
EXECUTE FUNCTION fn_activar_persona_al_registrar_rostro();

-- Tabla eventos_reconocimiento
CREATE TABLE IF NOT EXISTS eventos_reconocimiento (
    id SERIAL PRIMARY KEY,
    persona_id INTEGER REFERENCES personas(id),
    confianza FLOAT,
    fecha_evento TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    imagen BYTEA,
    ubicacion VARCHAR(255)
);

-- Tabla rostros_desconocidos
CREATE TABLE IF NOT EXISTS rostros_desconocidos (
    id SERIAL PRIMARY KEY,
    codificacion FLOAT8[] NOT NULL,
    imagen BYTEA,
    fecha_evento TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- Tabla personas_relacionadas para detectar posibles duplicados
CREATE TABLE IF NOT EXISTS personas_relacionadas (
    id SERIAL PRIMARY KEY,
    persona_id INTEGER NOT NULL REFERENCES personas(id) ON DELETE CASCADE,
    persona_relacionada_id INTEGER NOT NULL REFERENCES personas(id) ON DELETE CASCADE,
    fecha_creacion TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    CONSTRAINT unique_relacion UNIQUE(persona_id, persona_relacionada_id)
);

-- Trigger para relacionar personas duplicadas automáticamente
CREATE OR REPLACE FUNCTION fn_personas_relacionar()
RETURNS TRIGGER AS
$$
BEGIN
    INSERT INTO personas_relacionadas (persona_id, persona_relacionada_id)
    SELECT NEW.id, p.id
    FROM personas p
    WHERE p.id <> NEW.id
      AND (
          p.cedula = NEW.cedula
          OR (p.nombre = NEW.nombre AND p.apellido1 = NEW.apellido1 AND p.apellido2 = NEW.apellido2)
      )
    ON CONFLICT DO NOTHING;

    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

DROP TRIGGER IF EXISTS trg_personas_relacionar ON personas;

CREATE TRIGGER trg_personas_relacionar
AFTER INSERT ON personas
FOR EACH ROW
EXECUTE FUNCTION fn_personas_relacionar();



SELECT * FROM personas, codificaciones_faciales;
