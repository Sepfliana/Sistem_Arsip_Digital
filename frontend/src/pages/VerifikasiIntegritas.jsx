import { useCallback, useEffect, useMemo, useState } from "react";
import { FiFileText, FiShield } from "react-icons/fi";
import AppShell from "./AppShell";
import { api, fetchData } from "../services/apiService";
import { integrityBadge, normalizeIntegrityStatus } from "./BerkasCard";

const formatDate = (value) => value ? value.slice(0, 10) : "-";
const formatDateTime = (value) => value ? value.slice(0, 19).replace("T", " ") : "-";

function VerifikasiIntegritas() {
    const [berkas, setBerkas] = useState([]);
    const [history, setHistory] = useState([]);
    const [verifyingId, setVerifyingId] = useState("");
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

    const verifyItem = async (item) => {
        if (!item?.id) return;

        setVerifyingId(String(item.id));
        setNotice("");
        try {
            const response = await api.post(`/berkas/${item.id}/verify`);
            const nextStatus = response.data?.integrity_status || response.data?.status || item.status_integritas;
            const verifiedAt = response.data?.verified_at || new Date().toISOString();
            setBerkas((current) => current.map((currentItem) => String(currentItem.id) === String(item.id)
                ? { ...currentItem, status_integritas: nextStatus, tanggal_verifikasi_terakhir: verifiedAt }
                : currentItem));
            setNotice(response.data?.message || "Verifikasi integritas selesai.");
            await loadData();
        } catch (requestError) {
            setError(requestError.response?.data?.message || "Verifikasi integritas gagal");
        } finally {
            setVerifyingId("");
        }
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
                            return (
                                <article className="verification-work-item" key={item.id}>
                                    <span className="activity-feed-icon"><FiFileText aria-hidden="true" /></span>
                                    <div className="activity-feed-content">
                                        <div className="activity-feed-header">
                                            <strong>{item.jenis_berkas || "Berkas"}</strong>
                                            <span className={`badge ${badge.className}`}>{badge.label}</span>
                                        </div>
                                        <dl className="activity-feed-meta">
                                            <div><dt>Nomor Perkara</dt><dd>{item.nomor_perkara || "-"}</dd></div>
                                            <div><dt>Nama Berkas</dt><dd>{item.nama_berkas || "-"}</dd></div>
                                            <div><dt>Tanggal Upload</dt><dd>{formatDate(item.tanggal_mulai_aktif || item.tanggal_berkas || item.created_at)}</dd></div>
                                        </dl>
                                    </div>
                                    <button className="primary-button" type="button" disabled={String(verifyingId) === String(item.id)} onClick={() => verifyItem(item)}>
                                        {String(verifyingId) === String(item.id) ? "Memverifikasi..." : "Verifikasi"}
                                    </button>
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
        </AppShell>
    );
}

export default VerifikasiIntegritas;
