/**
 * Standalone validation script for Anomali.jsx logic functions.
 * Run: node frontend/src/pages/Anomali/__tests__/anomali-logic-validation.mjs
 *
 * Tests the FIXED getRiskCategory, getReviewStatus, getCategoryBadge logic
 * against the three required cases plus edge cases.
 *
 * This file duplicates the pure functions extracted from Anomali.jsx
 * to validate correctness without requiring a React/Vite runtime.
 */

let passed = 0;
let failed = 0;

function assert(condition, label, detail) {
    if (condition) {
        passed++;
        console.log(`  PASS: ${label}`);
    } else {
        failed++;
        console.error(`  FAIL: ${label}${detail ? ` — ${detail}` : ""}`);
    }
}

// ─── Extracted logic (mirrors the FIXED Anomali.jsx) ───

function getRiskCategory(item) {
    if (!item) return "Normal";
    const s = String(item.status_analisis || "").toUpperCase();
    if (s === "NOT_ANALYZED" || s === "AI_ERROR") return null;
    if (!item.anomalyId) return "Normal";

    const risk = String(item.tingkat_risiko || "").toUpperCase();

    if (risk.includes("HIGH") || risk.includes("TINGGI")) return "High Risk";
    return "Perlu Ditinjau";
}

function getReviewStatus(item) {
    if (!item.anomalyId) return "Selesai";

    const status = String(item.status_keputusan || "").toUpperCase();
    if (status === "DITERIMA") return "Sedang Ditinjau";
    if (status === "SELESAI" || status === "OVERRIDE") return "Selesai";
    return "Belum Ditinjau";
}

function getCategoryBadge(category) {
    if (category === "High Risk") return { className: "danger", label: "High Risk" };
    if (category === "Perlu Ditinjau") return { className: "warning", label: "Perlu Ditinjau" };
    if (category === null) return { className: "neutral", label: "Belum Dianalisis" };
    return { className: "success", label: "Normal" };
}

function renderScore(item) {
    return item.anomalyId ? Number(item.skor_anomali || 0).toFixed(2) : "-";
}

// ─── Merge logic (mirrors Anomali.jsx analysisRows) ───

function mergeRow(log, report) {
    return {
        ...log,
        ...(report || {}),
        auditLogId: log.id,
        anomalyId: report?.id || null,
        skor_anomali: report?.skor_anomali || 0,
        tingkat_risiko: report?.tingkat_risiko || "Normal",
        status_keputusan: report?.status_keputusan || "SELESAI",
        status_analisis: log.status_analisis || "NOT_ANALYZED"
    };
}

// ─── Test data ───

const auditLogNormal = {
    id: 101,
    user_id: 1,
    nama_pengguna: "admin",
    aksi: "LOGIN_SUCCESS",
    waktu: "2026-08-25T08:51:00.000Z",
    status: "SUCCESS",
    status_analisis: "ANALYZED_NORMAL"
};

const auditLogAnomaly = {
    id: 205,
    user_id: 1,
    nama_pengguna: "admin",
    aksi: "LOGIN_SUCCESS",
    waktu: "2026-08-24T14:46:00.000Z",
    status: "SUCCESS",
    status_analisis: "ANALYZED_ANOMALY"
};

const auditLogLunaLogout = {
    id: 203,
    user_id: 2,
    nama_pengguna: "Luna",
    aksi: "LOGOUT",
    waktu: "2026-08-24T14:45:00.000Z",
    status: "SUCCESS",
    status_analisis: "ANALYZED_ANOMALY"
};

const reportHighTinggi = {
    id: 50,
    sumber_audit_log_id: 205,
    user_id: 1,
    skor_anomali: 9.94,
    tingkat_risiko: "TINGGI",
    status_keputusan: "PENDING"
};

const reportHighEnglish = {
    id: 51,
    sumber_audit_log_id: 203,
    user_id: 2,
    skor_anomali: 8.91,
    tingkat_risiko: "HIGH",
    status_keputusan: "PENDING"
};

const reportMediumSedang = {
    id: 52,
    sumber_audit_log_id: 999,
    user_id: 3,
    skor_anomali: 2.10,
    tingkat_risiko: "SEDANG",
    status_keputusan: "PENDING"
};

const reportMediumAccepted = {
    id: 53,
    sumber_audit_log_id: 998,
    user_id: 3,
    skor_anomali: 1.80,
    tingkat_risiko: "SEDANG",
    status_keputusan: "DITERIMA"
};

const reportMediumDone = {
    id: 54,
    sumber_audit_log_id: 997,
    user_id: 3,
    skor_anomali: 2.00,
    tingkat_risiko: "MEDIUM",
    status_keputusan: "SELESAI"
};

const reportMediumOverride = {
    id: 55,
    sumber_audit_log_id: 996,
    user_id: 3,
    skor_anomali: 1.90,
    tingkat_risiko: "MEDIUM",
    status_keputusan: "OVERRIDE"
};

// ─── CASE A: NORMAL tanpa anomalyId ───

console.log("\n=== CASE A: Audit log NORMAL tanpa anomalyId ===");

const rowNormal = mergeRow(auditLogNormal, undefined);

assert(rowNormal.anomalyId === null, "anomalyId is null", `got ${rowNormal.anomalyId}`);
assert(renderScore(rowNormal) === "-", "score displays '-'", `got ${renderScore(rowNormal)}`);
assert(getRiskCategory(rowNormal) === "Normal", "kategori is 'Normal'", `got ${getRiskCategory(rowNormal)}`);
assert(getReviewStatus(rowNormal) === "Selesai", "status is 'Selesai'", `got ${getReviewStatus(rowNormal)}`);

const badgeNormal = getCategoryBadge(getRiskCategory(rowNormal));
assert(badgeNormal.className === "success", "badge className is 'success'", `got ${badgeNormal.className}`);
assert(badgeNormal.label === "Normal", "badge label is 'Normal'", `got ${badgeNormal.label}`);

// ─── CASE B: ANOMALY HIGH (TINGGI from backend) ───

console.log("\n=== CASE B: ANOMALY HIGH (tingkat_risiko = 'TINGGI', score = 9.94) ===");

const rowHighTinggi = mergeRow(auditLogAnomaly, reportHighTinggi);

assert(rowHighTinggi.anomalyId === 50, "anomalyId is set", `got ${rowHighTinggi.anomalyId}`);
assert(renderScore(rowHighTinggi) === "9.94", "score displays '9.94'", `got ${renderScore(rowHighTinggi)}`);
assert(getRiskCategory(rowHighTinggi) === "High Risk", "kategori is 'High Risk'", `got ${getRiskCategory(rowHighTinggi)}`);
assert(getReviewStatus(rowHighTinggi) === "Belum Ditinjau", "status is 'Belum Ditinjau' (PENDING)", `got ${getReviewStatus(rowHighTinggi)}`);

const badgeHigh = getCategoryBadge(getRiskCategory(rowHighTinggi));
assert(badgeHigh.className === "danger", "badge className is 'danger'", `got ${badgeHigh.className}`);
assert(badgeHigh.label === "High Risk", "badge label is 'High Risk'", `got ${badgeHigh.label}`);

// ─── CASE B2: ANOMALY HIGH (English "HIGH") ───

console.log("\n=== CASE B2: ANOMALY HIGH (tingkat_risiko = 'HIGH', score = 8.91) ===");

const rowHighEnglish = mergeRow(auditLogLunaLogout, reportHighEnglish);

assert(rowHighEnglish.anomalyId === 51, "anomalyId is set", `got ${rowHighEnglish.anomalyId}`);
assert(renderScore(rowHighEnglish) === "8.91", "score displays '8.91'", `got ${renderScore(rowHighEnglish)}`);
assert(getRiskCategory(rowHighEnglish) === "High Risk", "kategori is 'High Risk'", `got ${getRiskCategory(rowHighEnglish)}`);
assert(getReviewStatus(rowHighEnglish) === "Belum Ditinjau", "status is 'Belum Ditinjau' (PENDING)", `got ${getReviewStatus(rowHighEnglish)}`);

// ─── CASE C: ANOMALY MEDIUM (SEDANG) ───

console.log("\n=== CASE C: ANOMALY MEDIUM (tingkat_risiko = 'SEDANG', score = 2.10, PENDING) ===");

const rowMedium = mergeRow(
    { id: 999, aksi: "LOGIN_SUCCESS", waktu: "2026-08-24T10:00:00.000Z", status_analisis: "ANALYZED_ANOMALY" },
    reportMediumSedang
);

assert(rowMedium.anomalyId === 52, "anomalyId is set", `got ${rowMedium.anomalyId}`);
assert(renderScore(rowMedium) === "2.10", "score displays '2.10'", `got ${renderScore(rowMedium)}`);
assert(getRiskCategory(rowMedium) === "Perlu Ditinjau", "kategori is 'Perlu Ditinjau'", `got ${getRiskCategory(rowMedium)}`);
assert(getReviewStatus(rowMedium) === "Belum Ditinjau", "status is 'Belum Ditinjau' (PENDING)", `got ${getReviewStatus(rowMedium)}`);

const badgeMedium = getCategoryBadge(getRiskCategory(rowMedium));
assert(badgeMedium.className === "warning", "badge className is 'warning'", `got ${badgeMedium.className}`);

// ─── CASE C2: ANOMALY MEDIUM (English "MEDIUM") ───

console.log("\n=== CASE C2: ANOMALY MEDIUM (tingkat_risiko = 'MEDIUM', score = 2.00, SELESAI) ===");

const rowMediumEnglish = mergeRow(
    { id: 997, aksi: "LOGIN_SUCCESS", waktu: "2026-08-24T10:00:00.000Z", status_analisis: "ANALYZED_ANOMALY" },
    reportMediumDone
);

assert(getRiskCategory(rowMediumEnglish) === "Perlu Ditinjau", "kategori is 'Perlu Ditinjau'", `got ${getRiskCategory(rowMediumEnglish)}`);
assert(getReviewStatus(rowMediumEnglish) === "Selesai", "status is 'Selesai' (SELESAI)", `got ${getReviewStatus(rowMediumEnglish)}`);

// ─── CASE C3: ANOMALY MEDIUM (DITERIMA) ───

console.log("\n=== CASE C3: ANOMALY MEDIUM (tingkat_risiko = 'SEDANG', DITERIMA) ===");

const rowMediumAccepted = mergeRow(
    { id: 998, aksi: "LOGIN_SUCCESS", waktu: "2026-08-24T10:00:00.000Z", status_analisis: "ANALYZED_ANOMALY" },
    reportMediumAccepted
);

assert(getRiskCategory(rowMediumAccepted) === "Perlu Ditinjau", "kategori is 'Perlu Ditinjau'", `got ${getRiskCategory(rowMediumAccepted)}`);
assert(getReviewStatus(rowMediumAccepted) === "Sedang Ditinjau", "status is 'Sedang Ditinjau' (DITERIMA)", `got ${getReviewStatus(rowMediumAccepted)}`);

// ─── CASE C4: ANOMALY MEDIUM (OVERRIDE) ───

console.log("\n=== CASE C4: ANOMALY MEDIUM (tingkat_risiko = 'MEDIUM', OVERRIDE) ===");

const rowMediumOverride = mergeRow(
    { id: 996, aksi: "LOGIN_SUCCESS", waktu: "2026-08-24T10:00:00.000Z", status_analisis: "ANALYZED_ANOMALY" },
    reportMediumOverride
);

assert(getRiskCategory(rowMediumOverride) === "Perlu Ditinjau", "kategori is 'Perlu Ditinjau'", `got ${getRiskCategory(rowMediumOverride)}`);
assert(getReviewStatus(rowMediumOverride) === "Selesai", "status is 'Selesai' (OVERRIDE)", `got ${getReviewStatus(rowMediumOverride)}`);

// ─── Regression: null/undefined input ───

console.log("\n=== REGRESSION: null/undefined input ===");

assert(getRiskCategory(null) === "Normal", "null input → 'Normal'", `got ${getRiskCategory(null)}`);
assert(getRiskCategory(undefined) === "Normal", "undefined input → 'Normal'", `got ${getRiskCategory(undefined)}`);
assert(getRiskCategory({}) === "Normal", "empty object → 'Normal' (no anomalyId)", `got ${getRiskCategory({})}`);
assert(getReviewStatus({}) === "Selesai", "empty object → 'Selesai' (no anomalyId)", `got ${getReviewStatus({})}`);

// ─── Regression: anomalyId present but score = 0 and no risk level ───

console.log("\n=== REGRESSION: anomalyId present but empty risk/score ===");

const rowEmptyAnomaly = mergeRow(
    { id: 800, aksi: "LOGIN_SUCCESS", waktu: "2026-08-24T10:00:00.000Z", status_analisis: "ANALYZED_ANOMALY" },
    { id: 200, sumber_audit_log_id: 800, skor_anomali: 0, tingkat_risiko: "", status_keputusan: "PENDING" }
);

assert(getRiskCategory(rowEmptyAnomaly) === "Perlu Ditinjau", "anomalyId with empty risk → 'Perlu Ditinjau'", `got ${getRiskCategory(rowEmptyAnomaly)}`);

// ─── Verify score does NOT override backend risk level ───

console.log("\n=== EDGE: high score with SEDANG risk stays Perlu Ditinjau ===");

const rowHighScore = mergeRow(
    { id: 900, aksi: "LOGIN_SUCCESS", waktu: "2026-08-24T10:00:00.000Z", status_analisis: "ANALYZED_ANOMALY" },
    { id: 300, sumber_audit_log_id: 900, skor_anomali: 0.95, tingkat_risiko: "SEDANG", status_keputusan: "PENDING" }
);

assert(getRiskCategory(rowHighScore) === "Perlu Ditinjau", "score 0.95 with SEDANG → 'Perlu Ditinjau'", `got ${getRiskCategory(rowHighScore)}`);

// ─── Verify HIGH score respects TINGGI regardless of numeric score ───

console.log("\n=== EDGE: TINGGI with low score → High Risk ===");

const rowLowScoreTinggi = mergeRow(
    { id: 901, aksi: "LOGIN_SUCCESS", waktu: "2026-08-24T10:00:00.000Z", status_analisis: "ANALYZED_ANOMALY" },
    { id: 301, sumber_audit_log_id: 901, skor_anomali: 0.10, tingkat_risiko: "TINGGI", status_keputusan: "PENDING" }
);

assert(getRiskCategory(rowLowScoreTinggi) === "High Risk", "TINGGI with score 0.10 → 'High Risk'", `got ${getRiskCategory(rowLowScoreTinggi)}`);

// ─── NOT_ANALYZED: no detection result ───

console.log("\n=== NOT_ANALYZED: audit log record 423 (AI was down) ===");

const rowNotAnalyzed = mergeRow(
    { id: 423, aksi: "AKSES_SISTEM", waktu: "2026-08-24T19:43:00.000Z", status_analisis: "NOT_ANALYZED" },
    undefined
);

assert(getRiskCategory(rowNotAnalyzed) === null, "NOT_ANALYZED → null (no category)", `got ${getRiskCategory(rowNotAnalyzed)}`);
assert(renderScore(rowNotAnalyzed) === "-", "score displays '-'", `got ${renderScore(rowNotAnalyzed)}`);
const badgeNA = getCategoryBadge(getRiskCategory(rowNotAnalyzed));
assert(badgeNA.className === "neutral", "badge className is 'neutral'", `got ${badgeNA.className}`);
assert(badgeNA.label === "Belum Dianalisis", "badge label is 'Belum Dianalisis'", `got ${badgeNA.label}`);

// ─── AI_ERROR: no detection result ───

console.log("\n=== AI_ERROR: audit log with AI processing error ===");

const rowAiError = mergeRow(
    { id: 500, aksi: "LOGIN_SUCCESS", waktu: "2026-08-25T10:00:00.000Z", status_analisis: "AI_ERROR" },
    undefined
);

assert(getRiskCategory(rowAiError) === null, "AI_ERROR → null (no category)", `got ${getRiskCategory(rowAiError)}`);
assert(renderScore(rowAiError) === "-", "score displays '-'", `got ${renderScore(rowAiError)}`);

// ─── ANALYZED_NORMAL: no anomalyId → Normal ───

console.log("\n=== ANALYZED_NORMAL: analyzed and found normal ===");

const rowAnalyzedNormal = mergeRow(
    { id: 350, aksi: "LOGIN_SUCCESS", waktu: "2026-08-25T08:00:00.000Z", status_analisis: "ANALYZED_NORMAL" },
    undefined
);

assert(getRiskCategory(rowAnalyzedNormal) === "Normal", "ANALYZED_NORMAL → Normal", `got ${getRiskCategory(rowAnalyzedNormal)}`);
assert(renderScore(rowAnalyzedNormal) === "-", "score displays '-'", `got ${renderScore(rowAnalyzedNormal)}`);

// ─── ANALYZED_ANOMALY with status_analisis ───

console.log("\n=== ANALYZED_ANOMALY: with explicit status_analisis ===");

const rowAnalyzedAnomaly = mergeRow(
    { id: 400, aksi: "LOGIN_SUCCESS", waktu: "2026-08-24T10:00:00.000Z", status_analisis: "ANALYZED_ANOMALY" },
    { id: 100, sumber_audit_log_id: 400, skor_anomali: 9.94, tingkat_risiko: "TINGGI", status_keputusan: "PENDING" }
);

assert(getRiskCategory(rowAnalyzedAnomaly) === "High Risk", "ANALYZED_ANOMALY + TINGGI → High Risk", `got ${getRiskCategory(rowAnalyzedAnomaly)}`);
assert(renderScore(rowAnalyzedAnomaly) === "9.94", "score displays '9.94'", `got ${renderScore(rowAnalyzedAnomaly)}`);

// ─── Stats: null category excluded from counts ───

console.log("\n=== STATS: NOT_ANALYZED not counted in detection categories ===");

const allRows = [rowNormal, rowHighTinggi, rowMedium, rowNotAnalyzed, rowAiError, rowAnalyzedNormal];
const analyzedRows = allRows.filter((r) => getRiskCategory(r) !== null);
const normalCount = analyzedRows.filter((r) => getRiskCategory(r) === "Normal").length;
const highCount = analyzedRows.filter((r) => getRiskCategory(r) === "High Risk").length;
const reviewCount = analyzedRows.filter((r) => getRiskCategory(r) === "Perlu Ditinjau").length;

assert(analyzedRows.length === 4, "analyzed count = 4 (excludes NOT_ANALYZED and AI_ERROR)", `got ${analyzedRows.length}`);
assert(normalCount === 2, "normal count = 2", `got ${normalCount}`);
assert(highCount === 1, "high count = 1", `got ${highCount}`);
assert(reviewCount === 1, "review count = 1", `got ${reviewCount}`);

// ─── Summary ───

console.log("\n" + "=".repeat(60));
console.log(`RESULTS: ${passed} passed, ${failed} failed, ${passed + failed} total`);
console.log("=".repeat(60));

if (failed > 0) {
    process.exit(1);
} else {
    console.log("ALL TESTS PASSED.\n");
}
