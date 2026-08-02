const express = require("express");
const fs = require("fs");
const multer = require("multer");
const path = require("path");
const router = express.Router();

const {
    getAllPerkara,
    getPerkaraById,
    getPerkaraCover,
    createPerkara,
    updatePerkara,
    deletePerkara
} = require("../controllers/perkaraController");

const {
    verifyToken
} = require("../middleware/authMiddleware");

const {
    authorizeRoles
} = require("../middleware/roleMiddleware");

const uploadDir = path.join(__dirname, "..", "uploads", "covers");
if (!fs.existsSync(uploadDir)) {
    fs.mkdirSync(uploadDir, { recursive: true });
}

const storage = multer.diskStorage({
    destination: (req, file, cb) => cb(null, uploadDir),
    filename: (req, file, cb) => {
        const safeName = file.originalname.replace(/[^a-zA-Z0-9._-]/g, "_");
        cb(null, `${Date.now()}-${safeName}`);
    }
});

const upload = multer({
    storage,
    fileFilter: (req, file, cb) => {
        const isPdf = file.mimetype === "application/pdf" && path.extname(file.originalname).toLowerCase() === ".pdf";
        if (!isPdf) return cb(new Error("Cover Perkara hanya menerima file PDF"));
        cb(null, true);
    }
});

const handleUploadError = (err, req, res, next) => {
    if (err) {
        return res.status(400).json({ message: err.message || "Upload cover gagal" });
    }

    next();
};

router.get(
    "/",
    verifyToken,
    authorizeRoles("Admin", "Arsiparis", "User"),
    getAllPerkara
);

router.get(
    "/:id",
    verifyToken,
    authorizeRoles("Admin", "Arsiparis", "User"),
    getPerkaraById
);

router.get(
    "/:id/cover",
    verifyToken,
    authorizeRoles("Admin", "Arsiparis", "User"),
    getPerkaraCover
);

router.get(
    "/:id/cover/:coverId",
    verifyToken,
    authorizeRoles("Admin", "Arsiparis", "User"),
    getPerkaraCover
);

router.post(
    "/",
    verifyToken,
    authorizeRoles("Admin", "Arsiparis"),
    upload.array("cover", 10),
    handleUploadError,
    createPerkara
);

router.put(
    "/:id",
    verifyToken,
    authorizeRoles("Admin", "Arsiparis"),
    upload.array("cover", 10),
    handleUploadError,
    updatePerkara
);

router.delete(
    "/:id",
    verifyToken,
    authorizeRoles("Admin"),
    deletePerkara
);

module.exports = router;
