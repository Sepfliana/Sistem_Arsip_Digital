const pool = require("../config/database");
const fs = require("fs");
const path = require("path");
const { createAuditLog } = require("../services/auditLogService");
const {
    STATUS_PENUH,
    findAvailableRak,
    recalculateLocationByRak
} = require("../services/storageLocationService");

const COVER_UPLOAD_DIR = path.join(__dirname, "..", "uploads", "covers");

const removeCoverFile = (coverFile) => {
    if (!coverFile) return;

    const resolvedPath = path.resolve(COVER_UPLOAD_DIR, path.basename(coverFile));
    const resolvedDir = path.resolve(COVER_UPLOAD_DIR);

    if (!resolvedPath.startsWith(resolvedDir)) return;

    fs.promises.unlink(resolvedPath).catch((error) => {
        if (error.code !== "ENOENT") {
            console.error("Gagal menghapus cover perkara:", error.message);
        }
    });
};

const normalizeTerdakwaList = (terdakwa = []) => {
    if (typeof terdakwa === "string") {
        try {
            const parsed = JSON.parse(terdakwa);
            return normalizeTerdakwaList(parsed);
        } catch (error) {
            return normalizeTerdakwaList([terdakwa]);
        }
    }

    if (!Array.isArray(terdakwa)) {
        return [];
    }

    return terdakwa
        .map((item) => {
            if (typeof item === "string") {
                return { nama_terdakwa: item.trim() };
            }

            return {
                id: item.id,
                nama_terdakwa: String(item.nama_terdakwa || item.nama || "").trim()
            };
        })
        .filter((item) => item.nama_terdakwa);
};

const serializeTerdakwaList = (terdakwaList) => terdakwaList
    .map((item) => item.nama_terdakwa)
    .filter(Boolean)
    .join(", ");

const parseTerdakwaText = (value = "") => String(value || "")
    .split(",")
    .map((item) => item.trim())
    .filter(Boolean)
    .map((nama_terdakwa, index) => ({
        id: index + 1,
        nama_terdakwa
    }));

const attachTerdakwa = async (perkaraRows) => perkaraRows.map((row) => ({
    ...row,
    terdakwa: parseTerdakwaText(row.nama_terdakwa)
}));

const normalizePositiveInteger = (value) => {
    if (value === undefined || value === null || value === "") {
        return null;
    }

    const numberValue = Number(value);

    if (!Number.isInteger(numberValue) || numberValue <= 0) {
        return null;
    }

    return numberValue;
};

const validateMasterData = async ({
    jaksa_id,
    jenis_pidana_id,
    jenis_perkara_id,
    instansi_penyidik_id
}) => {
    const jaksaId = normalizePositiveInteger(jaksa_id);
    const jenisPidanaId = normalizePositiveInteger(jenis_pidana_id);
    const jenisPerkaraId = normalizePositiveInteger(jenis_perkara_id);
    const instansiPenyidikId = normalizePositiveInteger(instansi_penyidik_id);

    if (jaksaId === null) {
        return { errorMessage: "ID jaksa tidak valid" };
    }

    if (jenisPidanaId === null) {
        return { errorMessage: "ID jenis pidana tidak valid" };
    }

    if (jenisPerkaraId === null) {
        return { errorMessage: "ID jenis perkara tidak valid" };
    }

    if (instansiPenyidikId === null) {
        return { errorMessage: "ID instansi penyidik tidak valid" };
    }

    const jaksaResult = await pool.query(
        `
        SELECT id
        FROM jaksa
        WHERE id = $1
        `,
        [jaksaId]
    );

    if (jaksaResult.rows.length === 0) {
        return { errorMessage: "Jaksa tidak ditemukan" };
    }

    const jenisPidanaResult = await pool.query(
        `
        SELECT id
        FROM jenis_pidana
        WHERE id = $1
        `,
        [jenisPidanaId]
    );

    if (jenisPidanaResult.rows.length === 0) {
        return { errorMessage: "Jenis pidana tidak ditemukan" };
    }

    const jenisPerkaraResult = await pool.query(
        `
        SELECT id, jenis_pidana_id
        FROM jenis_perkara
        WHERE id = $1
        `,
        [jenisPerkaraId]
    );

    if (jenisPerkaraResult.rows.length === 0) {
        return { errorMessage: "Jenis perkara tidak ditemukan" };
    }

    if (String(jenisPerkaraResult.rows[0].jenis_pidana_id) !== String(jenisPidanaId)) {
        return { errorMessage: "Jenis perkara tidak sesuai dengan jenis pidana." };
    }

    const instansiResult = await pool.query(
        `
        SELECT id
        FROM instansi_penyidik
        WHERE id = $1
        `,
        [instansiPenyidikId]
    );

    if (instansiResult.rows.length === 0) {
        return { errorMessage: "Instansi penyidik tidak ditemukan" };
    }

    return {
        jaksaId,
        jenisPidanaId,
        jenisPerkaraId,
        instansiPenyidikId
    };
};

const perkaraDetailSelect = `
    SELECT
        perkara.id,
        perkara.nomor_perkara,
        perkara.nama_terdakwa,
        perkara.jaksa_id,
        jaksa.nama_jaksa,
        perkara.jenis_pidana_id,
        jenis_pidana.nama_jenis_pidana,
        perkara.jenis_perkara_id,
        jenis_perkara.nama_jenis_perkara,
        perkara.instansi_penyidik_id,
        instansi_penyidik.nama_instansi,
        perkara.melanggar_pasal,
        perkara.lemari_id,
        lemari.nama_lemari AS lemari,
        perkara.rak_id,
        rak.nama_rak AS rak,
        perkara.tanggal_mulai,
        perkara.tanggal_selesai,
        perkara.cover_file,
        perkara.keterangan,
        perkara.created_at,
        perkara.updated_at
    FROM perkara
    JOIN jaksa
        ON perkara.jaksa_id = jaksa.id
    JOIN jenis_pidana
        ON perkara.jenis_pidana_id = jenis_pidana.id
    JOIN jenis_perkara
        ON perkara.jenis_perkara_id = jenis_perkara.id
    JOIN instansi_penyidik
        ON perkara.instansi_penyidik_id = instansi_penyidik.id
    JOIN lemari
        ON perkara.lemari_id = lemari.id
    JOIN rak
        ON perkara.rak_id = rak.id
`;

const getPerkaraDetailById = async (id) => {
    const result = await pool.query(
        `
        ${perkaraDetailSelect}
        WHERE perkara.id = $1
        `,
        [id]
    );

    return result.rows[0];
};

const getUploadedCoverFiles = (req) => {
    if (Array.isArray(req.files)) return req.files;
    if (req.file) return [req.file];
    return [];
};

const buildCoverUrl = (perkaraId, coverId = null) => coverId
    ? `/perkara/${perkaraId}/cover/${coverId}`
    : `/perkara/${perkaraId}/cover`;

const normalizeCoverRow = (row, perkaraId, index = 0) => ({
    id: row.id ? String(row.id) : `legacy-${perkaraId}`,
    perkara_id: perkaraId,
    file_name: row.file_name || path.basename(row.file_path || row.cover_file || ""),
    mime_type: row.mime_type || "application/pdf",
    ukuran: row.ukuran || null,
    halaman: row.halaman || null,
    urutan: row.urutan || index + 1,
    created_at: row.created_at || null,
    url: buildCoverUrl(perkaraId, row.id || null)
});

const getPerkaraCovers = async (perkara) => {
    if (!perkara?.id) return [];

    const result = await pool.query(
        `
        SELECT id, perkara_id, file_path, file_name, mime_type, ukuran, halaman, urutan, created_at
        FROM perkara_covers
        WHERE perkara_id = $1
        ORDER BY urutan ASC, id ASC
        `,
        [perkara.id]
    );

    if (result.rows.length > 0) {
        return result.rows.map((row, index) => normalizeCoverRow(row, perkara.id, index));
    }

    if (!perkara.cover_file) return [];

    return [normalizeCoverRow({ file_path: perkara.cover_file, file_name: path.basename(perkara.cover_file) }, perkara.id, 0)];
};

const attachCoversPerkara = async (perkara) => {
    if (!perkara) return perkara;
    const covers = await getPerkaraCovers(perkara);

    return {
        ...perkara,
        covers,
        cover_url: covers[0]?.url || null
    };
};

const persistUploadedCovers = async (client, perkaraId, files) => {
    if (!files.length) return;

    const countResult = await client.query(
        `SELECT COALESCE(MAX(urutan), 0)::int AS max_urutan FROM perkara_covers WHERE perkara_id = $1`,
        [perkaraId]
    );
    let order = Number(countResult.rows[0]?.max_urutan || 0);

    for (const file of files) {
        order += 1;
        await client.query(
            `
            INSERT INTO perkara_covers (perkara_id, file_path, file_name, mime_type, ukuran, urutan)
            VALUES ($1, $2, $3, $4, $5, $6)
            `,
            [perkaraId, file.filename, file.originalname, file.mimetype, file.size, order]
        );
    }
};

const replaceUploadedCovers = async (client, perkaraId, files) => {
    if (!files.length) return [];

    const existing = await client.query(
        `SELECT file_path FROM perkara_covers WHERE perkara_id = $1`,
        [perkaraId]
    );

    await client.query(`DELETE FROM perkara_covers WHERE perkara_id = $1`, [perkaraId]);
    await persistUploadedCovers(client, perkaraId, files);

    return existing.rows.map((row) => row.file_path).filter(Boolean);
};


const resolveCoverPath = async (perkaraId, coverId = null) => {
    if (coverId) {
        const coverResult = await pool.query(
            `
            SELECT file_path, file_name
            FROM perkara_covers
            WHERE perkara_id = $1 AND id = $2
            `,
            [perkaraId, coverId]
        );

        if (coverResult.rows.length > 0) {
            return coverResult.rows[0];
        }

        return null;
    }

    const firstCover = await pool.query(
        `
        SELECT file_path, file_name
        FROM perkara_covers
        WHERE perkara_id = $1
        ORDER BY urutan ASC, id ASC
        LIMIT 1
        `,
        [perkaraId]
    );

    if (firstCover.rows.length > 0) return firstCover.rows[0];

    const legacyResult = await pool.query(
        `SELECT cover_file FROM perkara WHERE id = $1`,
        [perkaraId]
    );

    if (legacyResult.rows.length === 0) return null;
    const coverFile = legacyResult.rows[0].cover_file;

    return coverFile ? { file_path: coverFile, file_name: path.basename(coverFile) } : null;
};

const attachBerkasPerkara = async (perkara) => {
    if (!perkara) return perkara;

    const result = await pool.query(
        `
        SELECT
            berkas.*,
            perkara.nomor_perkara,
            perkara.nama_terdakwa,
            lemari.nama_lemari,
            rak.nama_rak
        FROM berkas
        JOIN perkara
            ON berkas.perkara_id = perkara.id
        LEFT JOIN lemari
            ON perkara.lemari_id = lemari.id
        LEFT JOIN rak
            ON perkara.rak_id = rak.id
        WHERE berkas.perkara_id = $1
        ORDER BY berkas.id DESC
        `,
        [perkara.id]
    );

    const berkasByJenis = {
        "Pra Penuntutan": null,
        "Penuntutan": null,
        "Eksekusi": null
    };

    result.rows.forEach((item) => {
        if (Object.prototype.hasOwnProperty.call(berkasByJenis, item.jenis_berkas) && !berkasByJenis[item.jenis_berkas]) {
            berkasByJenis[item.jenis_berkas] = item;
        }
    });

    return {
        ...perkara,
        berkas: result.rows,
        berkas_by_jenis: berkasByJenis
    };
};

const resolveLokasiPerkara = async ({ lemari_id, rak_id }) => {
    if (lemari_id && rak_id) {
        return { lemariId: lemari_id, rakId: rak_id };
    }

    if (rak_id) {
        const rakResult = await pool.query(
            `SELECT id, lemari_id FROM rak WHERE id = $1`,
            [rak_id]
        );

        if (rakResult.rows.length === 0) {
            return { errorStatus: 404, errorMessage: "Rak tidak ditemukan" };
        }

        return {
            lemariId: rakResult.rows[0].lemari_id,
            rakId: rakResult.rows[0].id
        };
    }

    const availableRak = await findAvailableRak(pool, lemari_id || null);

    if (!availableRak) {
        return {
            errorStatus: 400,
            errorMessage: "Tidak ada rak yang tersedia."
        };
    }

    return {
        lemariId: availableRak.lemari_id,
        rakId: availableRak.rak_id
    };
};

const validateLokasiPerkara = async ({ lemari_id, rak_id, currentPerkaraId = null }) => {
    const cekLemari = await pool.query(
        `
        SELECT id
        FROM lemari
        WHERE id = $1
        `,
        [lemari_id]
    );

    if (cekLemari.rows.length === 0) {
        return { errorStatus: 400, errorMessage: "Lemari tidak ditemukan" };
    }

    const cekRak = await pool.query(
        `
        SELECT id, kapasitas, jumlah_perkara, status
        FROM rak
        WHERE id = $1
        `,
        [rak_id]
    );

    if (cekRak.rows.length === 0) {
        return { errorStatus: 400, errorMessage: "Rak tidak ditemukan" };
    }

    const selectedRak = cekRak.rows[0];
    const currentPerkaraUsesRak = currentPerkaraId
        ? await pool.query(
            `
            SELECT id
            FROM perkara
            WHERE id = $1
            AND rak_id = $2
            `,
            [currentPerkaraId, rak_id]
        )
        : { rows: [] };

    if (
        currentPerkaraUsesRak.rows.length === 0 &&
        (selectedRak.status === STATUS_PENUH || Number(selectedRak.jumlah_perkara || 0) >= Number(selectedRak.kapasitas || 0))
    ) {
        return { errorStatus: 400, errorMessage: "Rak penuh dan tidak dapat dipilih" };
    }

    const validasiRakLemari = await pool.query(
        `
        SELECT id
        FROM rak
        WHERE id = $1
        AND lemari_id = $2
        `,
        [rak_id, lemari_id]
    );

    if (validasiRakLemari.rows.length === 0) {
        return { errorStatus: 400, errorMessage: "Rak tidak berada pada lemari yang dipilih" };
    }

    return {};
};

// GET semua perkara
const getAllPerkara = async (req, res) => {
    try {
        const {
            lemari_id,
            rak_id,
            search,
            nomor_perkara,
            nama_terdakwa,
            jaksa_id,
            jenis_pidana_id,
            jenis_perkara_id,
            instansi_penyidik_id,
            tahun
        } = req.query;
        const values = [];
        const conditions = [];

        const addLikeFilter = (column, value) => {
            if (!value) {
                return;
            }

            values.push(`%${value}%`);
            conditions.push(`${column} ILIKE $${values.length}`);
        };

        const addIdFilter = (column, value, message) => {
            if (!value) {
                return null;
            }

            const normalizedValue = normalizePositiveInteger(value);

            if (normalizedValue === null) {
                return message;
            }

            values.push(normalizedValue);
            conditions.push(`${column} = $${values.length}`);
            return null;
        };

        let query = `
            SELECT
                perkara.id,
                perkara.nomor_perkara,
                perkara.nama_terdakwa,
                jaksa.nama_jaksa,
                jenis_pidana.nama_jenis_pidana,
                jenis_perkara.nama_jenis_perkara,
                instansi_penyidik.nama_instansi,
                perkara.tanggal_mulai,
                perkara.tanggal_selesai
            FROM perkara
            JOIN jaksa
                ON perkara.jaksa_id = jaksa.id
            JOIN jenis_pidana
                ON perkara.jenis_pidana_id = jenis_pidana.id
            JOIN jenis_perkara
                ON perkara.jenis_perkara_id = jenis_perkara.id
            JOIN instansi_penyidik
                ON perkara.instansi_penyidik_id = instansi_penyidik.id
            JOIN lemari
                ON perkara.lemari_id = lemari.id
            JOIN rak
                ON perkara.rak_id = rak.id
        `;

        const idFilterError =
            addIdFilter("perkara.lemari_id", lemari_id, "ID lemari tidak valid") ||
            addIdFilter("perkara.rak_id", rak_id, "ID rak tidak valid") ||
            addIdFilter("perkara.jaksa_id", jaksa_id, "ID jaksa tidak valid") ||
            addIdFilter("perkara.jenis_pidana_id", jenis_pidana_id, "ID jenis pidana tidak valid") ||
            addIdFilter("perkara.jenis_perkara_id", jenis_perkara_id, "ID jenis perkara tidak valid") ||
            addIdFilter("perkara.instansi_penyidik_id", instansi_penyidik_id, "ID instansi penyidik tidak valid");

        if (idFilterError) {
            return res.status(400).json({
                message: idFilterError
            });
        }

        if (tahun) {
            const normalizedTahun = normalizePositiveInteger(tahun);

            if (normalizedTahun === null) {
                return res.status(400).json({
                    message: "Tahun tidak valid"
                });
            }

            values.push(normalizedTahun);
            conditions.push(`EXTRACT(YEAR FROM perkara.tanggal_mulai) = $${values.length}`);
        }

        addLikeFilter("perkara.nomor_perkara", nomor_perkara);
        addLikeFilter("perkara.nama_terdakwa", nama_terdakwa);

        if (search) {
            values.push(`%${search}%`);
            conditions.push(`(
                perkara.nomor_perkara ILIKE $${values.length}
                OR perkara.nama_terdakwa ILIKE $${values.length}
                OR jaksa.nama_jaksa ILIKE $${values.length}
                OR jenis_pidana.nama_jenis_pidana ILIKE $${values.length}
                OR jenis_perkara.nama_jenis_perkara ILIKE $${values.length}
                OR instansi_penyidik.nama_instansi ILIKE $${values.length}
                OR CAST(EXTRACT(YEAR FROM perkara.tanggal_mulai) AS TEXT) ILIKE $${values.length}
            )`);
        }

        if (conditions.length > 0) {
            query += ` WHERE ${conditions.join(" AND ")}`;
        }

        query += ` ORDER BY perkara.nama_terdakwa ASC, perkara.tanggal_mulai DESC, perkara.id DESC`;

        const result = await pool.query(query, values);
        const rows = await attachTerdakwa(result.rows);

        res.status(200).json(rows);

    } catch (error) {
        res.status(500).json({
            message: "Gagal mengambil data perkara",
            error: error.message
        });
    }
};

// GET perkara berdasarkan ID
const getPerkaraById = async (req, res) => {
    try {
        const { id } = req.params;

        const result = await pool.query(
            `
            ${perkaraDetailSelect}
            WHERE perkara.id = $1
            `,
            [id]
        );

        if (result.rows.length === 0) {
            return res.status(404).json({
                message: "Perkara tidak ditemukan"
            });
        }

        const rows = await attachTerdakwa(result.rows);
        const detail = await attachBerkasPerkara(await attachCoversPerkara(rows[0]));

        res.status(200).json(detail);

    } catch (error) {
        res.status(500).json({
            message: "Gagal mengambil data perkara",
            error: error.message
        });
    }
};

const getPerkaraCover = async (req, res) => {
    try {
        const { id, coverId } = req.params;

        const perkaraResult = await pool.query(`SELECT id FROM perkara WHERE id = $1`, [id]);

        if (perkaraResult.rows.length === 0) {
            return res.status(404).json({ message: "Perkara tidak ditemukan" });
        }

        const cover = await resolveCoverPath(id, coverId || null);

        if (!cover?.file_path) {
            return res.status(404).json({ message: "Cover perkara belum tersedia" });
        }

        const coverPath = path.resolve(COVER_UPLOAD_DIR, path.basename(cover.file_path));
        const resolvedDir = path.resolve(COVER_UPLOAD_DIR);

        if (!coverPath.startsWith(resolvedDir) || !fs.existsSync(coverPath)) {
            return res.status(404).json({ message: "File cover tidak ditemukan" });
        }

        res.setHeader("Content-Type", "application/pdf");
        res.setHeader("Content-Disposition", `inline; filename="${path.basename(cover.file_name || cover.file_path)}"`);
        res.sendFile(coverPath);
    } catch (error) {
        res.status(500).json({
            message: "Gagal membuka cover perkara",
            error: error.message
        });
    }
};

// POST tambah perkara
const createPerkara = async (req, res) => {
    try {
        const {
            nomor_perkara,
            jaksa_id,
            jenis_pidana_id,
            jenis_perkara_id,
            instansi_penyidik_id,
            melanggar_pasal,
            tanggal_mulai,
            tanggal_selesai,
            lemari_id,
            rak_id,
            keterangan,
            nama_terdakwa,
            terdakwa,
            replace_cover
        } = req.body;

        const coverFiles = getUploadedCoverFiles(req);
        const coverFile = coverFiles[0]?.filename || null;

        const terdakwaList = normalizeTerdakwaList(terdakwa || [nama_terdakwa]);

        if (!nomor_perkara || terdakwaList.length === 0 || !melanggar_pasal || !tanggal_mulai) {
            return res.status(400).json({
                message: "Nomor perkara, nama terdakwa, melanggar pasal, dan tanggal mulai wajib diisi"
            });
        }

        if (normalizePositiveInteger(lemari_id) === null || normalizePositiveInteger(rak_id) === null) {
            return res.status(400).json({
                message: "ID lemari dan rak wajib diisi dengan benar"
            });
        }

        if (
            normalizePositiveInteger(jaksa_id) === null ||
            normalizePositiveInteger(jenis_pidana_id) === null ||
            normalizePositiveInteger(jenis_perkara_id) === null ||
            normalizePositiveInteger(instansi_penyidik_id) === null
        ) {
            return res.status(400).json({
                message: "ID jaksa, jenis pidana, jenis perkara, dan instansi penyidik wajib diisi dengan benar"
            });
        }

        if (terdakwaList.length === 0) {
            return res.status(400).json({
                message: "Minimal satu terdakwa wajib diisi"
            });
        }

        const validasiMasterData = await validateMasterData({
            jaksa_id,
            jenis_pidana_id,
            jenis_perkara_id,
            instansi_penyidik_id
        });

        if (validasiMasterData.errorMessage) {
            return res.status(400).json({
                message: validasiMasterData.errorMessage
            });
        }

        const lokasi = await resolveLokasiPerkara({ lemari_id, rak_id });

        if (lokasi.errorMessage) {
            return res.status(lokasi.errorStatus).json({
                message: lokasi.errorMessage
            });
        }

        const finalLemariId = lokasi.lemariId;
        const finalRakId = lokasi.rakId;
        const validasiLokasi = await validateLokasiPerkara({
            lemari_id: finalLemariId,
            rak_id: finalRakId
        });

        if (validasiLokasi.errorMessage) {
            return res.status(validasiLokasi.errorStatus).json({
                message: validasiLokasi.errorMessage
            });
        }

        const client = await pool.connect();
        let createdPerkara;

        try {
            await client.query("BEGIN");

            const result = await client.query(
                `
                INSERT INTO perkara
                (
                    nomor_perkara,
                    nama_terdakwa,
                    jaksa_id,
                    jenis_pidana_id,
                    jenis_perkara_id,
                    instansi_penyidik_id,
                    melanggar_pasal,
                    tanggal_mulai,
                    tanggal_selesai,
                    lemari_id,
                    rak_id,
                    cover_file,
                    keterangan
                )
                VALUES
                ($1, $2, $3, $4, $5, $6, $7, $8, $9, $10, $11, $12, $13)
                RETURNING *
                `,
                [
                    nomor_perkara,
                    serializeTerdakwaList(terdakwaList),
                    validasiMasterData.jaksaId,
                    validasiMasterData.jenisPidanaId,
                    validasiMasterData.jenisPerkaraId,
                    validasiMasterData.instansiPenyidikId,
                    melanggar_pasal,
                    tanggal_mulai,
                    tanggal_selesai || null,
                    finalLemariId,
                    finalRakId,
                    coverFile,
                    keterangan || null
                ]
            );

            createdPerkara = result.rows[0];
            await persistUploadedCovers(client, createdPerkara.id, coverFiles);
            await recalculateLocationByRak(client, finalRakId);
            await client.query("COMMIT");
        } catch (error) {
            await client.query("ROLLBACK");
            throw error;
        } finally {
            client.release();
        }

        const createdDetail = await getPerkaraDetailById(createdPerkara.id);
        const createdWithCovers = await attachCoversPerkara(createdDetail);
        const [createdWithTerdakwa] = await attachTerdakwa([createdWithCovers]);

        res.status(201).json({
            message: "Perkara berhasil ditambahkan",
            data: createdWithTerdakwa
        });

        await createAuditLog(req.user.id, "CREATE_PERKARA", "PERKARA", createdPerkara.id);

    } catch (error) {

        if (error.code === "23505") {
            return res.status(400).json({
                message: "Nomor perkara sudah digunakan"
            });
        }

        res.status(500).json({
            message: "Gagal menambahkan perkara",
            error: error.message
        });
    }
};

// PUT update perkara
const updatePerkara = async (req, res) => {
    try {
        const { id } = req.params;

        const {
            nomor_perkara,
            jaksa_id,
            jenis_pidana_id,
            jenis_perkara_id,
            instansi_penyidik_id,
            melanggar_pasal,
            tanggal_mulai,
            tanggal_selesai,
            lemari_id,
            rak_id,
            keterangan,
            nama_terdakwa,
            terdakwa,
            replace_cover
        } = req.body;

        const coverFiles = getUploadedCoverFiles(req);
        const coverFile = coverFiles[0]?.filename || null;

        const terdakwaList = normalizeTerdakwaList(terdakwa || [nama_terdakwa]);

        if (!nomor_perkara || terdakwaList.length === 0 || !melanggar_pasal || !tanggal_mulai) {
            return res.status(400).json({
                message: "Nomor perkara, nama terdakwa, melanggar pasal, dan tanggal mulai wajib diisi"
            });
        }

        if (terdakwaList.length === 0) {
            return res.status(400).json({
                message: "Minimal satu terdakwa wajib diisi"
            });
        }

        if (normalizePositiveInteger(lemari_id) === null || normalizePositiveInteger(rak_id) === null) {
            return res.status(400).json({
                message: "ID lemari dan rak wajib diisi dengan benar"
            });
        }

        if (
            normalizePositiveInteger(jaksa_id) === null ||
            normalizePositiveInteger(jenis_pidana_id) === null ||
            normalizePositiveInteger(jenis_perkara_id) === null ||
            normalizePositiveInteger(instansi_penyidik_id) === null
        ) {
            return res.status(400).json({
                message: "ID jaksa, jenis pidana, jenis perkara, dan instansi penyidik wajib diisi dengan benar"
            });
        }

        const cekPerkara = await pool.query(
            `
            SELECT *
            FROM perkara
            WHERE id = $1
            `,
            [id]
        );

        if (cekPerkara.rows.length === 0) {
            return res.status(404).json({
                message: "Perkara tidak ditemukan"
            });
        }

        const perkaraLama = cekPerkara.rows[0];
        const finalJaksaId = jaksa_id ?? perkaraLama.jaksa_id;
        const finalJenisPidanaId = jenis_pidana_id ?? perkaraLama.jenis_pidana_id;
        const finalJenisPerkaraId = jenis_perkara_id ?? perkaraLama.jenis_perkara_id;
        const finalInstansiPenyidikId = instansi_penyidik_id ?? perkaraLama.instansi_penyidik_id;
        const validasiMasterData = await validateMasterData({
            jaksa_id: finalJaksaId,
            jenis_pidana_id: finalJenisPidanaId,
            jenis_perkara_id: finalJenisPerkaraId,
            instansi_penyidik_id: finalInstansiPenyidikId
        });

        if (validasiMasterData.errorMessage) {
            return res.status(400).json({
                message: validasiMasterData.errorMessage
            });
        }

        const finalLemariId = lemari_id ?? perkaraLama.lemari_id;
        const finalRakId = rak_id ?? perkaraLama.rak_id;
        const validasiLokasi = await validateLokasiPerkara({
            lemari_id: finalLemariId,
            rak_id: finalRakId,
            currentPerkaraId: id
        });

        if (validasiLokasi.errorMessage) {
            return res.status(validasiLokasi.errorStatus).json({
                message: validasiLokasi.errorMessage
            });
        }

        const client = await pool.connect();
        let updatedPerkara;

        try {
            await client.query("BEGIN");

            const result = await client.query(
                `
                UPDATE perkara
                SET
                    nomor_perkara = $1,
                    nama_terdakwa = $2,
                    jaksa_id = $3,
                    jenis_pidana_id = $4,
                    jenis_perkara_id = $5,
                    instansi_penyidik_id = $6,
                    melanggar_pasal = $7,
                    tanggal_mulai = $8,
                    tanggal_selesai = $9,
                    lemari_id = $10,
                    rak_id = $11,
                    keterangan = $12,
                    cover_file = $13,
                    updated_at = CURRENT_TIMESTAMP
                WHERE id = $14
                RETURNING *
                `,
                [
                    nomor_perkara ?? perkaraLama.nomor_perkara,
                    serializeTerdakwaList(terdakwaList),
                    validasiMasterData.jaksaId,
                    validasiMasterData.jenisPidanaId,
                    validasiMasterData.jenisPerkaraId,
                    validasiMasterData.instansiPenyidikId,
                    melanggar_pasal ?? perkaraLama.melanggar_pasal,
                    tanggal_mulai !== undefined ? tanggal_mulai : perkaraLama.tanggal_mulai,
                    tanggal_selesai !== undefined ? (tanggal_selesai || null) : perkaraLama.tanggal_selesai,
                    finalLemariId,
                    finalRakId,
                    keterangan !== undefined ? (keterangan || null) : perkaraLama.keterangan,
                    coverFile || perkaraLama.cover_file,
                    id
                ]
            );

            updatedPerkara = result.rows[0];
            const replacedCoverFiles = String(replace_cover || "").toLowerCase() === "true"
                ? await replaceUploadedCovers(client, updatedPerkara.id, coverFiles)
                : [];
            if (replacedCoverFiles.length === 0) {
                await persistUploadedCovers(client, updatedPerkara.id, coverFiles);
            }
            updatedPerkara.replaced_cover_files = replacedCoverFiles;

            await recalculateLocationByRak(client, perkaraLama.rak_id);

            if (String(perkaraLama.rak_id) !== String(finalRakId)) {
                await recalculateLocationByRak(client, finalRakId);
            }

            await client.query("COMMIT");
        } catch (error) {
            await client.query("ROLLBACK");
            throw error;
        } finally {
            client.release();
        }

        (updatedPerkara.replaced_cover_files || []).forEach(removeCoverFile);

        const updatedDetail = await getPerkaraDetailById(updatedPerkara.id);
        const updatedWithCovers = await attachCoversPerkara(updatedDetail);
        const [updatedWithTerdakwa] = await attachTerdakwa([updatedWithCovers]);


        res.status(200).json({
            message: "Perkara berhasil diperbarui",
            data: updatedWithTerdakwa
        });

        await createAuditLog(req.user.id, "UPDATE_PERKARA", "PERKARA", id);

    } catch (error) {

        if (error.statusCode) {
            return res.status(error.statusCode).json({
                message: error.message
            });
        }

        if (error.code === "23505") {
            return res.status(400).json({
                message: "Nomor perkara sudah digunakan"
            });
        }

        res.status(500).json({
            message: "Gagal memperbarui perkara",
            error: error.message
        });
    }
};

// DELETE perkara
const deletePerkara = async (req, res) => {
    try {
        const { id } = req.params;

        const cekBerkas = await pool.query(
            `
            SELECT id
            FROM berkas
            WHERE perkara_id = $1
            LIMIT 1
            `,
            [id]
        );

        if (cekBerkas.rows.length > 0) {
            return res.status(400).json({
                message: "Perkara masih memiliki berkas dan tidak dapat dihapus"
            });
        }

        const client = await pool.connect();
        let deletedPerkara;

        try {
            await client.query("BEGIN");

            const result = await client.query(
                `
                DELETE FROM perkara
                WHERE id = $1
                RETURNING *
                `,
                [id]
            );

            deletedPerkara = result.rows[0];

            if (deletedPerkara) {
                await recalculateLocationByRak(client, deletedPerkara.rak_id);
            }

            await client.query("COMMIT");
        } catch (error) {
            await client.query("ROLLBACK");
            throw error;
        } finally {
            client.release();
        }

        if (!deletedPerkara) {
            return res.status(404).json({
                message: "Perkara tidak ditemukan"
            });
        }

        res.status(200).json({
            message: "Perkara berhasil dihapus",
            data: deletedPerkara
        });

        if (deletedPerkara.cover_file) {
            removeCoverFile(deletedPerkara.cover_file);
        }

        await createAuditLog(req.user.id, "DELETE_PERKARA", "PERKARA", id);

    } catch (error) {
        res.status(500).json({
            message: "Gagal menghapus perkara",
            error: error.message
        });
    }
};

module.exports = {
    getAllPerkara,
    getPerkaraById,
    getPerkaraCover,
    createPerkara,
    updatePerkara,
    deletePerkara
};








