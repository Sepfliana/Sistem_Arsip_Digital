/**
 * Standalone backfill script — fixes AI_ERROR records and syncs laporan_anomali.
 * Usage: node backfill_run.js
 */
const pool = require("./config/database");
const axios = require("axios");

const configuredAiServiceUrl = process.env.AI_SERVICE_URL || "http://127.0.0.1:8000";
const AI_BATCH_URL = new URL("/predict-batch", configuredAiServiceUrl).toString();
const AI_PREDICT_URL = new URL("/predict", configuredAiServiceUrl).toString();
const AI_HEALTH_URL = new URL("/health", configuredAiServiceUrl).toString();
const TRAINING_MEAN_IP = "192.168.1.122";

const net = require("net");
const normalizeIpForAi = (ip) => {
    if (!ip || ip === "unknown") return TRAINING_MEAN_IP;
    const cleaned = String(ip).replace(/^::ffff:/, "");
    if (cleaned === "::1") return "127.0.0.1";
    if (net.isIP(cleaned) === 4) return cleaned;
    return TRAINING_MEAN_IP;
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

const analyzeRecords = async (records, label) => {
    if (records.length === 0) {
        console.log(`[BACKFILL] ${label}: 0 records to process.`);
        return { total: 0, processed: 0, errors: 0 };
    }

    let useBatchMode = true;
    try {
        await axios.post(AI_BATCH_URL, { records: [] }, { timeout: 5000 });
    } catch (e) {
        if (e.response && e.response.status === 404) {
            useBatchMode = false;
        } else if (e.response && e.response.status === 422) {
            useBatchMode = true;
        } else {
            useBatchMode = false;
        }
    }

    console.log(`[BACKFILL] ${label}: ${records.length} records, mode=${useBatchMode ? "batch" : "individual"}`);
    let totalProcessed = 0;
    let totalErrors = 0;
    const BATCH_SIZE = 50;

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
                        await pool.query(`UPDATE audit_log SET status_analisis = 'AI_ERROR' WHERE id = $1`, [result.audit_log_id]);
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
                        console.error(`[BACKFILL] Failed to update audit_log ${result.audit_log_id}:`, updateErr.message);
                    }
                }
            } catch (batchErr) {
                totalErrors += batch.length;
                console.error(`[BACKFILL] Batch error for records ${i}-${i + batch.length}:`, batchErr.message);
                for (const r of batch) {
                    await pool.query(`UPDATE audit_log SET status_analisis = 'AI_ERROR' WHERE id = $1`, [r.id]);
                }
            }
            console.log(`[BACKFILL] ${label} Progress: ${Math.min(i + BATCH_SIZE, records.length)}/${records.length} (processed=${totalProcessed}, errors=${totalErrors})`);
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
                console.error(`[BACKFILL] Individual predict failed for audit_log ${r.id}:`, err.message);
                await pool.query(`UPDATE audit_log SET status_analisis = 'AI_ERROR' WHERE id = $1`, [r.id]);
            }
            if ((i + 1) % 50 === 0 || i === records.length - 1) {
                console.log(`[BACKFILL] ${label} Progress: ${i + 1}/${records.length} (processed=${totalProcessed}, errors=${totalErrors})`);
            }
        }
    }

    console.log(`[BACKFILL] ${label} Complete. total=${records.length} processed=${totalProcessed} errors=${totalErrors}`);
    return { total: records.length, processed: totalProcessed, errors: totalErrors };
};

const syncLaporanAnomali = async () => {
    console.log("\n[SYNC] Checking laporan_anomali consistency with ANALYZED_ANOMALY audit logs...");

    const { rows: missingAnomalies } = await pool.query(`
        SELECT al.id, al.user_id, al.anomaly_score, al.risk_level, al.analysis_detail
        FROM audit_log al
        WHERE al.status_analisis = 'ANALYZED_ANOMALY'
          AND NOT EXISTS (
              SELECT 1 FROM laporan_anomali la WHERE la.sumber_audit_log_id = al.id
          )
        ORDER BY al.id
    `);

    if (missingAnomalies.length === 0) {
        console.log("[SYNC] All ANALYZED_ANOMALY records already have laporan_anomali entries.");
        return 0;
    }

    console.log(`[SYNC] Found ${missingAnomalies.length} ANALYZED_ANOMALY records missing laporan_anomali entries. Creating...`);

    let created = 0;
    for (const row of missingAnomalies) {
        const detail = row.analysis_detail ? (typeof row.analysis_detail === "string" ? JSON.parse(row.analysis_detail) : row.analysis_detail) : {};
        const tingkatRisiko = (row.risk_level === "HIGH") ? "TINGGI" : "SEDANG";
        try {
            await pool.query(
                `INSERT INTO laporan_anomali
                    (user_id, sumber_audit_log_id, skor_anomali, tingkat_risiko, status_keputusan, penjelasan)
                 VALUES ($1, $2, $3, $4, $5, $6)
                 ON CONFLICT DO NOTHING`,
                [row.user_id, row.id, row.anomaly_score, tingkatRisiko, "PENDING", JSON.stringify(detail)]
            );
            created++;
        } catch (e) {
            console.error(`[SYNC] Failed to create laporan_anomali for audit_log ${row.id}:`, e.message);
        }
    }

    console.log(`[SYNC] Created ${created} missing laporan_anomali entries.`);
    return created;
};

const printSummary = async () => {
    const { rows: statusRows } = await pool.query(`
        SELECT status_analisis, COUNT(*) as cnt
        FROM audit_log
        GROUP BY status_analisis
        ORDER BY cnt DESC
    `);
    console.log("\n=== STATUS DISTRIBUTION ===");
    for (const r of statusRows) {
        console.log(`  ${r.status_analisis}: ${r.cnt}`);
    }

    const { rows: completeness } = await pool.query(`
        SELECT
            COUNT(*) as total_audit,
            COUNT(anomaly_score) as has_score,
            COUNT(risk_level) as has_risk,
            COUNT(CASE WHEN status_analisis = 'NOT_ANALYZED' THEN 1 END) as not_analyzed,
            COUNT(CASE WHEN status_analisis = 'AI_ERROR' THEN 1 END) as ai_error,
            COUNT(CASE WHEN risk_level = 'LOW' THEN 1 END) as low,
            COUNT(CASE WHEN risk_level = 'MEDIUM' THEN 1 END) as medium,
            COUNT(CASE WHEN risk_level = 'HIGH' THEN 1 END) as high
        FROM audit_log
    `);
    const c = completeness[0];
    console.log("\n=== COMPLETENESS ===");
    console.log(`  total_audit:     ${c.total_audit}`);
    console.log(`  has_score:       ${c.has_score}`);
    console.log(`  has_risk:        ${c.has_risk}`);
    console.log(`  NOT_ANALYZED:    ${c.not_analyzed}`);
    console.log(`  AI_ERROR:        ${c.ai_error}`);
    console.log(`  LOW:             ${c.low}`);
    console.log(`  MEDIUM:          ${c.medium}`);
    console.log(`  HIGH:            ${c.high}`);

    const { rows: anomali } = await pool.query("SELECT COUNT(*) as cnt FROM laporan_anomali");
    console.log(`\n=== LAPORAN_ANOMALI ===`);
    console.log(`  total: ${anomali[0].cnt}`);

    const { rows: orphanCheck } = await pool.query(`
        SELECT COUNT(*) as cnt FROM laporan_anomali la
        WHERE NOT EXISTS (SELECT 1 FROM audit_log al WHERE al.id = la.sumber_audit_log_id AND al.status_analisis = 'ANALYZED_ANOMALY')
    `);
    console.log(`  orphaned (no matching ANALYZED_ANOMALY): ${orphanCheck[0].cnt}`);
};

(async () => {
    try {
        console.log("=== STATUS SEBELUM ===");
        await printSummary();

        // Step 1: Re-analyze NOT_ANALYZED, AI_ERROR, and ANALYZED_* with null scores
        const { rows: needsAnalysis } = await pool.query(`
            SELECT id, user_id, aksi, target_tipe, target_id, waktu, durasi_ms,
                   jumlah_objek, status, ip_address, device, status_analisis, anomaly_score
            FROM audit_log
            WHERE status_analisis IN ('NOT_ANALYZED', 'AI_ERROR')
               OR (status_analisis LIKE 'ANALYZED_%' AND anomaly_score IS NULL)
            ORDER BY id
        `);

        if (needsAnalysis.length > 0) {
            console.log(`\n=== RE-ANALYZING ${needsAnalysis.length} RECORDS (NOT_ANALYZED + AI_ERROR) ===`);
            await analyzeRecords(needsAnalysis, "RE-ANALYZE");
        } else {
            console.log("\n=== NO RECORDS NEED RE-ANALYSIS ===");
        }

        // Step 2: Sync laporan_anomali for all ANALYZED_ANOMALY
        const synced = await syncLaporanAnomali();

        console.log("\n=== STATUS SESUDAH ===");
        await printSummary();
    } catch (err) {
        console.error("FATAL:", err);
    } finally {
        await pool.end();
    }
})();
