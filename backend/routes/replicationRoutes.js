const express = require("express");
const router = express.Router();

const {
    getReplicationStatus
} = require("../controllers/replicationController");

const {
    verifyToken
} = require("../middleware/authMiddleware");

const {
    authorizeRoles
} = require("../middleware/roleMiddleware");

router.get(
    "/status",
    verifyToken,
    authorizeRoles("Admin"),
    getReplicationStatus
);

module.exports = router;
