const pool = require("../config/database");
const { createAuditLog } = require("../services/auditLogService");

const PEMINJAMAN_AKTIF_STATUSES = ["MENUNGGU", "DISETUJUI", "DIPINJAM"];

const isUserRole = (req) => String(req.user.role || "").toLowerCase() === "user";

const peminjamanSelect = `
    SELECT
        peminjaman.id,
        peminjaman.user_id,
        peminjaman.disetujui_oleh,
        peminjaman.keperluan,
        peminjaman.tanggal_pinjam,
        peminjaman.tanggal_kembali,
        peminjaman.status,

        pemohon.id AS pemohon_id,
        pemohon.nama_lengkap AS pemohon_nama_lengkap,
        pemohon.nama_lengkap AS nama_peminjam,
        pemohon.username AS pemohon_username,
        pemohon.nip AS pemohon_nip,
        pemohon.jabatan AS pemohon_jabatan,

        penyetuju.id AS penyetuju_id,
        penyetuju.nama_lengkap AS penyetuju_nama_lengkap,

        berkas.id AS berkas_id,
        berkas.nomor_berkas,
        berkas.nama_berkas,
        perkara.nomor_perkara,
        perkara.nama_terdakwa

    FROM peminjaman
    JOIN users pemohon
        ON pemohon.id = peminjaman.user_id
    LEFT JOIN users penyetuju
        ON penyetuju.id = peminjaman.disetujui_oleh
    JOIN berkas
        ON peminjaman.berkas_id = berkas.id
    LEFT JOIN perkara
        ON berkas.perkara_id = perkara.id
`;

const cekBerkas = async (berkas_id) => {
    const result = await pool.query(
        `
        SELECT id
        FROM berkas
        WHERE id = $1
        `,
        [berkas_id]
    );

    return result.rows.length > 0;
};

const cekUser = async (user_id) => {
    const result = await pool.query(
        `
        SELECT id
        FROM users
        WHERE id = $1
        `,
        [user_id]
    );

    return result.rows.length > 0;
};

const cekPeminjamanAktif = async ({ berkas_id, exclude_id }) => {
    const values = [berkas_id, PEMINJAMAN_AKTIF_STATUSES];
    let query = `
        SELECT id
        FROM peminjaman
        WHERE berkas_id = $1
        AND status = ANY($2)
    `;

    if (exclude_id) {
        values.push(exclude_id);
        query += ` AND id <> $${values.length}`;
    }

    const result = await pool.query(query, values);

    return result.rows.length > 0;
};

// GET semua peminjaman
const getAllPeminjaman = async (req, res) => {
    try {
        const values = [];
        let query = peminjamanSelect;

        if (isUserRole(req)) {
            values.push(req.user.id);
            query += ` WHERE peminjaman.user_id = $1`;
        }

        query += ` ORDER BY peminjaman.id`;

        const result = await pool.query(query, values);

        res.status(200).json(result.rows);

    } catch (error) {
        res.status(500).json({
            message: "Gagal mengambil data peminjaman",
            error: error.message
        });
    }
};

// GET peminjaman berdasarkan ID
const getPeminjamanById = async (req, res) => {
    try {
        const { id } = req.params;

        const result = await pool.query(
            `
            ${peminjamanSelect}
            WHERE peminjaman.id = $1
            `,
            [id]
        );

        if (result.rows.length === 0) {
            return res.status(404).json({
                message: "Peminjaman tidak ditemukan"
            });
        }

        if (isUserRole(req) && Number(result.rows[0].user_id) !== Number(req.user.id)) {
            return res.status(403).json({
                message: "Akses ditolak"
            });
        }

        res.status(200).json(result.rows[0]);

    } catch (error) {
        res.status(500).json({
            message: "Gagal mengambil data peminjaman",
            error: error.message
        });
    }
};

// POST ajukan peminjaman
const createPeminjaman = async (req, res) => {
    const operationStart = Date.now();
    try {
        const {
            berkas_id,
            keperluan,
            tanggal_pinjam,
            tanggal_kembali
        } = req.body;

        const user_id = req.user.id;

        if (!await cekBerkas(berkas_id)) {
            return res.status(404).json({
                message: "Berkas tidak ditemukan"
            });
        }

        if (!await cekUser(user_id)) {
            return res.status(404).json({
                message: "User tidak ditemukan"
            });
        }

        if (await cekPeminjamanAktif({ berkas_id })) {
            return res.status(400).json({
                message: "Berkas sedang dipinjam dan belum dikembalikan"
            });
        }

        const result = await pool.query(
            `
            INSERT INTO peminjaman
            (
                berkas_id,
                user_id,
                disetujui_oleh,
                keperluan,
                tanggal_pinjam,
                tanggal_kembali,
                status
            )
            VALUES
            ($1, $2, NULL, $3, $4, $5, 'MENUNGGU')
            RETURNING *
            `,
            [
                berkas_id,
                user_id,
                keperluan,
                tanggal_pinjam,
                tanggal_kembali || null
            ]
        );

        await createAuditLog(
            req.user.id,
            "AJUKAN_PEMINJAMAN",
            "PEMINJAMAN",
            result.rows[0].id,
            null, 0, 1, "SUCCESS", null, null, operationStart
        );

        res.status(201).json({
            message: "Permohonan peminjaman berhasil diajukan",
            data: result.rows[0]
        });

    } catch (error) {
        res.status(500).json({
            message: "Gagal menambahkan peminjaman",
            error: error.message
        });
    }
};

const setujuiPeminjaman = async (req, res) => {
    const operationStart = Date.now();
    try {
        const { id } = req.params;

        const cek = await pool.query(
            `
            SELECT *
            FROM peminjaman
            WHERE id = $1
            `,
            [id]
        );

        if (cek.rows.length === 0) {
            return res.status(404).json({
                message: "Data peminjaman tidak ditemukan"
            });
        }

        const peminjaman = cek.rows[0];

        if (peminjaman.status !== "MENUNGGU") {
            return res.status(400).json({
                message: "Peminjaman hanya bisa disetujui dari status MENUNGGU"
            });
        }

        if (await cekPeminjamanAktif({ berkas_id: peminjaman.berkas_id, exclude_id: id })) {
            return res.status(400).json({
                message: "Berkas sedang dipinjam dan belum dikembalikan"
            });
        }

        await pool.query(
            `
            UPDATE peminjaman
            SET
                status = 'DISETUJUI',
                disetujui_oleh = $1
            WHERE id = $2
            `,
            [req.user.id, id]
        );

        const result = await pool.query(
            `
            UPDATE peminjaman
            SET status = 'DIPINJAM'
            WHERE id = $1
            AND status = 'DISETUJUI'
            RETURNING *
            `,
            [id]
        );

        await createAuditLog(
            req.user.id,
            "SETUJUI_PEMINJAMAN",
            "PEMINJAMAN",
            id,
            null, 0, 1, "SUCCESS", null, null, operationStart
        );

        await createAuditLog(
            req.user.id,
            "PINJAM",
            "PEMINJAMAN",
            id,
            null, 0, 1, "SUCCESS", null, null, operationStart
        );

        res.status(200).json({
            message: "Peminjaman berhasil disetujui dan dicatat sedang dipinjam",
            data: result.rows[0]
        });

    } catch (error) {
        res.status(500).json({
            message: "Gagal menyetujui peminjaman",
            error: error.message
        });
    }
};

const catatDipinjam = async (req, res) => {
    const operationStart = Date.now();
    try {
        const { id } = req.params;

        const result = await pool.query(
            `
            UPDATE peminjaman
            SET status = 'DIPINJAM'
            WHERE id = $1
            AND status = 'DISETUJUI'
            RETURNING *
            `,
            [id]
        );

        if (result.rows.length === 0) {
            return res.status(400).json({
                message: "Peminjaman hanya bisa dicatat dipinjam dari status DISETUJUI"
            });
        }

        await createAuditLog(
            req.user.id,
            "PINJAM",
            "PEMINJAMAN",
            id,
            null, 0, 1, "SUCCESS", null, null, operationStart
        );

        res.status(200).json({
            message: "Peminjaman berhasil dicatat sebagai DIPINJAM",
            data: result.rows[0]
        });
    } catch (error) {
        res.status(500).json({
            message: "Gagal mencatat peminjaman",
            error: error.message
        });
    }
};

const tolakPeminjaman = async (req, res) => {
    const operationStart = Date.now();
    try {
        const { id } = req.params;

        const result = await pool.query(
            `
            UPDATE peminjaman
            SET
                status = 'DITOLAK',
                disetujui_oleh = $1
            WHERE id = $2
            AND status = 'MENUNGGU'
            RETURNING *
            `,
            [req.user.id, id]
        );

        if (result.rows.length === 0) {
            return res.status(400).json({
                message: "Peminjaman hanya bisa ditolak dari status MENUNGGU"
            });
        }

        await createAuditLog(
            req.user.id,
            "TOLAK_PEMINJAMAN",
            "PEMINJAMAN",
            id,
            null, 0, 1, "SUCCESS", null, null, operationStart
        );

        res.status(200).json({
            message: "Peminjaman berhasil ditolak",
            data: result.rows[0]
        });
    } catch (error) {
        res.status(500).json({
            message: "Gagal menolak peminjaman",
            error: error.message
        });
    }
};

// PUT kembalikan berkas
const kembalikanBerkas = async (req, res) => {
    const operationStart = Date.now();
    try {
        const { id } = req.params;

        const cek = await pool.query(
            `
            SELECT *
            FROM peminjaman
            WHERE id = $1
            `,
            [id]
        );

        if (cek.rows.length === 0) {
            return res.status(404).json({
                message: "Data peminjaman tidak ditemukan"
            });
        }

        const peminjaman = cek.rows[0];

        if (peminjaman.status === "DIKEMBALIKAN") {
            return res.status(400).json({
                message: "Berkas sudah dikembalikan sebelumnya"
            });
        }

        if (peminjaman.status !== "DIPINJAM") {
            return res.status(400).json({
                message: "Hanya berkas berstatus DIPINJAM yang dapat ditandai sudah dikembalikan"
            });
        }

        const result = await pool.query(
            `
            UPDATE peminjaman
            SET
                status = 'DIKEMBALIKAN',
                tanggal_kembali = CURRENT_DATE
            WHERE id = $1
            RETURNING *
            `,
            [id]
        );

        await createAuditLog(
            req.user.id,
            "PENGEMBALIAN",
            "PEMINJAMAN",
            id,
            null, 0, 1, "SUCCESS", null, null, operationStart
        );

        res.status(200).json({
            message: "Berkas berhasil dikembalikan",
            data: result.rows[0]
        });

    } catch (error) {
        res.status(500).json({
            message: "Gagal mengembalikan berkas",
            error: error.message
        });
    }
};

// PUT update peminjaman oleh arsiparis/admin
const updatePeminjaman = async (req, res) => {
    const operationStart = Date.now();
    try {
        const { id } = req.params;

        const {
            berkas_id,
            user_id,
            disetujui_oleh,
            keperluan,
            tanggal_pinjam,
            tanggal_kembali,
            status
        } = req.body;

        const cekPeminjaman = await pool.query(
            `
            SELECT *
            FROM peminjaman
            WHERE id = $1
            `,
            [id]
        );

        if (cekPeminjaman.rows.length === 0) {
            return res.status(404).json({
                message: "Peminjaman tidak ditemukan"
            });
        }

        const peminjamanLama = cekPeminjaman.rows[0];
        const finalBerkasId = berkas_id ?? peminjamanLama.berkas_id;
        const finalUserId = user_id ?? peminjamanLama.user_id;
        const finalDisetujuiOleh = disetujui_oleh ?? peminjamanLama.disetujui_oleh;

        if (!await cekBerkas(finalBerkasId)) {
            return res.status(404).json({
                message: "Berkas tidak ditemukan"
            });
        }

        if (!await cekUser(finalUserId)) {
            return res.status(404).json({
                message: "User tidak ditemukan"
            });
        }

        if (finalDisetujuiOleh && !await cekUser(finalDisetujuiOleh)) {
            return res.status(404).json({
                message: "User penyetuju tidak ditemukan"
            });
        }

        const finalStatus = status ?? peminjamanLama.status;

        if (
            PEMINJAMAN_AKTIF_STATUSES.includes(finalStatus) &&
            await cekPeminjamanAktif({ berkas_id: finalBerkasId, exclude_id: id })
        ) {
            return res.status(400).json({
                message: "Berkas sedang dipinjam dan belum dikembalikan"
            });
        }

        const result = await pool.query(
            `
            UPDATE peminjaman
            SET
                berkas_id = $1,
                user_id = $2,
                disetujui_oleh = $3,
                keperluan = $4,
                tanggal_pinjam = $5,
                tanggal_kembali = $6,
                status = $7
            WHERE id = $8
            RETURNING *
            `,
            [
                finalBerkasId,
                finalUserId,
                finalDisetujuiOleh,
                keperluan !== undefined ? keperluan : peminjamanLama.keperluan,
                tanggal_pinjam !== undefined ? tanggal_pinjam : peminjamanLama.tanggal_pinjam,
                tanggal_kembali !== undefined ? tanggal_kembali : peminjamanLama.tanggal_kembali,
                finalStatus,
                id
            ]
        );

        await createAuditLog(
            req.user.id,
            "UPDATE_PEMINJAMAN",
            "PEMINJAMAN",
            id,
            null, 0, 1, "SUCCESS", null, null, operationStart
        );

        res.status(200).json({
            message: "Peminjaman berhasil diperbarui",
            data: result.rows[0]
        });

    } catch (error) {
        res.status(500).json({
            message: "Gagal memperbarui peminjaman",
            error: error.message
        });
    }
};

const deletePeminjaman = async (req, res) => {
    const operationStart = Date.now();
    try {
        const { id } = req.params;

        const cekPeminjaman = await pool.query(
            `
            SELECT id
            FROM peminjaman
            WHERE id = $1
            `,
            [id]
        );

        if (cekPeminjaman.rows.length === 0) {
            return res.status(404).json({
                message: "Peminjaman tidak ditemukan"
            });
        }

        const result = await pool.query(
            `
            DELETE FROM peminjaman
            WHERE id = $1
            RETURNING *
            `,
            [id]
        );

        await createAuditLog(
            req.user.id,
            "DELETE_PEMINJAMAN",
            "PEMINJAMAN",
            id,
            null, 0, 1, "SUCCESS", null, null, operationStart
        );

        res.status(200).json({
            message: "Peminjaman berhasil dihapus",
            data: result.rows[0]
        });

    } catch (error) {
        res.status(500).json({
            message: "Gagal menghapus peminjaman",
            error: error.message
        });
    }
};

module.exports = {
    getAllPeminjaman,
    getPeminjamanById,
    createPeminjaman,
    updatePeminjaman,
    setujuiPeminjaman,
    catatDipinjam,
    tolakPeminjaman,
    kembalikanBerkas,
    deletePeminjaman
};


