import { useCallback, useEffect, useState } from "react";
import { Link } from "react-router-dom";
import { FiAlertTriangle, FiArchive, FiBookOpen, FiCheckCircle, FiChevronRight, FiClock, FiFileText, FiGrid, FiShield, FiUpload, FiUserPlus, FiUsers, FiXCircle } from "react-icons/fi";
import AppShell from "../AppShell";
import { api, fetchData } from "../../services/apiService";

const countActiveLoans = (items) => {
    return items.filter((item) => ["MENUNGGU", "DISETUJUI", "DIPINJAM"].includes(normalizeLoanStatus(item.status))).length;
};

const getNamaPengguna = (item) => item.nama_pengguna || item.nama_lengkap || item.username || "-";
const getNamaTerdakwa = (item) => item.nama_terdakwa || item.terdakwa?.map((terdakwaItem) => terdakwaItem.nama_terdakwa).filter(Boolean).join(", ") || item.nomor_perkara || "-";
const normalizeLoanStatus = (status) => String(status || "").toUpperCase();

const loanStatusLabels = {
    MENUNGGU: "Menunggu Persetujuan Arsiparis",
    DISETUJUI: "Disetujui",
    DIPINJAM: "Sedang Dipinjam",
    DITOLAK: "Ditolak",
    DIKEMBALIKAN: "Sudah Dikembalikan"
};

const getLoanStatusLabel = (status) => loanStatusLabels[normalizeLoanStatus(status)] || status || "-";

const isLoanOverdue = (item) => {
    if (normalizeLoanStatus(item.status) !== "DIPINJAM" || !item.tanggal_kembali) return false;

    const dueDate = new Date(item.tanggal_kembali);
    if (Number.isNaN(dueDate.getTime())) return false;

    dueDate.setHours(23, 59, 59, 999);
    return dueDate < new Date();
};

const formatRelativeTime = (value) => {
    if (!value) return "Waktu tidak tersedia";

    const date = new Date(value);
    if (Number.isNaN(date.getTime())) return "Waktu tidak tersedia";

    const diffMinutes = Math.max(0, Math.floor((Date.now() - date.getTime()) / 60000));
    if (diffMinutes < 1) return "Baru saja";
    if (diffMinutes < 60) return `${diffMinutes} menit lalu`;

    const diffHours = Math.floor(diffMinutes / 60);
    if (diffHours < 24) return `${diffHours} jam lalu`;

    const diffDays = Math.floor(diffHours / 24);
    if (diffDays < 7) return `${diffDays} hari lalu`;

    return date.toLocaleDateString("id-ID", { day: "numeric", month: "long", year: "numeric" });
};

const formatDateTime = (value) => {
    if (!value) return "Waktu tidak tersedia";

    const date = new Date(value);
    if (Number.isNaN(date.getTime())) return "Waktu tidak tersedia";

    return `${date.toLocaleDateString("id-ID", { day: "2-digit", month: "long", year: "numeric" })} ${date.toLocaleTimeString("id-ID", { hour: "2-digit", minute: "2-digit" })} WIB`;
};

const describeActivity = (activity) => {
    const action = String(activity.aksi || "Aktivitas").replaceAll("_", " ").toLowerCase();
    const target = String(activity.target_tipe || "").replaceAll("_", " ").toLowerCase();
    const readableAction = action.charAt(0).toUpperCase() + action.slice(1);

    if (!target) return readableAction;
    return `${readableAction} ${target}`;
};

const getActivityIcon = (activity) => {
    const action = String(activity.aksi || "").toUpperCase();
    if (action.includes("UPLOAD") || action.includes("UNGGAH") || action.includes("TAMBAH_BERKAS")) return FiUpload;
    if (action.includes("VERIFIKASI")) return FiCheckCircle;
    if (action.includes("USER") || action.includes("PENGGUNA")) return FiUserPlus;
    if (action.includes("PINJAM")) return FiClock;
    if (action.includes("HAPUS") || action.includes("DELETE")) return FiAlertTriangle;
    return FiFileText;
};

const getAdminSummaryCards = (stats) => ([
    { key: "perkara", label: "Jumlah Perkara", value: stats.perkara, icon: FiBookOpen },
    { key: "arsip", label: "Jumlah Berkas", value: stats.arsip, icon: FiArchive },
    { key: "user", label: "Pengguna Aktif", value: stats.user, icon: FiUsers },
    { key: "anomali", label: "Anomali Belum Ditangani", value: stats.anomali, icon: FiAlertTriangle }
]);

const normalizeIntegrityStatus = (status) => {
    const normalized = String(status || "BELUM_DIVERIFIKASI").toUpperCase();
    if (normalized === "VALID") return "VALID";
    if (["HASH TIDAK SESUAI", "INVALID", "TIDAK_VALID", "TIDAK VALID"].includes(normalized)) return "TIDAK_VALID";
    return "BELUM_DIVERIFIKASI";
};

const buildActionNotifications = ({ anomali, berkas, perkara }) => {
    const perkaraWithBerkas = new Set(berkas.filter((item) => item.perkara_id).map((item) => String(item.perkara_id)));
    const isUnresolved = (item) => String(item.status_keputusan || "").trim().toUpperCase() !== "SELESAI";
    const highRiskCount = anomali.filter((item) => ["TINGGI", "HIGH"].includes(String(item.tingkat_risiko || "").toUpperCase()) && isUnresolved(item)).length;
    const unverifiedCount = berkas.filter((item) => normalizeIntegrityStatus(item.status_integritas) === "BELUM_DIVERIFIKASI").length;
    const invalidCount = berkas.filter((item) => normalizeIntegrityStatus(item.status_integritas) === "TIDAK_VALID").length;
    const missingBerkasCount = perkara.filter((item) => !perkaraWithBerkas.has(String(item.id))).length;

    return [
        { key: "anomali-high-risk", title: "Anomali Risiko Tinggi", count: highRiskCount, description: "Perlu ditinjau dan ditangani.", icon: FiAlertTriangle, to: "/anomali", tone: "danger" },
        { key: "berkas-unverified", title: "Berkas Belum Diverifikasi Integritas", count: unverifiedCount, description: "Menunggu proses verifikasi integritas.", icon: FiShield, to: "/verifikasi-integritas", tone: "warning" },
        { key: "berkas-invalid", title: "Berkas Gagal Diverifikasi", count: invalidCount, description: "Memerlukan pemeriksaan lebih lanjut.", icon: FiXCircle, to: "/verifikasi-integritas", tone: "danger" },
        { key: "perkara-without-berkas", title: "Perkara yang Belum Memiliki Berkas", count: missingBerkasCount, description: "Belum memiliki berkas digital.", icon: FiFileText, to: "/perkara", tone: "neutral" }
    ].filter((item) => item.count > 0);
};

function Dashboard() {
    const role = (localStorage.getItem("role") || "User").toLowerCase();
    const [loading, setLoading] = useState(true);
    const [error, setError] = useState("");
    const [stats, setStats] = useState({
        arsip: 0,
        perkara: 0,
        peminjamanAktif: 0,
        user: 0,
        lemari: 0,
        anomali: 0,
        retensi: 0
    });
    const [activities, setActivities] = useState([]);
    const [arsipItems, setArsipItems] = useState([]);
    const [retensi, setRetensi] = useState([]);
    const [peminjamanNotifikasi, setPeminjamanNotifikasi] = useState([]);
    const [anomali, setAnomali] = useState([]);
    const [perkaraData, setPerkaraData] = useState([]);
    const [search, setSearch] = useState("");
    const [searchResults, setSearchResults] = useState([]);

    const safeFetch = async (endpoint, fallback) => {
        try {
            return await fetchData(endpoint);
        } catch (requestError) {
            if (requestError.response?.status === 403 || requestError.response?.status === 401) {
                return fallback;
            }

            throw requestError;
        }
    };

    const loadDashboard = useCallback(async () => {
        setLoading(true);
        setError("");

        try {
            const [arsipData, perkaraDataResult, peminjamanData, userData, auditData, retensiData, lemariData, anomaliData] = await Promise.all([
                safeFetch("/berkas", []),
                role === "user" ? Promise.resolve([]) : safeFetch("/perkara", []),
                safeFetch("/peminjaman", []),
                role === "admin" ? safeFetch("/users", []) : Promise.resolve([]),
                role === "user" ? Promise.resolve([]) : safeFetch("/audit-log", []),
                role === "user" ? Promise.resolve([]) : safeFetch("/berkas/retensi/peringatan", []),
                safeFetch("/lemari", []),
                safeFetch("/audit-log/anomali", [])
            ]);

            setStats({
                arsip: Array.isArray(arsipData) ? arsipData.length : 0,
                perkara: Array.isArray(perkaraDataResult) ? perkaraDataResult.length : 0,
                peminjamanAktif: countActiveLoans(Array.isArray(peminjamanData) ? peminjamanData : []),
                user: Array.isArray(userData) ? userData.filter((item) => item.is_active === true || item.is_active === 1 || item.is_active === "true").length : 0,
                lemari: Array.isArray(lemariData) ? lemariData.length : 0,
                anomali: Array.isArray(anomaliData) ? anomaliData.filter((item) => String(item.status_keputusan || "").toLowerCase() !== "selesai").length : 0,
                retensi: Array.isArray(retensiData) ? retensiData.length : 0
            });
            setActivities(Array.isArray(auditData) ? auditData.slice(0, 8) : []);
            setArsipItems(Array.isArray(arsipData) ? arsipData : []);
            setPerkaraData(Array.isArray(perkaraDataResult) ? perkaraDataResult : []);
            setRetensi(Array.isArray(retensiData) ? retensiData.slice(0, 8) : []);
            setPeminjamanNotifikasi(
                (Array.isArray(peminjamanData) ? peminjamanData : [])
                    .filter((item) => role === "user" || ["MENUNGGU", "DISETUJUI", "DIPINJAM", "DITOLAK", "DIKEMBALIKAN"].includes(normalizeLoanStatus(item.status)))
                    .slice(0, 20)
            );
            setAnomali(Array.isArray(anomaliData) ? anomaliData : []);
        } catch (requestError) {
            setError(requestError.response?.data?.message || "Dashboard gagal dimuat");
        } finally {
            setLoading(false);
        }
    }, [role]);

    useEffect(() => {
        Promise.resolve().then(loadDashboard);
    }, [loadDashboard]);

    const handleSearch = async (event) => {
        event.preventDefault();
        try {
            const perkaraData = await fetchData("/perkara", { search });
            setSearchResults(Array.isArray(perkaraData) ? perkaraData : []);
            setError("");
        } catch (requestError) {
            setError(requestError.response?.data?.message || "Pencarian perkara gagal");
        }
    };

    const updateLoanStatus = async (id, action) => {
        try {
            await api.put(`/peminjaman/${id}/${action}`);
            await loadDashboard();
        } catch (requestError) {
            setError(requestError.response?.data?.message || "Status peminjaman gagal diperbarui");
        }
    };

    const getArsiparisActivityFeed = () => {
        const loanEvents = peminjamanNotifikasi.map((item) => {
            const status = normalizeLoanStatus(item.status);
            const overdue = isLoanOverdue(item);
            const pemohon = item.pemohon_nama_lengkap || item.nama_peminjam || item.pemohon_username || "-";
            const base = {
                id: `loan-${item.id}`,
                time: item.tanggal_pinjam,
                icon: FiClock,
                user: pemohon,
                perkara: getNamaTerdakwa(item),
                berkas: item.nama_berkas || item.nomor_berkas || "-",
                link: "/peminjaman"
            };

            if (status === "MENUNGGU") {
                return {
                    ...base,
                    tone: "info",
                    title: "Permintaan peminjaman baru",
                    description: `${base.berkas} diajukan oleh ${pemohon}.`,
                    actions: [
                        { label: "Setujui", onClick: () => updateLoanStatus(item.id, "setujui"), className: "secondary-button" },
                        { label: "Tolak", onClick: () => updateLoanStatus(item.id, "tolak"), className: "danger-button" }
                    ]
                };
            }

            if (status === "DIPINJAM") {
                return {
                    ...base,
                    tone: overdue ? "danger" : "warning",
                    title: overdue ? "Berkas belum dikembalikan" : "Berkas sedang dipinjam",
                    description: overdue
                        ? `${base.berkas} melewati tanggal kembali ${item.tanggal_kembali?.slice(0, 10) || "-"}.`
                        : `${base.berkas} sedang dipinjam oleh ${pemohon}.`,
                    actions: [{ label: "Lihat", to: "/peminjaman", className: "secondary-button" }]
                };
            }

            if (status === "DISETUJUI") {
                return {
                    ...base,
                    tone: "success",
                    title: "Persetujuan peminjaman",
                    description: `${base.berkas} telah disetujui untuk ${pemohon}.`,
                    actions: [{ label: "Lihat", to: "/peminjaman", className: "secondary-button" }]
                };
            }

            if (status === "DITOLAK") {
                return {
                    ...base,
                    tone: "danger",
                    title: "Penolakan peminjaman",
                    description: `${base.berkas} ditolak untuk ${pemohon}.`,
                    actions: [{ label: "Lihat", to: "/peminjaman", className: "secondary-button" }]
                };
            }

            return {
                ...base,
                tone: "success",
                title: "Pengembalian berkas",
                description: `${base.berkas} sudah dikembalikan oleh ${pemohon}.`,
                actions: [{ label: "Lihat", to: "/peminjaman", className: "secondary-button" }]
            };
        });

        const retensiEvents = retensi.map((item) => {
            const isAktif = item.jenis_notifikasi_retensi === "AKTIF_HAMPIR_HABIS";
            const isSelesai = item.jenis_notifikasi_retensi === "INAKTIF_SELESAI";

            return {
                id: `retensi-${item.id}-${item.jenis_notifikasi_retensi || "warning"}`,
                time: item.tanggal_jatuh_tempo || item.tanggal_akhir_aktif || item.tanggal_akhir_inaktif,
                tone: isSelesai ? "danger" : "warning",
                icon: FiAlertTriangle,
                title: isSelesai
                    ? "Berkas menunggu keputusan permanen/musnah"
                    : `Masa retensi ${isAktif ? "aktif" : "inaktif"} akan berakhir`,
                user: "Sistem",
                perkara: getNamaTerdakwa(item),
                berkas: item.nama_berkas || item.nomor_berkas || "-",
                description: isSelesai
                    ? `${item.nama_berkas || "Berkas"} sudah selesai masa retensinya.`
                    : `Sisa ${item.sisa_hari_retensi ?? "-"} hari sebelum jatuh tempo.`,
                actions: item.perkara_id ? [{ label: "Lihat Berkas", to: `/perkara/${item.perkara_id}/berkas`, className: "secondary-button" }] : []
            };
        });

        const decisionEvents = arsipItems
            .filter((item) => item.status_berkas === "SELESAI")
            .map((item) => ({
                id: `decision-${item.id}`,
                time: item.tanggal_jatuh_tempo || item.tanggal_akhir_inaktif || item.tanggal_berkas,
                tone: "warning",
                icon: FiFileText,
                title: "Berkas menunggu keputusan permanen/musnah",
                user: "Sistem",
                perkara: getNamaTerdakwa(item),
                berkas: item.nama_berkas || item.nomor_berkas || "-",
                description: `${item.nama_berkas || "Berkas"} perlu ditentukan nasib akhirnya.`,
                actions: item.perkara_id ? [{ label: "Lihat Berkas", to: `/perkara/${item.perkara_id}/berkas`, className: "secondary-button" }] : []
            }));

        const auditEvents = activities.map((activity) => {
            const Icon = getActivityIcon(activity);
            const isRetensi = String(activity.aksi || "").toUpperCase().includes("RETENSI");

            return {
                id: `audit-${activity.id}`,
                time: activity.waktu,
                tone: isRetensi ? "success" : "neutral",
                icon: Icon,
                title: isRetensi ? "Perpindahan aktif ke inaktif otomatis" : "Aktivitas penting",
                user: getNamaPengguna(activity),
                perkara: "-",
                berkas: activity.target_tipe || "-",
                description: describeActivity(activity),
                actions: []
            };
        });

        return [...loanEvents, ...retensiEvents, ...decisionEvents, ...auditEvents]
            .sort((left, right) => new Date(right.time || 0) - new Date(left.time || 0))
            .slice(0, 20);
    };

    if (role === "user") {
        return (
            <AppShell title="Dashboard" subtitle="Cari perkara dan buka berkas yang dibutuhkan">
                {error && <div className="notice error">{error}</div>}
                <section className="panel">
                    <div className="user-search-hero">
                        <span>Temukan berkas perkara</span>
                        <strong>Cari perkara untuk melihat berkas dan mengajukan peminjaman.</strong>
                    </div>
                    <div className="panel-heading">
                        <h2>Pencarian Berkas</h2>
                    </div>
                    <form className="form-grid search-form" onSubmit={handleSearch}>
                        <label className="field">
                            <span>Nomor, Nama Terdakwa, atau Tahun Perkara</span>
                            <input value={search} onChange={(event) => setSearch(event.target.value)} placeholder="Cari perkara..." required />
                        </label>
                        <button className="primary-button" type="submit">Cari</button>
                    </form>
                </section>

                <section className="summary-grid user-summary-grid">
                    <div className="metric-card"><span>Hasil Pencarian</span><strong>{searchResults.length}</strong></div>
                    <div className="metric-card"><span>Akses Berkas</span><strong>Mandiri</strong></div>
                    <div className="metric-card"><span>Status Pinjam</span><strong>Riwayat</strong></div>
                </section>

                <section className="panel guide-panel">
                    <div className="panel-heading"><h2>Cara Meminjam Berkas</h2></div>
                    <div className="workflow guide-steps"><span>1. Cari perkara</span><span>2. Buka berkas</span><span>3. Kirim permohonan</span><span>4. Tunggu persetujuan</span></div>
                </section>

                <section className="panel">
                    <div className="panel-heading">
                        <h2>Notifikasi Peminjaman</h2>
                    </div>
                    {peminjamanNotifikasi.length === 0 ? (
                        <div className="empty-state"><span>i</span><strong>Belum ada notifikasi peminjaman.</strong><p>Status permohonan akan tampil di sini.</p></div>
                    ) : (
                        <div className="priority-list">
                            {peminjamanNotifikasi.map((item) => (
                                <Link className="priority-item" key={item.id} to="/peminjaman">
                                    <FiClock aria-hidden="true" />
                                    <span>{item.nama_berkas} - {getLoanStatusLabel(item.status)}</span>
                                </Link>
                            ))}
                        </div>
                    )}
                </section>

                <section className="panel">
                    <div className="panel-heading">
                        <h2>Hasil Pencarian</h2>
                    </div>
                    {searchResults.length === 0 ? (
                        <div className="empty-state"><span>i</span><strong>Belum ada hasil.</strong><p>Masukkan nomor, nama, atau tahun perkara.</p></div>
                    ) : (
                        <div className="table-wrap">
                            <table>
                                <thead>
                                    <tr>
                                        <th>Nomor Perkara</th>
                                        <th>Nama Terdakwa</th>
                                        <th>Tahun</th>
                                        <th>Lokasi</th>
                                        <th>Aksi</th>
                                    </tr>
                                </thead>
                                <tbody>
                                    {searchResults.map((item) => (
                                        <tr key={item.id}>
                                            <td>{item.nomor_perkara}</td>
                                            <td>{getNamaTerdakwa(item)}</td>
                                            <td>{item.created_at?.slice(0, 4) || "-"}</td>
                                            <td>{item.nama_lemari} / {item.nama_rak}</td>
                                            <td><Link className="secondary-button" to={`/perkara/${item.id}/berkas`}>Buka Berkas</Link></td>
                                        </tr>
                                    ))}
                                </tbody>
                            </table>
                        </div>
                    )}
                </section>
            </AppShell>
        );
    }

    if (role === "arsiparis") {
        const activityFeed = getArsiparisActivityFeed();

        return (
            <AppShell
                title="Dashboard"
                subtitle="Aktivitas dan notifikasi operasional arsip"
            >
                {error && <div className="notice error">{error}</div>}
                {loading && <div className="notice">Memuat dashboard...</div>}

                <section className="panel arsiparis-activity-panel">
                    <div className="panel-heading">
                        <h2>Aktivitas & Notifikasi</h2>
                        <span className="table-count">{activityFeed.length} aktivitas</span>
                    </div>

                    {activityFeed.length === 0 ? (
                        <div className="empty-state"><span>i</span><strong>Tidak ada aktivitas penting saat ini.</strong><p>Permintaan, retensi, dan status berkas akan tampil di sini.</p></div>
                    ) : (
                        <div className="activity-feed-list">
                            {activityFeed.map((item) => {
                                const Icon = item.icon || FiFileText;

                                return (
                                    <article className={`activity-feed-item ${item.tone}`} key={item.id}>
                                        <span className="activity-feed-icon"><Icon aria-hidden="true" /></span>
                                        <div className="activity-feed-content">
                                            <div className="activity-feed-header">
                                                <strong>{item.title}</strong>
                                                <time>{formatDateTime(item.time)}</time>
                                            </div>
                                            <p>{item.description}</p>
                                            <dl className="activity-feed-meta">
                                                <div><dt>Pengguna</dt><dd>{item.user}</dd></div>
                                                <div><dt>Perkara</dt><dd>{item.perkara}</dd></div>
                                                <div><dt>Berkas</dt><dd>{item.berkas}</dd></div>
                                            </dl>
                                            {item.actions?.length > 0 && (
                                                <div className="activity-feed-actions">
                                                    {item.actions.map((action) => action.to ? (
                                                        <Link className={action.className} key={action.label} to={action.to}>{action.label}</Link>
                                                    ) : (
                                                        <button className={action.className} key={action.label} type="button" onClick={action.onClick}>{action.label}</button>
                                                    ))}
                                                </div>
                                            )}
                                        </div>
                                    </article>
                                );
                            })}
                        </div>
                    )}
                </section>
            </AppShell>
        );
    }

    const adminSummaryCards = getAdminSummaryCards(stats);
    const actionNotifications = buildActionNotifications({ anomali, berkas: arsipItems, perkara: perkaraData });

    return (
        <AppShell
            title="Dashboard"
            subtitle="Ringkasan operasional Sistem Arsip Digital"
        >
            {error && <div className="notice error">{error}</div>}
            {loading && <div className="notice">Memuat dashboard...</div>}

            <section className="summary-grid admin-summary-grid">
                {adminSummaryCards.map((card) => {
                    const Icon = card.icon || FiGrid;
                    return (
                        <div className="metric-card dashboard-summary-card" key={card.key}>
                            <span>{card.label}</span>
                            <strong>{card.value}</strong>
                            <Icon aria-hidden="true" />
                        </div>
                    );
                })}
            </section>

            <section className="panel action-center-panel">
                <div className="panel-heading">
                    <h2>Notifikasi</h2>
                    <span className="notification-category-count">{actionNotifications.length} kategori tindakan</span>
                </div>
                {actionNotifications.length === 0 ? (
                    <div className="empty-state"><span>i</span><strong>Tidak ada notifikasi yang memerlukan tindakan.</strong><p>Seluruh pekerjaan yang harus ditindaklanjuti sudah selesai.</p></div>
                ) : (
                    <div className="notification-list">
                        {actionNotifications.map((item) => {
                            const Icon = item.icon || FiAlertTriangle;
                            return (
                                <Link className={`notification-card-item ${item.tone || "neutral"}`} key={item.key} to={item.to}>
                                    <div className="notification-item-icon">
                                        <Icon aria-hidden="true" />
                                    </div>
                                    <div className="notification-item-content">
                                        <h3 className="notification-item-title">{item.title}</h3>
                                        <p className="notification-item-desc">{item.description}</p>
                                        <span className="notification-item-count">{item.count} data perlu tindakan</span>
                                    </div>
                                    <FiChevronRight className="notification-item-arrow" aria-hidden="true" />
                                </Link>
                            );
                        })}
                    </div>
                )}
            </section>

            <section className="panel timeline-panel full-width-panel">
                <div className="panel-heading">
                    <h2>Aktivitas Terbaru</h2>
                </div>
                {activities.length === 0 ? (
                    <p className="empty-state">Belum ada aktivitas yang dapat ditampilkan.</p>
                ) : (
                    <div className="timeline-scroll-container">
                        <div className="timeline-list">
                            {activities.slice(0, 10).map((activity) => {
                                const Icon = getActivityIcon(activity);

                                return (
                                    <div className="timeline-item-row" key={activity.id}>
                                        <div className="timeline-item-icon">
                                            <Icon aria-hidden="true" />
                                        </div>
                                        <div className="timeline-item-body">
                                            <strong className="timeline-user">{getNamaPengguna(activity)}</strong>
                                            <span className="timeline-desc">{describeActivity(activity)}</span>
                                        </div>
                                        <time className="timeline-time">{formatRelativeTime(activity.waktu)}</time>
                                    </div>
                                );
                            })}
                        </div>
                    </div>
                )}
            </section>
        </AppShell>
    );
}

export default Dashboard;
