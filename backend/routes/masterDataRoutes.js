const express = require("express");
const router = express.Router();

const {
    getAllJaksa,
    getAllJenisPidana,
    getAllInstansiPenyidik,
    getJenisPerkaraByJenisPidana
} = require("../controllers/masterDataController");

const {
    verifyToken
} = require("../middleware/authMiddleware");

const {
    authorizeRoles
} = require("../middleware/roleMiddleware");

const allowReadMasterData = [
    verifyToken,
    authorizeRoles("Admin", "Arsiparis", "User")
];

router.get(
    "/jaksa",
    allowReadMasterData,
    getAllJaksa
);

router.get(
    "/jenis-pidana",
    allowReadMasterData,
    getAllJenisPidana
);

router.get(
    "/instansi-penyidik",
    allowReadMasterData,
    getAllInstansiPenyidik
);

router.get(
    "/jenis-perkara/:jenisPidanaId",
    allowReadMasterData,
    getJenisPerkaraByJenisPidana
);

module.exports = router;
