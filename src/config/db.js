const { Pool } = require('pg');
require('dotenv').config();

const pool = new Pool({
    host: process.env.DB_HOST,
    port: process.env.DB_PORT,
    database: process.env.DB_NAME,
    user: process.env.DB_USER,
    password: process.env.DB_PASSWORD,

    max: 10,
    idleTimeoutMillis: 30000,
    connectionTimeoutMillis: 5000
});

pool.on('connect', () => {
    console.log('Conexión con PostgreSQL establecida');
});

pool.on('error', (err) => {
    console.error('Error en el pool de PostgreSQL:', err);
});

async function testConnection() {
    const client = await pool.connect();

    try {
        const result = await client.query(
            'SELECT NOW() AS fecha'
        );

        console.log(
            'PostgreSQL funcionando:',
            result.rows[0].fecha
        );
    } finally {
        client.release();
    }
}

module.exports = {
    pool,
    testConnection
};