const pool = require("../config/database");
const { createAuditLog } = require("../services/auditLogService");
const {
    STATUS_KOSONG,
    recalculateLemari,
    recalculateLocationByRak
} = require("../services/storageLocationService");

const DEFAULT_RAK_CAPACITY = 40;

const normalizeText = (value) => (typeof value === "string" ? value.trim() : value);

const normalizeNonNegativeInteger = (value) => {
    if (value === undefined || value === null || value === "") {
        return 0;
    }

    const numberValue = Number(value);

    if (!Number.isInteger(numberValue) || numberValue < 0) {
        return null;
    }

    return numberValue;
};

const normalizePositiveInteger = (value) => {
    const numberValue = Number(value);

    if (!Number.isInteger(numberValue) || numberValue <= 0) {
        return null;
    }

    return numberValue;
};

// GET semua lemari
const getAllLemari = async (req, res) => {
    try {
        const { search, q } = req.query;
        const searchTerm = normalizeText(search || q);

        let sql = `
            SELECT
                id,
                nama_lemari,
                lokasi,
                jumlah_rak,
                kapasitas_total,
                jumlah_terpakai,
                status
            FROM lemari
        `;
        const params = [];

        if (searchTerm) {
            sql += ` WHERE LOWER(nama_lemari) LIKE $1 OR LOWER(lokasi) LIKE $1`;
            params.push(`%${searchTerm.toLowerCase()}%`);
        }

        sql += ` ORDER BY id`;

        const result = await pool.query(sql, params);

        res.status(200).json(result.rows);

    } catch (error) {
        res.status(500).json({
            message: "Gagal mengambil data lemari",
            error: error.message
        });
    }
};

// GET lemari berdasarkan ID
const getLemariById = async (req, res) => {
    try {
        const id = normalizePositiveInteger(req.params.id);

        if (id === null) {
            return res.status(400).json({
                message: "ID lemari tidak valid"
            });
        }

        const result = await pool.query(
            `
            SELECT
                id,
                nama_lemari,
                lokasi,
                jumlah_rak,
                kapasitas_total,
                jumlah_terpakai,
                status
            FROM lemari
            WHERE id = $1
            `,
            [id]
        );

        if (result.rows.length === 0) {
            return res.status(404).json({
                message: "Data lemari tidak ditemukan"
            });
        }

        const rakResult = await pool.query(
            `
            SELECT
                id,
                lemari_id,
                nama_rak,
                kapasitas,
                jumlah_perkara,
                status
            FROM rak
            WHERE lemari_id = $1
            ORDER BY id
            `,
            [id]
        );

        res.status(200).json({
            ...result.rows[0],
            rak: rakResult.rows
        });

    } catch (error) {
        res.status(500).json({
            message: "Gagal mengambil data lemari",
            error: error.message
        });
    }
};

// POST tambah lemari
const createLemari = async (req, res) => {
    try {
        const nama_lemari = normalizeText(req.body.nama_lemari);
        const lokasi = normalizeText(req.body.lokasi);
        const jumlah_rak = normalizeNonNegativeInteger(req.body.jumlah_rak);

        if (!nama_lemari || !lokasi) {
            return res.status(400).json({
                message: "Nama lemari dan lokasi wajib diisi"
            });
        }

        if (jumlah_rak === null || jumlah_rak <= 0) {
            return res.status(400).json({
                message: "Jumlah rak harus lebih dari 0"
            });
        }

        const client = await pool.connect();
        let createdLemari;

        try {
            await client.query("BEGIN");

            const result = await client.query(
                `
                INSERT INTO lemari
                (
                    nama_lemari,
                    lokasi,
                    jumlah_rak,
                    kapasitas_total,
                    jumlah_terpakai,
                    status
                )
                VALUES
                ($1, $2, $3, $4, 0, $5)
                RETURNING *
                `,
                [
                    nama_lemari,
                    lokasi,
                    jumlah_rak,
                    jumlah_rak * DEFAULT_RAK_CAPACITY,
                    STATUS_KOSONG
                ]
            );

            createdLemari = result.rows[0];

            for (let index = 1; index <= jumlah_rak; index += 1) {
                await client.query(
                    `
                    INSERT INTO rak
                    (
                        lemari_id,
                        nama_rak,
                        kapasitas,
                        jumlah_perkara,
                        status
                    )
                    VALUES ($1, $2, $3, 0, $4)
                    `,
                    [createdLemari.id, `${nama_lemari}-${index}`, DEFAULT_RAK_CAPACITY, STATUS_KOSONG]
                );
            }

            await recalculateLemari(client, createdLemari.id);
            await client.query("COMMIT");
        } catch (error) {
            await client.query("ROLLBACK");
            throw error;
        } finally {
            client.release();
        }

        const detailResult = await pool.query(
            `
            SELECT
                id,
                nama_lemari,
                lokasi,
                jumlah_rak,
                kapasitas_total,
                jumlah_terpakai,
                status
            FROM lemari
            WHERE id = $1
            `,
            [createdLemari.id]
        );

        res.status(201).json({
            message: "Lemari berhasil ditambahkan",
            data: detailResult.rows[0]
        });

        await createAuditLog(req.user.id, "CREATE_LEMARI", "LEMARI", createdLemari.id);

    } catch (error) {
        res.status(500).json({
            message: "Gagal menambahkan lemari",
            error: error.message
        });
    }
};

// PUT update lemari
const updateLemari = async (req, res) => {
    try {
        const id = normalizePositiveInteger(req.params.id);
        const nama_lemari = normalizeText(req.body.nama_lemari);
        const lokasi = normalizeText(req.body.lokasi);
        const jumlah_rak = normalizeNonNegativeInteger(req.body.jumlah_rak);

        if (id === null) {
            return res.status(400).json({
                message: "ID lemari tidak valid"
            });
        }

        if (!nama_lemari || !lokasi) {
            return res.status(400).json({
                message: "Nama lemari dan lokasi wajib diisi"
            });
        }

        if (jumlah_rak === null || jumlah_rak <= 0) {
            return res.status(400).json({
                message: "Jumlah rak harus lebih dari 0"
            });
        }

        const client = await pool.connect();
        let updatedLemari;

        try {
            await client.query("BEGIN");

            const existingResult = await client.query(
                `
                SELECT *
                FROM lemari
                WHERE id = $1
                FOR UPDATE
                `,
                [id]
            );

            if (existingResult.rows.length === 0) {
                await client.query("ROLLBACK");
                return res.status(404).json({
                    message: "Data lemari tidak ditemukan"
                });
            }

            const oldJumlahRak = Number(existingResult.rows[0].jumlah_rak || 0);

            if (jumlah_rak < oldJumlahRak) {
                const removableResult = await client.query(
                    `
                    SELECT id, jumlah_perkara
                    FROM rak
                    WHERE lemari_id = $1
                    ORDER BY id DESC
                    LIMIT $2
                    `,
                    [id, oldJumlahRak - jumlah_rak]
                );

                if (removableResult.rows.some((row) => Number(row.jumlah_perkara || 0) > 0)) {
                    await client.query("ROLLBACK");
                    return res.status(400).json({
                        message: "Jumlah rak tidak dapat dikurangi karena rak yang akan dihapus masih berisi perkara"
                    });
                }

                await client.query(
                    `
                    DELETE FROM rak
                    WHERE id = ANY($1::int[])
                    `,
                    [removableResult.rows.map((row) => row.id)]
                );
            }

            if (jumlah_rak > oldJumlahRak) {
                for (let index = oldJumlahRak + 1; index <= jumlah_rak; index += 1) {
                    await client.query(
                        `
                        INSERT INTO rak
                        (
                            lemari_id,
                            nama_rak,
                            kapasitas,
                            jumlah_perkara,
                            status
                        )
                        VALUES ($1, $2, $3, 0, $4)
                        `,
                        [id, `${nama_lemari}-${index}`, DEFAULT_RAK_CAPACITY, STATUS_KOSONG]
                    );
                }
            }

            await client.query(
                `
                UPDATE rak
                SET nama_rak = $2 || '-' || urutan.nomor
                FROM (
                    SELECT
                        id,
                        ROW_NUMBER() OVER (ORDER BY id) AS nomor
                    FROM rak
                    WHERE lemari_id = $1
                ) AS urutan
                WHERE rak.id = urutan.id
                `,
                [id, nama_lemari]
            );

            const result = await client.query(
                `
                UPDATE lemari
                SET
                    nama_lemari = $1,
                    lokasi = $2,
                    jumlah_rak = $3,
                    kapasitas_total = $4
                WHERE id = $5
                RETURNING *
                `,
                [
                    nama_lemari,
                    lokasi,
                    jumlah_rak,
                    jumlah_rak * DEFAULT_RAK_CAPACITY,
                    id
                ]
            );

            updatedLemari = result.rows[0];
            await recalculateLemari(client, id);
            await client.query("COMMIT");
        } catch (error) {
            await client.query("ROLLBACK");
            throw error;
        } finally {
            client.release();
        }

        const detailResult = await pool.query(
            `
            SELECT
                id,
                nama_lemari,
                lokasi,
                jumlah_rak,
                kapasitas_total,
                jumlah_terpakai,
                status
            FROM lemari
            WHERE id = $1
            `,
            [id]
        );

        res.status(200).json({
            message: "Lemari berhasil diperbarui",
            data: detailResult.rows[0] || updatedLemari
        });

        await createAuditLog(req.user.id, "UPDATE_LEMARI", "LEMARI", id);

    } catch (error) {
        res.status(500).json({
            message: "Gagal memperbarui lemari",
            error: error.message
        });
    }
};

// DELETE lemari
const deleteLemari = async (req, res) => {
    try {
        const id = normalizePositiveInteger(req.params.id);

        if (id === null) {
            return res.status(400).json({
                message: "ID lemari tidak valid"
            });
        }

        const cekPerkara = await pool.query(
            `
            SELECT id
            FROM perkara
            WHERE lemari_id = $1
            LIMIT 1
            `,
            [id]
        );

        if (cekPerkara.rows.length > 0) {
            return res.status(400).json({
                message: "Lemari masih digunakan oleh perkara dan tidak dapat dihapus"
            });
        }

        const client = await pool.connect();
        let deletedLemari;

        try {
            await client.query("BEGIN");

            const rakResult = await client.query(
                `
                SELECT id
                FROM rak
                WHERE lemari_id = $1
                `,
                [id]
            );

            for (const row of rakResult.rows) {
                await recalculateLocationByRak(client, row.id);
            }

            await client.query(
                `
                DELETE FROM rak
                WHERE lemari_id = $1
                `,
                [id]
            );

            const result = await client.query(
                `
                DELETE FROM lemari
                WHERE id = $1
                RETURNING *
                `,
                [id]
            );

            deletedLemari = result.rows[0];
            await client.query("COMMIT");
        } catch (error) {
            await client.query("ROLLBACK");
            throw error;
        } finally {
            client.release();
        }

        if (!deletedLemari) {
            return res.status(404).json({
                message: "Lemari tidak ditemukan"
            });
        }

        await createAuditLog(req.user.id, "DELETE_LEMARI", "LEMARI", id);

        res.status(200).json({
            message: "Lemari berhasil dihapus",
            data: deletedLemari
        });

    } catch (error) {
        res.status(500).json({
            message: "Gagal menghapus lemari",
            error: error.message
        });
    }
};

module.exports = {
    getAllLemari,
    getLemariById,
    createLemari,
    updateLemari,
    deleteLemari
};
