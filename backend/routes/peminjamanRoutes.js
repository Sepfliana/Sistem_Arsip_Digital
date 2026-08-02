const express = require("express");
const router = express.Router();

const {
    getAllPeminjaman,
    getPeminjamanById,
    createPeminjaman,
    updatePeminjaman,
    setujuiPeminjaman,
    catatDipinjam,
    tolakPeminjaman,
    kembalikanBerkas,
    deletePeminjaman
} = require("../controllers/peminjamanController");

const {
    verifyToken
} = require("../middleware/authMiddleware");

const {
    authorizeRoles
} = require("../middleware/roleMiddleware");

router.get(
    "/",
    verifyToken,
    authorizeRoles("Admin", "Arsiparis", "User"),
    getAllPeminjaman
);

router.get(
    "/:id",
    verifyToken,
    authorizeRoles("Admin", "Arsiparis", "User"),
    getPeminjamanById
);

router.post(
    "/",
    verifyToken,
    authorizeRoles("User"),
    createPeminjaman
);

router.put(
    "/:id/setujui",
    verifyToken,
    authorizeRoles("Admin", "Arsiparis"),
    setujuiPeminjaman
);

router.put(
    "/:id/pinjam",
    verifyToken,
    authorizeRoles("Admin", "Arsiparis"),
    catatDipinjam
);

router.put(
    "/:id/tolak",
    verifyToken,
    authorizeRoles("Admin", "Arsiparis"),
    tolakPeminjaman
);

router.put(
    "/:id",
    verifyToken,
    authorizeRoles("Admin", "Arsiparis"),
    updatePeminjaman
);

router.put(
    "/:id/kembalikan",
    verifyToken,
    authorizeRoles("Admin", "Arsiparis"),
    kembalikanBerkas
);

router.delete(
    "/:id",
    verifyToken,
    authorizeRoles("Admin", "Arsiparis"),
    deletePeminjaman
);

module.exports = router;
