const express = require("express");

const upload = require("../utils/upload");

const {
    recognizeFace,
    registerFace,
    checkLivenessFace
} = require("../controllers/faceControllers");

const router = express.Router();

router.get("/status", (req, res) => {
    res.json({
        success: true,
        message: "Módulo facial funcionando"
    });
});

router.post(
    "/recognize",
    upload.single("file"),
    recognizeFace
);

router.post(
    "/register",
    upload.single("file"),
    registerFace
);

router.post(
    "/liveness",
    upload.array("frames", 10),
    checkLivenessFace
);

module.exports = router;