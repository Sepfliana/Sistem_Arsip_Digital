const pool = require("../config/database");

const normalizePositiveInteger = (value) => {
    const numberValue = Number(value);

    if (!Number.isInteger(numberValue) || numberValue <= 0) {
        return null;
    }

    return numberValue;
};

const getAllJaksa = async (req, res) => {
    try {
        const result = await pool.query(`
            SELECT
                id,
                nama_jaksa
            FROM jaksa
            WHERE is_active = true
            ORDER BY nama_jaksa ASC
        `);

        res.status(200).json(result.rows);
    } catch (error) {
        res.status(500).json({
            message: "Gagal mengambil data jaksa",
            error: error.message
        });
    }
};

const getAllJenisPidana = async (req, res) => {
    try {
        const result = await pool.query(`
            SELECT
                id,
                nama_jenis_pidana
            FROM jenis_pidana
            WHERE is_active = true
            ORDER BY nama_jenis_pidana ASC
        `);

        res.status(200).json(result.rows);
    } catch (error) {
        res.status(500).json({
            message: "Gagal mengambil data jenis pidana",
            error: error.message
        });
    }
};

const getAllInstansiPenyidik = async (req, res) => {
    try {
        const result = await pool.query(`
            SELECT
                id,
                nama_instansi
            FROM instansi_penyidik
            WHERE is_active = true
            ORDER BY nama_instansi ASC
        `);

        res.status(200).json(result.rows);
    } catch (error) {
        res.status(500).json({
            message: "Gagal mengambil data instansi penyidik",
            error: error.message
        });
    }
};

const getJenisPerkaraByJenisPidana = async (req, res) => {
    try {
        const jenisPidanaId = normalizePositiveInteger(req.params.jenisPidanaId);

        if (jenisPidanaId === null) {
            return res.status(400).json({
                message: "ID jenis pidana tidak valid"
            });
        }

        const result = await pool.query(
            `
            SELECT
                id,
                nama_jenis_perkara
            FROM jenis_perkara
            WHERE jenis_pidana_id = $1
              AND is_active = true
            ORDER BY nama_jenis_perkara ASC
            `,
            [jenisPidanaId]
        );

        res.status(200).json(result.rows);
    } catch (error) {
        res.status(500).json({
            message: "Gagal mengambil data jenis perkara",
            error: error.message
        });
    }
};

module.exports = {
    getAllJaksa,
    getAllJenisPidana,
    getAllInstansiPenyidik,
    getJenisPerkaraByJenisPidana
};
