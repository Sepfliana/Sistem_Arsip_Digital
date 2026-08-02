const express = require("express");
const router = express.Router();

const {
    getAllAuditLogs,
    verifyAuditLogs,
    getAnomalyReports,
    updateAnomalyDecision
} = require("../controllers/auditLogController");

const {
    verifyToken
} = require("../middleware/authMiddleware");

const {
    authorizeRoles
} = require("../middleware/roleMiddleware");

router.get(
    "/anomali",
    verifyToken,
    authorizeRoles("Admin"),
    getAnomalyReports
);

router.put(
    "/anomali/:id/decision",
    verifyToken,
    authorizeRoles("Admin"),
    updateAnomalyDecision
);

router.get(
    "/",
    verifyToken,
    authorizeRoles("Admin"),
    getAllAuditLogs
);

router.get(
    "/verify-chain",
    verifyToken,
    authorizeRoles("Admin"),
    verifyAuditLogs
);

module.exports = router;
