import { useCallback, useEffect, useMemo, useRef, useState } from "react";
import { FiFileText, FiShield } from "react-icons/fi";
import AppShell from "./AppShell";
import { api, fetchData } from "../services/apiService";
import { BerkasDetailModal, integrityBadge, normalizeIntegrityStatus } from "./BerkasCard";

const formatDate = (value) => value ? value.slice(0, 10) : "-";
const formatDateTime = (value) => value ? value.slice(0, 19).replace("T", " ") : "-";

function VerifikasiIntegritas() {
    const [berkas, setBerkas] = useState([]);
    const [history, setHistory] = useState([]);
    const [verifyingId, setVerifyingId] = useState("");
    const [previewPdfBerkas, setPreviewPdfBerkas] = useState(null);
    const [notice, setNotice] = useState("");
    const [error, setError] = useState("");

    const loadData = useCallback(async () => {
        try {
            const [berkasData, historyData] = await Promise.all([
                fetchData("/berkas"),
                fetchData("/berkas/integrity/history")
            ]);
            setBerkas(Array.isArray(berkasData) ? berkasData : []);
            setHistory(Array.isArray(historyData) ? historyData : []);
            setError("");
        } catch (requestError) {
            setError(requestError.response?.data?.message || "Dashboard monitoring verifikasi gagal dimuat");
        }
    }, []);

    useEffect(() => {
        Promise.resolve().then(loadData);
    }, [loadData]);

    const summary = useMemo(() => {
        return berkas.reduce((result, item) => {
            const status = normalizeIntegrityStatus(item.status_integritas);
            if (status === "VALID") result.valid += 1;
            else if (status === "TIDAK_VALID") result.invalid += 1;
            else result.unverified += 1;
            return result;
        }, { unverified: 0, valid: 0, invalid: 0 });
    }, [berkas]);

    const unverifiedItems = useMemo(() => berkas.filter((item) => normalizeIntegrityStatus(item.status_integritas) === "BELUM_DIVERIFIKASI"), [berkas]);

    const noticeTimerRef = useRef(null);

    const showNotice = useCallback((message) => {
        if (noticeTimerRef.current) clearTimeout(noticeTimerRef.current);
        setNotice(message);
        noticeTimerRef.current = setTimeout(() => {
            setNotice("");
        }, 2000);
    }, []);

    useEffect(() => {
        return () => {
            if (noticeTimerRef.current) clearTimeout(noticeTimerRef.current);
        };
    }, []);

    const verifyItem = async (item) => {
        if (!item?.id) return;

        setVerifyingId(String(item.id));
        setNotice("");
        setError("");
        try {
            const response = await api.post(`/berkas/${item.id}/verify`);
            const nextStatus = response.data?.integrity_status || response.data?.status || item.status_integritas;
            const verifiedAt = response.data?.verified_at || new Date().toISOString();
            
            // Update berkas state in memory immediately
            setBerkas((current) => current.map((currentItem) => String(currentItem.id) === String(item.id)
                ? { ...currentItem, status_integritas: nextStatus, tanggal_verifikasi_terakhir: verifiedAt }
                : currentItem));

            // Update verification history in memory immediately
            setHistory((current) => [
                {
                    id: Date.now(),
                    nomor_perkara: item.nomor_perkara || "-",
                    jenis_berkas: item.jenis_berkas || item.nama_berkas || "Berkas",
                    nama_berkas: item.nama_berkas || item.jenis_berkas || "Berkas",
                    status: nextStatus,
                    tanggal_verifikasi: verifiedAt,
                    diverifikasi_oleh_nama: localStorage.getItem("username") || "User"
                },
                ...current
            ]);

            showNotice(response.data?.message || "✓ Verifikasi integritas selesai.");
        } catch (requestError) {
            setError(requestError.response?.data?.message || "Verifikasi integritas gagal");
        } finally {
            setVerifyingId("");
        }
    };

    const handleViewPdf = (item) => {
        if (!item?.id) return;
        setPreviewPdfBerkas(item);
    };

    return (
        <AppShell title="Dashboard Monitoring Verifikasi Integritas" subtitle="Pantau status integritas dan selesaikan berkas yang belum diverifikasi">
            {notice && <div className="toast success">{notice}</div>}
            {error && <div className="notice error">{error}</div>}

            <section className="summary-grid">
                <div className="metric-card"><span>Belum Diverifikasi</span><strong>{summary.unverified}</strong></div>
                <div className="metric-card"><span>Valid</span><strong>{summary.valid}</strong></div>
                <div className="metric-card"><span>Tidak Valid</span><strong>{summary.invalid}</strong></div>
            </section>

            <section className="panel">
                <div className="panel-heading"><h2>Berkas Belum Diverifikasi</h2><span className="table-count">{unverifiedItems.length} pekerjaan</span></div>
                {unverifiedItems.length === 0 ? (
                    <div className="empty-state"><span>✓</span><strong>Seluruh berkas telah diverifikasi.</strong><p>Tidak ada berkas yang perlu diperiksa saat ini.</p></div>
                ) : (
                    <div className="verification-work-list">
                        {unverifiedItems.map((item) => {
                            const badge = integrityBadge(item.status_integritas);
                            const namaTerdakwa = item.nama_terdakwa || (Array.isArray(item.terdakwa) ? item.terdakwa.map((t) => t.nama_terdakwa).filter(Boolean).join(", ") : "") || "-";

                            return (
                                <article className="verification-card-compact" key={item.id}>
                                    {/* Bagian Kiri: Ikon dokumen + nama berkas + badge status */}
                                    <div className="verification-card-left">
                                        <div className="doc-icon-wrap">
                                            <FiFileText aria-hidden="true" />
                                        </div>
                                        <div className="doc-identity">
                                            <strong className="doc-name">{item.jenis_berkas || item.nama_berkas || "Berkas"}</strong>
                                            <span className={`badge ${badge.className}`}>{badge.label}</span>
                                        </div>
                                    </div>

                                    {/* Bagian Tengah: Nomor Perkara & Nama Terdakwa */}
                                    <div className="verification-card-center">
                                        <div className="perkara-info-item">
                                            <span className="info-label">Nomor Perkara:</span>
                                            <span className="info-value">{item.nomor_perkara || "-"}</span>
                                        </div>
                                        <div className="perkara-info-item">
                                            <span className="info-label">Nama Terdakwa:</span>
                                            <span className="info-value">{namaTerdakwa}</span>
                                        </div>
                                    </div>

                                    {/* Bagian Kanan: Tombol "Lihat PDF" (Sekunder) & "Verifikasi Integritas" (Primer) */}
                                    <div className="verification-card-right">
                                        <button
                                            className="secondary-button compact-button"
                                            type="button"
                                            onClick={() => handleViewPdf(item)}
                                        >
                                            Lihat PDF
                                        </button>
                                        <button
                                            className="primary-button compact-button"
                                            type="button"
                                            disabled={String(verifyingId) === String(item.id)}
                                            onClick={() => verifyItem(item)}
                                        >
                                            {String(verifyingId) === String(item.id) ? "Memverifikasi..." : "Verifikasi Integritas"}
                                        </button>
                                    </div>
                                </article>
                            );
                        })}
                    </div>
                )}
            </section>

            <section className="panel">
                <div className="panel-heading"><h2>Riwayat Verifikasi</h2><FiShield aria-hidden="true" /></div>
                {history.length === 0 ? (
                    <div className="empty-state"><span>i</span><strong>Belum ada riwayat verifikasi.</strong><p>Hasil verifikasi akan tampil setelah berkas diperiksa.</p></div>
                ) : (
                    <div className="table-wrap">
                        <table>
                            <thead>
                                <tr>
                                    <th>Tanggal Verifikasi</th>
                                    <th>Nomor Perkara</th>
                                    <th>Jenis Berkas</th>
                                    <th>Nama Berkas</th>
                                    <th>Status Integritas</th>
                                    <th>Pengguna</th>
                                </tr>
                            </thead>
                            <tbody>
                                {history.map((item) => {
                                    const badge = integrityBadge(item.status);
                                    return (
                                        <tr key={item.id}>
                                            <td>{formatDateTime(item.tanggal_verifikasi)}</td>
                                            <td>{item.nomor_perkara || "-"}</td>
                                            <td>{item.jenis_berkas || item.nomor_berkas || "-"}</td>
                                            <td>{item.nama_berkas || "-"}</td>
                                            <td><span className={`badge ${badge.className}`}>{badge.label}</span></td>
                                            <td>{item.diverifikasi_oleh_nama || "-"}</td>
                                        </tr>
                                    );
                                })}
                            </tbody>
                        </table>
                    </div>
                )}
            </section>

            {/* PREVIEW PDF MODAL */}
            {previewPdfBerkas && (
                <BerkasDetailModal
                    berkas={previewPdfBerkas}
                    canVerify={true}
                    verifying={String(verifyingId) === String(previewPdfBerkas?.id)}
                    onClose={() => setPreviewPdfBerkas(null)}
                    onOpenPdf={(b) => {
                        api.get(`/berkas/${b.id}/file`, { responseType: "blob" })
                            .then((res) => window.open(URL.createObjectURL(res.data), "_blank"))
                            .catch(() => window.open(`/api/berkas/${b.id}/file`, "_blank"));
                    }}
                    onVerifyIntegrity={(b) => {
                        setPreviewPdfBerkas(null);
                        verifyItem(b);
                    }}
                />
            )}
        </AppShell>
    );
}

export default VerifikasiIntegritas;
