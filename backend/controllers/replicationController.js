const pool = require("../config/database");

const getReplicationStatus = async (req, res) => {
    try {
        const result = await pool.query(`
            SELECT
                application_name,
                client_addr,
                state,
                sync_state
            FROM pg_stat_replication
        `);

        if (result.rows.length === 0) {
            return res.status(200).json({
                primary: "ONLINE",
                secondary: "OFFLINE",
                replication: "DISCONNECTED"
            });
        }

        const streamingReplica = result.rows.find(
            (row) => String(row.state || "").toLowerCase() === "streaming"
        );

        const replica = streamingReplica || result.rows[0];

        return res.status(200).json({
            primary: "ONLINE",
            secondary: "ONLINE",
            replication: streamingReplica ? "STREAMING" : String(replica.state || "UNKNOWN").toUpperCase(),
            sync_state: replica.sync_state
        });
    } catch (error) {
        return res.status(500).json({
            message: "Gagal membaca status replikasi PostgreSQL",
            error: error.message
        });
    }
};

module.exports = {
    getReplicationStatus
};
