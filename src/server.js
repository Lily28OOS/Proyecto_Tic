const app = require("./app");

const {
    syncUsuariosTemporal,
    loadFacesFromDB
} = require("./services/dbService");

const {
    loadModels
} = require("./services/faceService");

const PORT = 8000;

async function startServer() {
    try {
        console.log("Cargando modelos faciales...");

        await loadModels();

        console.log("Modelos cargados correctamente.");

        console.log("Probando base de datos...");

        const sincronizado = await syncUsuariosTemporal();

        console.log(
            "Resultado sincronización:",
            sincronizado
        );

        const rostros = await loadFacesFromDB();

        console.log(
            "Rostros activos:",
            rostros.length
        );

        app.listen(PORT, "0.0.0.0", () => {
            console.log(`Servidor ejecutándose en http://localhost:${PORT}`);
        });

    } catch (error) {
        console.error("Error al iniciar servidor:", error);
        process.exit(1);
    }
}

startServer();