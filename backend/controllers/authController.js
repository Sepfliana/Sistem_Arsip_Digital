const pool = require("../config/database");
const bcrypt = require("bcrypt");
const jwt = require("jsonwebtoken");
const speakeasy = require("speakeasy");
const { createAuditLog } = require("../services/auditLogService");
const {
    EMAIL_INVALID_MESSAGE,
    normalizeEmail,
    isValidEmail,
    parseTotpSecretPayload
} = require("../utils/accountSecurity");

const createLoginToken = (user) => {
    return jwt.sign(
        {
            id: user.id,
            username: user.username,
            role: user.nama_peran
        },
        process.env.JWT_SECRET,
        {
            expiresIn: "1d"
        }
    );
};

const createPendingToken = (user, purpose) => {
    return jwt.sign(
        {
            id: user.id,
            username: user.username,
            role: user.nama_peran,
            type: "pending_auth",
            purpose
        },
        process.env.JWT_SECRET,
        {
            expiresIn: "10m"
        }
    );
};

const createPasswordResetToken = (user) => {
    return jwt.sign(
        {
            id: user.id,
            username: user.username,
            email: normalizeEmail(user.email),
            type: "password_reset"
        },
        process.env.JWT_SECRET,
        {
            expiresIn: "10m"
        }
    );
};

const login = async (req, res) => {
    try {
        const { username, password } = req.body || {};

        if (!username || !password) {
            return res.status(400).json({
                message: "Username dan password wajib diisi"
            });
        }

        const result = await pool.query(
            `
            SELECT
                users.id,
                users.username,
                users.email,
                users.password_hash,
                users.is_active,
                users.is_2fa_enabled,
                roles.nama_peran
            FROM users
            JOIN roles
                ON users.role_id = roles.id
            WHERE users.username = $1
            `,
            [username]
        );

        if (result.rows.length === 0) {
            return res.status(401).json({
                message: "Username atau password salah"
            });
        }

        const user = result.rows[0];

        if (!user.is_active) {
            return res.status(403).json({
                message: "Akun tidak aktif"
            });
        }

        const validPassword = await bcrypt.compare(
            password,
            user.password_hash
        );

        if (!validPassword) {
            return res.status(401).json({
                message: "Username atau password salah"
            });
        }

        if (user.is_2fa_enabled) {
            return res.status(200).json({
                message: "OTP diperlukan",
                require2FA: true,
                userId: user.id,
                username: user.username,
                role: user.nama_peran,
                pendingToken: createPendingToken(user, "login_2fa")
            });
        }

        if (!user.is_2fa_enabled) {
            return res.status(200).json({
                message: "Setup 2FA diperlukan",
                requireSetup2FA: true,
                userId: user.id,
                username: user.username,
                role: user.nama_peran,
                pendingToken: createPendingToken(user, "setup_2fa")
            });
        }

        const jwtToken = createLoginToken(user);

        return res.status(200).json({
            message: "Login berhasil",
            token: jwtToken,
            user: {
                id: user.id,
                username: user.username,
                role: user.nama_peran
            }
        });

    } catch (error) {
        return res.status(500).json({
            message: "Login gagal",
            error: error.message
        });
    }
};

const verifyLoginOTP = async (req, res) => {
    console.log("[OTP] Endpoint hit: /auth/verify-login-otp");
    try {
        const { userId, token, pendingToken } = req.body || {};
        console.log("[OTP] Body:", req.body);

        if (!userId || !token || !pendingToken) {
            return res.status(400).json({
                message: "User, OTP, dan token sementara wajib diisi"
            });
        }

        let pendingPayload;

        try {
            pendingPayload = jwt.verify(
                pendingToken,
                process.env.JWT_SECRET
            );
        } catch (error) {
            return res.status(401).json({
                message: "Token sementara tidak valid"
            });
        }

        if (
            pendingPayload.type !== "pending_auth" ||
            pendingPayload.purpose !== "login_2fa" ||
            String(pendingPayload.id) !== String(userId)
        ) {
            return res.status(401).json({
                message: "Token sementara tidak valid"
            });
        }

        const result = await pool.query(
            `
            SELECT
                users.id,
                users.username,
                users.email,
                users.is_active,
                users.is_2fa_enabled,
                users.totp_secret_encrypted,
                roles.nama_peran
            FROM users
            JOIN roles
                ON users.role_id = roles.id
            WHERE users.id = $1
            `,
            [userId]
        );

        if (result.rows.length === 0) {
            return res.status(404).json({
                message: "User tidak ditemukan"
            });
        }

        const user = result.rows[0];

        if (!user.is_active) {
            return res.status(403).json({
                message: "Akun tidak aktif"
            });
        }

        if (!user.is_2fa_enabled || !user.totp_secret_encrypted) {
            return res.status(403).json({
                message: "2FA belum aktif"
            });
        }

        if (!isValidEmail(user.email)) {
            return res.status(403).json({
                message: EMAIL_INVALID_MESSAGE
            });
        }

        const parsedSecret = parseTotpSecretPayload(user.totp_secret_encrypted);
        const accountEmail = normalizeEmail(user.email);

        if (!parsedSecret.secret || parsedSecret.email !== accountEmail || parsedSecret.isLegacy) {
            await pool.query(
                `
                UPDATE users
                SET is_2fa_enabled = false,
                    totp_secret_encrypted = NULL
                WHERE id = $1
                `,
                [user.id]
            );

            return res.status(409).json({
                message: "Email akun berubah atau secret 2FA tidak lagi valid. Silakan lakukan setup 2FA ulang."
            });
        }

        const cleanToken = String(token || "").trim();

        console.log("[OTP] Secret:", parsedSecret.secret);
        console.log("[OTP] Token:", cleanToken);

        const verified = speakeasy.totp.verify({
            secret: parsedSecret.secret,
            encoding: "base32",
            token: cleanToken,
            window: 2
        });

        console.log("[OTP] Verify Result:", verified);

        if (!verified) {
            const resp = { message: "Kode OTP tidak valid" };
            console.log("[OTP] Response:", resp);
            return res.status(400).json(resp);
        }

        const jwtToken = createLoginToken(user);

        await createAuditLog(
            user.id,
            "LOGIN_SUCCESS",
            "USER",
            user.id
        );

        const successResp = {
            message: "Login berhasil",
            token: jwtToken,
            user: {
                id: user.id,
                username: user.username,
                role: user.nama_peran
            }
        };
        console.log("[OTP] Response:", successResp);

        res.status(200).json(successResp);

    } catch (error) {
        console.error("[OTP] Catch Error:", error);
        res.status(500).json({
            message: "Verifikasi OTP gagal",
            error: error.message
        });
    }
};

const logout = async (req, res) => {
    try {
        await createAuditLog(
            req.user.id,
            "LOGOUT",
            "USER",
            req.user.id
        );

        res.status(200).json({
            message: "Logout berhasil"
        });
    } catch (error) {
        res.status(500).json({
            message: "Logout gagal",
            error: error.message
        });
    }
};

const requestPasswordReset = async (req, res) => {
    try {
        const { username, email } = req.body || {};

        if (!username || !email) {
            return res.status(400).json({
                message: "Username dan email wajib diisi"
            });
        }

        if (!isValidEmail(email)) {
            return res.status(400).json({
                message: "Format email tidak valid"
            });
        }

        const requestedEmail = normalizeEmail(email);

        const result = await pool.query(
            `
            SELECT
                id,
                username,
                email,
                is_active
            FROM users
            WHERE username = $1
              AND LOWER(email) = LOWER($2)
            `,
            [username, requestedEmail]
        );

        if (result.rows.length === 0) {
            return res.status(404).json({
                message: "Data akun tidak ditemukan"
            });
        }

        const user = result.rows[0];

        if (!isValidEmail(user.email) || normalizeEmail(user.email) !== requestedEmail) {
            return res.status(404).json({
                message: "Data akun tidak ditemukan"
            });
        }

        if (!user.is_active) {
            return res.status(403).json({
                message: "Akun tidak aktif"
            });
        }

        const resetToken = createPasswordResetToken(user);

        await createAuditLog(
            user.id,
            "REQUEST_RESET_PASSWORD",
            "USER",
            user.id
        );

        return res.status(200).json({
            message: "Verifikasi akun berhasil",
            resetToken
        });
    } catch (error) {
        return res.status(500).json({
            message: "Gagal memproses lupa password",
            error: error.message
        });
    }
};

const resetPassword = async (req, res) => {
    try {
        const { resetToken, password } = req.body || {};

        if (!resetToken || !password) {
            return res.status(400).json({
                message: "Token reset dan password baru wajib diisi"
            });
        }

        if (String(password).length < 6) {
            return res.status(400).json({
                message: "Password minimal 6 karakter"
            });
        }

        let payload;

        try {
            payload = jwt.verify(resetToken, process.env.JWT_SECRET);
        } catch (error) {
            return res.status(401).json({
                message: "Token reset tidak valid atau kedaluwarsa"
            });
        }

        if (payload.type !== "password_reset") {
            return res.status(401).json({
                message: "Token reset tidak valid"
            });
        }

        if (!isValidEmail(payload.email)) {
            return res.status(401).json({
                message: "Token reset tidak valid"
            });
        }

        const userResult = await pool.query(
            `
            SELECT id, email, is_active
            FROM users
            WHERE id = $1
            `,
            [payload.id]
        );

        if (userResult.rows.length === 0 || !userResult.rows[0].is_active) {
            return res.status(404).json({
                message: "User tidak ditemukan atau tidak aktif"
            });
        }

        if (normalizeEmail(userResult.rows[0].email) !== normalizeEmail(payload.email)) {
            return res.status(401).json({
                message: "Token reset tidak valid karena email akun berubah"
            });
        }

        const passwordHash = await bcrypt.hash(password, 10);
        const result = await pool.query(
            `
            UPDATE users
            SET password_hash = $1
            WHERE id = $2
              AND is_active = true
            RETURNING id
            `,
            [passwordHash, payload.id]
        );

        if (result.rows.length === 0) {
            return res.status(404).json({
                message: "User tidak ditemukan atau tidak aktif"
            });
        }

        await createAuditLog(
            payload.id,
            "RESET_PASSWORD",
            "USER",
            payload.id
        );

        return res.status(200).json({
            message: "Password berhasil diperbarui"
        });
    } catch (error) {
        return res.status(500).json({
            message: "Gagal mengubah password",
            error: error.message
        });
    }
};

module.exports = {
    login,
    verifyLoginOTP,
    logout,
    requestPasswordReset,
    resetPassword
};
