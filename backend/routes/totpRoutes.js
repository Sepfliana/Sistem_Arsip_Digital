const express = require("express");
const router = express.Router();

const {
    generate2FA,
    verify2FA,
    getDebugCurrentOTP
} = require("../controllers/totpController");

const {
    verifyPendingAuth
} = require("../middleware/authMiddleware");

router.get(
    "/debug-current",
    getDebugCurrentOTP
);

router.post(
    "/generate",
    verifyPendingAuth("setup_2fa"),
    generate2FA
);

router.post(
    "/verify",
    verifyPendingAuth("setup_2fa"),
    verify2FA
);

module.exports = router;
