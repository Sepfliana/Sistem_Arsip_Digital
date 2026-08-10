import { useCallback, useEffect, useMemo, useState } from "react";
import { FiChevronDown, FiShield } from "react-icons/fi";
import AppShell from "../AppShell";
import { fetchData } from "../../services/apiService";

const getNamaPengguna = (item) => item.nama_pengguna || item.nama_lengkap || item.username || "-";

const INDONESIAN_MONTHS = [
    "Januari", "Februari", "Maret", "April", "Mei", "Juni",
    "Juli", "Agustus", "September", "Oktober", "November", "Desember"
];

const getMonthYearInfo = (dateString) => {
    if (!dateString) return { key: "unknown", label: "Lainnya", year: 0, month: 0 };
    const d = new Date(dateString);
    if (Number.isNaN(d.getTime())) return { key: "unknown", label: "Lainnya", year: 0, month: 0 };

    const year = d.getFullYear();
    const month = d.getMonth();
    const key = `${year}-${String(month + 1).padStart(2, "0")}`;
    const label = `${INDONESIAN_MONTHS[month]} ${year}`;

    return { key, label, year, month };
};

function AuditLog() {
    const [logs, setLogs] = useState([]);
    const [chainStatus, setChainStatus] = useState(null);
    const [userFilter, setUserFilter] = useState("");
    const [actionFilter, setActionFilter] = useState("");
    const [dateFilter, setDateFilter] = useState("");
    const [loading, setLoading] = useState(false);
    const [error, setError] = useState("");
    const [openGroups, setOpenGroups] = useState({});

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

    const groupedLogs = useMemo(() => {
        const groupsMap = new Map();

        filteredLogs.forEach((log) => {
            const { key, label, year, month } = getMonthYearInfo(log.waktu);
            if (!groupsMap.has(key)) {
                groupsMap.set(key, {
                    key,
                    label,
                    year,
                    month,
                    logs: []
                });
            }
            groupsMap.get(key).logs.push(log);
        });

        const sortedGroups = Array.from(groupsMap.values()).sort((a, b) => {
            if (a.year !== b.year) return b.year - a.year;
            return b.month - a.month;
        });

        return sortedGroups;
    }, [filteredLogs]);

    useEffect(() => {
        if (groupedLogs.length > 0) {
            setOpenGroups((prev) => {
                if (Object.keys(prev).length === 0) {
                    return { [groupedLogs[0].key]: true };
                }
                return prev;
            });
        }
    }, [groupedLogs]);

    const toggleGroup = (groupKey) => {
        setOpenGroups((prev) => ({
            ...prev,
            [groupKey]: !prev[groupKey]
        }));
    };

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
                    <div>
                        <h2>Daftar Audit Log</h2>
                        <p className="panel-subtitle">Menampilkan {filteredLogs.length} aktivitas terkelompok berdasarkan bulan.</p>
                    </div>
                    <button className="primary-button" onClick={verifyChain}>Verifikasi Integritas Hash Chain</button>
                </div>

                <div className="filter-vertical-container">
                    <label className="field">
                        <span>Filter Pengguna</span>
                        <input
                            className="search-input"
                            placeholder="Filter pengguna"
                            value={userFilter}
                            onChange={(event) => setUserFilter(event.target.value)}
                        />
                    </label>
                    <label className="field">
                        <span>Filter Aksi</span>
                        <input
                            className="search-input"
                            placeholder="Filter aksi"
                            value={actionFilter}
                            onChange={(event) => setActionFilter(event.target.value)}
                        />
                    </label>
                    <label className="field">
                        <span>Filter Tanggal</span>
                        <input
                            className="search-input"
                            type="date"
                            value={dateFilter}
                            onChange={(event) => setDateFilter(event.target.value)}
                        />
                    </label>
                </div>

                {loading ? (
                    <div className="loading-state"><span className="spinner" />Memuat audit log...</div>
                ) : groupedLogs.length === 0 ? (
                    <div className="empty-state"><span>i</span><strong>Belum ada audit log.</strong><p>Aktivitas keamanan akan tampil di halaman ini.</p></div>
                ) : (
                    <div className="audit-accordion-stack">
                        {groupedLogs.map((group, index) => {
                            const isOpen = Boolean(openGroups[group.key]);

                            return (
                                <div className={`audit-accordion-item ${isOpen ? "is-open" : ""}`} key={group.key}>
                                    <button
                                        type="button"
                                        className="audit-accordion-header"
                                        onClick={() => toggleGroup(group.key)}
                                        aria-expanded={isOpen}
                                    >
                                        <div className="accordion-header-title">
                                            <span className="accordion-month-name">{group.label}</span>
                                            {index === 0 && <span className="badge success compact-badge">Terbaru</span>}
                                        </div>
                                        <div className="accordion-header-meta">
                                            <span className="accordion-count">{group.logs.length} aktivitas</span>
                                            <span className={`accordion-arrow ${isOpen ? "rotated" : ""}`}>
                                                <FiChevronDown aria-hidden="true" />
                                            </span>
                                        </div>
                                    </button>

                                    {isOpen && (
                                        <div className="audit-accordion-content">
                                            <div className="table-wrap">
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
                                                        {group.logs.map((log) => (
                                                            <tr
                                                                key={log.id}
                                                                className={!chainStatus?.valid && chainStatus?.brokenAt === log.id ? "row-danger" : ""}
                                                            >
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
                                            </div>
                                        </div>
                                    )}
                                </div>
                            );
                        })}
                    </div>
                )}
            </section>
        </AppShell>
    );
}

export default AuditLog;
