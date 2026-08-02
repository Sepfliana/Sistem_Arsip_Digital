const express = require("express");
const router = express.Router();

const {
    getAllRak,
    getRakById,
    createRak,
    updateRak,
    deleteRak
} = require("../controllers/rakController");

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
    getAllRak
);

router.get(
    "/:id",
    verifyToken,
    authorizeRoles("Admin", "Arsiparis", "User"),
    getRakById
);

router.post(
    "/",
    verifyToken,
    authorizeRoles("Admin", "Arsiparis"),
    createRak
);

router.put(
    "/:id",
    verifyToken,
    authorizeRoles("Admin", "Arsiparis"),
    updateRak
);

router.delete(
    "/:id",
    verifyToken,
    authorizeRoles("Admin"),
    deleteRak
);

module.exports = router;
