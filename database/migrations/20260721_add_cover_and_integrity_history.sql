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
);

CREATE INDEX IF NOT EXISTS idx_perkara_covers_perkara
ON perkara_covers(perkara_id, urutan, id);

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
);

CREATE INDEX IF NOT EXISTS idx_verifikasi_integritas_berkas_waktu
ON verifikasi_integritas_berkas(tanggal_verifikasi DESC, id DESC);
