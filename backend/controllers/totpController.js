const pool = require("../config/database");
const speakeasy = require("speakeasy");
const QRCode = require("qrcode");
const jwt = require("jsonwebtoken");
const { createAuditLog } = require("../services/auditLogService");
const {
    EMAIL_INVALID_MESSAGE,
    normalizeEmail,
    isValidEmail,
    createTotpSecretPayload,
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

const generate2FA = async (req, res) => {
    const operationStart = Date.now();
    try {

        const userId = req.user.id;

        const userResult = await pool.query(
            `
            SELECT
                users.id,
                users.username,
                users.email,
                users.is_active,
                users.is_2fa_enabled,
                users.totp_secret_encrypted
            FROM users
            WHERE users.id = $1
            `,
            [userId]
        );

        if (userResult.rows.length === 0) {
            return res.status(404).json({
                message: "User tidak ditemukan"
            });
        }

        const user = userResult.rows[0];

        if (!user.is_active) {
            return res.status(403).json({
                message: "Akun tidak aktif"
            });
        }

        if (user.is_2fa_enabled) {
            return res.status(409).json({
                message: "2FA sudah aktif"
            });
        }

        if (!isValidEmail(user.email)) {
            return res.status(400).json({
                message: EMAIL_INVALID_MESSAGE
            });
        }

        const accountEmail = normalizeEmail(user.email);
        let secretBase32;
        let otpauthUrl;

        const existingParsed = parseTotpSecretPayload(user.totp_secret_encrypted);
        if (existingParsed.secret && existingParsed.email === accountEmail && !existingParsed.isLegacy) {
            secretBase32 = existingParsed.secret;
            otpauthUrl = speakeasy.otpauthURL({
                secret: secretBase32,
                label: accountEmail,
                issuer: "Sistem Arsip Digital",
                encoding: "base32"
            });
        } else {
            const secret = speakeasy.generateSecret({
                issuer: "Sistem Arsip Digital",
                name: accountEmail
            });
            secretBase32 = secret.base32;
            otpauthUrl = secret.otpauth_url;

            await pool.query(
                `
                UPDATE users
                SET totp_secret_encrypted = $1
                WHERE id = $2
                `,
                [
                    createTotpSecretPayload({
                        secret: secretBase32,
                        email: accountEmail
                    }),
                    userId
                ]
            );
        }

        await createAuditLog(
            userId,
            "SETUP_2FA_GENERATE",
            "USER",
            userId,
            null, 0, 1, "SUCCESS", null, null, operationStart
        );

        const qrCode = await QRCode.toDataURL(
            otpauthUrl
        );

        res.status(200).json({
            message: "QR Code berhasil dibuat",
            qrCode,
            secret: secretBase32
        });

    } catch (error) {
        res.status(500).json({
            message: "Gagal membuat QR Code",
            error: error.message
        });
    }
};

const verify2FA = async (req, res) => {
    console.log("[OTP] Endpoint hit: /totp/verify");
    const operationStart = Date.now();
    try {

        const userId = req.user.id;
        const { token } = req.body;
        console.log("[OTP] Body:", req.body);

        if (!token) {
            return res.status(400).json({
                message: "Kode OTP wajib diisi"
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

        if (user.is_2fa_enabled) {
            return res.status(409).json({
                message: "2FA sudah aktif"
            });
        }

        if (!user.totp_secret_encrypted) {
            return res.status(400).json({
                message: "Secret 2FA belum dibuat"
            });
        }

        if (!isValidEmail(user.email)) {
            return res.status(400).json({
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
                [userId]
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

        await pool.query(
            `
            UPDATE users
            SET is_2fa_enabled = true
            WHERE id = $1
            `,
            [userId]
        );

        await createAuditLog(
            userId,
            "AKTIVASI_OTP",
            "USER",
            userId,
            null, 0, 1, "SUCCESS", null, null, operationStart
        );

        const jwtToken = createLoginToken(user);

        const successResp = {
            message: "2FA berhasil diaktifkan",
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
            message: "Gagal verifikasi 2FA",
            error: error.message
        });
    }
};

const getDebugCurrentOTP = async (req, res) => {
    try {
        const userResult = await pool.query(
            `
            SELECT totp_secret_encrypted
            FROM users
            WHERE totp_secret_encrypted IS NOT NULL
            ORDER BY id DESC
            LIMIT 1
            `
        );

        if (userResult.rows.length === 0) {
            return res.status(404).json({ message: "Tidak ada secret TOTP yang tersimpan di DB" });
        }

        const storedPayload = userResult.rows[0].totp_secret_encrypted;
        const parsed = parseTotpSecretPayload(storedPayload);
        const secretStr = parsed.secret || "";

        const maskedSecret = secretStr.length > 10
            ? secretStr.slice(0, 6) + "..." + secretStr.slice(-4)
            : secretStr;

        const now = new Date();
        const generatedOTP = speakeasy.totp({
            secret: secretStr,
            encoding: "base32"
        });

        const epochSeconds = Math.floor(now.getTime() / 1000);
        const secondsRemaining = 30 - (epochSeconds % 30);

        res.status(200).json({
            serverTimeUTC: now.toISOString(),
            serverTimeLocal: now.toString(),
            secret: maskedSecret,
            generatedOTP,
            secondsRemaining
        });
    } catch (error) {
        res.status(500).json({ error: error.message });
    }
};

module.exports = {
    generate2FA,
    verify2FA,
    getDebugCurrentOTP
};
