const { pool } = require('../config/db');

const API_PERSONA_URL =
    'http://172.16.226.42:3000/administracion/usuario/v1/buscar_por_idpersonal';

// =====================================================
// API EXTERNA
// =====================================================

async function fetchPersonMetadata(idpersonal = '1') {
    try {
        const response = await fetch(API_PERSONA_URL, {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json'
            },
            body: JSON.stringify({
                idpersonal
            }),
            signal: AbortSignal.timeout(30000)
        });

        if (!response.ok) {
            throw new Error(
                `API externa respondió con estado ${response.status}`
            );
        }

        const data = await response.json();

        const usuarios =
            data?.p_data?.p_usuarios || [];

        console.log(
            `Usuarios recibidos API: ${usuarios.length}`
        );

        return usuarios;

    } catch (error) {
        console.error(
            'Error API externa:',
            error.message
        );

        return [];
    }
}


// =====================================================
// GUARDAR API EN TABLA TEMPORAL
// =====================================================

async function syncUsuariosTemporal() {

    const usuarios = await fetchPersonMetadata();

    if (!usuarios.length) {
        console.warn(
            'API no devolvió usuarios'
        );

        return false;
    }

    const client = await pool.connect();

    try {

        await client.query('BEGIN');

        for (const usuario of usuarios) {

            await client.query(
                `
                INSERT INTO usuarios_temporal
                (
                    idpersonal,
                    cedula,
                    persona,
                    ubicacion,
                    correo_personal_institucional,
                    correo_personal_alternativo
                )
                VALUES
                ($1, $2, $3, $4, $5, $6)
                ON CONFLICT DO NOTHING
                `,
                [
                    usuario?.idpersonal,
                    usuario?.cedula,
                    usuario?.persona,
                    usuario?.ubicacion,
                    usuario?.correo_personal_institucional,
                    usuario?.correo_personal_alternativo
                ]
            );
        }

        await client.query('COMMIT');

        console.log(
            'Usuarios sincronizados correctamente'
        );

        return true;

    } catch (error) {

        await client.query('ROLLBACK');

        console.error(
            'Error guardando usuarios temporales:',
            error
        );

        return false;

    } finally {

        client.release();
    }
}


// =====================================================
// PERSONAS
// =====================================================

async function getPersonByCedula(cedula) {

    const client = await pool.connect();

    try {

        // -------------------------------------------------
        // 1. Buscar si ya existe en personas
        // -------------------------------------------------

        let result = await client.query(
            `
            SELECT *
            FROM personas
            WHERE cedula = $1
            `,
            [cedula]
        );

        if (result.rows.length > 0) {
            return result.rows[0];
        }


        // -------------------------------------------------
        // 2. Buscar en usuarios_temporal
        // -------------------------------------------------

        result = await client.query(
            `
            SELECT *
            FROM usuarios_temporal
            WHERE cedula = $1
            `,
            [cedula]
        );

        if (result.rows.length === 0) {
            return null;
        }

        const usuario = result.rows[0];


        // -------------------------------------------------
        // 3. Separar nombre completo
        // -------------------------------------------------

        const nombreCompleto =
            String(usuario.persona || '').trim();

        const partes =
            nombreCompleto.split(/\s+/);

        const apellido1 =
            partes.length > 0 ? partes[0] : '';

        const apellido2 =
            partes.length > 1 ? partes[1] : '';

        const nombre =
            partes.length > 2
                ? partes.slice(2).join(' ')
                : '';


        // -------------------------------------------------
        // 4. Crear persona institucional
        // -------------------------------------------------

        result = await client.query(
            `
            INSERT INTO personas
            (
                cedula,
                nombre,
                apellido1,
                apellido2,
                activo
            )
            VALUES
            ($1, $2, $3, $4, FALSE)

            RETURNING *
            `,
            [
                usuario.cedula,
                nombre,
                apellido1,
                apellido2
            ]
        );

        return result.rows[0];

    } catch (error) {

        console.error(
            'Error obteniendo persona por cédula:',
            error
        );

        throw error;

    } finally {

        client.release();
    }
}


// =====================================================
// INSERTAR PERSONA
// =====================================================

async function insertPerson(data) {

    const client = await pool.connect();

    try {

        const result = await client.query(
            `
            INSERT INTO personas
            (
                cedula,
                nombre,
                apellido1,
                apellido2
            )
            VALUES
            ($1, $2, $3, $4)

            RETURNING id
            `,
            [
                data?.cedula,
                data?.nombre,
                data?.apellido1,
                data?.apellido2
            ]
        );

        return result.rows[0].id;

    } catch (error) {

        console.error(
            'Error insertando persona:',
            error
        );

        return null;

    } finally {

        client.release();
    }
}


// =====================================================
// CODIFICACIONES FACIALES
// =====================================================

async function saveFaceDescriptor(
    personaId,
    descriptor,
    thumb = null,
    imageHash = null
) {
    const client = await pool.connect();

    try {
        let emb = descriptor.map(
            value => Number(value)
        );

        const norma = Math.sqrt(
            emb.reduce(
                (sum, value) => sum + value * value,
                0
            )
        );

        if (norma === 0) {
            throw new Error(
                'Descriptor facial vacío'
            );
        }

        emb = emb.map(
            value => value / norma
        );

        await client.query(
            `
            INSERT INTO codificaciones_faciales
            (
                persona_id,
                codificacion,
                thumb,
                image_Hash
            )
            VALUES
            (
                $1,
                $2::double precision[],
                $3,
                $4
            )
            `,
            [
                personaId,
                emb,
                thumb,
                imageHash
            ]
        );

        console.log(
            `Rostro guardado para persona_id=${personaId}`
        );

        return true;

    } catch (error) {

        console.error(
            'Error guardando descriptor:',
            error
        );

        return false;

    } finally {

        client.release();
    }
}


// =====================================================
// CARGAR ROSTROS
// =====================================================

async function loadFacesFromDB() {

    const result = await pool.query(
        `
        SELECT
            p.id AS persona_id,
            p.cedula,
            p.nombre,
            p.apellido1,
            p.apellido2,
            cf.codificacion

        FROM personas p

        INNER JOIN codificaciones_faciales cf
        ON p.id = cf.persona_id

        WHERE p.activo = TRUE
        `
    );

    const rows = [];

    for (const row of result.rows) {

        let emb = row.codificacion.map(
            value => Number(value)
        );

        const norma = Math.sqrt(
            emb.reduce(
                (sum, value) => sum + value * value,
                0
            )
        );

        if (norma === 0) {
            continue;
        }

        emb = emb.map(
            value => value / norma
        );

        rows.push({
            persona_id: row.persona_id,
            cedula: row.cedula,
            nombre: row.nombre,
            apellido1: row.apellido1,
            apellido2: row.apellido2,
            embedding: emb
        });
    }

    console.log(
        `Rostros cargados: ${rows.length}`
    );

    return rows;
}


// =====================================================
// EXPORTAR FUNCIONES
// =====================================================

module.exports = {
    fetchPersonMetadata,
    syncUsuariosTemporal,
    getPersonByCedula,
    insertPerson,
    saveFaceDescriptor,
    loadFacesFromDB
};