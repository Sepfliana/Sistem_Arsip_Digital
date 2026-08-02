-- Skema referensi Sistem Arsip Digital untuk dokumentasi BAB IV.
-- File ini adalah artefak implementasi basis data, bukan migrasi otomatis.

CREATE TABLE roles (
    id SERIAL PRIMARY KEY,
    nama_peran VARCHAR(50) NOT NULL UNIQUE
);

CREATE TABLE users (
    id SERIAL PRIMARY KEY,
    role_id INTEGER NOT NULL REFERENCES roles(id),
    username VARCHAR(80) NOT NULL UNIQUE,
    password_hash TEXT NOT NULL,
    nama_lengkap VARCHAR(150),
    nip VARCHAR(40),
    jabatan VARCHAR(120),
    foto_profil TEXT,
    email VARCHAR(150) NOT NULL UNIQUE,
    is_active BOOLEAN NOT NULL DEFAULT TRUE,
    is_2fa_enabled BOOLEAN NOT NULL DEFAULT FALSE,
    totp_secret_encrypted TEXT,
    created_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE lemari (
    id SERIAL PRIMARY KEY,
    nama_lemari VARCHAR(120) NOT NULL,
    lokasi VARCHAR(150),
    jumlah_rak INTEGER NOT NULL DEFAULT 0,
    kapasitas_total INTEGER NOT NULL DEFAULT 0,
    jumlah_terpakai INTEGER NOT NULL DEFAULT 0,
    status VARCHAR(30) NOT NULL DEFAULT 'Kosong'
);

CREATE TABLE rak (
    id SERIAL PRIMARY KEY,
    lemari_id INTEGER NOT NULL REFERENCES lemari(id),
    nama_rak VARCHAR(120) NOT NULL,
    kapasitas INTEGER NOT NULL CHECK (kapasitas > 0),
    jumlah_perkara INTEGER NOT NULL DEFAULT 0,
    status VARCHAR(30) NOT NULL DEFAULT 'Kosong',
    CONSTRAINT uq_rak_lemari_nama UNIQUE (lemari_id, nama_rak)
);

CREATE TABLE jaksa (
    id SERIAL PRIMARY KEY,
    nama_jaksa VARCHAR(150) NOT NULL,
    is_active BOOLEAN NOT NULL DEFAULT TRUE
);

CREATE TABLE jenis_pidana (
    id SERIAL PRIMARY KEY,
    nama_jenis_pidana VARCHAR(150) NOT NULL,
    is_active BOOLEAN NOT NULL DEFAULT TRUE
);

CREATE TABLE jenis_perkara (
    id SERIAL PRIMARY KEY,
    jenis_pidana_id INTEGER NOT NULL REFERENCES jenis_pidana(id),
    nama_jenis_perkara VARCHAR(150) NOT NULL,
    is_active BOOLEAN NOT NULL DEFAULT TRUE
);

CREATE TABLE instansi_penyidik (
    id SERIAL PRIMARY KEY,
    nama_instansi VARCHAR(150) NOT NULL,
    is_active BOOLEAN NOT NULL DEFAULT TRUE
);

CREATE TABLE perkara (
    id SERIAL PRIMARY KEY,
    nomor_perkara VARCHAR(120) NOT NULL UNIQUE,
    nama_terdakwa VARCHAR(200) NOT NULL,
    jaksa_id INTEGER NOT NULL REFERENCES jaksa(id),
    jenis_pidana_id INTEGER NOT NULL REFERENCES jenis_pidana(id),
    jenis_perkara_id INTEGER NOT NULL REFERENCES jenis_perkara(id),
    instansi_penyidik_id INTEGER NOT NULL REFERENCES instansi_penyidik(id),
    melanggar_pasal TEXT NOT NULL,
    tanggal_mulai DATE NOT NULL,
    tanggal_selesai DATE,
    lemari_id INTEGER NOT NULL REFERENCES lemari(id),
    rak_id INTEGER NOT NULL REFERENCES rak(id),
    cover_file TEXT,
    keterangan TEXT,
    created_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP
);


CREATE TABLE berkas (
    id SERIAL PRIMARY KEY,
    perkara_id INTEGER NOT NULL REFERENCES perkara(id),
    jenis_berkas VARCHAR(40) NOT NULL CHECK (jenis_berkas IN ('Pra Penuntutan', 'Penuntutan', 'Eksekusi')),
    uploaded_by INTEGER REFERENCES users(id),
    nomor_berkas VARCHAR(120) NOT NULL,
    nama_berkas VARCHAR(220) NOT NULL,
    tanggal_berkas DATE,
    status_berkas VARCHAR(30) NOT NULL DEFAULT 'AKTIF',
    nasib_akhir VARCHAR(40),
    masa_retensi_aktif INTEGER NOT NULL CHECK (masa_retensi_aktif > 0),
    masa_retensi_inaktif INTEGER NOT NULL CHECK (masa_retensi_inaktif > 0),
    tanggal_mulai_aktif DATE,
    tanggal_mulai_inaktif DATE,
    nama_file TEXT,
    tipe_file VARCHAR(120),
    ukuran BIGINT,
    hash_sha256 CHAR(64),
    status_integritas VARCHAR(20) NOT NULL DEFAULT 'BELUM_DIVERIFIKASI',
    tanggal_verifikasi_terakhir TIMESTAMP,
    path_file TEXT,
    CONSTRAINT uq_berkas_perkara_nomor UNIQUE (perkara_id, nomor_berkas)
);

CREATE TABLE peminjaman (
    id SERIAL PRIMARY KEY,
    berkas_id INTEGER NOT NULL REFERENCES berkas(id),
    user_id INTEGER NOT NULL REFERENCES users(id),
    disetujui_oleh INTEGER REFERENCES users(id),
    keperluan TEXT,
    tanggal_pinjam DATE NOT NULL,
    tanggal_kembali DATE,
    status VARCHAR(30) NOT NULL DEFAULT 'MENUNGGU'
);

CREATE TABLE audit_log (
    id SERIAL PRIMARY KEY,
    user_id INTEGER REFERENCES users(id),
    aksi VARCHAR(120) NOT NULL,
    target_tipe VARCHAR(80) NOT NULL,
    target_id INTEGER,
    waktu TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
    durasi_ms INTEGER NOT NULL DEFAULT 0,
    jumlah_objek INTEGER NOT NULL DEFAULT 1,
    status VARCHAR(30) NOT NULL DEFAULT 'SUCCESS',
    ip_address VARCHAR(80) NOT NULL DEFAULT 'unknown',
    device VARCHAR(80) NOT NULL DEFAULT 'unknown',
    hash_sebelumnya CHAR(64),
    hash_entri CHAR(64) NOT NULL
);

CREATE TABLE laporan_anomali (
    id SERIAL PRIMARY KEY,
    user_id INTEGER REFERENCES users(id),
    sumber_audit_log_id INTEGER NOT NULL REFERENCES audit_log(id),
    skor_anomali NUMERIC(18, 10) NOT NULL,
    tingkat_risiko VARCHAR(30) NOT NULL,
    status_keputusan VARCHAR(30) NOT NULL DEFAULT 'PENDING'
);

CREATE INDEX idx_perkara_lokasi ON perkara(lemari_id, rak_id);
CREATE INDEX idx_berkas_perkara ON berkas(perkara_id);
CREATE INDEX idx_berkas_jenis ON berkas(jenis_berkas);
CREATE INDEX idx_peminjaman_status ON peminjaman(status);
CREATE INDEX idx_audit_log_waktu ON audit_log(waktu);
CREATE INDEX idx_laporan_anomali_status ON laporan_anomali(status_keputusan);


