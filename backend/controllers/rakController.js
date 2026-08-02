const pool = require("../config/database");
const { createAuditLog } = require("../services/auditLogService");
const {
    recalculateLemari,
    recalculateLocationByRak
} = require("../services/storageLocationService");

const normalizeText = (value) => (typeof value === "string" ? value.trim() : value);

const normalizePositiveInteger = (value) => {
    if (value === undefined || value === null || value === "") {
        return null;
    }

    const numberValue = Number(value);

    if (!Number.isInteger(numberValue) || numberValue <= 0) {
        return null;
    }

    return numberValue;
};

const rakSelect = `
    SELECT
        rak.id,
        rak.nama_rak,
        rak.kapasitas,
        rak.jumlah_perkara,
        rak.status,
        lemari.id AS lemari_id,
        lemari.nama_lemari,
        GREATEST(rak.kapasitas - rak.jumlah_perkara, 0)::int AS sisa_kapasitas,
        (rak.jumlah_perkara = 0) AS is_kosong,
        (rak.jumlah_perkara >= rak.kapasitas) AS is_penuh
    FROM rak
    JOIN lemari ON rak.lemari_id = lemari.id
`;

const getRakDetailById = async (id) => {
    const result = await pool.query(`
        ${rakSelect}
        WHERE rak.id = $1
        GROUP BY rak.id, lemari.id
    `, [id]);

    return result.rows[0];
};

// GET semua rak
const getAllRak = async (req, res) => {
    try {
        const { lemari_id } = req.query;
        const values = [];
        let query = rakSelect;

        if (lemari_id) {
            const normalizedLemariId = normalizePositiveInteger(lemari_id);

            if (normalizedLemariId === null) {
                return res.status(400).json({
                    message: "ID lemari tidak valid"
                });
            }

            values.push(normalizedLemariId);
            query += ` WHERE rak.lemari_id = $1`;
        }

        query += `
            ORDER BY rak.id
        `;

        const result = await pool.query(query, values);

        res.status(200).json(result.rows);

    } catch (error) {
        res.status(500).json({
            message: "Gagal mengambil data rak",
            error: error.message
        });
    }
};

// GET rak berdasarkan ID
const getRakById = async (req, res) => {
    try {
        const id = normalizePositiveInteger(req.params.id);

        if (id === null) {
            return res.status(400).json({
                message: "ID rak tidak valid"
            });
        }

        const result = await pool.query(`
            ${rakSelect}
            WHERE rak.id = $1
        `, [id]);

        if (result.rows.length === 0) {
            return res.status(404).json({
                message: "Rak tidak ditemukan"
            });
        }

        res.status(200).json(result.rows[0]);

    } catch (error) {
        res.status(500).json({
            message: "Gagal mengambil data rak",
            error: error.message
        });
    }
};

// POST rak
const createRak = async (req, res) => {
    try {
        return res.status(400).json({
            message: "Rak dibuat otomatis saat lemari dibuat. Gunakan edit rak untuk mengubah kapasitas."
        });

    } catch (error) {
        res.status(500).json({
            message: "Gagal menambahkan rak",
            error: error.message
        });
    }
};

// PUT update rak
const updateRak = async (req, res) => {
    try {
        const id = normalizePositiveInteger(req.params.id);
        const kapasitas = normalizePositiveInteger(req.body.kapasitas);

        if (id === null) {
            return res.status(400).json({
                message: "ID rak tidak valid"
            });
        }

        if (kapasitas === null) {
            return res.status(400).json({
                message: "Kapasitas rak wajib diisi dengan angka lebih dari 0"
            });
        }

        // Cek rak
        const rakResult = await pool.query(
            `
            SELECT id
            FROM rak
            WHERE id = $1
            `,
            [id]
        );

        if (rakResult.rows.length === 0) {
            return res.status(404).json({
                message: "Rak tidak ditemukan"
            });
        }

        // Update
        const result = await pool.query(
            `
            UPDATE rak
            SET
                kapasitas = $1
            WHERE id = $2
            RETURNING id
            `,
            [kapasitas, id]
        );
        await recalculateLocationByRak(pool, result.rows[0].id);
        const updatedRak = await getRakDetailById(result.rows[0].id);

        res.status(200).json({
            message: "Rak berhasil diperbarui",
            data: updatedRak
        });

        await createAuditLog(req.user.id, "UPDATE_RAK", "RAK", id);

    } catch (error) {

        res.status(500).json({
            message: "Gagal memperbarui rak",
            error: error.message
        });
    }
};

// DELETE rak
const deleteRak = async (req, res) => {
    try {
        const id = normalizePositiveInteger(req.params.id);

        if (id === null) {
            return res.status(400).json({
                message: "ID rak tidak valid"
            });
        }

        const cekPerkara = await pool.query(
            `
            SELECT id
            FROM perkara
            WHERE rak_id = $1
            LIMIT 1
            `,
            [id]
        );

        if (cekPerkara.rows.length > 0) {
            return res.status(400).json({
                message: "Rak masih digunakan oleh perkara dan tidak dapat dihapus"
            });
        }

        const rakBeforeDelete = await pool.query(
            `
            SELECT lemari_id
            FROM rak
            WHERE id = $1
            `,
            [id]
        );

        const result = await pool.query(
            `
            DELETE FROM rak
            WHERE id = $1
            RETURNING *
            `,
            [id]
        );

        if (result.rows.length === 0) {
            return res.status(404).json({
                message: "Rak tidak ditemukan"
            });
        }

        res.status(200).json({
            message: "Rak berhasil dihapus",
            data: result.rows[0]
        });

        if (rakBeforeDelete.rows[0]?.lemari_id) {
            const remainingRak = await pool.query(
                `
                SELECT id
                FROM rak
                WHERE lemari_id = $1
                LIMIT 1
                `,
                [rakBeforeDelete.rows[0].lemari_id]
            );

            if (remainingRak.rows[0]) {
                await recalculateLocationByRak(pool, remainingRak.rows[0].id);
            } else {
                await recalculateLemari(pool, rakBeforeDelete.rows[0].lemari_id);
            }
        }

        await createAuditLog(req.user.id, "DELETE_RAK", "RAK", id);

    } catch (error) {
        res.status(500).json({
            message: "Gagal menghapus rak",
            error: error.message
        });
    }
};

module.exports = {
    getAllRak,
    getRakById,
    createRak,
    updateRak,
    deleteRak
};
