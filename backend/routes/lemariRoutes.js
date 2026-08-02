const express = require("express");
const router = express.Router();

const {
    getAllLemari,
    getLemariById,
    createLemari,
    updateLemari,
    deleteLemari
} = require("../controllers/lemariController");

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
    getAllLemari
);

router.get(
    "/:id",
    verifyToken,
    authorizeRoles("Admin", "Arsiparis", "User"),
    getLemariById
);

router.post(
    "/",
    verifyToken,
    authorizeRoles("Admin", "Arsiparis"),
    createLemari
);

router.put(
    "/:id",
    verifyToken,
    authorizeRoles("Admin", "Arsiparis"),
    updateLemari
);

router.delete(
    "/:id",
    verifyToken,
    authorizeRoles("Admin"),
    deleteLemari
);

module.exports = router;
