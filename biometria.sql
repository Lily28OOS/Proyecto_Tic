-- =====================================================
-- BASE DE DATOS
-- =====================================================
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
        CONNECTION LIMIT = -1;
    END IF;
END
$$;

-- =====================================================
-- TABLA PERSONAS
-- =====================================================
CREATE TABLE IF NOT EXISTS personas (
    id SERIAL PRIMARY KEY,
    cedula VARCHAR(15) UNIQUE,
    tipo_persona VARCHAR(20) NOT NULL
        CHECK (tipo_persona IN ('institucional', 'temporal', 'visitante')),
    nombre VARCHAR(50),
    nombre2 VARCHAR(50),
    apellido1 VARCHAR(50),
    apellido2 VARCHAR(50),
    activo BOOLEAN NOT NULL DEFAULT FALSE,
    fecha_creacion TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    fecha_expiracion TIMESTAMP
);

CREATE INDEX IF NOT EXISTS idx_personas_cedula ON personas(cedula);
CREATE INDEX IF NOT EXISTS idx_personas_tipo ON personas(tipo_persona);

-- =====================================================
-- CODIFICACIONES FACIALES
-- =====================================================
CREATE TABLE IF NOT EXISTS codificaciones_faciales (
    id SERIAL PRIMARY KEY,
    persona_id INTEGER NOT NULL REFERENCES personas(id) ON DELETE CASCADE,
    codificacion JSONB NOT NULL,
    modelo VARCHAR(50) NOT NULL,
    version_modelo VARCHAR(20),
    calidad FLOAT CHECK (calidad >= 0 AND calidad <= 1),
    activo BOOLEAN DEFAULT TRUE,
    fecha_creacion TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX IF NOT EXISTS idx_codificaciones_persona
ON codificaciones_faciales(persona_id);

-- =====================================================
-- TRIGGER: ACTIVAR PERSONA AL REGISTRAR ROSTRO
-- =====================================================
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

DROP TRIGGER IF EXISTS trg_activar_persona_al_registrar_rostro
ON codificaciones_faciales;

CREATE TRIGGER trg_activar_persona_al_registrar_rostro
AFTER INSERT ON codificaciones_faciales
FOR EACH ROW
EXECUTE FUNCTION fn_activar_persona_al_registrar_rostro();

-- =====================================================
-- METADATA DE PERSONAS (API EXTERNA)
-- =====================================================
CREATE TABLE IF NOT EXISTS persona_metadata (
    persona_id INTEGER PRIMARY KEY REFERENCES personas(id) ON DELETE CASCADE,
    metadata JSONB,
    fecha_actualizacion TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- =====================================================
-- EVENTOS DE RECONOCIMIENTO
-- =====================================================
CREATE TABLE IF NOT EXISTS eventos_reconocimiento (
    id SERIAL PRIMARY KEY,
    persona_id INTEGER REFERENCES personas(id),
    distancia FLOAT,
    modelo VARCHAR(50),
    fecha_evento TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    imagen BYTEA,
    ubicacion VARCHAR(255)
);

CREATE INDEX IF NOT EXISTS idx_eventos_persona
ON eventos_reconocimiento(persona_id);

-- =====================================================
-- ROSTROS DESCONOCIDOS
-- =====================================================
CREATE TABLE IF NOT EXISTS rostros_desconocidos (
    id SERIAL PRIMARY KEY,
    codificacion JSONB NOT NULL,
    imagen BYTEA,
    fecha_evento TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- =====================================================
-- PERSONAS RELACIONADAS (DUPLICADOS)
-- =====================================================
CREATE TABLE IF NOT EXISTS personas_relacionadas (
    id SERIAL PRIMARY KEY,
    persona_id INTEGER NOT NULL REFERENCES personas(id) ON DELETE CASCADE,
    persona_relacionada_id INTEGER NOT NULL REFERENCES personas(id) ON DELETE CASCADE,
    fecha_creacion TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    CONSTRAINT unique_relacion UNIQUE (persona_id, persona_relacionada_id)
);

-- =====================================================
-- TRIGGER: DETECTAR POSIBLES DUPLICADOS
-- =====================================================
CREATE OR REPLACE FUNCTION fn_personas_relacionar()
RETURNS TRIGGER AS
$$
BEGIN
    INSERT INTO personas_relacionadas (persona_id, persona_relacionada_id)
    SELECT NEW.id, p.id
    FROM personas p
    WHERE p.id <> NEW.id
      AND (
          (NEW.cedula IS NOT NULL AND p.cedula = NEW.cedula)
          OR (
              p.nombre = NEW.nombre
              AND p.apellido1 = NEW.apellido1
              AND p.apellido2 = NEW.apellido2
          )
      )
    ON CONFLICT DO NOTHING;

    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

DROP TRIGGER IF EXISTS trg_personas_relacionar
ON personas;

CREATE TRIGGER trg_personas_relacionar
AFTER INSERT ON personas
FOR EACH ROW
EXECUTE FUNCTION fn_personas_relacionar();
