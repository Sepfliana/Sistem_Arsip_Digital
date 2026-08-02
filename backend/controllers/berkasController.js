const pool = require("../config/database");
const { createAuditLog } = require("../services/auditLogService");
const crypto = require("crypto");
const fs = require("fs");
const path = require("path");

const JENIS_BERKAS = ["Pra Penuntutan", "Penuntutan", "Eksekusi"];
const RETENSI_WARNING_DAYS = 30;

const calculateFileHash = (filePath) => {
    const fileBuffer = fs.readFileSync(filePath);

    return crypto
        .createHash("sha256")
        .update(fileBuffer)
        .digest("hex");
};

const getAuditContext = (req) => ({
    ipAddress: req.ip || req.headers["x-forwarded-for"] || req.socket?.remoteAddress || "unknown",
    device: req.headers["user-agent"] || "unknown"
});

const getVerificationBerkas = async (id) => {
    const result = await pool.query(
        `
        SELECT
            berkas.id,
            berkas.perkara_id,
            berkas.nomor_berkas,
            berkas.nama_berkas,
            berkas.nama_file,
            berkas.tipe_file,
            berkas.ukuran,
            berkas.hash_sha256,
            berkas.status_integritas,
            berkas.tanggal_verifikasi_terakhir,
            berkas.path_file,
            berkas.tanggal_berkas,
            berkas.tanggal_mulai_aktif,
            perkara.nomor_perkara,
            perkara.nama_terdakwa
        FROM berkas
        LEFT JOIN perkara
            ON berkas.perkara_id = perkara.id
        WHERE berkas.id = $1
        `,
        [id]
    );

    return result.rows[0] || null;
};

const escapePdfText = (value) => String(value || "-")
    .replace(/\\/g, "\\\\")
    .replace(/\(/g, "\\(")
    .replace(/\)/g, "\\)");

const createSimplePdf = (lines) => {
    const contentLines = ["BT", "/F1 12 Tf", "50 790 Td"];

    lines.forEach((line, index) => {
        if (index > 0) {
            contentLines.push("0 -22 Td");
        }
        contentLines.push(`(${escapePdfText(line)}) Tj`);
    });

    contentLines.push("ET");

    const stream = contentLines.join("\n");
    const objects = [
        "<< /Type /Catalog /Pages 2 0 R >>",
        "<< /Type /Pages /Kids [3 0 R] /Count 1 >>",
        "<< /Type /Page /Parent 2 0 R /MediaBox [0 0 595 842] /Resources << /Font << /F1 4 0 R >> >> /Contents 5 0 R >>",
        "<< /Type /Font /Subtype /Type1 /BaseFont /Helvetica >>",
        `<< /Length ${Buffer.byteLength(stream)} >>\nstream\n${stream}\nendstream`
    ];

    let pdf = "%PDF-1.4\n";
    const offsets = [0];

    objects.forEach((object, index) => {
        offsets.push(Buffer.byteLength(pdf));
        pdf += `${index + 1} 0 obj\n${object}\nendobj\n`;
    });

    const xrefOffset = Buffer.byteLength(pdf);
    pdf += `xref\n0 ${objects.length + 1}\n0000000000 65535 f \n`;
    offsets.slice(1).forEach((offset) => {
        pdf += `${String(offset).padStart(10, "0")} 00000 n \n`;
    });
    pdf += `trailer\n<< /Size ${objects.length + 1} /Root 1 0 R >>\nstartxref\n${xrefOffset}\n%%EOF`;

    return Buffer.from(pdf, "utf8");
};

const normalizeJenisBerkas = (jenisBerkas) => {
    const selected = JENIS_BERKAS.find((jenis) => jenis === String(jenisBerkas || "").trim());

    return selected || null;
};

const normalizeRetensiStatus = (status) => {
    if (!status) {
        return "AKTIF";
    }

    const allowedStatuses = ["AKTIF", "INAKTIF", "PERMANEN", "MUSNAH"];
    const normalized = String(status).toUpperCase();

    return allowedStatuses.includes(normalized) ? normalized : "AKTIF";
};

const parsePositiveNumber = (value, fallback = 1) => {
    const parsed = Number(value);

    return Number.isFinite(parsed) && parsed > 0 ? parsed : fallback;
};

const addYears = (date, years) => {
    const next = new Date(date);
    next.setFullYear(next.getFullYear() + parsePositiveNumber(years));

    return next;
};

const daysUntil = (date) => Math.ceil((date - new Date()) / (1000 * 60 * 60 * 24));

const getRetensiInfo = (berkas) => {
    if (!berkas.tanggal_mulai_aktif) {
        return {
            status_berkas: normalizeRetensiStatus(berkas.status_berkas),
            tanggal_akhir_aktif: null,
            tanggal_akhir_inaktif: null,
            jenis_notifikasi_retensi: null,
            sisa_hari_retensi: null
        };
    }

    const today = new Date();
    const mulaiAktif = new Date(berkas.tanggal_mulai_aktif);
    const akhirAktif = addYears(mulaiAktif, berkas.masa_retensi_aktif);
    const akhirInaktif = addYears(akhirAktif, berkas.masa_retensi_inaktif);
    const storedStatus = String(berkas.status_berkas || "").toUpperCase();

    if (["PERMANEN", "MUSNAH"].includes(storedStatus)) {
        return {
            status_berkas: storedStatus,
            tanggal_akhir_aktif: akhirAktif,
            tanggal_akhir_inaktif: akhirInaktif,
            jenis_notifikasi_retensi: null,
            sisa_hari_retensi: null
        };
    }

    if (today <= akhirAktif) {
        const sisaHari = daysUntil(akhirAktif);

        return {
            status_berkas: "AKTIF",
            tanggal_akhir_aktif: akhirAktif,
            tanggal_akhir_inaktif: akhirInaktif,
            jenis_notifikasi_retensi: sisaHari <= RETENSI_WARNING_DAYS ? "AKTIF_HAMPIR_HABIS" : null,
            sisa_hari_retensi: sisaHari
        };
    }

    if (today <= akhirInaktif) {
        const sisaHari = daysUntil(akhirInaktif);

        return {
            status_berkas: "INAKTIF",
            tanggal_akhir_aktif: akhirAktif,
            tanggal_akhir_inaktif: akhirInaktif,
            jenis_notifikasi_retensi: sisaHari <= RETENSI_WARNING_DAYS ? "INAKTIF_HAMPIR_HABIS" : null,
            sisa_hari_retensi: sisaHari
        };
    }

    return {
        status_berkas: "SELESAI",
        tanggal_akhir_aktif: akhirAktif,
        tanggal_akhir_inaktif: akhirInaktif,
        jenis_notifikasi_retensi: "INAKTIF_SELESAI",
        sisa_hari_retensi: daysUntil(akhirInaktif)
    };
};

const attachRetensiInfo = (berkas) => {
    const retensiInfo = getRetensiInfo(berkas);

    return {
        ...berkas,
        ...retensiInfo,
        tanggal_akhir_aktif: retensiInfo.tanggal_akhir_aktif?.toISOString() || null,
        tanggal_akhir_inaktif: retensiInfo.tanggal_akhir_inaktif?.toISOString() || null,
        tanggal_jatuh_tempo: retensiInfo.status_berkas === "AKTIF"
            ? retensiInfo.tanggal_akhir_aktif?.toISOString() || null
            : retensiInfo.tanggal_akhir_inaktif?.toISOString() || null,
        sidik_jari_digital: berkas.hash_sha256 || null
    };
};

const getAllBerkasRows = async () => {
    const result = await pool.query(`
        SELECT
            berkas.id,
            berkas.perkara_id,
            berkas.jenis_berkas,
            berkas.uploaded_by,
            berkas.nomor_berkas,
            berkas.nama_berkas,
            berkas.tanggal_berkas,
            berkas.status_berkas,
            berkas.nasib_akhir,
            berkas.masa_retensi_aktif,
            berkas.masa_retensi_inaktif,
            berkas.tanggal_mulai_aktif,
            berkas.tanggal_mulai_inaktif,
            berkas.nama_file,
            berkas.tipe_file,
            berkas.ukuran,
            berkas.hash_sha256,
            berkas.status_integritas,
            berkas.tanggal_verifikasi_terakhir,
            berkas.path_file,

            perkara.nomor_perkara,
            perkara.nama_terdakwa,
            lemari.nama_lemari,
            rak.nama_rak

        FROM berkas
        LEFT JOIN perkara
            ON berkas.perkara_id = perkara.id
        LEFT JOIN lemari
            ON perkara.lemari_id = lemari.id
        LEFT JOIN rak
            ON perkara.rak_id = rak.id
    `);

    return result.rows;
};

const getIntegrityHistory = async (req, res) => {
    try {
        const {
            tanggal,
            status,
            nomor_perkara,
            nama_terdakwa,
            nama_berkas
        } = req.query;
        const values = [];
        const conditions = [];

        const addLike = (column, value) => {
            if (!value) return;
            values.push(`%${value}%`);
            conditions.push(`${column} ILIKE $${values.length}`);
        };

        if (tanggal) {
            values.push(tanggal);
            conditions.push(`DATE(verifikasi_integritas_berkas.tanggal_verifikasi) = $${values.length}`);
        }

        if (status) {
            values.push(String(status).toUpperCase());
            conditions.push(`verifikasi_integritas_berkas.status = $${values.length}`);
        }

        addLike("verifikasi_integritas_berkas.nomor_perkara", nomor_perkara);
        addLike("verifikasi_integritas_berkas.nama_terdakwa", nama_terdakwa);
        addLike("verifikasi_integritas_berkas.nama_berkas", nama_berkas);

        const query = `
            SELECT
                verifikasi_integritas_berkas.*,
                COALESCE(NULLIF(users.nama_lengkap, ''), users.username) AS diverifikasi_oleh_nama
            FROM verifikasi_integritas_berkas
            LEFT JOIN users
                ON verifikasi_integritas_berkas.diverifikasi_oleh = users.id
            ${conditions.length ? `WHERE ${conditions.join(" AND ")}` : ""}
            ORDER BY verifikasi_integritas_berkas.tanggal_verifikasi DESC, verifikasi_integritas_berkas.id DESC
        `;

        const result = await pool.query(query, values);
        res.status(200).json(result.rows);
    } catch (error) {
        res.status(500).json({
            message: "Gagal mengambil riwayat verifikasi integritas",
            error: error.message
        });
    }
};

const getSystemNotifications = async (req, res) => {
    try {
        const vaeResult = await pool.query(`
            SELECT
                laporan_anomali.id,
                laporan_anomali.skor_anomali,
                laporan_anomali.tingkat_risiko,
                laporan_anomali.status_keputusan,
                audit_log.waktu,
                COALESCE(perkara.nama_terdakwa, perkara_berkas.nama_terdakwa, '-') AS perkara
            FROM laporan_anomali
            JOIN audit_log
                ON laporan_anomali.sumber_audit_log_id = audit_log.id
            LEFT JOIN perkara
                ON audit_log.target_tipe = 'PERKARA' AND audit_log.target_id = perkara.id
            LEFT JOIN berkas
                ON audit_log.target_tipe = 'BERKAS' AND audit_log.target_id = berkas.id
            LEFT JOIN perkara AS perkara_berkas
                ON berkas.perkara_id = perkara_berkas.id
            WHERE UPPER(laporan_anomali.tingkat_risiko) IN ('SEDANG', 'TINGGI', 'MEDIUM', 'HIGH')
              AND LOWER(COALESCE(laporan_anomali.status_keputusan, '')) <> 'selesai'
            ORDER BY audit_log.waktu DESC
            LIMIT 50
        `);

        const integrityResult = await pool.query(`
            SELECT
                id,
                tanggal_verifikasi AS waktu,
                nama_terdakwa AS perkara,
                nama_berkas,
                status
            FROM verifikasi_integritas_berkas
            WHERE status = 'HASH TIDAK SESUAI'
            ORDER BY tanggal_verifikasi DESC, id DESC
            LIMIT 50
        `);

        const vaeNotifications = vaeResult.rows.map((item) => ({
            id: `vae-${item.id}`,
            type: "VAE",
            title: "VAE",
            waktu: item.waktu,
            perkara: item.perkara || "-",
            skor: Number(item.skor_anomali || 0),
            risiko: String(item.tingkat_risiko || "-").toUpperCase()
        }));

        const integrityNotifications = integrityResult.rows.map((item) => ({
            id: `integrity-${item.id}`,
            type: "INTEGRITAS_BERKAS",
            title: "Integritas Berkas",
            waktu: item.waktu,
            perkara: item.perkara || "-",
            nama_berkas: item.nama_berkas || "-",
            status: item.status
        }));

        const notifications = [...vaeNotifications, ...integrityNotifications]
            .sort((left, right) => new Date(right.waktu || 0) - new Date(left.waktu || 0));

        res.status(200).json(notifications);
    } catch (error) {
        res.status(500).json({
            message: "Gagal mengambil notifikasi sistem",
            error: error.message
        });
    }
};
const getBerkasRetensiSelesai = async (req, res) => {
    try {
        const data = (await getAllBerkasRows())
            .map(attachRetensiInfo)
            .filter((berkas) => berkas.status_berkas === "SELESAI");

        res.status(200).json(data);
    } catch (error) {
        res.status(500).json({
            message: "Gagal mengambil data retensi selesai",
            error: error.message
        });
    }
};

const prosesRetensiOtomatis = async (req, res) => {
    try {
        const result = await pool.query(`
            SELECT *
            FROM berkas
            WHERE tanggal_mulai_aktif IS NOT NULL
        `);

        let totalDiproses = 0;

        for (const berkas of result.rows) {
            const retensiInfo = getRetensiInfo(berkas);

            if (retensiInfo.status_berkas !== "INAKTIF" || String(berkas.status_berkas || "").toUpperCase() === "INAKTIF") {
                continue;
            }

            await pool.query(
                `
                UPDATE berkas
                SET
                    status_berkas = $1,
                    tanggal_mulai_inaktif = COALESCE(tanggal_mulai_inaktif, $2)
                WHERE id = $3
                `,
                ["INAKTIF", retensiInfo.tanggal_akhir_aktif, berkas.id]
            );

            await createAuditLog(req.user.id, "RETENSI_INAKTIF", "BERKAS", berkas.id);
            totalDiproses++;
        }

        res.status(200).json({
            message: "Retensi aktif ke inaktif berhasil diproses. Penentuan Permanen atau Musnah tetap dilakukan Arsiparis.",
            total_diproses: totalDiproses
        });
    } catch (error) {
        res.status(500).json({
            message: "Gagal memproses retensi otomatis",
            error: error.message
        });
    }
};

const getBerkasAkanJatuhTempo = async (req, res) => {
    try {
        const data = (await getAllBerkasRows())
            .map(attachRetensiInfo)
            .filter((berkas) => berkas.jenis_notifikasi_retensi);

        res.status(200).json(data);
    } catch (error) {
        res.status(500).json({
            message: "Gagal mengambil data retensi",
            error: error.message
        });
    }
};

const getAllBerkas = async (req, res) => {
    try {
        const { search, status } = req.query;
        let data = (await getAllBerkasRows()).map(attachRetensiInfo);

        if (search) {
            const term = String(search).toLowerCase();
            data = data.filter((berkas) => [
                berkas.nomor_berkas,
                berkas.nama_berkas,
                berkas.jenis_berkas,
                berkas.nomor_perkara,
                berkas.nama_terdakwa
            ].some((value) => String(value || "").toLowerCase().includes(term)));
        }

        if (status) {
            data = data.filter((berkas) => berkas.status_berkas === String(status).toUpperCase());
        }

        data.sort((a, b) => a.id - b.id);

        res.status(200).json(data);
    } catch (error) {
        res.status(500).json({
            message: "Gagal mengambil data berkas",
            error: error.message
        });
    }
};

const getBerkasById = async (req, res) => {
    try {
        const { id } = req.params;
        const result = await pool.query(
            `
            SELECT *
            FROM berkas
            WHERE id = $1
            `,
            [id]
        );

        if (result.rows.length === 0) {
            return res.status(404).json({
                message: "Berkas tidak ditemukan"
            });
        }

        const [berkas] = (await getAllBerkasRows())
            .filter((item) => String(item.id) === String(id))
            .map(attachRetensiInfo);

        res.status(200).json(berkas);
    } catch (error) {
        res.status(500).json({
            message: "Gagal mengambil data berkas",
            error: error.message
        });
    }
};

const validateBerkasPayload = ({ perkara_id, jenis_berkas, nomor_berkas, nama_berkas, masa_retensi_aktif, masa_retensi_inaktif }) => {
    if (!perkara_id) return "Perkara wajib diisi";
    if (!normalizeJenisBerkas(jenis_berkas)) return "Jenis berkas tidak valid";
    if (!nomor_berkas) return "Nomor berkas wajib diisi";
    if (!nama_berkas) return "Nama berkas wajib diisi";
    if (!parsePositiveNumber(masa_retensi_aktif, 0)) return "Masa retensi aktif wajib lebih dari 0";
    if (!parsePositiveNumber(masa_retensi_inaktif, 0)) return "Masa retensi inaktif wajib lebih dari 0";

    return null;
};

const createBerkas = async (req, res) => {
    try {
        const {
            perkara_id,
            jenis_berkas,
            nomor_berkas,
            nama_berkas,
            tanggal_berkas,
            masa_retensi_aktif,
            masa_retensi_inaktif,
            tanggal_mulai_aktif,
            status_berkas,
            nasib_akhir
        } = req.body;

        const validationMessage = validateBerkasPayload({
            perkara_id,
            jenis_berkas,
            nomor_berkas,
            nama_berkas,
            masa_retensi_aktif,
            masa_retensi_inaktif
        });

        if (validationMessage) {
            return res.status(400).json({ message: validationMessage });
        }

        if (!req.file) {
            return res.status(400).json({
                message: "File arsip PDF wajib diunggah"
            });
        }

        const cekPerkara = await pool.query(`SELECT id FROM perkara WHERE id = $1`, [perkara_id]);

        if (cekPerkara.rows.length === 0) {
            return res.status(404).json({
                message: "Perkara tidak ditemukan"
            });
        }

        const cekDuplikat = await pool.query(
            `
            SELECT id
            FROM berkas
            WHERE perkara_id = $1
              AND nomor_berkas = $2
            `,
            [perkara_id, nomor_berkas]
        );

        if (cekDuplikat.rows.length > 0) {
            return res.status(400).json({
                message: "Nomor berkas tersebut sudah ada pada perkara ini"
            });
        }

        const hash_sha256 = calculateFileHash(req.file.path);
        const result = await pool.query(
            `
            INSERT INTO berkas
            (
                perkara_id,
                jenis_berkas,
                uploaded_by,
                nomor_berkas,
                nama_berkas,
                tanggal_berkas,
                masa_retensi_aktif,
                masa_retensi_inaktif,
                tanggal_mulai_aktif,
                status_berkas,
                nasib_akhir,
                nama_file,
                tipe_file,
                ukuran,
                hash_sha256,
                path_file
            )
            VALUES
            ($1,$2,$3,$4,$5,$6,$7,$8,$9,$10,$11,$12,$13,$14,$15,$16)
            RETURNING *
            `,
            [
                perkara_id,
                normalizeJenisBerkas(jenis_berkas),
                req.user.id,
                nomor_berkas,
                nama_berkas,
                tanggal_berkas || new Date(),
                parsePositiveNumber(masa_retensi_aktif),
                parsePositiveNumber(masa_retensi_inaktif),
                tanggal_mulai_aktif || new Date(),
                normalizeRetensiStatus(status_berkas),
                nasib_akhir || null,
                req.file.originalname,
                req.file.mimetype,
                req.file.size,
                hash_sha256,
                req.file.path
            ]
        );

        await createAuditLog(req.user.id, "CREATE_BERKAS", "BERKAS", result.rows[0].id, {
            jenis_berkas: result.rows[0].jenis_berkas,
            hash_sha256
        });

        res.status(201).json({
            message: "Berkas berhasil ditambahkan",
            data: attachRetensiInfo(result.rows[0])
        });
    } catch (error) {
        res.status(500).json({
            message: "Gagal menambahkan berkas",
            error: error.message
        });
    }
};

const updateBerkas = async (req, res) => {
    try {
        const { id } = req.params;
        const {
            perkara_id,
            jenis_berkas,
            nomor_berkas,
            nama_berkas,
            tanggal_berkas,
            masa_retensi_aktif,
            masa_retensi_inaktif,
            tanggal_mulai_aktif,
            tanggal_mulai_inaktif,
            status_berkas,
            nasib_akhir
        } = req.body;

        const existingResult = await pool.query(`SELECT * FROM berkas WHERE id = $1`, [id]);

        if (existingResult.rows.length === 0) {
            return res.status(404).json({
                message: "Berkas tidak ditemukan"
            });
        }

        const existingBerkas = existingResult.rows[0];
        const finalPerkaraId = perkara_id || existingBerkas.perkara_id;
        const finalJenisBerkas = normalizeJenisBerkas(jenis_berkas || existingBerkas.jenis_berkas);
        const finalNomorBerkas = nomor_berkas || existingBerkas.nomor_berkas;
        const finalNamaBerkas = nama_berkas || existingBerkas.nama_berkas;
        const finalMasaAktif = parsePositiveNumber(masa_retensi_aktif || existingBerkas.masa_retensi_aktif);
        const finalMasaInaktif = parsePositiveNumber(masa_retensi_inaktif || existingBerkas.masa_retensi_inaktif);

        const validationMessage = validateBerkasPayload({
            perkara_id: finalPerkaraId,
            jenis_berkas: finalJenisBerkas,
            nomor_berkas: finalNomorBerkas,
            nama_berkas: finalNamaBerkas,
            masa_retensi_aktif: finalMasaAktif,
            masa_retensi_inaktif: finalMasaInaktif
        });

        if (validationMessage) {
            return res.status(400).json({ message: validationMessage });
        }

        const cekPerkara = await pool.query(`SELECT id FROM perkara WHERE id = $1`, [finalPerkaraId]);

        if (cekPerkara.rows.length === 0) {
            return res.status(404).json({
                message: "Perkara tidak ditemukan"
            });
        }

        const cekDuplikat = await pool.query(
            `
            SELECT id
            FROM berkas
            WHERE perkara_id = $1
              AND nomor_berkas = $2
              AND id <> $3
            `,
            [finalPerkaraId, finalNomorBerkas, id]
        );

        if (cekDuplikat.rows.length > 0) {
            return res.status(400).json({
                message: "Nomor berkas tersebut sudah ada pada perkara ini"
            });
        }

        const hash_sha256 = req.file ? calculateFileHash(req.file.path) : existingBerkas.hash_sha256;
        const finalStatus = normalizeRetensiStatus(status_berkas || existingBerkas.status_berkas);
        const result = await pool.query(
            `
            UPDATE berkas
            SET
                perkara_id = $1,
                jenis_berkas = $2,
                uploaded_by = $3,
                nomor_berkas = $4,
                nama_berkas = $5,
                tanggal_berkas = $6,
                masa_retensi_aktif = $7,
                masa_retensi_inaktif = $8,
                tanggal_mulai_aktif = $9,
                tanggal_mulai_inaktif = $10,
                status_berkas = $11,
                nasib_akhir = $12,
                nama_file = $13,
                tipe_file = $14,
                ukuran = $15,
                path_file = $16,
                hash_sha256 = $17
            WHERE id = $18
            RETURNING *
            `,
            [
                finalPerkaraId,
                finalJenisBerkas,
                req.user.id,
                finalNomorBerkas,
                finalNamaBerkas,
                tanggal_berkas || existingBerkas.tanggal_berkas,
                finalMasaAktif,
                finalMasaInaktif,
                tanggal_mulai_aktif || existingBerkas.tanggal_mulai_aktif,
                tanggal_mulai_inaktif || existingBerkas.tanggal_mulai_inaktif,
                finalStatus,
                nasib_akhir !== undefined ? nasib_akhir : existingBerkas.nasib_akhir,
                req.file?.originalname || existingBerkas.nama_file,
                req.file?.mimetype || existingBerkas.tipe_file,
                req.file?.size || existingBerkas.ukuran,
                req.file?.path || existingBerkas.path_file,
                hash_sha256,
                id
            ]
        );

        await createAuditLog(req.user.id, "UPDATE_BERKAS", "BERKAS", id, {
            jenis_berkas: result.rows[0].jenis_berkas,
            hash_sha256
        });

        if (existingBerkas.status_berkas !== finalStatus) {
            await createAuditLog(req.user.id, "PERUBAHAN_STATUS_ARSIP", "BERKAS", id);
        }

        res.status(200).json({
            message: "Berkas berhasil diperbarui",
            data: attachRetensiInfo(result.rows[0])
        });
    } catch (error) {
        res.status(500).json({
            message: "Gagal memperbarui berkas",
            error: error.message
        });
    }
};

const deleteBerkas = async (req, res) => {
    try {
        const { id } = req.params;

        const cekPeminjaman = await pool.query(
            `
            SELECT id
            FROM peminjaman
            WHERE berkas_id = $1
            LIMIT 1
            `,
            [id]
        );

        if (cekPeminjaman.rows.length > 0) {
            return res.status(400).json({
                message: "Berkas masih memiliki data peminjaman dan tidak dapat dihapus"
            });
        }

        const result = await pool.query(
            `
            DELETE FROM berkas
            WHERE id = $1
            RETURNING *
            `,
            [id]
        );

        if (result.rows.length === 0) {
            return res.status(404).json({
                message: "Berkas tidak ditemukan"
            });
        }

        await createAuditLog(req.user.id, "DELETE_BERKAS", "BERKAS", id);

        res.status(200).json({
            message: "Berkas berhasil dihapus",
            data: result.rows[0]
        });
    } catch (error) {
        res.status(500).json({
            message: "Gagal menghapus berkas",
            error: error.message
        });
    }
};

const getBerkasFile = async (req, res) => {
    try {
        const { id } = req.params;

        const result = await pool.query(
            `
            SELECT
                id,
                nama_file,
                path_file,
                hash_sha256
            FROM berkas
            WHERE id = $1
            `,
            [id]
        );

        if (result.rows.length === 0) {
            return res.status(404).json({
                message: "Berkas tidak ditemukan"
            });
        }

        const berkas = result.rows[0];

        if (!berkas.path_file || !fs.existsSync(berkas.path_file)) {
            return res.status(404).json({
                message: "File arsip tidak ditemukan"
            });
        }

        const currentHash = calculateFileHash(berkas.path_file);

        if (berkas.hash_sha256 && currentHash !== berkas.hash_sha256) {
            await createAuditLog(
                req.user.id,
                "POTENSI_ANOMALI_HASH_BERKAS",
                "BERKAS",
                id,
                {
                    expected: berkas.hash_sha256,
                    actual: currentHash
                }
            );

            return res.status(409).json({
                message: "Integritas file arsip berubah. Akses file diblokir.",
                expected_hash: berkas.hash_sha256,
                actual_hash: currentHash
            });
        }

        await createAuditLog(req.user.id, "ACCESS_BERKAS_FILE", "BERKAS", id);

        res.download(
            path.resolve(berkas.path_file),
            berkas.nama_file || `berkas-${id}.pdf`
        );
    } catch (error) {
        res.status(500).json({
            message: "Gagal mengakses file berkas",
            error: error.message
        });
    }
};

const verifyBerkasIntegrity = async (req, res) => {
    try {
        const { id } = req.params;

        const berkas = await getVerificationBerkas(id);

        if (!berkas) {
            return res.status(404).json({
                message: "Berkas tidak ditemukan"
            });
        }

        if (!berkas.hash_sha256) {
            return res.status(409).json({
                message: "Berkas belum memiliki hash SHA-256 tersimpan"
            });
        }

        if (!berkas.path_file || !fs.existsSync(berkas.path_file)) {
            return res.status(404).json({
                message: "File fisik arsip tidak ditemukan"
            });
        }

        const currentHash = calculateFileHash(berkas.path_file);
        const storedHash = String(berkas.hash_sha256).toLowerCase();
        const valid = currentHash === storedHash;
        const integrityStatus = valid ? "VALID" : "HASH TIDAK SESUAI";
        const verifiedAt = new Date();

        await pool.query(
            `
            UPDATE berkas
            SET
                status_integritas = $1,
                tanggal_verifikasi_terakhir = $2
            WHERE id = $3
            `,
            [integrityStatus, verifiedAt, id]
        );

        await pool.query(
            `
            INSERT INTO verifikasi_integritas_berkas
            (
                berkas_id,
                perkara_id,
                nomor_perkara,
                nama_terdakwa,
                nomor_berkas,
                nama_berkas,
                sha256_database,
                sha256_hasil,
                status,
                diverifikasi_oleh,
                keterangan,
                tanggal_verifikasi
            )
            VALUES ($1, $2, $3, $4, $5, $6, $7, $8, $9, $10, $11, $12)
            `,
            [
                berkas.id,
                berkas.perkara_id,
                berkas.nomor_perkara,
                berkas.nama_terdakwa,
                berkas.nomor_berkas,
                berkas.nama_berkas,
                storedHash,
                currentHash,
                integrityStatus,
                req.user.id,
                valid ? "Hash file sesuai dengan database" : "Hash file berbeda dari SHA-256 database",
                verifiedAt
            ]
        );

        const auditContext = getAuditContext(req);

        await createAuditLog(
            req.user.id,
            "VERIFIKASI_INTEGRITAS_BERKAS",
            "BERKAS",
            id,
            {
                stored_hash: storedHash,
                file_hash: currentHash,
                integrity_status: integrityStatus,
                hasil_hash: integrityStatus
            },
            0,
            1,
            integrityStatus,
            auditContext.ipAddress,
            auditContext.device
        );

        res.status(200).json({
            message: valid ? "Integritas berkas valid" : "Integritas berkas hash tidak sesuai",
            status: integrityStatus,
            integrity_status: integrityStatus,
            valid,
            hash_database: storedHash,
            hash_file: currentHash,
            verified_at: verifiedAt.toISOString(),
            berkas: {
                id: berkas.id,
                perkara_id: berkas.perkara_id,
                nomor_perkara: berkas.nomor_perkara,
                nama_terdakwa: berkas.nama_terdakwa,
                nomor_berkas: berkas.nomor_berkas,
                nama_berkas: berkas.nama_berkas,
                nama_file: berkas.nama_file,
                tipe_file: berkas.tipe_file,
                ukuran: berkas.ukuran,
                tanggal_upload: berkas.tanggal_mulai_aktif || berkas.tanggal_berkas,
                lokasi_penyimpanan: berkas.path_file,
                status_integritas: integrityStatus,
                tanggal_verifikasi_terakhir: verifiedAt.toISOString()
            }
        });
    } catch (error) {
        res.status(500).json({
            message: "Gagal memverifikasi integritas berkas",
            error: error.message
        });
    }
};

const exportVerificationReport = async (req, res) => {
    try {
        const { id } = req.params;
        const { hash_database, hash_file, status, verified_at } = req.body;
        const berkas = await getVerificationBerkas(id);

        if (!berkas) {
            return res.status(404).json({
                message: "Berkas tidak ditemukan"
            });
        }

        const normalizedStatus = String(status || "").toUpperCase();
        const reportStatus = ["MATCH", "VALID"].includes(normalizedStatus) ? "VALID" : "INVALID";
        const verifiedAt = verified_at ? new Date(verified_at) : new Date();
        const databaseHash = hash_database || berkas.hash_sha256;
        const pdf = createSimplePdf([
            "Laporan Verifikasi Integritas Berkas",
            "Sistem Arsip Digital",
            "",
            `Nama Arsip: ${berkas.nama_berkas || "-"}`,
            `Nama File: ${berkas.nama_file || "-"}`,
            `Nomor Perkara: ${berkas.nomor_perkara || "-"}`,
            `Waktu Verifikasi: ${verifiedAt.toISOString()}`,
            `Hash Database: ${databaseHash || "-"}`,
            `Hash File: ${hash_file || "-"}`,
            `Hasil: ${reportStatus === "VALID" ? "Integritas Valid" : "Integritas Tidak Valid"}`
        ]);

        await createAuditLog(req.user.id, "EXPORT_VERIFICATION_REPORT", "BERKAS", id, { status: reportStatus });

        res.setHeader("Content-Type", "application/pdf");
        res.setHeader("Content-Disposition", `attachment; filename=verification-report-${id}.pdf`);
        res.status(200).send(pdf);
    } catch (error) {
        res.status(500).json({
            message: "Gagal membuat laporan verifikasi",
            error: error.message
        });
    }
};

module.exports = {
    getAllBerkas,
    getBerkasById,
    createBerkas,
    updateBerkas,
    deleteBerkas,
    getBerkasFile,
    verifyBerkasIntegrity,
    exportVerificationReport,
    getBerkasAkanJatuhTempo,
    getIntegrityHistory,
    getSystemNotifications,
    prosesRetensiOtomatis,
    getBerkasRetensiSelesai
};



