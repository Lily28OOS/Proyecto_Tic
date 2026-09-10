const ort = require("onnxruntime-node");
const sharp = require("sharp");
const path = require("path");

const detectorPath = path.join(
    __dirname,
    "../../models/detector/retinaface_mv1_0.25.onnx"
);

const recognitionPath = path.join(
    __dirname,
    "../../models/recognition/w600k_r50.onnx"
);


let detectorSession = null;
let recognitionSession = null;


// =====================================================
// CARGAR MODELOS
// =====================================================

async function loadModels() {
    console.log("[INFO] Cargando modelos faciales...");

    detectorSession =
        await ort.InferenceSession.create(detectorPath);

    recognitionSession =
        await ort.InferenceSession.create(recognitionPath);

    console.log("[INFO] RetinaFace cargado.");
    console.log("[INFO] ArcFace cargado.");
    console.log("[INFO] Todos los modelos cargados correctamente.");
}


// =====================================================
// NORMALIZAR EMBEDDING
// =====================================================

function normalizeEmbedding(embedding) {
    const values = Array.from(embedding, Number);

    let sum = 0;

    for (const value of values) {
        sum += value * value;
    }

    const norm = Math.sqrt(sum);

    if (!norm) {
        return null;
    }

    return values.map(value => value / norm);
}


// =====================================================
// RETINAFACE - IOU / NMS
// =====================================================

function iou(a, b) {
    const x1 = Math.max(a[0], b[0]);
    const y1 = Math.max(a[1], b[1]);
    const x2 = Math.min(a[2], b[2]);
    const y2 = Math.min(a[3], b[3]);

    const intersection =
        Math.max(0, x2 - x1) *
        Math.max(0, y2 - y1);

    const areaA =
        Math.max(0, a[2] - a[0]) *
        Math.max(0, a[3] - a[1]);

    const areaB =
        Math.max(0, b[2] - b[0]) *
        Math.max(0, b[3] - b[1]);

    const union =
        areaA + areaB - intersection;

    return union > 0 ? intersection / union : 0;
}

function nms(detections, threshold = 0.4) {
    const sorted = [...detections]
        .sort((a, b) => b.score - a.score);

    const result = [];

    while (sorted.length) {
        const current = sorted.shift();

        result.push(current);

        for (let i = sorted.length - 1; i >= 0; i--) {
            if (
                iou(current.box, sorted[i].box) >
                threshold
            ) {
                sorted.splice(i, 1);
            }
        }
    }

    return result;
}


// =====================================================
// RETINAFACE - PRIORS
// =====================================================

function generatePriors(width, height) {
    const minSizes = [
        [16, 32],
        [64, 128],
        [256, 512]
    ];

    const steps = [8, 16, 32];
    const priors = [];

    for (let k = 0; k < steps.length; k++) {
        const step = steps[k];

        const featureHeight =
            Math.ceil(height / step);

        const featureWidth =
            Math.ceil(width / step);

        for (let i = 0; i < featureHeight; i++) {
            for (let j = 0; j < featureWidth; j++) {
                for (const size of minSizes[k]) {
                    priors.push([
                        (j + 0.5) * step / width,
                        (i + 0.5) * step / height,
                        size / width,
                        size / height
                    ]);
                }
            }
        }
    }

    return priors;
}


// =====================================================
// DECODIFICAR RETINAFACE
// =====================================================

function decodeBox(loc, prior) {
    const cx =
        prior[0] + loc[0] * 0.1 * prior[2];

    const cy =
        prior[1] + loc[1] * 0.1 * prior[3];

    const w =
        prior[2] * Math.exp(loc[2] * 0.2);

    const h =
        prior[3] * Math.exp(loc[3] * 0.2);

    return [
        cx - w / 2,
        cy - h / 2,
        cx + w / 2,
        cy + h / 2
    ];
}

function decodeLandmarks(values, prior) {
    const points = [];

    for (let i = 0; i < 5; i++) {
        points.push([
            prior[0] +
            values[i * 2] *
            0.1 *
            prior[2],

            prior[1] +
            values[i * 2 + 1] *
            0.1 *
            prior[3]
        ]);
    }

    return points;
}


// =====================================================
// PREPARAR IMAGEN
// =====================================================

async function prepareDetectorInput(buffer, width, height) {
    const { data } = await sharp(buffer)
        .removeAlpha()
        .resize(width, height)
        .raw()
        .toBuffer({
            resolveWithObject: true
        });

    const planeSize = width * height;

    const tensorData =
        new Float32Array(planeSize * 3);

    for (let i = 0; i < planeSize; i++) {
        // Sharp entrega RGB
        const r = data[i * 3];
        const g = data[i * 3 + 1];
        const b = data[i * 3 + 2];

        tensorData[i] =
            r - 104;

        tensorData[planeSize + i] =
            g - 117;

        tensorData[planeSize * 2 + i] =
            b - 123;
    }

    return new ort.Tensor(
        "float32",
        tensorData,
        [1, 3, height, width]
    );
}

async function prepareRecognitionInput(
    faceBuffer
) {
    const width = 112;
    const height = 112;

    const { data } =
        await sharp(faceBuffer)
            .removeAlpha()
            .resize(width, height)
            .raw()
            .toBuffer({
                resolveWithObject: true
            });

    const planeSize =
        width * height;

    const tensorData =
        new Float32Array(
            planeSize * 3
        );

    for (
        let i = 0;
        i < planeSize;
        i++
    ) {
        const r =
            data[i * 3];

        const g =
            data[i * 3 + 1];

        const b =
            data[i * 3 + 2];

        // ArcFace:
        // RGB -> [-1, 1]

        tensorData[i] =
            (r - 127.5) /
            127.5;

        tensorData[
            planeSize + i
        ] =
            (g - 127.5) /
            127.5;

        tensorData[
            planeSize * 2 + i
        ] =
            (b - 127.5) /
            127.5;
    }

    return new ort.Tensor(
        "float32",
        tensorData,
        [1, 3, height, width]
    );
}

// =====================================================
// DETECTAR ROSTRO
// =====================================================

async function detectFace(imageBuffer) {
    if (!detectorSession) {
        throw new Error(
            "RetinaFace no está cargado"
        );
    }

    const metadata =
        await sharp(imageBuffer).metadata();

    const originalWidth = metadata.width;
    const originalHeight = metadata.height;

    if (!originalWidth || !originalHeight) {
        return null;
    }

    const scale =
        640 /
        Math.max(
            originalWidth,
            originalHeight
        );

    const width =
        Math.round(originalWidth * scale);

    const height =
        Math.round(originalHeight * scale);

    const input =
        await prepareDetectorInput(
            imageBuffer,
            width,
            height
        );

    const outputs =
        await detectorSession.run({ input });

    const loc =
        outputs.loc.data;

    const conf =
        outputs.conf.data;

    const landmarkData =
        outputs.landmarks.data;

    const locCount =
        loc.length / 4;

    const confStride =
        conf.length / locCount;

    const landmarkStride =
        landmarkData.length / locCount;

    const priors =
        generatePriors(
            width,
            height
        );

    const detections = [];

    const count =
        Math.min(
            locCount,
            priors.length
        );

    for (let i = 0; i < count; i++) {
        const score =
            conf[i * confStride + 1];

        if (score < 0.55) {
            continue;
        }

        const box =
            decodeBox(
                loc.slice(
                    i * 4,
                    i * 4 + 4
                ),
                priors[i]
            );

        const landmarks =
            decodeLandmarks(
                landmarkData.slice(
                    i * landmarkStride,
                    i * landmarkStride +
                    landmarkStride
                ),
                priors[i]
            );

        detections.push({
            box: [
                Math.max(
                    0,
                    box[0] * originalWidth
                ),

                Math.max(
                    0,
                    box[1] * originalHeight
                ),

                Math.min(
                    originalWidth,
                    box[2] * originalWidth
                ),

                Math.min(
                    originalHeight,
                    box[3] * originalHeight
                )
            ],

            landmarks:
                landmarks.map(([x, y]) => [
                    x * originalWidth,
                    y * originalHeight
                ]),

            score
        });
    }

    const filtered =
        nms(
            detections,
            0.4
        );

    return filtered.length
        ? filtered[0]
        : null;
}


// =====================================================
// ALINEAR Y RECORTAR ROSTRO
// =====================================================

async function cropFace(
    imageBuffer,
    detection
) {
    const metadata =
        await sharp(imageBuffer).metadata();

    const imageWidth =
        metadata.width;

    const imageHeight =
        metadata.height;

    if (
        !imageWidth ||
        !imageHeight
    ) {
        throw new Error(
            "No se pudo obtener el tamaño de la imagen"
        );
    }

    const landmarks =
        detection.landmarks;

    /*
     * RetinaFace devuelve:
     * 0 = ojo izquierdo
     * 1 = ojo derecho
     * 2 = nariz
     * 3 = boca izquierda
     * 4 = boca derecha
     */

    if (
        !landmarks ||
        landmarks.length < 5
    ) {
        throw new Error(
            "RetinaFace no devolvió landmarks suficientes"
        );
    }

    const leftEye =
        landmarks[0];

    const rightEye =
        landmarks[1];

    // Ángulo de los ojos
    const angle =
        Math.atan2(
            rightEye[1] - leftEye[1],
            rightEye[0] - leftEye[0]
        ) *
        180 /
        Math.PI;

    /*
     * Distancia entre los ojos.
     * Se utiliza para determinar cuánto espacio
     * necesitamos alrededor del rostro.
     */
    const eyeDistance =
        Math.sqrt(
            Math.pow(
                rightEye[0] - leftEye[0],
                2
            ) +
            Math.pow(
                rightEye[1] - leftEye[1],
                2
            )
        );

    if (
        !Number.isFinite(eyeDistance) ||
        eyeDistance < 5
    ) {
        throw new Error(
            "Landmarks faciales inválidos"
        );
    }

    /*
     * El rostro se rota para dejar los ojos
     * aproximadamente horizontales.
     */
    const rotated =
        await sharp(imageBuffer)
            .rotate(-angle, {
                background: {
                    r: 0,
                    g: 0,
                    b: 0,
                    alpha: 0
                }
            })
            .png()
            .toBuffer();

    /*
     * Después de la rotación volvemos a detectar
     * el rostro para obtener coordenadas correctas
     * sobre la imagen ya transformada.
     *
     * Esto evita intentar transformar manualmente
     * las coordenadas de los landmarks.
     */
    const rotatedDetection =
        await detectFace(rotated);

    if (!rotatedDetection) {
        throw new Error(
            "No se pudo detectar el rostro después de alinearlo"
        );
    }

    const [
        x1,
        y1,
        x2,
        y2
    ] = rotatedDetection.box;

    const faceWidth =
        x2 - x1;

    const faceHeight =
        y2 - y1;

    if (
        faceWidth <= 0 ||
        faceHeight <= 0
    ) {
        throw new Error(
            "Área de rostro inválida"
        );
    }

    /*
     * Agregamos margen.
     *
     * ArcFace necesita algo más que únicamente
     * los píxeles internos del bounding box.
     */
    const marginX =
        faceWidth * 0.25;

    const marginY =
        faceHeight * 0.35;

    const left =
        Math.max(
            0,
            Math.floor(x1 - marginX)
        );

    const top =
        Math.max(
            0,
            Math.floor(y1 - marginY)
        );

    const right =
        Math.min(
            imageWidth,
            Math.ceil(x2 + marginX)
        );

    const bottom =
        Math.min(
            imageHeight,
            Math.ceil(y2 + marginY)
        );

    const width =
        right - left;

    const height =
        bottom - top;

    if (
        width <= 0 ||
        height <= 0
    ) {
        throw new Error(
            "Área de recorte inválida"
        );
    }

    return sharp(rotated)
        .extract({
            left,
            top,
            width,
            height
        })
        .resize(
            112,
            112,
            {
                fit: "fill"
            }
        )
        .removeAlpha()
        .toBuffer();
}


// =====================================================
// GENERAR EMBEDDING ARCface
// =====================================================

async function embeddingFromFace(faceBuffer) {
    if (!recognitionSession) {
        throw new Error(
            "ArcFace no está cargado"
        );
    }

    const tensor =
        await prepareRecognitionInput(
            faceBuffer
        );

    const inputName =
        recognitionSession
            .inputNames[0];

    const outputName =
        recognitionSession
            .outputNames[0];

    const result =
        await recognitionSession.run({
            [inputName]: tensor
        });

    const output =
        result[outputName];

    if (!output) {
        throw new Error(
            "ArcFace no devolvió embedding"
        );
    }

    const embedding =
        normalizeEmbedding(
            output.data
        );

    if (!embedding) {
        throw new Error(
            "ArcFace generó un embedding inválido"
        );
    }

    return embedding;
}

// =====================================================
// GENERAR EMBEDDING
// =====================================================

async function generateEmbedding(imageBuffer) {
    if (
        !detectorSession ||
        !recognitionSession
    ) {
        throw new Error(
            "Los modelos faciales no están cargados"
        );
    }

    const detection =
        await detectFace(
            imageBuffer
        );

    if (!detection) {
        return null;
    }

    const faceBuffer =
        await cropFace(
            imageBuffer,
            detection
        );

    const embedding =
        await embeddingFromFace(
            faceBuffer
        );

    return {
        embedding,
        detection
    };
}

// =====================================================
// LIVENESS PASIVO
// =====================================================

function normalizeLandmarks(detection) {
    if (
        !detection ||
        !detection.box ||
        !detection.landmarks ||
        detection.landmarks.length < 5
    ) {
        return null;
    }

    const [
        x1,
        y1,
        x2,
        y2
    ] = detection.box;

    const width = x2 - x1;
    const height = y2 - y1;

    if (
        width <= 0 ||
        height <= 0
    ) {
        return null;
    }

    return detection.landmarks.map(
        ([x, y]) => [
            (x - x1) / width,
            (y - y1) / height
        ]
    );
}


function calculateLandmarkMovement(
    previous,
    current
) {
    if (
        !previous ||
        !current ||
        previous.length !== current.length
    ) {
        return 0;
    }

    let total = 0;

    for (let i = 0; i < previous.length; i++) {
        const dx =
            current[i][0] -
            previous[i][0];

        const dy =
            current[i][1] -
            previous[i][1];

        total += Math.sqrt(
            dx * dx +
            dy * dy
        );
    }

    return total / previous.length;
}


function calculateFaceScaleChange(
    previousDetection,
    currentDetection
) {
    const previousBox =
        previousDetection.box;

    const currentBox =
        currentDetection.box;

    const previousWidth =
        previousBox[2] -
        previousBox[0];

    const currentWidth =
        currentBox[2] -
        currentBox[0];

    if (
        previousWidth <= 0 ||
        currentWidth <= 0
    ) {
        return 0;
    }

    return Math.abs(
        currentWidth /
        previousWidth -
        1
    );
}


function calculateFaceCenterMovement(
    previousDetection,
    currentDetection
) {
    const p =
        previousDetection.box;

    const c =
        currentDetection.box;

    const previousCenterX =
        (p[0] + p[2]) / 2;

    const previousCenterY =
        (p[1] + p[3]) / 2;

    const currentCenterX =
        (c[0] + c[2]) / 2;

    const currentCenterY =
        (c[1] + c[3]) / 2;

    const previousWidth =
        p[2] - p[0];

    const previousHeight =
        p[3] - p[1];

    if (
        previousWidth <= 0 ||
        previousHeight <= 0
    ) {
        return 0;
    }

    const dx =
        (currentCenterX -
            previousCenterX) /
        previousWidth;

    const dy =
        (currentCenterY -
            previousCenterY) /
        previousHeight;

    return Math.sqrt(
        dx * dx +
        dy * dy
    );
}


// =====================================================
// ANALIZAR LIVENESS TEMPORAL
// =====================================================

async function analyzeLiveness(
    imageBuffers
) {
    if (
        !Array.isArray(imageBuffers) ||
        imageBuffers.length < 4
    ) {
        return {
            live: false,
            score: 0,
            message:
                "No hay suficientes fotogramas para analizar la prueba de vida."
        };
    }

    const detections = [];

    for (const buffer of imageBuffers) {
        const detection =
            await detectFace(buffer);

        if (!detection) {
            continue;
        }

        detections.push(detection);
    }

    if (detections.length < 4) {
        return {
            live: false,
            score: 0,
            message:
                "No se pudo seguir el rostro durante la secuencia."
        };
    }

    const normalizedLandmarks = [];

    for (const detection of detections) {
        normalizedLandmarks.push(
            normalizeLandmarks(detection)
        );
    }

    let landmarkMovement = 0;
    let faceScaleChange = 0;
    let centerMovement = 0;

    let comparisons = 0;

    for (
        let i = 1;
        i < detections.length;
        i++
    ) {
        landmarkMovement +=
            calculateLandmarkMovement(
                normalizedLandmarks[i - 1],
                normalizedLandmarks[i]
            );

        faceScaleChange +=
            calculateFaceScaleChange(
                detections[i - 1],
                detections[i]
            );

        centerMovement +=
            calculateFaceCenterMovement(
                detections[i - 1],
                detections[i]
            );

        comparisons++;
    }

    if (!comparisons) {
        return {
            live: false,
            score: 0,
            message:
                "No se pudo analizar el movimiento facial."
        };
    }

    landmarkMovement /=
        comparisons;

    faceScaleChange /=
        comparisons;

    centerMovement /=
        comparisons;

    /*
     * La fotografía estática normalmente conserva
     * prácticamente idéntica la geometría interna
     * de los landmarks.
     *
     * Una persona real presenta pequeñas variaciones
     * entre los fotogramas.
     */

    const movementScore =
        Math.min(
            landmarkMovement / 0.025,
            1
        );

    const scaleScore =
        Math.min(
            faceScaleChange / 0.03,
            1
        );

    const centerScore =
        Math.min(
            centerMovement / 0.04,
            1
        );

    /*
     * Damos más importancia a la deformación
     * interna del rostro que al simple desplazamiento.
     *
     * Esto es importante porque una fotografía
     * también puede ser movida delante de la cámara.
     */

    const score =
        (
            movementScore * 0.75 +
            scaleScore * 0.15 +
            centerScore * 0.10
        );

    const live =
        score >= 0.64 &&
        landmarkMovement >= 0.008 &&
        faceScaleChange >= 0.005;

    return {
        live,
        score,
        framesReceived:
            imageBuffers.length,
        framesAnalyzed:
            detections.length,
        landmarkMovement,
        faceScaleChange,
        centerMovement,
        message: live
            ? "Presencia real detectada"
            : "No se pudo confirmar una presencia real"
    };
}

module.exports = {
    loadModels,
    generateEmbedding,
    normalizeEmbedding,
    detectFace,
    analyzeLiveness
};
