const express = require("express");
const router = express.Router();

const {
    getAllUsers,
    getUserById,
    createUser,
    updateUser,
    deleteUser
} = require("../controllers/userController");

const {
    verifyToken
} = require("../middleware/authMiddleware");

const {
    authorizeRoles
} = require("../middleware/roleMiddleware");

router.get(
    "/",
    verifyToken,
    authorizeRoles("Admin"),
    getAllUsers
);

router.get(
    "/:id",
    verifyToken,
    authorizeRoles("Admin", "Arsiparis", "User"),
    getUserById
);

router.post(
    "/",
    verifyToken,
    authorizeRoles("Admin"),
    createUser
);

router.put(
    "/:id",
    verifyToken,
    authorizeRoles("Admin"),
    updateUser
);

router.delete(
    "/:id",
    verifyToken,
    authorizeRoles("Admin"),
    deleteUser
);

module.exports = router;
