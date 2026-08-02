import { useCallback, useEffect, useMemo, useState } from "react";
import { FiAlertTriangle, FiCheckCircle, FiClock, FiEye, FiRefreshCw, FiShield } from "react-icons/fi";
import AppShell from "../AppShell";
import { api, fetchData } from "../../services/apiService";

const getNamaPengguna = (item) => item.nama_pengguna || item.nama_lengkap || item.username || "-";

const formatDateTime = (value) => {
    if (!value) return "-";

    const date = new Date(value);
    if (Number.isNaN(date.getTime())) return "-";

    return date.toLocaleString("id-ID", {
        day: "numeric",
        month: "long",
        year: "numeric",
        hour: "2-digit",
        minute: "2-digit"
    });
};

const normalizeAction = (value) => {
    if (String(value || "").toUpperCase() === "VERIFIKASI_INTEGRITAS_BERKAS") {
        return "Verifikasi Integritas Berkas";
    }

    const text = String(value || "Aktivitas").replaceAll("_", " ").toLowerCase();
    return text.charAt(0).toUpperCase() + text.slice(1);
};

const getRiskCategory = (item) => {
    const risk = String(item.tingkat_risiko || "").toUpperCase();
    const score = Number(item.skor_anomali || 0);

    if (risk.includes("HIGH") || score >= 0.9) return "High Risk";
    if (item.anomalyId || risk || score > 0) return "Perlu Ditinjau";
    return "Normal";
};

const getCategoryBadge = (category) => {
    if (category === "High Risk") return { className: "danger", label: "High Risk" };
    if (category === "Perlu Ditinjau") return { className: "warning", label: "Perlu Ditinjau" };
    return { className: "success", label: "Normal" };
};

const getReviewStatus = (item) => {
    if (!item.anomalyId) return "Selesai";

    const status = String(item.status_keputusan || "").toUpperCase();
    if (status === "DITERIMA") return "Sedang Ditinjau";
    if (status === "SELESAI" || status === "OVERRIDE") return "Selesai";
    return "Belum Ditinjau";
};

const getStatusBadgeClass = (status) => {
    if (status === "Selesai") return "success";
    if (status === "Sedang Ditinjau") return "warning";
    return "neutral";
};

const isSameDay = (value, date = new Date()) => {
    if (!value) return false;
    const itemDate = new Date(value);
    if (Number.isNaN(itemDate.getTime())) return false;

    return itemDate.getFullYear() === date.getFullYear()
        && itemDate.getMonth() === date.getMonth()
        && itemDate.getDate() === date.getDate();
};

const toDateInput = (value) => {
    if (!value) return "";
    const date = new Date(value);
    if (Number.isNaN(date.getTime())) return "";

    return date.toISOString().slice(0, 10);
};

function Anomali() {
    const [auditLogs, setAuditLogs] = useState([]);
    const [reports, setReports] = useState([]);
    const [selectedReport, setSelectedReport] = useState(null);
    const [decisionMode, setDecisionMode] = useState("");
    const [overrideReason, setOverrideReason] = useState("");
    const [loading, setLoading] = useState(false);
    const [error, setError] = useState("");
    const [activeFilter, setActiveFilter] = useState("Semua");
    const [startDate, setStartDate] = useState("");
    const [endDate, setEndDate] = useState("");
    const [userSearch, setUserSearch] = useState("");

    const analysisRows = useMemo(() => {
        const reportByAuditId = new Map(reports.map((report) => [Number(report.sumber_audit_log_id), report]));
        const rows = auditLogs.map((log) => {
            const report = reportByAuditId.get(Number(log.id));

            return {
                ...log,
                ...(report || {}),
                auditLogId: log.id,
                anomalyId: report?.id || null,
                skor_anomali: report?.skor_anomali || 0,
                tingkat_risiko: report?.tingkat_risiko || "Normal",
                status_keputusan: report?.status_keputusan || "SELESAI"
            };
        });

        const loggedIds = new Set(auditLogs.map((log) => Number(log.id)));
        const orphanReports = reports
            .filter((report) => !loggedIds.has(Number(report.sumber_audit_log_id)))
            .map((report) => ({ ...report, auditLogId: report.sumber_audit_log_id, anomalyId: report.id }));

        return [...rows, ...orphanReports].sort((a, b) => new Date(b.waktu || 0) - new Date(a.waktu || 0));
    }, [auditLogs, reports]);

    const stats = useMemo(() => {
        const normal = analysisRows.filter((item) => getRiskCategory(item) === "Normal").length;
        const review = analysisRows.filter((item) => getRiskCategory(item) === "Perlu Ditinjau").length;
        const high = analysisRows.filter((item) => getRiskCategory(item) === "High Risk").length;

        return {
            total: analysisRows.length,
            normal,
            review,
            high,
            pending: analysisRows.filter((item) => item.anomalyId && getReviewStatus(item) !== "Selesai").length
        };
    }, [analysisRows]);

    const filteredRows = useMemo(() => analysisRows.filter((item) => {
        const category = getRiskCategory(item);
        const status = getReviewStatus(item);
        const itemDate = toDateInput(item.waktu);
        const name = getNamaPengguna(item).toLowerCase();

        if (activeFilter === "Normal" && category !== "Normal") return false;
        if (activeFilter === "Perlu Ditinjau" && category !== "Perlu Ditinjau") return false;
        if (activeFilter === "High Risk" && category !== "High Risk") return false;
        if (activeFilter === "Belum Ditinjau" && status !== "Belum Ditinjau") return false;
        if (activeFilter === "Sudah Ditinjau" && (!item.anomalyId || status === "Belum Ditinjau")) return false;
        if (startDate && itemDate && itemDate < startDate) return false;
        if (endDate && itemDate && itemDate > endDate) return false;
        if (userSearch.trim() && !name.includes(userSearch.trim().toLowerCase())) return false;

        return true;
    }), [activeFilter, analysisRows, endDate, startDate, userSearch]);

    const todayStats = useMemo(() => {
        const todayRows = analysisRows.filter((item) => isSameDay(item.waktu));
        const source = todayRows.length > 0 ? todayRows : analysisRows;

        return {
            isToday: todayRows.length > 0,
            total: source.length,
            normal: source.filter((item) => getRiskCategory(item) === "Normal").length,
            review: source.filter((item) => getRiskCategory(item) === "Perlu Ditinjau").length,
            high: source.filter((item) => getRiskCategory(item) === "High Risk").length
        };
    }, [analysisRows]);

    const loadReports = useCallback(async () => {
        setLoading(true);

        try {
            const [auditData, anomalyData] = await Promise.all([
                fetchData("/audit-log"),
                fetchData("/audit-log/anomali")
            ]);
            setAuditLogs(Array.isArray(auditData) ? auditData : []);
            setReports(Array.isArray(anomalyData) ? anomalyData : []);
            setError("");
        } catch (requestError) {
            setError(requestError.response?.data?.message || "Gagal memuat laporan anomali");
        } finally {
            setLoading(false);
        }
    }, []);

    useEffect(() => {
        Promise.resolve().then(loadReports);
    }, [loadReports]);

    const closeDetail = () => {
        setSelectedReport(null);
        setDecisionMode("");
        setOverrideReason("");
    };

    const saveDecision = async () => {
        const decision = decisionMode === "override" ? "OVERRIDE" : "DITERIMA";

        try {
            await api.put(`/audit-log/anomali/${selectedReport.anomalyId}/decision`, {
                decision,
                reason: overrideReason
            });
            await loadReports();
            closeDetail();
        } catch (requestError) {
            setError(requestError.response?.data?.message || "Gagal menyimpan keputusan anomali");
        }
    };

    const progressItems = [
        { label: "Normal", value: stats.normal, className: "success" },
        { label: "Perlu Ditinjau", value: stats.review, className: "warning" },
        { label: "High Risk", value: stats.high, className: "danger" }
    ];
    const filters = ["Semua", "Normal", "Perlu Ditinjau", "High Risk", "Belum Ditinjau", "Sudah Ditinjau"];

    return (
        <AppShell title="Deteksi Anomali" subtitle="Ringkasan aktivitas yang perlu perhatian dan tindak lanjut">
            {error && <div className="toast error">{error}</div>}

            <section className="summary-grid">
                <div className="metric-card"><span>Total Aktivitas Dianalisis</span><strong>{stats.total}</strong></div>
                <div className="metric-card"><span>Aktivitas Normal</span><strong>{stats.normal}</strong></div>
                <div className="metric-card"><span>Perlu Ditinjau</span><strong>{stats.review + stats.high}</strong></div>
                <div className="metric-card"><span>High Risk</span><strong>{stats.high}</strong></div>
            </section>

            <section className={`analysis-summary ${stats.high > 0 ? "danger" : stats.review > 0 ? "warning" : "success"}`}>
                <span>{stats.high > 0 ? <FiAlertTriangle aria-hidden="true" /> : <FiCheckCircle aria-hidden="true" />}</span>
                <p>
                    {todayStats.isToday ? "Hari ini" : "Dari data yang tersedia"} sistem menganalisis {todayStats.total} aktivitas. {todayStats.normal} aktivitas dinilai normal, {todayStats.review} aktivitas memerlukan peninjauan, {todayStats.high > 0 ? `dan ditemukan ${todayStats.high} aktivitas High Risk.` : "dan tidak ada aktivitas berisiko tinggi."}
                </p>
            </section>

            <section className="panel activity-stat-panel">
                <div className="panel-heading"><h2>Statistik Aktivitas</h2></div>
                <div className="risk-progress-list">
                    {progressItems.map((item) => {
                        const percent = stats.total === 0 ? 0 : Math.round((item.value / stats.total) * 100);

                        return (
                            <div className="risk-progress-item" key={item.label}>
                                <div>
                                    <strong>{item.label}</strong>
                                    <span>{percent}%</span>
                                </div>
                                <div className="risk-progress-track">
                                    <span className={item.className} style={{ width: `${percent}%` }} />
                                </div>
                            </div>
                        );
                    })}
                </div>
            </section>

            <section className="panel table-panel anomaly-table-panel">
                <div className="panel-heading">
                    <div>
                        <h2>Daftar Aktivitas dan Anomali</h2>
                        <p className="panel-subtitle">Menampilkan {filteredRows.length} dari {analysisRows.length} aktivitas.</p>
                    </div>
                    <button className="secondary-button" onClick={loadReports}><FiRefreshCw aria-hidden="true" />Muat Ulang</button>
                </div>

                <div className="filter-vertical-container">
                    <label className="field">
                        <span>Kategori Anomali</span>
                        <select
                            value={activeFilter}
                            onChange={(event) => setActiveFilter(event.target.value)}
                        >
                            {filters.map((filter) => (
                                <option key={filter} value={filter}>{filter}</option>
                            ))}
                        </select>
                    </label>
                    <label className="field">
                        <span>Mulai Tanggal</span>
                        <input type="date" value={startDate} onChange={(event) => setStartDate(event.target.value)} />
                    </label>
                    <label className="field">
                        <span>Sampai Tanggal</span>
                        <input type="date" value={endDate} onChange={(event) => setEndDate(event.target.value)} />
                    </label>
                    <label className="field">
                        <span>Nama Pengguna</span>
                        <input value={userSearch} onChange={(event) => setUserSearch(event.target.value)} placeholder="Cari nama pengguna" />
                    </label>
                </div>

                <div className="table-wrap">
                    {loading ? (
                        <div className="loading-state"><span className="spinner" />Memuat laporan anomali...</div>
                    ) : filteredRows.length === 0 ? (
                        <div className="empty-state"><span>i</span><strong>Tidak ada data sesuai filter.</strong><p>Coba ubah kategori, tanggal, atau nama pengguna.</p></div>
                    ) : (
                        <table>
                            <thead>
                                <tr>
                                    <th>Tanggal</th>
                                    <th>Nama Pengguna</th>
                                    <th>Aktivitas</th>
                                    <th>Skor Risiko</th>
                                    <th>Kategori</th>
                                    <th>Status</th>
                                    <th>Aksi</th>
                                </tr>
                            </thead>
                            <tbody>
                                {filteredRows.map((report) => {
                                    const category = getRiskCategory(report);
                                    const categoryBadge = getCategoryBadge(category);
                                    const status = getReviewStatus(report);

                                    return (
                                        <tr key={`${report.anomalyId || "normal"}-${report.auditLogId || report.id}`}>
                                            <td>{formatDateTime(report.waktu)}</td>
                                            <td>{getNamaPengguna(report)}</td>
                                            <td>{normalizeAction(report.aksi)}</td>
                                            <td>{report.anomalyId ? Number(report.skor_anomali || 0).toFixed(2) : "-"}</td>
                                            <td><span className={`badge ${categoryBadge.className}`}>{categoryBadge.label}</span></td>
                                            <td><span className={`badge ${getStatusBadgeClass(status)}`}>{status}</span></td>
                                            <td><button className="secondary-button" onClick={() => setSelectedReport(report)}><FiEye aria-hidden="true" />Detail</button></td>
                                        </tr>
                                    );
                                })}
                            </tbody>
                        </table>
                    )}
                </div>
            </section>

            {selectedReport && (
                <div className="modal-backdrop">
                    <div className="modal-card anomaly-detail-modal">
                        <div className="panel-heading">
                            <h2>Detail Anomali</h2>
                            <button className="secondary-button" onClick={closeDetail}>Tutup</button>
                        </div>

                        <div className="anomaly-detail-grid readable-detail-grid">
                            <div><span>Aktivitas</span><strong>{normalizeAction(selectedReport.aksi)}</strong></div>
                            <div><span>Pengguna</span><strong>{getNamaPengguna(selectedReport)}</strong></div>
                            <div><span>Tanggal</span><strong>{formatDateTime(selectedReport.waktu)}</strong></div>
                            <div><span>Nilai Risiko</span><strong>{selectedReport.anomalyId ? Number(selectedReport.skor_anomali || 0).toFixed(2) : "-"}</strong></div>
                            <div><span>Kategori</span><strong>{getRiskCategory(selectedReport)}</strong></div>
                            {String(selectedReport.aksi || "").toUpperCase() === "VERIFIKASI_INTEGRITAS_BERKAS" && (
                                <>
                                    <div><span>Sumber Aktivitas</span><strong>Verifikasi Integritas Berkas</strong></div>
                                    <div><span>Status Integritas</span><strong>{selectedReport.integrity_status || selectedReport.status || "-"}</strong></div>
                                </>
                            )}
                        </div>

                        <div className="explanation-panel">
                            <h3>Mengapa aktivitas ini ditandai?</h3>
                            <p>{selectedReport.anomalyId ? "Sistem menemukan pola aktivitas yang berbeda dibandingkan kebiasaan atau aktivitas umum sebelumnya." : "Aktivitas ini berada dalam pola yang wajar dan tidak memerlukan peninjauan khusus."}</p>
                        </div>

                        <div className="explanation-panel recommendation-panel">
                            <h3>Rekomendasi</h3>
                            <p>{selectedReport.anomalyId ? "Disarankan untuk melakukan pemeriksaan terhadap aktivitas ini melalui Audit Log sebelum mengambil keputusan." : "Tidak ada tindakan khusus yang diperlukan. Tetap pantau aktivitas melalui Audit Log bila diperlukan."}</p>
                        </div>

                        {decisionMode === "override" && selectedReport.anomalyId && (
                            <label className="field override-field">
                                <span>Alasan Override</span>
                                <input value={overrideReason} onChange={(event) => setOverrideReason(event.target.value)} required placeholder="Masukkan alasan override" />
                            </label>
                        )}

                        <div className="modal-actions">
                            {selectedReport.anomalyId ? (
                                <>
                                    <button className="secondary-button" onClick={() => setDecisionMode("accept")}><FiClock aria-hidden="true" />Tandai Sedang Ditinjau</button>
                                    <button className="danger-button" onClick={() => setDecisionMode("override")}><FiShield aria-hidden="true" />Tandai Selesai</button>
                                    {decisionMode && (
                                        <button
                                            className="primary-button"
                                            disabled={decisionMode === "override" && !overrideReason.trim()}
                                            onClick={saveDecision}
                                        >
                                            Simpan Keputusan
                                        </button>
                                    )}
                                </>
                            ) : (
                                <button className="primary-button" onClick={closeDetail}>Mengerti</button>
                            )}
                        </div>
                    </div>
                </div>
            )}
        </AppShell>
    );
}

export default Anomali;
