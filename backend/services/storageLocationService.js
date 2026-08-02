const STATUS_KOSONG = "Kosong";
const STATUS_TERSEDIA = "Tersedia";
const STATUS_PENUH = "Penuh";

const getQueryRunner = (clientOrPool) => clientOrPool;

const calculateRakStatus = (jumlahPerkara, kapasitas) => {
    if (jumlahPerkara <= 0) {
        return STATUS_KOSONG;
    }

    if (jumlahPerkara >= kapasitas) {
        return STATUS_PENUH;
    }

    return STATUS_TERSEDIA;
};

const recalculateRak = async (clientOrPool, rakId) => {
    const runner = getQueryRunner(clientOrPool);
    const result = await runner.query(
        `
        UPDATE rak
        SET
            jumlah_perkara = stats.jumlah_perkara,
            status = CASE
                WHEN stats.jumlah_perkara = 0 THEN $2
                WHEN stats.jumlah_perkara >= rak.kapasitas THEN $3
                ELSE $4
            END
        FROM (
            SELECT
                rak.id,
                COUNT(perkara.id)::int AS jumlah_perkara
            FROM rak
            LEFT JOIN perkara ON perkara.rak_id = rak.id
            WHERE rak.id = $1
            GROUP BY rak.id
        ) AS stats
        WHERE rak.id = stats.id
        RETURNING rak.lemari_id
        `,
        [rakId, STATUS_KOSONG, STATUS_PENUH, STATUS_TERSEDIA]
    );

    return result.rows[0]?.lemari_id;
};

const recalculateLemari = async (clientOrPool, lemariId) => {
    const runner = getQueryRunner(clientOrPool);
    await runner.query(
        `
        UPDATE lemari
        SET
            jumlah_rak = stats.total_rak,
            kapasitas_total = stats.kapasitas_total,
            jumlah_terpakai = stats.jumlah_terpakai,
            status = CASE
                WHEN stats.total_rak = 0 OR stats.jumlah_terpakai = 0 THEN $2
                WHEN stats.rak_penuh = stats.total_rak THEN $3
                ELSE $4
            END
        FROM (
            SELECT
                lemari.id,
                COUNT(rak.id)::int AS total_rak,
                COALESCE(SUM(rak.kapasitas), 0)::int AS kapasitas_total,
                COUNT(rak.id) FILTER (WHERE rak.jumlah_perkara > 0)::int AS jumlah_terpakai,
                COUNT(rak.id) FILTER (WHERE rak.status = $3)::int AS rak_penuh
            FROM lemari
            LEFT JOIN rak ON rak.lemari_id = lemari.id
            WHERE lemari.id = $1
            GROUP BY lemari.id
        ) AS stats
        WHERE lemari.id = stats.id
        `,
        [lemariId, STATUS_KOSONG, STATUS_PENUH, STATUS_TERSEDIA]
    );
};

const recalculateLocationByRak = async (clientOrPool, rakId) => {
    const lemariId = await recalculateRak(clientOrPool, rakId);

    if (lemariId) {
        await recalculateLemari(clientOrPool, lemariId);
    }
};

const recalculateAllLocations = async (clientOrPool) => {
    const runner = getQueryRunner(clientOrPool);
    const rakResult = await runner.query("SELECT id FROM rak ORDER BY id");

    for (const row of rakResult.rows) {
        await recalculateRak(runner, row.id);
    }

    const lemariResult = await runner.query("SELECT id FROM lemari ORDER BY id");

    for (const row of lemariResult.rows) {
        await recalculateLemari(runner, row.id);
    }
};

const findAvailableRak = async (clientOrPool, lemariId = null) => {
    const runner = getQueryRunner(clientOrPool);
    const values = [STATUS_PENUH];
    let whereClause = "COALESCE(rak.status, $2) <> $1";
    values.push(STATUS_KOSONG);

    if (lemariId) {
        values.push(lemariId);
        whereClause += ` AND rak.lemari_id = $${values.length}`;
    }

    const result = await runner.query(
        `
        SELECT
            rak.id AS rak_id,
            rak.lemari_id,
            rak.kapasitas,
            rak.jumlah_perkara,
            rak.status,
            lemari.nama_lemari,
            rak.nama_rak
        FROM rak
        JOIN lemari ON rak.lemari_id = lemari.id
        WHERE ${whereClause}
        AND rak.jumlah_perkara < rak.kapasitas
        ORDER BY lemari.nama_lemari, lemari.id, rak.id
        LIMIT 1
        `,
        values
    );

    return result.rows[0] || null;
};

module.exports = {
    STATUS_KOSONG,
    STATUS_TERSEDIA,
    STATUS_PENUH,
    calculateRakStatus,
    recalculateRak,
    recalculateLemari,
    recalculateLocationByRak,
    recalculateAllLocations,
    findAvailableRak
};
