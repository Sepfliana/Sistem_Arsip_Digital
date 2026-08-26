const pool = require("../config/database");
const axios = require("axios");
const { verifyAuditChain } = require("../services/auditLogService");
const { createAuditLog, updateAuditLogAnalysis } = require("../services/auditLogService");
const backfillState = require("../services/backfillState");

const configuredAiServiceUrl = process.env.AI_SERVICE_URL || "http://127.0.0.1:8000";
const AI_BATCH_URL = new URL("/predict-batch", configuredAiServiceUrl).toString();
const AI_PREDICT_URL = new URL("/predict", configuredAiServiceUrl).toString();
const TRAINING_MEAN_IP = "192.168.1.122";

const net = require("net");
const normalizeIpForAi = (ip) => {
    if (!ip || ip === "unknown") return TRAINING_MEAN_IP;
    const cleaned = String(ip).replace(/^::ffff:/, "");
    if (cleaned === "::1") return "127.0.0.1";
    if (net.isIP(cleaned) === 4) return cleaned;
    return TRAINING_MEAN_IP;
};

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
                audit_log.status_analisis,
                audit_log.anomaly_score,
                audit_log.analysis_threshold,
                audit_log.risk_level,
                audit_log.analysis_detail,
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
                laporan_anomali.penjelasan,
                audit_log.aksi,
                audit_log.target_tipe,
                audit_log.target_id,
                audit_log.waktu,
                audit_log.status,
                audit_log.ip_address,
                audit_log.device,
                audit_log.status_analisis,
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
    const operationStart = Date.now();
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
            { reason: reason || null },
            0, 1, "SUCCESS", null, null, operationStart
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

const runBackfillAnalysis = async () => {
    const BATCH_SIZE = 50;

    const { rows: records } = await pool.query(`
        SELECT id, user_id, aksi, target_tipe, target_id, waktu, durasi_ms,
               jumlah_objek, status, ip_address, device, status_analisis,
               anomaly_score
        FROM audit_log
        WHERE status_analisis IN ('NOT_ANALYZED', 'AI_ERROR')
           OR (
               status_analisis IN ('ANALYZED_NORMAL', 'ANALYZED_ANOMALY')
               AND (anomaly_score IS NULL OR risk_level IS NULL OR analysis_detail IS NULL)
           )
        ORDER BY id
    `);

    if (records.length === 0) {
        console.log("[AI-BACKFILL] Tidak ada audit log yang perlu dianalisis.");
        const { rows: stats } = await pool.query(
            "SELECT COUNT(*) AS total, COUNT(anomaly_score) AS analyzed FROM audit_log"
        );
        return { total: Number(stats[0].total), processed: 0, errors: 0 };
    }

    let useBatchMode = true;
    try {
        const healthCheck = await axios.get(AI_BATCH_URL.replace("/predict-batch", "/health"), { timeout: 5000 });
        console.log(`[AI-BACKFILL] AI service status: ${healthCheck.data.model}`);
    } catch (e) {
        console.error("[AI-BACKFILL] AI service unreachable:", e.message);
        return { total: records.length, processed: 0, errors: records.length };
    }

    try {
        await axios.post(AI_BATCH_URL, { records: [] }, { timeout: 5000 });
    } catch (e) {
        if (e.response && e.response.status === 404) {
            console.log("[AI-BACKFILL] /predict-batch not available, falling back to individual /predict calls.");
            useBatchMode = false;
        } else if (e.response && e.response.status === 422) {
            useBatchMode = true;
        } else {
            console.log("[AI-BACKFILL] /predict-batch check failed:", e.message, "- falling back to individual /predict calls.");
            useBatchMode = false;
        }
    }

    console.log(`[AI-BACKFILL] Starting re-analysis of ${records.length} records through final VAE pipeline...`);
    let totalProcessed = 0;
    let totalErrors = 0;

    if (useBatchMode) {
        for (let i = 0; i < records.length; i += BATCH_SIZE) {
            const batch = records.slice(i, i + BATCH_SIZE);
                const payload = {
                    records: batch.map((r) => ({
                        audit_log_id: r.id,
                        waktu: new Date(r.waktu).toISOString(),
                        user_id: r.user_id,
                        aksi: r.aksi,
                        status: r.status,
                        device: r.device || "unknown",
                        ip_address: normalizeIpForAi(r.ip_address),
                        durasi_ms: Number(r.durasi_ms || 0),
                        jumlah_objek: Number(r.jumlah_objek || 1),
                    }))
            };

            try {
                const aiResponse = await axios.post(AI_BATCH_URL, payload, {
                    headers: { "Content-Type": "application/json" },
                    timeout: 120000,
                });

                const results = aiResponse.data.results || [];
                for (const result of results) {
                    if (result.status === "ERROR") {
                        totalErrors++;
                        await pool.query(
                            `UPDATE audit_log SET status_analisis = 'AI_ERROR' WHERE id = $1`,
                            [result.audit_log_id]
                        );
                        continue;
                    }
                    try {
                        await updateAuditLogAnalysis(result.audit_log_id, {
                            score: result.anomaly_score,
                            threshold: result.threshold,
                            risk_level: result.risk_level,
                            status: result.status,
                            is_anomaly: result.is_anomaly,
                            feature_errors: result.feature_errors,
                            feature_contributions: result.feature_contributions,
                            dominant_features: result.dominant_features,
                            explanation: result.explanation,
                            preprocessing_contract: result.preprocessing_contract,
                        }, batch.find((r) => String(r.id) === String(result.audit_log_id))?.user_id);
                        totalProcessed++;
                    } catch (updateErr) {
                        totalErrors++;
                        console.error(`[AI-BACKFILL] Failed to update audit_log ${result.audit_log_id}:`, updateErr.message);
                    }
                }
            } catch (batchErr) {
                totalErrors += batch.length;
                console.error(`[AI-BACKFILL] Batch error for records ${i}-${i + batch.length}:`, batchErr.message);
                for (const r of batch) {
                    await pool.query(
                        `UPDATE audit_log SET status_analisis = 'AI_ERROR' WHERE id = $1`,
                        [r.id]
                    );
                }
            }

            console.log(`[AI-BACKFILL] Progress: ${Math.min(i + BATCH_SIZE, records.length)}/${records.length} (processed=${totalProcessed}, errors=${totalErrors})`);
        }
    } else {
        for (let i = 0; i < records.length; i++) {
            const r = records[i];
            const aiPayload = {
                waktu: new Date(r.waktu).toISOString(),
                user_id: r.user_id,
                aksi: r.aksi,
                status: r.status,
                device: r.device || "unknown",
                ip_address: normalizeIpForAi(r.ip_address),
                durasi_ms: Number(r.durasi_ms || 0),
                jumlah_objek: Number(r.jumlah_objek || 1),
            };

            try {
                const aiResponse = await axios.post(AI_PREDICT_URL, aiPayload, {
                    headers: { "Content-Type": "application/json" },
                    timeout: 30000,
                });
                const result = aiResponse.data;
                await updateAuditLogAnalysis(r.id, {
                    score: result.score || result.anomaly_score || 0,
                    threshold: result.threshold,
                    risk_level: result.risk_level,
                    status: result.status,
                    is_anomaly: result.is_anomaly,
                    feature_errors: result.feature_errors,
                    feature_contributions: result.feature_contributions,
                    dominant_features: result.dominant_features,
                    explanation: result.explanation,
                    preprocessing_contract: result.preprocessing_contract,
                }, r.user_id);
                totalProcessed++;
            } catch (err) {
                totalErrors++;
                console.error(`[AI-BACKFILL] Individual predict failed for audit_log ${r.id}:`, err.message);
                await pool.query(
                    `UPDATE audit_log SET status_analisis = 'AI_ERROR' WHERE id = $1`,
                    [r.id]
                );
            }

            if ((i + 1) % 50 === 0 || i === records.length - 1) {
                console.log(`[AI-BACKFILL] Progress: ${i + 1}/${records.length} (processed=${totalProcessed}, errors=${totalErrors})`);
            }
        }
    }

    console.log(`[AI-BACKFILL] Complete. total=${records.length} processed=${totalProcessed} errors=${totalErrors}`);
    return { total: records.length, processed: totalProcessed, errors: totalErrors };
};

const backfillAnalyze = async (req, res) => {
    if (backfillState.isBackfillRunning) {
        return res.status(409).json({
            message: "Backfill sedang berjalan secara otomatis oleh worker. Coba lagi nanti.",
        });
    }
    try {
        const result = await runBackfillAnalysis();
        return res.status(200).json({
            message: "Backfill re-analisis seluruh audit log dengan final VAE pipeline selesai.",
            ...result,
        });
    } catch (error) {
        console.error("[AI-BACKFILL] Fatal error:", error.message);
        return res.status(500).json({
            message: "Gagal melakukan backfill analisis",
            error: error.message,
        });
    }
};

module.exports = {
    getAllAuditLogs,
    verifyAuditLogs,
    getAnomalyReports,
    updateAnomalyDecision,
    backfillAnalyze,
    runBackfillAnalysis,
};
