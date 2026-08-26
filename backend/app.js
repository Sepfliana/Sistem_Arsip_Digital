const express = require("express");
const pool = require("./config/database");
const userRoutes = require("./routes/userRoutes");
const lemariRoutes = require("./routes/lemariRoutes");
const rakRoutes = require("./routes/rakRoutes");
const perkaraRoutes = require("./routes/perkaraRoutes");
const berkasRoutes = require("./routes/berkasRoutes");
const peminjamanRoutes = require("./routes/peminjamanRoutes");
const authRoutes = require("./routes/authRoutes");
const totpRoutes = require("./routes/totpRoutes");
const auditLogRoutes = require("./routes/auditLogRoutes");
const replicationRoutes = require("./routes/replicationRoutes");
const masterDataRoutes = require("./routes/masterDataRoutes");
const { requestAuditContext } = require("./utils/auditRequestContext");
const cors = require("cors");
const { runBackfillAnalysis } = require("./controllers/auditLogController");

const app = express();

const ensureIntegrityColumns = async () => {
    try {
        await pool.query(`
            ALTER TABLE berkas
            ADD COLUMN IF NOT EXISTS status_integritas VARCHAR(20) NOT NULL DEFAULT 'BELUM_DIVERIFIKASI',
            ADD COLUMN IF NOT EXISTS tanggal_verifikasi_terakhir TIMESTAMP
        `);
        await pool.query(`
            ALTER TABLE perkara
            ADD COLUMN IF NOT EXISTS cover_file TEXT,
            ADD COLUMN IF NOT EXISTS nama_terdakwa VARCHAR(200)
        `);
        await pool.query(`
            CREATE TABLE IF NOT EXISTS perkara_covers (
                id SERIAL PRIMARY KEY,
                perkara_id INTEGER NOT NULL REFERENCES perkara(id) ON DELETE CASCADE,
                file_path TEXT NOT NULL,
                file_name TEXT NOT NULL,
                mime_type VARCHAR(120) NOT NULL DEFAULT 'application/pdf',
                ukuran BIGINT,
                halaman INTEGER,
                urutan INTEGER NOT NULL DEFAULT 1,
                created_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP
            )
        `);
        await pool.query(`
            CREATE INDEX IF NOT EXISTS idx_perkara_covers_perkara ON perkara_covers(perkara_id, urutan, id)
        `);
        await pool.query(`
            CREATE TABLE IF NOT EXISTS verifikasi_integritas_berkas (
                id SERIAL PRIMARY KEY,
                berkas_id INTEGER NOT NULL REFERENCES berkas(id) ON DELETE CASCADE,
                perkara_id INTEGER REFERENCES perkara(id) ON DELETE SET NULL,
                nomor_perkara VARCHAR(120),
                nama_terdakwa VARCHAR(200),
                nomor_berkas VARCHAR(120),
                nama_berkas VARCHAR(220),
                sha256_database CHAR(64),
                sha256_hasil CHAR(64),
                status VARCHAR(30) NOT NULL,
                diverifikasi_oleh INTEGER REFERENCES users(id) ON DELETE SET NULL,
                keterangan TEXT,
                tanggal_verifikasi TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
                created_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP
            )
        `);
        await pool.query(`
            CREATE INDEX IF NOT EXISTS idx_verifikasi_integritas_berkas_waktu ON verifikasi_integritas_berkas(tanggal_verifikasi DESC, id)
        `);
        await pool.query(`
            ALTER TABLE audit_log
            ADD COLUMN IF NOT EXISTS status_analisis VARCHAR(20) NOT NULL DEFAULT 'NOT_ANALYZED'
        `);
        await pool.query(`
            ALTER TABLE audit_log
            ADD COLUMN IF NOT EXISTS anomaly_score NUMERIC(18, 10)
        `);
        await pool.query(`
            ALTER TABLE audit_log
            ADD COLUMN IF NOT EXISTS analysis_threshold NUMERIC(18, 10)
        `);
        await pool.query(`
            ALTER TABLE audit_log
            ADD COLUMN IF NOT EXISTS risk_level VARCHAR(20)
        `);
        await pool.query(`
            ALTER TABLE audit_log
            ADD COLUMN IF NOT EXISTS analysis_detail JSONB
        `);
        await pool.query(`
            ALTER TABLE laporan_anomali
            ADD COLUMN IF NOT EXISTS penjelasan JSONB
        `);
    } catch (error) {
        console.error("Gagal memastikan kolom pendukung database:", error.message);
    }
};

ensureIntegrityColumns().then(async () => {
    const MAX_RETRIES = 5;
    const RETRY_DELAY_MS = 5000;
    for (let attempt = 1; attempt <= MAX_RETRIES; attempt++) {
        try {
            console.log(`[STARTUP] Auto-backfill attempt ${attempt}/${MAX_RETRIES}: re-analyzing all audit logs with final VAE pipeline...`);
            const result = await runBackfillAnalysis();
            console.log(`[STARTUP] Auto-backfill complete: total=${result.total} processed=${result.processed} errors=${result.errors}`);
            return;
        } catch (err) {
            console.error(`[STARTUP] Auto-backfill attempt ${attempt}/${MAX_RETRIES} failed:`, err.message);
            if (attempt < MAX_RETRIES) {
                console.log(`[STARTUP] Retrying in ${RETRY_DELAY_MS / 1000}s...`);
                await new Promise((resolve) => setTimeout(resolve, RETRY_DELAY_MS));
            }
        }
    }
    console.error("[STARTUP] Auto-backfill gave up after max retries. Use POST /audit-log/backfill-analyze to retry manually.");
}).catch((err) => {
    console.error("[STARTUP] Column ensure failed (non-fatal):", err.message);
});

app.use(cors());
app.use(express.json());
// All request-originated audit logs now inherit the same normalized IPv4 and
// User-Agent, including controller call-sites that do not pass them explicitly.
app.use(requestAuditContext);

app.use("/users", userRoutes);
app.use("/lemari", lemariRoutes);
app.use("/rak", rakRoutes);
app.use("/perkara", perkaraRoutes);
app.use("/berkas", berkasRoutes);
app.use("/peminjaman", peminjamanRoutes);
app.use("/auth", authRoutes);
app.use("/totp", totpRoutes);
app.use("/audit-log", auditLogRoutes);
app.use("/replication", replicationRoutes);
app.use("/", masterDataRoutes);
app.use("/api/perkara", perkaraRoutes);
app.use("/api", masterDataRoutes);

app.get("/", async (_req, res) => {
    try {
        const result = await pool.query("SELECT NOW()");
        res.json({ message: "Backend Sistem Arsip Digital Berjalan", database: "Terhubung", waktu_server: result.rows[0] });
    } catch (error) {
        res.status(500).json({ message: "Koneksi database gagal", error: error.message });
    }
});

module.exports = app;
