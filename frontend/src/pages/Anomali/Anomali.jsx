import { useCallback, useEffect, useMemo, useRef, useState } from "react";
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

const getAnalysisStatus = (item) => {
    if (!item) return "NORMAL";
    const s = String(item.status_analisis || "").toUpperCase();
    if (s === "NOT_ANALYZED") return "NOT_ANALYZED";
    if (s === "AI_ERROR") return "AI_ERROR";
    if (s === "ANALYZED_ANOMALY") return "ANOMALY";
    if (s === "ANALYZED_NORMAL") return "NORMAL";
    return item.anomalyId ? "ANOMALY" : "NORMAL";
};

const getRiskCategory = (item) => {
    if (!item) return "Normal";
    const s = String(item.status_analisis || "").toUpperCase();
    if (s === "NOT_ANALYZED" || s === "AI_ERROR") return null;
    if (!item.anomalyId) return "Normal";

    const risk = String(item.tingkat_risiko || "").toUpperCase();
    if (risk.includes("HIGH") || risk.includes("TINGGI")) return "High Risk";
    return "Perlu Ditinjau";
};

const getCategoryBadge = (category) => {
    if (category === "High Risk") return { className: "danger", label: "High Risk" };
    if (category === "Perlu Ditinjau") return { className: "warning", label: "Perlu Ditinjau" };
    if (category === null) return { className: "neutral", label: "Belum Dianalisis" };
    return { className: "success", label: "Normal" };
};

const getReviewStatus = (item) => {
    if (!item.anomalyId) return "Selesai";

    const analysis = getAnalysisStatus(item);
    if (analysis === "NOT_ANALYZED") return "Selesai";
    if (analysis === "AI_ERROR") return "Selesai";

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

const getReviewNoteKey = (anomalyId) => `anomaly-review-note-${anomalyId}`;

const toDateInput = (value) => {
    if (!value) return "";
    const date = new Date(value);
    if (Number.isNaN(date.getTime())) return "";

    return date.toISOString().slice(0, 10);
};

const FEATURE_LABELS = {
    user_id: "User ID",
    activity: "Aktivitas",
    status: "Status",
    device: "Perangkat",
    ip_address: "Alamat IP",
    duration_ms: "Durasi",
    object_count: "Jumlah Objek",
    hour: "Jam Aktivitas",
    day_of_week: "Hari",
};

const parsePenjelasan = (penjelasan) => {
    if (!penjelasan) return null;
    if (typeof penjelasan === "string") {
        try { return JSON.parse(penjelasan); } catch { return null; }
    }
    return penjelasan;
};

const getTopFeatures = (penjelasan, count = 3) => {
    if (!penjelasan?.feature_contributions) return [];
    const entries = Object.entries(penjelasan.feature_contributions);
    if (entries.length === 0) return [];
    return entries
        .sort(([, a], [, b]) => b - a)
        .slice(0, count)
        .map(([feature, contribution]) => ({
            feature,
            label: FEATURE_LABELS[feature] || feature,
            contribution,
            error: penjelasan.feature_errors?.[feature] ?? 0,
        }));
};

function Anomali() {
    const [auditLogs, setAuditLogs] = useState([]);
    const [reports, setReports] = useState([]);
    const [selectedReport, setSelectedReport] = useState(null);
    const [decisionMode, setDecisionMode] = useState("");
    const [overrideReason, setOverrideReason] = useState("");
    const [decisionError, setDecisionError] = useState("");
    const [loading, setLoading] = useState(false);
    const [actionLoading, setActionLoading] = useState("");
    const [error, setError] = useState("");
    const [toastMessage, setToastMessage] = useState("");
    const [activeFilter, setActiveFilter] = useState("Semua");
    const [startDate, setStartDate] = useState("");
    const [endDate, setEndDate] = useState("");
    const [userSearch, setUserSearch] = useState("");

    const toastTimerRef = useRef(null);

    const showToast = useCallback((message) => {
        if (toastTimerRef.current) clearTimeout(toastTimerRef.current);
        setToastMessage(message);
        toastTimerRef.current = setTimeout(() => {
            setToastMessage("");
        }, 2000);
    }, []);

    useEffect(() => {
        return () => {
            if (toastTimerRef.current) clearTimeout(toastTimerRef.current);
        };
    }, []);

    const analysisRows = useMemo(() => {
        const reportByAuditId = new Map(reports.map((report) => [Number(report.sumber_audit_log_id), report]));
        const rows = auditLogs.map((log) => {
            const report = reportByAuditId.get(Number(log.id));
            const auditDetail = parsePenjelasan(log.analysis_detail);
            const reportPenjelasan = report?.penjelasan ? parsePenjelasan(report.penjelasan) : null;

            const effectiveScore = report?.skor_anomali || (log.anomaly_score != null ? Number(log.anomaly_score) : 0);
            const effectiveRisk = report?.tingkat_risiko || log.risk_level || "Normal";
            const effectivePenjelasan = reportPenjelasan || auditDetail;
            const effectiveStatus = log.status_analisis || "NOT_ANALYZED";

            return {
                ...log,
                ...(report || {}),
                auditLogId: log.id,
                anomalyId: report?.id || null,
                skor_anomali: effectiveScore,
                tingkat_risiko: effectiveRisk,
                status_keputusan: report?.status_keputusan || "SELESAI",
                penjelasan: effectivePenjelasan,
                status_analisis: effectiveStatus,
            };
        });

        const loggedIds = new Set(auditLogs.map((log) => Number(log.id)));
        const orphanReports = reports
            .filter((report) => !loggedIds.has(Number(report.sumber_audit_log_id)))
            .map((report) => ({ ...report, auditLogId: report.sumber_audit_log_id, anomalyId: report.id }));

        return [...rows, ...orphanReports].sort((a, b) => new Date(b.waktu || 0) - new Date(a.waktu || 0));
    }, [auditLogs, reports]);

    const stats = useMemo(() => {
        const analyzed = analysisRows.filter((item) => getRiskCategory(item) !== null);

        return {
            total: analysisRows.length,
            analyzed: analyzed.length,
            normal: analyzed.filter((item) => getRiskCategory(item) === "Normal").length,
            review: analyzed.filter((item) => getRiskCategory(item) === "Perlu Ditinjau").length,
            high: analyzed.filter((item) => getRiskCategory(item) === "High Risk").length,
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
        const analyzed = source.filter((item) => getRiskCategory(item) !== null);

        return {
            isToday: todayRows.length > 0,
            analyzed: analyzed.length,
            normal: analyzed.filter((item) => getRiskCategory(item) === "Normal").length,
            review: analyzed.filter((item) => getRiskCategory(item) === "Perlu Ditinjau").length,
            high: analyzed.filter((item) => getRiskCategory(item) === "High Risk").length
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

    const closeDetail = useCallback(() => {
        setSelectedReport(null);
        setDecisionMode("");
        setOverrideReason("");
        setDecisionError("");
    }, []);

    const openDetail = useCallback((report) => {
        setSelectedReport(report);
        const status = String(report?.status_keputusan || "").toUpperCase();
        if (status === "DITERIMA") setDecisionMode("accept");
        else if (status === "SELESAI" || status === "OVERRIDE") setDecisionMode("override");
        else setDecisionMode("");

        setDecisionError("");
        setOverrideReason(report.anomalyId ? localStorage.getItem(getReviewNoteKey(report.anomalyId)) || "" : "");
    }, []);

    const handleAction = async (targetMode) => {
        if (!selectedReport || !selectedReport.anomalyId) return;

        const isHighRisk = getRiskCategory(selectedReport) === "High Risk";
        const modeToUse = targetMode === "save" ? decisionMode : (targetMode || decisionMode);

        if (!modeToUse) {
            setDecisionError("Pilih salah satu keputusan terlebih dahulu.");
            return;
        }

        if (modeToUse === "override" && isHighRisk && !overrideReason.trim()) {
            setDecisionError("Keterangan pemeriksaan wajib diisi sebelum aktivitas dapat ditandai selesai.");
            return;
        }

        const decision = modeToUse === "override" ? "OVERRIDE" : "DITERIMA";

        setActionLoading(targetMode);
        setDecisionError("");
        setError("");

        try {
            await api.put(`/audit-log/anomali/${selectedReport.anomalyId}/decision`, {
                decision,
                reason: overrideReason.trim()
            });

            if (overrideReason.trim()) {
                localStorage.setItem(getReviewNoteKey(selectedReport.anomalyId), overrideReason.trim());
            }

            // Update reports local state immediately without full page reload
            setReports((prevReports) =>
                prevReports.map((item) =>
                    Number(item.id) === Number(selectedReport.anomalyId)
                        ? { ...item, status_keputusan: decision, reason: overrideReason.trim() }
                        : item
                )
            );

            setSelectedReport((prev) => (prev ? { ...prev, status_keputusan: decision } : null));
            setDecisionMode(modeToUse);

            // Show success toast for 2 seconds
            showToast("✓ Tinjauan selesai dan keputusan berhasil disimpan.");

            if (targetMode === "save") {
                closeDetail();
            }
        } catch (requestError) {
            setError(requestError.response?.data?.message || "Gagal menyimpan keputusan anomali");
        } finally {
            setActionLoading("");
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
            {toastMessage && <div className="toast success" role="status" aria-live="polite">{toastMessage}</div>}
            {error && <div className="toast error" role="alert">{error}</div>}

            <section className="summary-grid">
                <div className="metric-card"><span>Total Aktivitas Dianalisis</span><strong>{stats.analyzed}</strong></div>
                <div className="metric-card"><span>Aktivitas Normal</span><strong>{stats.normal}</strong></div>
                <div className="metric-card"><span>Perlu Ditinjau</span><strong>{stats.review}</strong></div>
                <div className="metric-card"><span>High Risk</span><strong>{stats.high}</strong></div>
            </section>

            <section className={`analysis-summary ${stats.high > 0 ? "danger" : stats.review > 0 ? "warning" : "success"}`}>
                <span>{stats.high > 0 ? <FiAlertTriangle aria-hidden="true" /> : <FiCheckCircle aria-hidden="true" />}</span>
                <p>
                    {todayStats.isToday ? "Hari ini" : "Dari data yang tersedia"} sistem menganalisis {todayStats.analyzed} aktivitas. {todayStats.normal} aktivitas dinilai normal, {todayStats.review} aktivitas memerlukan peninjauan, {todayStats.high > 0 ? `dan ditemukan ${todayStats.high} aktivitas berisiko tinggi.` : "dan tidak ada aktivitas berisiko tinggi."}
                </p>
            </section>

            <section className="panel activity-stat-panel">
                <div className="panel-heading"><h2>Statistik Aktivitas</h2></div>
                <div className="risk-progress-list">
                    {progressItems.map((item) => {
                        const percent = stats.analyzed === 0 ? 0 : Math.round((item.value / stats.analyzed) * 100);

                        return (
                            <div className={`risk-progress-item ${item.className}`} key={item.label}>
                                <div className="risk-progress-heading">
                                    <strong><i aria-hidden="true" />{item.label}</strong>
                                    <span>{percent}%</span>
                                </div>
                                <div className="risk-progress-track" aria-label={`${item.label}: ${item.value} aktivitas, ${percent}%`}>
                                    <span style={{ width: `${percent}%` }} />
                                </div>
                                <small>{item.value} aktivitas</small>
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
                    <button className="secondary-button" disabled={loading} onClick={loadReports}>
                        <FiRefreshCw className={loading ? "spinner-rotate" : ""} aria-hidden="true" />
                        {loading ? "Memuat..." : "Muat Ulang"}
                    </button>
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
                                    const hasScore = report.skor_anomali > 0 || report.anomaly_score > 0;
                                    const scoreDisplay = hasScore
                                        ? Number(report.skor_anomali || report.anomaly_score || 0).toFixed(2)
                                        : "-";

                                    return (
                                        <tr key={`${report.anomalyId || "na"}-${report.auditLogId || report.id}`}>
                                            <td>{formatDateTime(report.waktu)}</td>
                                            <td>{getNamaPengguna(report)}</td>
                                            <td>{normalizeAction(report.aksi)}</td>
                                            <td>{scoreDisplay}</td>
                                            <td><span className={`badge ${categoryBadge.className}`}>{categoryBadge.label}</span></td>
                                            <td><span className={`badge ${getStatusBadgeClass(status)}`}>{status}</span></td>
                                            <td><button className="secondary-button" onClick={() => openDetail(report)}><FiEye aria-hidden="true" />Detail</button></td>
                                        </tr>
                                    );
                                })}
                            </tbody>
                        </table>
                    )}
                </div>
            </section>

            {selectedReport && (
                <div className="modal-backdrop" onClick={closeDetail}>
                    <div className="modal-card anomaly-detail-modal" onClick={(e) => e.stopPropagation()}>
                        <div className="panel-heading">
                            <h2>Detail Aktivitas</h2>
                            <button className="secondary-button" onClick={closeDetail}>Tutup</button>
                        </div>

                        <div className="anomaly-detail-grid readable-detail-grid">
                            <div><span>Aktivitas</span><strong>{normalizeAction(selectedReport.aksi)}</strong></div>
                            <div><span>Pengguna</span><strong>{getNamaPengguna(selectedReport)}</strong></div>
                            <div><span>Tanggal</span><strong>{formatDateTime(selectedReport.waktu)}</strong></div>
                            <div><span>Kategori Deteksi</span><strong>{getRiskCategory(selectedReport) || "Belum Dianalisis"}</strong></div>
                            {(() => {
                                const penjelasan = parsePenjelasan(selectedReport.penjelasan);
                                const hasScore = penjelasan?.skor_anomali > 0 || selectedReport.skor_anomali > 0 || selectedReport.anomaly_score > 0;
                                if (penjelasan) {
                                    return (
                                        <>
                                            <div><span>Skor Anomali</span><strong>{Number(penjelasan.skor_anomali || 0).toFixed(6)}</strong></div>
                                            <div><span>Threshold</span><strong>{Number(penjelasan.threshold || 0).toFixed(6)}</strong></div>
                                            <div><span>Risk Level</span><strong>{penjelasan.risk_level || "-"}</strong></div>
                                        </>
                                    );
                                }
                                if (hasScore) {
                                    const score = selectedReport.skor_anomali || selectedReport.anomaly_score || 0;
                                    const threshold = selectedReport.analysis_threshold || 0;
                                    const rl = selectedReport.risk_level || "-";
                                    return (
                                        <>
                                            <div><span>Skor Anomali</span><strong>{Number(score).toFixed(6)}</strong></div>
                                            <div><span>Threshold</span><strong>{Number(threshold).toFixed(6)}</strong></div>
                                            <div><span>Risk Level</span><strong>{rl}</strong></div>
                                        </>
                                    );
                                }
                                return null;
                            })()}
                            {String(selectedReport.aksi || "").toUpperCase() === "VERIFIKASI_INTEGRITAS_BERKAS" && (
                                <>
                                    <div><span>Sumber Aktivitas</span><strong>Verifikasi Integritas Berkas</strong></div>
                                    <div><span>Status Integritas</span><strong>{selectedReport.integrity_status || selectedReport.status || "-"}</strong></div>
                                </>
                            )}
                        </div>

                        {(() => {
                            const analysis = getAnalysisStatus(selectedReport);
                            const category = getRiskCategory(selectedReport);
                            const penjelasan = parsePenjelasan(selectedReport.penjelasan);
                            const topFeatures = getTopFeatures(penjelasan, 3);
                            const score = penjelasan?.skor_anomali
                                ?? Number(selectedReport.skor_anomali || selectedReport.anomaly_score || 0);
                            const threshold = penjelasan?.threshold
                                ?? Number(selectedReport.analysis_threshold || 0);
                            const threshold15 = threshold * 1.5;
                            const hourFeature = topFeatures.find((f) => f.feature === "hour");
                            const hourError = penjelasan?.feature_errors?.hour ?? 0;
                            const hourContrib = penjelasan?.feature_contributions?.hour ?? 0;
                            const waktu = selectedReport.waktu ? new Date(selectedReport.waktu) : null;
                            const hourOfDay = waktu && !Number.isNaN(waktu.getTime()) ? waktu.getHours() : null;
                            const isWorkHour = hourOfDay !== null && hourOfDay >= 7 && hourOfDay < 17;

                            if (analysis === "NOT_ANALYZED" || analysis === "AI_ERROR") {
                                return (
                                    <div className="explanation-panel">
                                        <h3>Informasi Deteksi</h3>
                                        <p>
                                            {analysis === "NOT_ANALYZED"
                                                ? "Aktivitas ini belum dianalisis oleh model VAE karena layanan deteksi anomali tidak tersedia saat aktivitas tercatat."
                                                : "Terjadi kesalahan saat memproses aktivitas ini melalui model VAE."}
                                            {" "}Status ini bukan merupakan kategori hasil deteksi (Normal, Perlu Ditinjau, atau High Risk), melainkan informasi bahwa proses analisis belum terlaksana pada aktivitas ini.
                                        </p>
                                    </div>
                                );
                            }

                            if (category === "Normal") {
                                return (
                                    <>
                                        <div className="explanation-panel">
                                            <h3>Hasil Deteksi: Normal</h3>
                                            <p>
                                                Skor anomali {score.toFixed(6)} berada di bawah threshold {threshold.toFixed(6)},
                                                sehingga aktivitas ini tidak menunjukkan penyimpangan yang cukup untuk dikategorikan anomali.
                                            </p>
                                            {hourOfDay !== null && (
                                                <p>
                                                    Aktivitas dilakukan pada pukul {String(hourOfDay).padStart(2, "0")}:{String(waktu.getMinutes()).padStart(2, "0")}
                                                    {isWorkHour
                                                        ? ", yang berada dalam rentang jam kerja normal (07:00\u201317:00). Pola waktu ini sesuai dengan pola yang dipelajari model VAE dari data pelatihan."
                                                        : ", yang berada di luar jam kerja normal (07:00\u201317:00). Meskipun demikian, skor total reconstruction error masih berada di bawah threshold."}
                                                </p>
                                            )}
                                        </div>
                                        {topFeatures.length > 0 && topFeatures.some((f) => f.contribution > 0.05) && (
                                            <div className="explanation-panel">
                                                <h3>Kontribusi Fitur terhadap Skor</h3>
                                                <p>Berikut fitur dengan reconstruction error terbesar pada aktivitas ini:</p>
                                                <ul>
                                                    {topFeatures.map((f) => (
                                                        <li key={f.feature}>
                                                            <strong>{f.label}</strong>: reconstruction error = {f.error.toFixed(4)}, kontribusi {(f.contribution * 100).toFixed(1)}% terhadap total skor
                                                        </li>
                                                    ))}
                                                </ul>
                                            </div>
                                        )}
                                    </>
                                );
                            }

                            if (category === "Perlu Ditinjau") {
                                const hourExplanation = hourFeature && hourContrib > 0.1
                                    ? hourOfDay !== null
                                        ? isWorkHour
                                            ? `Aktivitas dilakukan pada pukul ${String(hourOfDay).padStart(2, "0")}:${String(waktu.getMinutes()).padStart(2, "0")}, yaitu dalam rentang jam kerja (07:00\u201317:00). Meskipun berada dalam jam kerja, fitur Jam Aktivitas masih menyumbang reconstruction error sebesar ${hourError.toFixed(4)} (${(hourContrib * 100).toFixed(1)}% dari total skor) karena kombinasi fitur lainnya menyimpang dari pola normal.`
                                            : `Aktivitas dilakukan pada pukul ${String(hourOfDay).padStart(2, "0")}:${String(waktu.getMinutes()).padStart(2, "0")}, yaitu di luar jam kerja normal (07:00\u201317:00). Model VAE mempelajari bahwa aktivitas normal terjadi pada jam 07:00\u201317:00. Penyimpangan jam ini menghasilkan reconstruction error sebesar ${hourError.toFixed(4)} dan berkontribusi ${(hourContrib * 100).toFixed(1)}% terhadap total skor anomali.`
                                        : `Fitur Jam Aktivitas menyumbang reconstruction error sebesar ${hourError.toFixed(4)} (${(hourContrib * 100).toFixed(1)}% dari total skor), yang menunjukkan penyimpangan pola waktu dari data pelatihan.`
                                    : null;

                                return (
                                    <>
                                        <div className="explanation-panel">
                                            <h3>Hasil Deteksi: Perlu Ditinjau (Low Risk)</h3>
                                            <p>
                                                Skor anomali {score.toFixed(6)} melewati threshold {threshold.toFixed(6)}
                                                {score < threshold15
                                                    ? ` tetapi belum mencapai 1,5 \u00D7 threshold (${threshold15.toFixed(6)}), sehingga aktivitas ini dikategorikan sebagai Perlu Ditinjau.`
                                                    : `, sehingga aktivitas ini mendekati batas kategori High Risk.`}
                                            </p>
                                        </div>
                                        {hourExplanation && (
                                            <div className="explanation-panel">
                                                <h3>Analisis Faktor Waktu</h3>
                                                <p>{hourExplanation}</p>
                                            </div>
                                        )}
                                        {topFeatures.length > 0 && (
                                            <div className="explanation-panel">
                                                <h3>Faktor Penyimpangan Terbesar</h3>
                                                <p>Berikut fitur dengan reconstruction error terbesar berdasarkan analisis model VAE:</p>
                                                <ul>
                                                    {topFeatures.map((f) => (
                                                        <li key={f.feature}>
                                                            <strong>{f.label}</strong>: reconstruction error = {f.error.toFixed(4)}, kontribusi {(f.contribution * 100).toFixed(1)}% terhadap total skor
                                                        </li>
                                                    ))}
                                                </ul>
                                            </div>
                                        )}
                                    </>
                                );
                            }

                            const hourExplanationHigh = hourFeature && hourContrib > 0.1
                                ? hourOfDay !== null
                                    ? isWorkHour
                                        ? `Aktivitas dilakukan pada pukul ${String(hourOfDay).padStart(2, "0")}:${String(waktu.getMinutes()).padStart(2, "0")}, yaitu dalam rentang jam kerja (07:00\u201317:00). Meskipun berada dalam jam kerja, skor anomali yang sangat tinggi menunjukkan bahwa fitur lainnya secara signifikan menyimpang dari pola normal.`
                                        : `Aktivitas dilakukan pada pukul ${String(hourOfDay).padStart(2, "0")}:${String(waktu.getMinutes()).padStart(2, "0")}, yaitu di luar jam kerja normal (07:00\u201317:00). Model VAE mempelajari bahwa aktivitas normal terjadi pada jam 07:00\u201317:00. Penyimpangan jam ini menghasilkan reconstruction error sebesar ${hourError.toFixed(4)} dan berkontribusi ${(hourContrib * 100).toFixed(1)}% terhadap total skor anomali yang sangat tinggi.`
                                    : `Fitur Jam Aktivitas menyumbang reconstruction error sebesar ${hourError.toFixed(4)} (${(hourContrib * 100).toFixed(1)}% dari total skor), yang menunjukkan penyimpangan pola waktu dari data pelatihan.`
                                : null;

                            return (
                                <>
                                    <div className="explanation-panel">
                                        <h3>Hasil Deteksi: High Risk</h3>
                                        <p>
                                            Skor anomali {score.toFixed(6)} mencapai atau melewati 1,5 \u00D7 threshold ({threshold15.toFixed(6)}),
                                            sehingga aktivitas ini dikategorikan sebagai High Risk dan memerlukan peninjauan lebih lanjut.
                                        </p>
                                        {threshold > 0 && (
                                            <p>
                                                Threshold: {threshold.toFixed(6)} \u2014 Skor: {score.toFixed(6)} \u2014 Rasio: {(score / threshold).toFixed(2)} kali threshold.
                                            </p>
                                        )}
                                    </div>
                                    {hourExplanationHigh && (
                                        <div className="explanation-panel">
                                            <h3>Analisis Faktor Waktu</h3>
                                            <p>{hourExplanationHigh}</p>
                                        </div>
                                    )}
                                    {topFeatures.length > 0 && (
                                        <div className="explanation-panel">
                                            <h3>Faktor Penyimpangan Terbesar</h3>
                                            <p>Berikut fitur dengan reconstruction error terbesar berdasarkan analisis model VAE:</p>
                                            <ul>
                                                {topFeatures.map((f) => (
                                                    <li key={f.feature}>
                                                        <strong>{f.label}</strong>: reconstruction error = {f.error.toFixed(4)}, kontribusi {(f.contribution * 100).toFixed(1)}% terhadap total skor
                                                    </li>
                                                ))}
                                            </ul>
                                        </div>
                                    )}
                                    {penjelasan?.explanation && (
                                        <div className="explanation-panel">
                                            <h3>Penjelasan Model</h3>
                                            <p>{penjelasan.explanation}</p>
                                        </div>
                                    )}
                                </>
                            );
                        })()}

                        {selectedReport.anomalyId && (
                            <section className="review-note-section">
                                <div className="review-note-heading">
                                    <h3>Keterangan Pemeriksaan</h3>
                                    {getRiskCategory(selectedReport) === "High Risk" && <span className="required-mark">Wajib diisi</span>}
                                </div>
                                <textarea
                                    value={overrideReason}
                                    onChange={(event) => {
                                        setOverrideReason(event.target.value);
                                        setDecisionError("");
                                    }}
                                    placeholder="Tuliskan hasil pemeriksaan aktivitas ini"
                                    rows="5"
                                />
                                <p>Catatan akan disertakan pada keputusan pemeriksaan.</p>
                                {decisionError && <p className="decision-validation" role="alert">{decisionError}</p>}
                            </section>
                        )}

                        <div className="modal-actions anomaly-decision-actions">
                            {selectedReport.anomalyId ? (
                                <>
                                    <button
                                        className={`secondary-button ${decisionMode === "accept" ? "is-selected" : ""}`}
                                        disabled={Boolean(actionLoading)}
                                        onClick={() => handleAction("accept")}
                                    >
                                        {actionLoading === "accept" ? (
                                            <>
                                                <span className="spinner-sm" aria-hidden="true" /> Memproses...
                                            </>
                                        ) : (
                                            <>
                                                <FiClock aria-hidden="true" /> Tandai Sedang Ditinjau
                                            </>
                                        )}
                                    </button>
                                    <button
                                        className={`danger-button ${decisionMode === "override" ? "is-selected" : ""}`}
                                        disabled={Boolean(actionLoading) || (getRiskCategory(selectedReport) === "High Risk" && !overrideReason.trim())}
                                        onClick={() => handleAction("override")}
                                    >
                                        {actionLoading === "override" ? (
                                            <>
                                                <span className="spinner-sm" aria-hidden="true" /> Memproses...
                                            </>
                                        ) : (
                                            <>
                                                <FiShield aria-hidden="true" /> Tandai Selesai
                                            </>
                                        )}
                                    </button>
                                    <button
                                        className="primary-button"
                                        disabled={Boolean(actionLoading) || !decisionMode}
                                        onClick={() => handleAction("save")}
                                    >
                                        {actionLoading === "save" ? (
                                            <>
                                                <span className="spinner-sm" aria-hidden="true" /> Menyimpan...
                                            </>
                                        ) : (
                                            "Simpan Keputusan"
                                        )}
                                    </button>
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

