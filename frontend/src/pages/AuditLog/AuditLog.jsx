import { useCallback, useEffect, useMemo, useState } from "react";
import AppShell from "../AppShell";
import { fetchData } from "../../services/apiService";

const getNamaPengguna = (item) => item.nama_pengguna || item.nama_lengkap || item.username || "-";
const pageSize = 10;

function AuditLog() {
    const [logs, setLogs] = useState([]);
    const [chainStatus, setChainStatus] = useState(null);
    const [userFilter, setUserFilter] = useState("");
    const [actionFilter, setActionFilter] = useState("");
    const [dateFilter, setDateFilter] = useState("");
    const [page, setPage] = useState(1);
    const [loading, setLoading] = useState(false);
    const [error, setError] = useState("");

    const filteredLogs = useMemo(() => {
        const userTerm = userFilter.toLowerCase();
        const actionTerm = actionFilter.toLowerCase();

        return logs.filter((log) => {
            const matchesUser = !userTerm || getNamaPengguna(log).toLowerCase().includes(userTerm);
            const matchesAction = !actionTerm || String(log.aksi || "").toLowerCase().includes(actionTerm);
            const matchesDate = !dateFilter || String(log.waktu || "").slice(0, 10) === dateFilter;

            return matchesUser && matchesAction && matchesDate;
        });
    }, [actionFilter, dateFilter, logs, userFilter]);

    const totalPages = Math.max(1, Math.ceil(filteredLogs.length / pageSize));
    const pagedLogs = filteredLogs.slice((page - 1) * pageSize, page * pageSize);

    const loadLogs = useCallback(async () => {
        setLoading(true);
        try {
            const data = await fetchData("/audit-log");
            setLogs(Array.isArray(data) ? data : []);
            setError("");
        } catch (requestError) {
            setError(requestError.response?.data?.message || "Gagal memuat audit log");
        } finally {
            setLoading(false);
        }
    }, []);

    const verifyChain = async () => {
        try {
            const data = await fetchData("/audit-log/verify-chain");
            setChainStatus(data);
            setError("");
        } catch (requestError) {
            setError(requestError.response?.data?.message || "Gagal memverifikasi chain");
        }
    };

    useEffect(() => {
        Promise.resolve().then(loadLogs);
    }, [loadLogs]);

    return (
        <AppShell title="Audit Log" subtitle="Jejak aktivitas penting dengan hash chaining">
            {error && <div className="toast error">{error}</div>}

            {chainStatus && (
                <section className={`integrity-banner ${chainStatus.valid ? "valid" : "invalid"}`}>
                    <strong>{chainStatus.valid ? "VALID" : "TERDETEKSI MANIPULASI"}</strong>
                    <span>{chainStatus.valid ? `Total log: ${chainStatus.total}` : `Log ID ${chainStatus.brokenAt}: ${chainStatus.reason}`}</span>
                </section>
            )}

            <section className="panel table-panel">
                <div className="panel-heading">
                    <h2>Daftar Audit Log</h2>
                    <button className="primary-button" onClick={verifyChain}>Verifikasi Integritas Hash Chain</button>
                </div>

                <div className="filter-vertical-container">
                    <label className="field">
                        <span>Filter Pengguna</span>
                        <input className="search-input" placeholder="Filter pengguna" value={userFilter} onChange={(event) => { setUserFilter(event.target.value); setPage(1); }} />
                    </label>
                    <label className="field">
                        <span>Filter Aksi</span>
                        <input className="search-input" placeholder="Filter aksi" value={actionFilter} onChange={(event) => { setActionFilter(event.target.value); setPage(1); }} />
                    </label>
                    <label className="field">
                        <span>Filter Tanggal</span>
                        <input className="search-input" type="date" value={dateFilter} onChange={(event) => { setDateFilter(event.target.value); setPage(1); }} />
                    </label>
                </div>

                <div className="table-wrap">
                    {loading ? (
                        <div className="loading-state"><span className="spinner" />Memuat audit log...</div>
                    ) : filteredLogs.length === 0 ? (
                        <div className="empty-state"><span>i</span><strong>Belum ada audit log.</strong><p>Aktivitas keamanan akan tampil di halaman ini.</p></div>
                    ) : (
                        <table>
                            <thead>
                                <tr>
                                    <th>Waktu</th>
                                    <th>Pengguna</th>
                                    <th>Aksi</th>
                                    <th>Target</th>
                                    <th>Status</th>
                                    <th>Hash Sebelumnya</th>
                                    <th>Hash Saat Ini</th>
                                </tr>
                            </thead>
                            <tbody>
                                {pagedLogs.map((log) => (
                                    <tr key={log.id} className={!chainStatus?.valid && chainStatus?.brokenAt === log.id ? "row-danger" : ""}>
                                        <td>{log.waktu?.slice(0, 19).replace("T", " ")}</td>
                                        <td>{getNamaPengguna(log)}</td>
                                        <td>{log.aksi}</td>
                                        <td>{log.target_tipe} #{log.target_id}</td>
                                        <td><span className="badge success">{log.status || "OK"}</span></td>
                                        <td>{log.hash_sebelumnya?.slice(0, 12) || "-"}</td>
                                        <td>{log.hash_entri?.slice(0, 12)}</td>
                                    </tr>
                                ))}
                            </tbody>
                        </table>
                    )}
                </div>

                {filteredLogs.length > 0 && (
                    <div className="pagination">
                        <span>Halaman {page} dari {totalPages}</span>
                        <button className="secondary-button" disabled={page === 1} onClick={() => setPage((current) => current - 1)}>Sebelumnya</button>
                        <button className="secondary-button" disabled={page === totalPages} onClick={() => setPage((current) => current + 1)}>Berikutnya</button>
                    </div>
                )}
            </section>
        </AppShell>
    );
}

export default AuditLog;
