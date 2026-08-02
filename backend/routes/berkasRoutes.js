const express = require("express");
const fs = require("fs");
const multer = require("multer");
const path = require("path");
const router = express.Router();

const {
    getAllBerkas,
    getBerkasById,
    createBerkas,
    updateBerkas,
    deleteBerkas,
    getBerkasFile,
    verifyBerkasIntegrity,
    exportVerificationReport,
    getBerkasAkanJatuhTempo,
    getIntegrityHistory,
    getSystemNotifications,
    prosesRetensiOtomatis,
    getBerkasRetensiSelesai
} = require("../controllers/berkasController");

const {
    verifyToken
} = require("../middleware/authMiddleware");

const {
    authorizeRoles
} = require("../middleware/roleMiddleware");

const uploadDir = path.join(__dirname, "..", "uploads", "berkas");
if (!fs.existsSync(uploadDir)) {
    fs.mkdirSync(uploadDir, {
        recursive: true
    });
}

const storage = multer.diskStorage({
    destination: (req, file, cb) => {
        cb(null, uploadDir);
    },
    filename: (req, file, cb) => {
        const safeName = file.originalname.replace(/[^a-zA-Z0-9._-]/g, "_");
        cb(null, `${Date.now()}-${safeName}`);
    }
});

const upload = multer({
    storage,
    fileFilter: (req, file, cb) => {
        const isPdf = file.mimetype === "application/pdf" && path.extname(file.originalname).toLowerCase() === ".pdf";

        if (!isPdf) {
            return cb(new Error("Upload hanya menerima file PDF"));
        }

        cb(null, true);
    }
});

const handleUploadError = (err, req, res, next) => {
    if (err) {
        return res.status(400).json({
            message: err.message || "Upload file gagal"
        });
    }

    next();
};

router.get(
    "/retensi/peringatan",
    verifyToken,
    authorizeRoles("Admin", "Arsiparis"),
    getBerkasAkanJatuhTempo
);

router.post(
    "/retensi/proses",
    verifyToken,
    authorizeRoles("Admin", "Arsiparis"),
    prosesRetensiOtomatis
);

router.get(
    "/retensi/selesai",
    verifyToken,
    authorizeRoles("Admin", "Arsiparis"),
    getBerkasRetensiSelesai
);

router.get(
    "/integrity/history",
    verifyToken,
    authorizeRoles("Admin"),
    getIntegrityHistory
);

router.get(
    "/integrity/notifications",
    verifyToken,
    authorizeRoles("Admin"),
    getSystemNotifications
);

router.get(
    "/",
    verifyToken,
    authorizeRoles("Admin", "Arsiparis", "User"),
    getAllBerkas
);

router.get(
    "/:id",
    verifyToken,
    authorizeRoles("Admin", "Arsiparis", "User"),
    getBerkasById
);

router.get(
    "/:id/file",
    verifyToken,
    authorizeRoles("Admin", "Arsiparis", "User"),
    getBerkasFile
);

router.post(
    "/:id/verify",
    verifyToken,
    authorizeRoles("Admin"),
    verifyBerkasIntegrity
);

router.post(
    "/:id/verification-report",
    verifyToken,
    authorizeRoles("Admin", "Arsiparis", "User"),
    exportVerificationReport
);

router.post(
    "/",
    verifyToken,
    authorizeRoles("Admin", "Arsiparis"),
    upload.single("file"),
    handleUploadError,
    createBerkas
);

router.put(
    "/:id",
    verifyToken,
    authorizeRoles("Admin", "Arsiparis"),
    upload.single("file"),
    handleUploadError,
    updateBerkas
);

router.delete(
    "/:id",
    verifyToken,
    authorizeRoles("Admin"),
    deleteBerkas
);

module.exports = router;
