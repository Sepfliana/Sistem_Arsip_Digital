const pool = require("../config/database");
const bcrypt = require("bcrypt");
const { createAuditLog } = require("../services/auditLogService");
const { normalizeEmail, isValidEmail } = require("../utils/accountSecurity");

const resolveRoleId = async ({ role_id, role_name }) => {
    if (role_id) {
        const result = await pool.query("SELECT id FROM roles WHERE id = $1", [role_id]);
        return result.rows[0]?.id || null;
    }

    if (role_name) {
        const result = await pool.query(
            "SELECT id FROM roles WHERE LOWER(nama_peran) = LOWER($1)",
            [role_name]
        );
        return result.rows[0]?.id || null;
    }

    return null;
};

const userSelectColumns = `
    users.id,
    users.role_id,
    users.username,
    users.nama_lengkap,
    users.nip,
    users.jabatan,
    users.foto_profil,
    users.email,
    users.is_active,
    roles.nama_peran,
    roles.nama_peran AS role_name
`;

const normalizeOptionalText = (value) => {
    if (value === undefined) {
        return undefined;
    }

    if (value === "") {
        return null;
    }

    return value;
};

const EMAIL_REQUIRED_MESSAGE = "Email wajib diisi dengan format yang valid";

const buildUserResponse = async (userId) => {
    const result = await pool.query(
        `
        SELECT
            ${userSelectColumns}
        FROM users
        JOIN roles ON users.role_id = roles.id
        WHERE users.id = $1
        `,
        [userId]
    );

    return result.rows[0] || null;
};

// GET semua user
const getAllUsers = async (req, res) => {
    try {
        const result = await pool.query(`
            SELECT
                ${userSelectColumns}
            FROM users
            JOIN roles ON users.role_id = roles.id
            ORDER BY users.id
        `);

        res.status(200).json(result.rows);
    } catch (error) {
        res.status(500).json({
            message: "Gagal mengambil data user",
            error: error.message
        });
    }
};

// GET user berdasarkan ID
const getUserById = async (req, res) => {
    try {
        const { id } = req.params;
        const isAdmin = String(req.user.role || "").toLowerCase() === "admin";

        if (!isAdmin && String(req.user.id) !== String(id)) {
            return res.status(403).json({
                message: "Akses ditolak"
            });
        }

        const user = await buildUserResponse(id);

        if (!user) {
            return res.status(404).json({
                message: "User tidak ditemukan"
            });
        }

        res.status(200).json(user);
    } catch (error) {
        res.status(500).json({
            message: "Gagal mengambil data user",
            error: error.message
        });
    }
};

// POST tambah user
const createUser = async (req, res) => {
    try {
        const {
            role_id,
            role_name,
            username,
            password,
            nama_lengkap,
            nip,
            jabatan,
            foto_profil,
            email
        } = req.body;

        if (!password) {
            return res.status(400).json({
                message: "Password wajib diisi"
            });
        }

        if (!isValidEmail(email)) {
            return res.status(400).json({
                message: EMAIL_REQUIRED_MESSAGE
            });
        }

        const finalRoleId = await resolveRoleId({ role_id, role_name });

        if (!finalRoleId) {
            return res.status(404).json({
                message: "Role tidak ditemukan"
            });
        }

        const passwordHash = await bcrypt.hash(password, 10);

        const result = await pool.query(
            `
            INSERT INTO users
            (
                role_id,
                username,
                password_hash,
                nama_lengkap,
                nip,
                jabatan,
                foto_profil,
                email
            )
            VALUES
            ($1, $2, $3, $4, $5, $6, $7, $8)
            RETURNING id
            `,
            [
                finalRoleId,
                username,
                passwordHash,
                normalizeOptionalText(nama_lengkap),
                normalizeOptionalText(nip),
                normalizeOptionalText(jabatan),
                normalizeOptionalText(foto_profil),
                normalizeEmail(email)
            ]
        );

        const user = await buildUserResponse(result.rows[0].id);

        res.status(201).json({
            message: "User berhasil dibuat",
            data: user
        });

        await createAuditLog(
            req.user.id,
            "CREATE_USER",
            "USER",
            result.rows[0].id
        );

    } catch (error) {

        if (error.code === "23505") {
            return res.status(400).json({
                message: "Username atau email sudah digunakan"
            });
        }

        res.status(500).json({
            message: "Gagal membuat user",
            error: error.message
        });
    }
};

// PUT update user
const updateUser = async (req, res) => {
    try {
        const { id } = req.params;

        const {
            role_id,
            role_name,
            username,
            nama_lengkap,
            nip,
            jabatan,
            foto_profil,
            email,
            password,
            is_active
        } = req.body;

        const cekUser = await pool.query(
            `
            SELECT *
            FROM users
            WHERE id = $1
            `,
            [id]
        );

        if (cekUser.rows.length === 0) {
            return res.status(404).json({
                message: "User tidak ditemukan"
            });
        }

        const userLama = cekUser.rows[0];
        const finalRoleId = await resolveRoleId({ role_id, role_name });

        if ((role_id || role_name) && !finalRoleId) {
            return res.status(404).json({
                message: "Role tidak ditemukan"
            });
        }

        if (email !== undefined && !isValidEmail(email)) {
            return res.status(400).json({
                message: EMAIL_REQUIRED_MESSAGE
            });
        }

        const finalEmail = email !== undefined ? normalizeEmail(email) : userLama.email;
        const isEmailChanged = normalizeEmail(userLama.email) !== normalizeEmail(finalEmail);

        let passwordHash = userLama.password_hash;

        if (password) {
            passwordHash = await bcrypt.hash(password, 10);
        }

        const result = await pool.query(
            `
            UPDATE users
            SET
                role_id = $1,
                username = $2,
                email = $3,
                password_hash = $4,
                is_active = $5,
                nama_lengkap = $6,
                nip = $7,
                jabatan = $8,
                foto_profil = $9,
                is_2fa_enabled = $10,
                totp_secret_encrypted = $11
            WHERE id = $12
            RETURNING id
            `,
            [
                finalRoleId ?? userLama.role_id,
                username ?? userLama.username,
                finalEmail,
                passwordHash,
                is_active ?? userLama.is_active,
                nama_lengkap !== undefined ? normalizeOptionalText(nama_lengkap) : userLama.nama_lengkap,
                nip !== undefined ? normalizeOptionalText(nip) : userLama.nip,
                jabatan !== undefined ? normalizeOptionalText(jabatan) : userLama.jabatan,
                foto_profil !== undefined ? normalizeOptionalText(foto_profil) : userLama.foto_profil,
                isEmailChanged ? false : userLama.is_2fa_enabled,
                isEmailChanged ? null : userLama.totp_secret_encrypted,
                id
            ]
        );

        const user = await buildUserResponse(result.rows[0].id);

        res.status(200).json({
            message: "User berhasil diperbarui",
            data: user
        });

        await createAuditLog(
            req.user.id,
            "UPDATE_USER",
            "USER",
            id
        );

        if (isEmailChanged) {
            await createAuditLog(
                req.user.id,
                "DISABLE_2FA_EMAIL_CHANGED",
                "USER",
                id
            );
        }

    } catch (error) {

        if (error.code === "23505") {
            return res.status(400).json({
                message: "Username atau email sudah digunakan"
            });
        }

        res.status(500).json({
            message: "Gagal memperbarui user",
            error: error.message
        });
    }
};

// DELETE user (soft delete)
const deleteUser = async (req, res) => {
    try {
        const { id } = req.params;

        const result = await pool.query(
            `
            UPDATE users
            SET is_active = false
            WHERE id = $1
            RETURNING id
            `,
            [id]
        );

        if (result.rows.length === 0) {
            return res.status(404).json({
                message: "User tidak ditemukan"
            });
        }

        const user = await buildUserResponse(id);

        res.status(200).json({
            message: "User berhasil dinonaktifkan",
            data: user
        });

        await createAuditLog(
            req.user.id,
            "DELETE_USER",
            "USER",
            id
        );

    } catch (error) {
        res.status(500).json({
            message: "Gagal menonaktifkan user",
            error: error.message
        });
    }
};

module.exports = {
    getAllUsers,
    getUserById,
    createUser,
    updateUser,
    deleteUser
};
