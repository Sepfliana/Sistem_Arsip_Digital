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
const cors = require("cors");

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
            CREATE INDEX IF NOT EXISTS idx_verifikasi_integritas_berkas_waktu ON verifikasi_integritas_berkas(tanggal_verifikasi DESC, id DESC)
        `);
    } catch (error) {
        console.error("Gagal memastikan kolom pendukung database:", error.message);
    }
};

ensureIntegrityColumns();

app.use(cors());
app.use(express.json());

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

app.get("/", async (req, res) => {
    try {
        const result = await pool.query("SELECT NOW()");
        res.json({
            message: "Backend Sistem Arsip Digital Berjalan",
            database: "Terhubung",
            waktu_server: result.rows[0]
        });
    } catch (error) {
        res.status(500).json({
            message: "Koneksi database gagal",
            error: error.message
        });
    }
});

module.exports = app;




