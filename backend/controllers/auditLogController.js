const pool = require("../config/database");
const { verifyAuditChain } = require("../services/auditLogService");
const { createAuditLog } = require("../services/auditLogService");

const getAllAuditLogs = async (req, res) => {
    try {
        const result = await pool.query(`
            SELECT
                audit_log.id,
                audit_log.user_id,
                users.nama_lengkap,
                COALESCE(NULLIF(users.nama_lengkap, ''), users.username) AS username,
                COALESCE(NULLIF(users.nama_lengkap, ''), users.username) AS nama_pengguna,
                audit_log.aksi,
                audit_log.target_tipe,
                audit_log.target_id,
                audit_log.waktu,
                audit_log.durasi_ms,
                audit_log.jumlah_objek,
                audit_log.status,
                CASE
                    WHEN audit_log.aksi = 'VERIFIKASI_INTEGRITAS_BERKAS'
                        THEN audit_log.status
                    ELSE NULL
                END AS integrity_status,
                audit_log.ip_address,
                audit_log.device,
                audit_log.hash_sebelumnya,
                audit_log.hash_entri
            FROM audit_log
            LEFT JOIN users
                ON audit_log.user_id = users.id
            ORDER BY audit_log.id DESC
        `);

        res.status(200).json(result.rows);
    } catch (error) {
        res.status(500).json({
            message: "Gagal mengambil audit log",
            error: error.message
        });
    }
};

const verifyAuditLogs = async (req, res) => {
    try {
        const result = await verifyAuditChain();

        res.status(200).json(result);
    } catch (error) {
        res.status(500).json({
            message: "Gagal memverifikasi audit log",
            error: error.message
        });
    }
};

const getAnomalyReports = async (req, res) => {
    try {
        const result = await pool.query(`
            SELECT
                laporan_anomali.id,
                laporan_anomali.user_id,
                users.nama_lengkap,
                COALESCE(NULLIF(users.nama_lengkap, ''), users.username) AS username,
                COALESCE(NULLIF(users.nama_lengkap, ''), users.username) AS nama_pengguna,
                laporan_anomali.sumber_audit_log_id,
                laporan_anomali.skor_anomali,
                laporan_anomali.tingkat_risiko,
                laporan_anomali.status_keputusan,
                audit_log.aksi,
                audit_log.target_tipe,
                audit_log.target_id,
                audit_log.waktu,
                audit_log.status,
                CASE
                    WHEN audit_log.aksi = 'VERIFIKASI_INTEGRITAS_BERKAS'
                        THEN audit_log.status
                    ELSE NULL
                END AS integrity_status
            FROM laporan_anomali
            JOIN audit_log
                ON laporan_anomali.sumber_audit_log_id = audit_log.id
            LEFT JOIN users
                ON laporan_anomali.user_id = users.id
            ORDER BY laporan_anomali.id DESC
        `);

        res.status(200).json(result.rows);
    } catch (error) {
        res.status(500).json({
            message: "Gagal mengambil laporan anomali",
            error: error.message
        });
    }
};

const updateAnomalyDecision = async (req, res) => {
    try {
        const { id } = req.params;
        const { decision, reason } = req.body;
        const normalizedDecision = String(decision || "").toUpperCase();
        const allowedDecisions = ["DITERIMA", "OVERRIDE", "SELESAI"];

        if (!allowedDecisions.includes(normalizedDecision)) {
            return res.status(400).json({
                message: "Keputusan anomali tidak valid"
            });
        }

        if (normalizedDecision === "OVERRIDE" && !String(reason || "").trim()) {
            return res.status(400).json({
                message: "Alasan override wajib diisi"
            });
        }

        const result = await pool.query(
            `
            UPDATE laporan_anomali
            SET status_keputusan = $1
            WHERE id = $2
            RETURNING *
            `,
            [normalizedDecision, id]
        );

        if (result.rows.length === 0) {
            return res.status(404).json({
                message: "Laporan anomali tidak ditemukan"
            });
        }

        await createAuditLog(
            req.user.id,
            `KEPUTUSAN_ANOMALI_${normalizedDecision}`,
            "LAPORAN_ANOMALI",
            id,
            { reason: reason || null }
        );

        return res.status(200).json({
            message: "Keputusan anomali berhasil disimpan",
            data: result.rows[0]
        });
    } catch (error) {
        return res.status(500).json({
            message: "Gagal menyimpan keputusan anomali",
            error: error.message
        });
    }
};

module.exports = {
    getAllAuditLogs,
    verifyAuditLogs,
    getAnomalyReports,
    updateAnomalyDecision
};
