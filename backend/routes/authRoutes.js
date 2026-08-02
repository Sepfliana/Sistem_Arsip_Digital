const express = require("express");
const router = express.Router();

const {
    login,
    verifyLoginOTP,
    logout,
    requestPasswordReset,
    resetPassword
} = require("../controllers/authController");

const {
    verifyToken
} = require("../middleware/authMiddleware");

router.post("/login", login);
router.post("/forgot-password", requestPasswordReset);
router.post("/reset-password", resetPassword);
router.post("/verify-login-otp", verifyLoginOTP);
router.post("/logout", verifyToken, logout);

module.exports = router;
