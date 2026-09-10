const crypto = require("crypto");
const sharp = require("sharp");

const {
    generateEmbedding,
    analyzeLiveness
} = require("../services/faceService");

const {
    loadFacesFromDB,
    getPersonByCedula,
    saveFaceDescriptor
} = require("../services/dbService");

const { pool } = require("../config/db");

const FACE_DUPLICATE_THRESHOLD = 0.50;

// =====================================================
// REVISION DE DUPLICADOS
// =====================================================

function getImageHash(buffer) {
    return crypto
        .createHash("sha256")
        .update(buffer)
        .digest("hex");
}

// =====================================================
// DISTANCIA EUCLIDIANA
// =====================================================

function euclideanDistance(a, b) {
    let sum = 0;

    const length =
        Math.min(a.length, b.length);

    for (let i = 0; i < length; i++) {
        const diff =
            a[i] - b[i];

        sum += diff * diff;
    }

    return Math.sqrt(sum);
}


// =====================================================
// VALIDAR CALIDAD DE LA FOTO
// =====================================================

async function validateRegistrationImage(
    imageBuffer,
    detection
) {
    const metadata =
        await sharp(imageBuffer).metadata();

    const imageWidth =
        metadata.width;

    const imageHeight =
        metadata.height;

    if (!imageWidth || !imageHeight) {
        return {
            valid: false,
            message: "No se pudo determinar el tamaño de la imagen"
        };
    }


    // -------------------------------------------------
    // 1. CONFIANZA DEL DETECTOR
    // -------------------------------------------------

    if (detection.score < 0.80) {
        return {
            valid: false,
            message:
                "El rostro no pudo detectarse con suficiente precisión. " +
                "Toma una foto más clara y de frente."
        };
    }


    // -------------------------------------------------
    // 2. VALIDAR LANDMARKS
    // -------------------------------------------------

    const landmarks =
        detection.landmarks;

    if (
        !landmarks ||
        landmarks.length < 5
    ) {
        return {
            valid: false,
            message:
                "No se pudieron localizar correctamente los puntos faciales."
        };
    }

    const [
        leftEye,
        rightEye,
        nose,
        leftMouth,
        rightMouth
    ] = landmarks;


    // -------------------------------------------------
    // 3. TAMAÑO DEL ROSTRO
    // -------------------------------------------------

    const [
        x1,
        y1,
        x2,
        y2
    ] = detection.box;

    const faceWidth =
        x2 - x1;

    const faceHeight =
        y2 - y1;

    const faceArea =
        faceWidth * faceHeight;

    const imageArea =
        imageWidth * imageHeight;

    const faceRatio =
        faceArea / imageArea;


    // El rostro debe ocupar al menos 10% de la imagen.
    if (faceRatio < 0.10) {
        return {
            valid: false,
            message:
                "El rostro es demasiado pequeño. " +
                "Acércate un poco más a la cámara."
        };
    }


    // -------------------------------------------------
    // 4. ROSTRO DEMASIADO CERCA DE LOS BORDES
    // -------------------------------------------------

    const marginX =
        imageWidth * 0.03;

    const marginY =
        imageHeight * 0.03;

    if (
        x1 < marginX ||
        y1 < marginY ||
        x2 > imageWidth - marginX ||
        y2 > imageHeight - marginY
    ) {
        return {
            valid: false,
            message:
                "El rostro está demasiado cerca del borde de la imagen."
        };
    }


    // -------------------------------------------------
    // 5. DISTANCIA ENTRE LOS OJOS
    // -------------------------------------------------

    const eyeDistance =
        Math.hypot(
            rightEye[0] - leftEye[0],
            rightEye[1] - leftEye[1]
        );

    if (
        !Number.isFinite(eyeDistance) ||
        eyeDistance < faceWidth * 0.25
    ) {
        return {
            valid: false,
            message:
                "Los ojos no se detectaron correctamente. " +
                "Mira directamente hacia la cámara."
        };
    }


    // -------------------------------------------------
    // 6. INCLINACIÓN DE LA CABEZA
    // -------------------------------------------------

    const angle =
        Math.abs(
            Math.atan2(
                rightEye[1] - leftEye[1],
                rightEye[0] - leftEye[0]
            ) *
            180 /
            Math.PI
        );

    if (angle > 15) {
        return {
            valid: false,
            message:
                "La cabeza está demasiado inclinada. " +
                "Mantén el rostro recto."
        };
    }


    // -------------------------------------------------
    // 7. POSICIÓN DE LOS OJOS
    // -------------------------------------------------

    const eyeCenterX =
        (leftEye[0] + rightEye[0]) / 2;

    const eyeCenterY =
        (leftEye[1] + rightEye[1]) / 2;

    const faceCenterX =
        (x1 + x2) / 2;

    const faceCenterY =
        (y1 + y2) / 2;

    if (
        Math.abs(
            eyeCenterX - faceCenterX
        ) >
        faceWidth * 0.30
    ) {
        return {
            valid: false,
            message:
                "El rostro no está correctamente orientado."
        };
    }


    // -------------------------------------------------
    // 8. ILUMINACIÓN Y NITIDEZ
    // -------------------------------------------------

    const stats =
        await sharp(imageBuffer)
            .greyscale()
            .stats();

    const brightness =
        stats.channels[0].mean;

    const stdev =
        stats.channels[0].stdev;


    // Foto demasiado oscura
    if (brightness < 45) {
        return {
            valid: false,
            message:
                "La imagen está demasiado oscura. " +
                "Mejora la iluminación."
        };
    }


    // Foto demasiado sobreexpuesta
    if (brightness > 220) {
        return {
            valid: false,
            message:
                "La imagen está demasiado iluminada. " +
                "Evita la luz directa sobre el rostro."
        };
    }


    // Contraste extremadamente bajo
    if (stdev < 20) {
        return {
            valid: false,
            message:
                "La imagen tiene muy poco contraste. " +
                "Utiliza una iluminación más uniforme."
        };
    }


    // -------------------------------------------------
    // 9. NITIDEZ
    // -------------------------------------------------

    const { data, info } =
        await sharp(imageBuffer)
            .greyscale()
            .resize({
                width: 256,
                height: 256,
                fit: "inside"
            })
            .raw()
            .toBuffer({
                resolveWithObject: true
            });

    let variance = 0;

    let mean = 0;

    for (const value of data) {
        mean += value;
    }

    mean /= data.length;

    for (const value of data) {
        const diff =
            value - mean;

        variance +=
            diff * diff;
    }

    variance /=
        data.length;


    /*
     * No es un detector de blur perfecto,
     * pero permite rechazar fotografías
     * extremadamente desenfocadas.
     */
    if (variance < 120) {
        return {
            valid: false,
            message:
                "La fotografía está demasiado desenfocada. " +
                "Mantén la cámara estable."
        };
    }


    // -------------------------------------------------
    // FOTO ACEPTADA
    // -------------------------------------------------

    return {
        valid: true,
        quality: {
            confidence: detection.score,
            faceRatio,
            brightness,
            contrast: stdev,
            sharpness: variance,
            eyeDistance,
            angle
        }
    };
}


// =====================================================
// RECONOCIMIENTO
// =====================================================

async function recognizeFace(req, res) {
    try {
        if (!req.file) {
            return res.status(400).json({
                success: false,
                message: "No se recibió ninguna imagen"
            });
        }

        const result =
            await generateEmbedding(
                req.file.buffer
            );

        if (!result) {
            return res.status(400).json({
                success: false,
                message: "No se detectó rostro"
            });
        }

        const faces =
            await loadFacesFromDB();

        if (!faces.length) {
            return res.status(404).json({
                success: false,
                message:
                    "No existen rostros registrados"
            });
        }

        let bestMatch = null;
        let minDistance = Infinity;

        for (const face of faces) {
            if (!face.embedding) {
                continue;
            }

            const distance =
                euclideanDistance(
                    result.embedding,
                    face.embedding
                );

            if (distance < minDistance) {
                minDistance = distance;
                bestMatch = face;
            }
        }

        const THRESHOLD_RECOGNITION = 0.90;

        if (
            !bestMatch ||
            minDistance >=
            THRESHOLD_RECOGNITION
        ) {
            return res.json({
                success: true,
                recognized: false,
                message:
                    "Rostro no reconocido",
                distance: minDistance
            });
        }

        return res.json({
            success: true,
            recognized: true,
            message:
                "Rostro reconocido",
            distance: minDistance,
            person: bestMatch
        });

    } catch (error) {
        console.error(
            "[ERROR] recognizeFace:",
            error
        );

        return res.status(500).json({
            success: false,
            message:
                "Error procesando el rostro"
        });
    }
}


// =====================================================
// REGISTRO
// =====================================================

async function registerFace(req, res) {
    try {
        const { cedula } =
            req.body;

        if (!cedula) {
            return res.status(400).json({
                success: false,
                message:
                    "La cédula es obligatoria"
            });
        }

        if (!req.file) {
            return res.status(400).json({
                success: false,
                message:
                    "No se recibió ninguna imagen"
            });
        }


        // -------------------------------------------------
        // PERSONA
        // -------------------------------------------------

        const persona =
            await getPersonByCedula(
                cedula
            );

        if (!persona) {
            return res.status(404).json({
                success: false,
                message:
                    "No se encontró una persona con esa cédula"
            });
        }

        const imageHash = getImageHash(req.file.buffer);

        const existingFaces = await pool.query(
            `
            SELECT id, codificacion
            FROM codificaciones_faciales
            WHERE persona_id = $1
            ORDER BY id ASC
            `,
            [persona.id]
        );


        // -------------------------------------------------
        // DETECCIÓN
        // -------------------------------------------------

        const result =
            await generateEmbedding(
                req.file.buffer
            );

        if (!result) {
            return res.status(400).json({
                success: false,
                message:
                    "No se detectó un rostro en la imagen"
            });
        }


        // -------------------------------------------------
        // VALIDACIÓN DE CALIDAD
        // -------------------------------------------------

        const quality =
            await validateRegistrationImage(
                req.file.buffer,
                result.detection
            );

        if (!quality.valid) {
            return res.status(400).json({
                success: false,
                message:
                    quality.message
            });
        }


        // -------------------------------------------------
        // EMBEDDING
        // -------------------------------------------------

        const embedding =
            result.embedding;


        // -------------------------------------------------
        // VERIFICAR DUPLICADO
        // -------------------------------------------------

        const faces =
            await loadFacesFromDB();

        for (const face of faces) {
            if (!face.embedding) {
                continue;
            }

            const distance =
                euclideanDistance(
                    embedding,
                    face.embedding
                );

            if (
                distance <
                FACE_DUPLICATE_THRESHOLD
            ) {
                return res.status(409).json({
                    success: false,
                    message:
                        "Rostro ya registrado",
                    distance
                });
            }
        }


        // -------------------------------------------------
        // MINIATURA
        // -------------------------------------------------

        const thumb =
            await sharp(req.file.buffer)
                .resize(
                    200,
                    200,
                    {
                        fit: "cover"
                    }
                )
                .jpeg({
                    quality: 80
                })
                .toBuffer();


        // -------------------------------------------------
        // GUARDAR
        // -------------------------------------------------

        const saved =
            await saveFaceDescriptor(
                persona.id,
                embedding,
                thumb,
                imageHash
            );

        if (!saved) {
            return res.status(500).json({
                success: false,
                message:
                    "No se pudo guardar el rostro"
            });
        }


        await pool.query(
            `
            UPDATE personas
            SET activo = TRUE
            WHERE id = $1
            `,
            [persona.id]
        );


        return res.status(201).json({
            success: true,
            message:
                "Rostro registrado correctamente",
            persona_id:
                persona.id,
            cedula:
                persona.cedula,
            quality:
                quality.quality
        });

    } catch (error) {
        console.error(
            "[ERROR] registerFace:",
            error
        );

        return res.status(500).json({
            success: false,
            message:
                "Error registrando el rostro"
        });
    }
}


async function checkLivenessFace(req, res) {
    try {
        if (
            !req.files ||
            req.files.length < 4
        ) {
            return res.status(400).json({
                success: false,
                message:
                    "Se necesitan al menos 4 fotogramas para realizar la prueba de vida"
            });
        }

        const frames =
            req.files.map(
                file => file.buffer
            );

        const result =
            await analyzeLiveness(
                frames
            );

        return res.json({
            success: true,
            live: result.live,
            score: result.score,
            framesReceived:
                result.framesReceived,
            framesAnalyzed:
                result.framesAnalyzed,
            message:
                result.message
        });

    } catch (error) {
        console.error(
            "[ERROR] checkLivenessFace:",
            error
        );

        return res.status(500).json({
            success: false,
            message:
                "Error procesando la prueba de vida"
        });
    }
}

module.exports = {
    recognizeFace,
    registerFace,
    checkLivenessFace
};
