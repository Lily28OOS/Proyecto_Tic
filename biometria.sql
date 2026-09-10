CREATE TABLE IF NOT EXISTS public.codificaciones_faciales
(
    id serial NOT NULL,
    persona_id integer NOT NULL,
    codificacion double precision[] NOT NULL,
    fecha_creacion timestamp without time zone DEFAULT CURRENT_TIMESTAMP,
    CONSTRAINT codificaciones_faciales_pkey PRIMARY KEY (id)
);

CREATE TABLE IF NOT EXISTS public.eventos_reconocimiento
(
    id serial NOT NULL,
    persona_id integer,
    confianza double precision,
    fecha_evento timestamp without time zone DEFAULT CURRENT_TIMESTAMP,
    imagen bytea,
    ubicacion character varying(255) COLLATE pg_catalog."default",
    CONSTRAINT eventos_reconocimiento_pkey PRIMARY KEY (id)
);

CREATE TABLE IF NOT EXISTS public.personas
(
    id serial NOT NULL,
    cedula character varying(10) COLLATE pg_catalog."default" NOT NULL,
    nombre character varying(25) COLLATE pg_catalog."default" NOT NULL,
    nombre2 character varying(25) COLLATE pg_catalog."default",
    apellido1 character varying(25) COLLATE pg_catalog."default" NOT NULL,
    apellido2 character varying(25) COLLATE pg_catalog."default" NOT NULL,
    activo boolean NOT NULL DEFAULT false,
    fecha_creacion timestamp without time zone DEFAULT CURRENT_TIMESTAMP,
    CONSTRAINT personas_pkey PRIMARY KEY (id),
    CONSTRAINT personas_cedula_key UNIQUE (cedula)
);

CREATE TABLE IF NOT EXISTS public.personas_relacionadas
(
    id serial NOT NULL,
    persona_id integer NOT NULL,
    persona_relacionada_id integer NOT NULL,
    fecha_creacion timestamp without time zone DEFAULT CURRENT_TIMESTAMP,
    CONSTRAINT personas_relacionadas_pkey PRIMARY KEY (id),
    CONSTRAINT unique_relacion UNIQUE (persona_id, persona_relacionada_id)
);

CREATE TABLE IF NOT EXISTS public.rostros_desconocidos
(
    id serial NOT NULL,
    codificacion double precision[] NOT NULL,
    imagen bytea,
    fecha_evento timestamp without time zone DEFAULT CURRENT_TIMESTAMP,
    CONSTRAINT rostros_desconocidos_pkey PRIMARY KEY (id)
);

CREATE TABLE IF NOT EXISTS public.usuarios_temporal
(
    id serial NOT NULL,
    idpersonal bigint NOT NULL,
    cedula character varying(50) COLLATE pg_catalog."default" NOT NULL,
    persona text COLLATE pg_catalog."default" NOT NULL,
    ubicacion text COLLATE pg_catalog."default",
    correo_personal_institucional text COLLATE pg_catalog."default",
    correo_personal_alternativo text COLLATE pg_catalog."default",
    created_at timestamp without time zone DEFAULT now(),
    CONSTRAINT usuarios_temporal_pkey PRIMARY KEY (id)
);

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

ALTER TABLE public.codificaciones_faciales
ADD COLUMN IF NOT EXISTS thumb BYTEA;

ALTER TABLE IF EXISTS public.codificaciones_faciales
    ADD CONSTRAINT codificaciones_faciales_persona_id_fkey FOREIGN KEY (persona_id)
    REFERENCES public.personas (id) MATCH SIMPLE
    ON UPDATE NO ACTION
    ON DELETE CASCADE;


ALTER TABLE IF EXISTS public.eventos_reconocimiento
    ADD CONSTRAINT eventos_reconocimiento_persona_id_fkey FOREIGN KEY (persona_id)
    REFERENCES public.personas (id) MATCH SIMPLE
    ON UPDATE NO ACTION
    ON DELETE NO ACTION;


ALTER TABLE IF EXISTS public.personas_relacionadas
    ADD CONSTRAINT personas_relacionadas_persona_id_fkey FOREIGN KEY (persona_id)
    REFERENCES public.personas (id) MATCH SIMPLE
    ON UPDATE NO ACTION
    ON DELETE CASCADE;


ALTER TABLE IF EXISTS public.personas_relacionadas
    ADD CONSTRAINT personas_relacionadas_persona_relacionada_id_fkey FOREIGN KEY (persona_relacionada_id)
    REFERENCES public.personas (id) MATCH SIMPLE
    ON UPDATE NO ACTION
    ON DELETE CASCADE;

ALTER TABLE codificaciones_faciales ADD COLUMN image_hash VARCHAR(64);

CREATE UNIQUE INDEX idx_codificaciones_image_hash ON codificaciones_faciales(image_hash);

END;
