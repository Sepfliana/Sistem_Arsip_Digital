const pool = require("../config/database");
const crypto = require("crypto");
const axios = require("axios");
const { getAuditRequestContext, normalizeIpv4 } = require("../utils/auditRequestContext");

// This is the single production integration target. A stale environment value
// containing /predict-stage11 is deliberately normalized to /predict.
const configuredAiServiceUrl = process.env.AI_SERVICE_URL || "http://127.0.0.1:8000";
const AI_SERVICE_URL = new URL("/predict", configuredAiServiceUrl).toString();
const TRAINING_MEAN_IP = "192.168.1.122";

const createAuditLog = async (
    userId, aksi, targetTipe, targetId, detail = null, durasiMs = 0,
    jumlahObjek = 1, status = "SUCCESS", ipAddress = null, device = null,
    startTime = null
) => {
    try {
        const requestContext = getAuditRequestContext();
        const resolvedIp = normalizeIpv4(ipAddress) || requestContext.ipAddress || null;
        const storedIp = resolvedIp || String(ipAddress || requestContext.rawIpAddress || "unknown");
        const resolvedDevice = (typeof device === "string" && device.trim() && device !== "unknown")
            ? device.trim()
            : requestContext.device || "unknown";
        const integrityStatus = detail?.integrity_status || detail?.hasil_hash || (
            aksi === "VERIFIKASI_INTEGRITAS_BERKAS" ? status : "UNKNOWN"
        );
        const lastLog = await pool.query("SELECT hash_entri FROM audit_log ORDER BY id DESC LIMIT 1");
        const hashSebelumnya = lastLog.rows.length ? lastLog.rows[0].hash_entri : null;
        const waktu = new Date();
        const computedDuration = startTime ? Math.max(0, Date.now() - startTime) : durasiMs;
        const data = `${userId}|${aksi}|${targetTipe}|${targetId}|${waktu.toISOString()}|${hashSebelumnya || ""}`;
        const hashEntri = crypto.createHash("sha256").update(data).digest("hex");
        const insertResult = await pool.query(
            `INSERT INTO audit_log
                (user_id, aksi, target_tipe, target_id, waktu, durasi_ms, jumlah_objek, status, ip_address, device, hash_sebelumnya, hash_entri, status_analisis)
             VALUES ($1, $2, $3, $4, $5, $6, $7, $8, $9, $10, $11, $12, $13)
             RETURNING id`,
            [userId, aksi, targetTipe, targetId, waktu, computedDuration, jumlahObjek, status, storedIp, resolvedDevice, hashSebelumnya, hashEntri, "NOT_ANALYZED"]
        );
        const auditLogId = insertResult.rows[0].id;

        try {
            const aiPayload = {
                waktu: waktu.toISOString(), user_id: userId, aksi, target_tipe: targetTipe,
                ip_address: resolvedIp || TRAINING_MEAN_IP, device: resolvedDevice, status,
                durasi_ms: computedDuration, jumlah_objek: jumlahObjek,
                integrity_status: integrityStatus, hasil_hash: integrityStatus,
            };
            console.log(`[AI-TRACE] audit_log_id=${auditLogId} | REQUEST → ${AI_SERVICE_URL}`);
            console.log(`[AI-TRACE] payload:`, JSON.stringify(aiPayload, null, 2));

            const AI_TIMEOUT_MS = Number(process.env.AI_TIMEOUT_MS || 30000);
            const AI_RETRY_COUNT = Number(process.env.AI_RETRY_COUNT || 1);
            let aiResponse = null;
            let lastAiError = null;
            for (let attempt = 0; attempt <= AI_RETRY_COUNT; attempt++) {
                try {
                    aiResponse = await axios.post(AI_SERVICE_URL, aiPayload, {
                        headers: { "Content-Type": "application/json" },
                        timeout: AI_TIMEOUT_MS,
                    });
                    break;
                } catch (retryErr) {
                    lastAiError = retryErr;
                    if (attempt < AI_RETRY_COUNT) {
                        console.log(`[AI-TRACE] audit_log_id=${auditLogId} | Attempt ${attempt + 1} failed, retrying in 2s... (${retryErr.message})`);
                        await new Promise((resolve) => setTimeout(resolve, 2000));
                    }
                }
            }
            if (!aiResponse) throw lastAiError;

            const aiData = aiResponse.data;
            console.log(`[AI-TRACE] audit_log_id=${auditLogId} | RESPONSE: status=${aiData.status} score=${aiData.score} anomaly_score=${aiData.anomaly_score} threshold=${aiData.threshold} risk_level=${aiData.risk_level}`);

            const penjelasan = {
                skor_anomali: Number(aiData.score || 0),
                threshold: Number(aiData.threshold || 0),
                risk_level: aiData.risk_level || "LOW",
                is_anomaly: Boolean(aiData.is_anomaly),
                feature_errors: aiData.feature_errors || {},
                feature_contributions: aiData.feature_contributions || {},
                dominant_features: aiData.dominant_features || [],
                explanation: aiData.explanation || "",
                preprocessing_contract: aiData.preprocessing_contract || "",
            };

            const score = Number(aiData.score || 0);
            const thresholdVal = Number(aiData.threshold || 0);
            const riskLevel = aiData.risk_level || "LOW";

            if (aiData.status === "ANOMALY") {
                const tingkatRisiko = riskLevel === "HIGH" ? "TINGGI" : "SEDANG";
                console.log(`[AI-TRACE] audit_log_id=${auditLogId} | → ANOMALY: INSERT laporan_anomali skor_anomali=${score} tingkat_risiko=${tingkatRisiko}`);
                await pool.query(
                    `INSERT INTO laporan_anomali
                        (user_id, sumber_audit_log_id, skor_anomali, tingkat_risiko, status_keputusan, penjelasan)
                     VALUES ($1, $2, $3, $4, $5, $6)`,
                    [userId, auditLogId, score, tingkatRisiko, "PENDING", JSON.stringify(penjelasan)]
                );
                await pool.query(
                    `UPDATE audit_log
                     SET status_analisis = 'ANALYZED_ANOMALY',
                         anomaly_score = $2,
                         analysis_threshold = $3,
                         risk_level = $4,
                         analysis_detail = $5
                     WHERE id = $1`,
                    [auditLogId, score, thresholdVal, riskLevel, JSON.stringify(penjelasan)]
                );
                console.log(`[AI-TRACE] audit_log_id=${auditLogId} | → DB UPDATED: status_analisis=ANALYZED_ANOMALY anomaly_score=${score}`);
            } else {
                console.log(`[AI-TRACE] audit_log_id=${auditLogId} | → NORMAL: UPDATE audit_log status_analisis=ANALYZED_NORMAL`);
                await pool.query(
                    `UPDATE audit_log
                     SET status_analisis = 'ANALYZED_NORMAL',
                         anomaly_score = $2,
                         analysis_threshold = $3,
                         risk_level = $4,
                         analysis_detail = $5
                     WHERE id = $1`,
                    [auditLogId, score, thresholdVal, riskLevel, JSON.stringify(penjelasan)]
                );
            }
        } catch (error) {
            console.error(`[AI-TRACE] audit_log_id=${auditLogId} | AI ERROR:`, error.message);
            if (error.response) {
                console.error(`[AI-TRACE] audit_log_id=${auditLogId} | AI Status:`, error.response.status);
                console.error(`[AI-TRACE] audit_log_id=${auditLogId} | AI Body:`, JSON.stringify(error.response.data, null, 2));
            }
            await pool.query(
                `UPDATE audit_log SET status_analisis = 'AI_ERROR' WHERE id = $1`,
                [auditLogId]
            );
        }
    } catch (error) {
        console.error("Audit log error:", error.message);
    }
};

const updateAuditLogAnalysis = async (auditLogId, aiData, userId) => {
    const score = Number(aiData.score || 0);
    const thresholdVal = Number(aiData.threshold || 0);
    const riskLevel = aiData.risk_level || "LOW";
    const penjelasan = {
        skor_anomali: score,
        threshold: thresholdVal,
        risk_level: riskLevel,
        is_anomaly: Boolean(aiData.is_anomaly),
        feature_errors: aiData.feature_errors || {},
        feature_contributions: aiData.feature_contributions || {},
        dominant_features: aiData.dominant_features || [],
        explanation: aiData.explanation || "",
        preprocessing_contract: aiData.preprocessing_contract || "",
    };

    if (aiData.status === "ANOMALY") {
        const tingkatRisiko = riskLevel === "HIGH" ? "TINGGI" : "SEDANG";
        const existing = await pool.query(
            `SELECT id FROM laporan_anomali WHERE sumber_audit_log_id = $1`,
            [auditLogId]
        );
        if (existing.rows.length === 0) {
            await pool.query(
                `INSERT INTO laporan_anomali
                    (user_id, sumber_audit_log_id, skor_anomali, tingkat_risiko, status_keputusan, penjelasan)
                 VALUES ($1, $2, $3, $4, $5, $6)`,
                [userId, auditLogId, score, tingkatRisiko, "PENDING", JSON.stringify(penjelasan)]
            );
        } else {
            await pool.query(
                `UPDATE laporan_anomali
                 SET skor_anomali = $2, tingkat_risiko = $3, penjelasan = $4
                 WHERE sumber_audit_log_id = $1`,
                [auditLogId, score, tingkatRisiko, JSON.stringify(penjelasan)]
            );
        }
        await pool.query(
            `UPDATE audit_log
             SET status_analisis = 'ANALYZED_ANOMALY',
                 anomaly_score = $2,
                 analysis_threshold = $3,
                 risk_level = $4,
                 analysis_detail = $5
             WHERE id = $1`,
            [auditLogId, score, thresholdVal, riskLevel, JSON.stringify(penjelasan)]
        );
    } else {
        const existingAnomaly = await pool.query(
            `SELECT id FROM laporan_anomali WHERE sumber_audit_log_id = $1`,
            [auditLogId]
        );
        if (existingAnomaly.rows.length > 0) {
            await pool.query(
                `DELETE FROM laporan_anomali WHERE sumber_audit_log_id = $1`,
                [auditLogId]
            );
        }
        await pool.query(
            `UPDATE audit_log
             SET status_analisis = 'ANALYZED_NORMAL',
                 anomaly_score = $2,
                 analysis_threshold = $3,
                 risk_level = $4,
                 analysis_detail = $5
             WHERE id = $1`,
            [auditLogId, score, thresholdVal, riskLevel, JSON.stringify(penjelasan)]
        );
    }
};

const verifyAuditChain = async () => {
    const result = await pool.query(`
        SELECT id, user_id, aksi, target_tipe, target_id, waktu, durasi_ms,
               jumlah_objek, status, ip_address, device, hash_sebelumnya, hash_entri
        FROM audit_log ORDER BY id
    `);
    let previousHash = null;
    for (const row of result.rows) {
        if (row.hash_sebelumnya !== previousHash) return { valid: false, brokenAt: row.id, reason: "Hash sebelumnya tidak sesuai" };
        const data = `${row.user_id}|${row.aksi}|${row.target_tipe}|${row.target_id}|${new Date(row.waktu).toISOString()}|${row.hash_sebelumnya || ""}`;
        if (row.hash_entri !== crypto.createHash("sha256").update(data).digest("hex")) return { valid: false, brokenAt: row.id, reason: "Hash entri tidak sesuai" };
        previousHash = row.hash_entri;
    }
    return { valid: true, total: result.rows.length };
};

module.exports = { AI_SERVICE_URL, createAuditLog, updateAuditLogAnalysis, verifyAuditChain };
