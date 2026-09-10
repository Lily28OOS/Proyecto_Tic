const express = require("express");
const cors = require("cors");

const faceRoutes = require("./routes/face");

const app = express();

app.use(cors());
app.use(express.json());

app.use("/face", faceRoutes);

app.get("/", (req, res) => {
    res.json({
        success: true,
        message: "API de Biometría UTM funcionando"
    });
});

module.exports = app;