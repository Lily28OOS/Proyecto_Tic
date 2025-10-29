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

CREATE TABLE IF NOT EXISTS personas_relacionadas (
    id SERIAL PRIMARY KEY,
    persona_id INTEGER NOT NULL REFERENCES personas(id) ON DELETE CASCADE,
    persona_relacionada_id INTEGER NOT NULL REFERENCES personas(id) ON DELETE CASCADE,
    fecha_creacion TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    CONSTRAINT unique_relacion UNIQUE(persona_id, persona_relacionada_id)
);

CREATE OR REPLACE FUNCTION fn_personas_relacionar()
RETURNS TRIGGER AS
$$
BEGIN
    -- Buscar personas que coincidan con la nueva persona
    INSERT INTO personas_relacionadas (persona_id, persona_relacionada_id, tipo_relacion)
    SELECT NEW.id, p.id, 'posible duplicado'
    FROM personas p
    WHERE p.id <> NEW.id
      AND (
          p.cedula = NEW.cedula
          OR (p.nombre = NEW.nombre AND p.apellido1 = NEW.apellido1 AND p.apellido2 = NEW.apellido2)
      )
    ON CONFLICT DO NOTHING;  -- Evita duplicados en la tabla

    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

CREATE TRIGGER trg_personas_relacionar
AFTER INSERT ON personas
FOR EACH ROW
EXECUTE FUNCTION fn_personas_relacionar();

SELECT fhv.* FROM esq_ficheros.fichero_hoja_vida AS fhv;

CREATE SERVER servidor_ficheros
FOREIGN DATA WRAPPER postgres_fdw
OPTIONS (
    host '192.168.2.95',
    dbname 'db_sga_ficheros',
    port '5432'
);

CREATE USER MAPPING FOR postgres
SERVER servidor_ficheros
OPTIONS (
    user 'postgres',
    password 'Desarrollo8ty7.'
);

IMPORT FOREIGN SCHEMA esq_ficheros
LIMIT TO (fichero_hoja_vida)
FROM SERVER servidor_ficheros
INTO public;

ALTER TABLE personas
DROP COLUMN IF EXISTS correo_electronico;

ALTER TABLE personas
DROP CONSTRAINT IF EXISTS personas_cedula_check;

ALTER TABLE personas
ADD CONSTRAINT personas_cedula_unique UNIQUE (cedula);

ALTER TABLE personas
ADD CONSTRAINT personas_cedula_check
CHECK (cedula ~ '^[0-9]{10}$');

SELECT conname, pg_get_constraintdef(c.oid)
FROM pg_constraint c
JOIN pg_class t ON c.conrelid = t.oid
WHERE t.relname = 'personas';

SELECT * FROM public.fichero_hoja_vida;

SELECT * from personas, codificaciones_faciales;

ALTER TABLE personas
ADD COLUMN IF NOT EXISTS estado VARCHAR(20)
DEFAULT 'pendiente_rostro'
CHECK (estado IN ('pendiente_rostro', 'activo', 'inactivo'));

CREATE OR REPLACE FUNCTION fn_activar_persona_al_registrar_rostro()
RETURNS TRIGGER AS
$$
BEGIN
    UPDATE personas
    SET estado = 'activo'
    WHERE id = NEW.persona_id;
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

CREATE TRIGGER trg_activar_persona_al_registrar_rostro
AFTER INSERT ON codificaciones_faciales
FOR EACH ROW
EXECUTE FUNCTION fn_activar_persona_al_registrar_rostro();

UPDATE personas
SET estado = 'activo'
WHERE id IN (SELECT persona_id FROM codificaciones_faciales);

-- Agregar la nueva columna 'activo' sin eliminar todavía 'estado'
ALTER TABLE personas
ADD COLUMN IF NOT EXISTS activo BOOLEAN;

-- Migrar los valores del campo 'estado' al booleano 'activo'
UPDATE personas
SET activo = CASE
    WHEN estado = 'activo' THEN TRUE
    ELSE FALSE
END;

SELECT estado, activo, COUNT(*)
FROM personas
GROUP BY estado, activo
ORDER BY estado;

-- Eliminar columna antigua 'estado'
ALTER TABLE personas
DROP COLUMN estado;

-- Definir valor por defecto y no nulo
ALTER TABLE personas
ALTER COLUMN activo SET DEFAULT FALSE,
ALTER COLUMN activo SET NOT NULL;

-- Función para activar persona al registrar rostro
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

-- Trigger
DROP TRIGGER IF EXISTS trg_activar_persona_al_registrar_rostro ON codificaciones_faciales;

CREATE TRIGGER trg_activar_persona_al_registrar_rostro
AFTER INSERT ON codificaciones_faciales
FOR EACH ROW
EXECUTE FUNCTION fn_activar_persona_al_registrar_rostro();

UPDATE personas
SET activo = TRUE
WHERE id IN (SELECT persona_id FROM codificaciones_faciales);
