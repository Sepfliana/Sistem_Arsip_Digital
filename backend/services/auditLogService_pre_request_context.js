const pool = require("../config/database");
const crypto = require("crypto");
const axios = require("axios");

// Production is deliberately pinned to the sole final FastAPI route.  Even a
// stale endpoint value such as /predict-stage11 is normalized to /predict.
const configuredAiServiceUrl = process.env.AI_SERVICE_URL || "http://127.0.0.1:8000";
const AI_SERVICE_URL = new URL("/predict", configuredAiServiceUrl).toString();

const createAuditLog = async (
    userId,
    aksi,
    targetTipe,
    targetId,
    detail = null,
    durasiMs = 0,
    jumlahObjek = 1,
    status = "SUCCESS",
    ipAddress = "unknown",
    device = "unknown"
) => {
    try {
        const integrityStatus = detail?.integrity_status || detail?.hasil_hash || (
            aksi === "VERIFIKASI_INTEGRITAS_BERKAS" ? status : "UNKNOWN"
        );

        const lastLog = await pool.query(`
            SELECT hash_entri
            FROM audit_log
            ORDER BY id DESC
            LIMIT 1
        `);
        const hashSebelumnya = lastLog.rows.length > 0 ? lastLog.rows[0].hash_entri : null;
        const waktu = new Date();
        const data = `${userId}|${aksi}|${targetTipe}|${targetId}|${waktu.toISOString()}|${hashSebelumnya || ""}`;
        const hashEntri = crypto.createHash("sha256").update(data).digest("hex");

        const insertResult = await pool.query(
            `
            INSERT INTO audit_log
            (
                user_id, aksi, target_tipe, target_id, waktu, durasi_ms,
                jumlah_objek, status, ip_address, device, hash_sebelumnya, hash_entri
            )
            VALUES ($1, $2, $3, $4, $5, $6, $7, $8, $9, $10, $11, $12)
            RETURNING id
            `,
            [userId, aksi, targetTipe, targetId, waktu, durasiMs, jumlahObjek, status, ipAddress, device, hashSebelumnya, hashEntri]
        );
        const auditLogId = insertResult.rows[0].id;

        try {
            const aiPayload = {
                waktu: waktu.toISOString(),
                user_id: userId,
                aksi,
                target_tipe: targetTipe,
                ip_address: ipAddress,
                device,
                status,
                durasi_ms: durasiMs,
                jumlah_objek: jumlahObjek,
                integrity_status: integrityStatus,
                hasil_hash: integrityStatus,
            };
            const aiResponse = await axios.post(AI_SERVICE_URL, aiPayload, {
                headers: { "Content-Type": "application/json" },
            });

            if (aiResponse.data?.status === "ANOMALY") {
                const score = Number(aiResponse.data.score || 0);
                // Risk is classified by the final service and remains separate
                // from the unweighted anomaly score and threshold decision.
                const tingkatRisiko = aiResponse.data.risk_level === "HIGH" ? "TINGGI" : "SEDANG";
                await pool.query(
                    `
                    INSERT INTO laporan_anomali
                    (
                        user_id, sumber_audit_log_id, skor_anomali, tingkat_risiko, status_keputusan
                    )
                    VALUES ($1, $2, $3, $4, $5)
                    `,
                    [userId, auditLogId, score, tingkatRisiko, "PENDING"]
                );
            }
        } catch (error) {
            console.error("AI Service Error:", error.message);
            if (error.response) {
                console.error("AI Service Status:", error.response.status);
                console.error("AI Service Response:", JSON.stringify(error.response.data, null, 2));
            }
        }
    } catch (error) {
        console.error("Audit log error:", error.message);
    }
};

const verifyAuditChain = async () => {
    const result = await pool.query(`
        SELECT
            id, user_id, aksi, target_tipe, target_id, waktu, durasi_ms,
            jumlah_objek, status, ip_address, device, hash_sebelumnya, hash_entri
        FROM audit_log
        ORDER BY id
    `);
    let previousHash = null;
    for (const row of result.rows) {
        if (row.hash_sebelumnya !== previousHash) {
            return { valid: false, brokenAt: row.id, reason: "Hash sebelumnya tidak sesuai" };
        }
        const waktu = new Date(row.waktu).toISOString();
        const data = `${row.user_id}|${row.aksi}|${row.target_tipe}|${row.target_id}|${waktu}|${row.hash_sebelumnya || ""}`;
        const expectedHash = crypto.createHash("sha256").update(data).digest("hex");
        if (row.hash_entri !== expectedHash) {
            return { valid: false, brokenAt: row.id, reason: "Hash entri tidak sesuai" };
        }
        previousHash = row.hash_entri;
    }
    return { valid: true, total: result.rows.length };
};

module.exports = { createAuditLog, verifyAuditChain };
