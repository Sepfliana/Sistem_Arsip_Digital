import { useState } from "react";
import CoverViewer from "./CoverViewer";
import PerkaraInformation from "./PerkaraInformation";
import { BerkasDetailModal, integrityBadge } from "./BerkasCard";

const JENIS_BERKAS_OPTIONS = ["Pra Penuntutan", "Penuntutan", "Eksekusi"];

const formatDate = (value) => {
    if (!value) return "-";
    const date = new Date(value);
    return Number.isNaN(date.getTime()) ? String(value).slice(0, 10) : date.toLocaleDateString("id-ID");
};

const normalizeJenisBerkas = (jenis) => String(jenis || "").trim().toLowerCase();

const getBerkasByJenis = (perkara, berkas = [], jenis) => {
    const mapped = perkara?.berkas_by_jenis?.[jenis];
    if (mapped) return mapped;
    return berkas.find((item) => normalizeJenisBerkas(item.jenis_berkas) === normalizeJenisBerkas(jenis)) || null;
};

function DetailPerkaraPage({ perkara, berkas = [], peminjaman = [], readOnly, canManageCover = false, canVerifyIntegrity = false, verifyingBerkasId = "", onAddBerkas, onBack, onOpenPdf, onCoverUpdated, onVerifyIntegrity }) {
    const [selectedBerkas, setSelectedBerkas] = useState(null);
    const [searchTerm, setSearchTerm] = useState("");

    if (!perkara) {
        return null;
    }

    const berkasByJenis = JENIS_BERKAS_OPTIONS.reduce((map, jenis) => {
        map[jenis] = getBerkasByJenis(perkara, berkas, jenis);
        return map;
    }, {});

    const stagesList = JENIS_BERKAS_OPTIONS.map((jenis) => ({
        stageTitle: jenis,
        berkas: berkasByJenis[jenis]
    }));

    const filteredStages = stagesList.filter(({ stageTitle, berkas: item }) => {
        if (!searchTerm.trim()) return true;
        const term = searchTerm.toLowerCase();
        const nama = (item?.nama_berkas || item?.jenis_berkas || stageTitle).toLowerCase();
        const nomor = (item?.nomor_berkas || "").toLowerCase();
        return nama.includes(term) || nomor.includes(term);
    });

    return (
        <>
            <div className="detail-page-heading">
                <div className="action-cell">
                    {!readOnly && <button className="primary-button" type="button" onClick={onAddBerkas}>Tambah Berkas</button>}
                    <button className="secondary-button" type="button" onClick={onBack}>Kembali</button>
                </div>
            </div>

            <div className="combined-perkara-layout">
                <CoverViewer perkara={perkara} berkas={berkas} canManageCover={canManageCover} onCoverUpdated={onCoverUpdated} />
                <PerkaraInformation perkara={perkara} />
            </div>

            {/* DAFTAR BERKAS COMPACT TABLE */}
            <section className="panel">
                <div className="panel-heading" style={{ display: "flex", justifyContent: "space-between", alignItems: "center", flexWrap: "wrap", gap: "12px" }}>
                    <h2>Daftar Berkas</h2>
                    {berkas.length > 3 && (
                        <input
                            type="text"
                            className="field-input"
                            style={{ width: "220px", padding: "6px 12px", fontSize: "13px" }}
                            placeholder="Cari berkas..."
                            value={searchTerm}
                            onChange={(e) => setSearchTerm(e.target.value)}
                        />
                    )}
                </div>

                <div className="berkas-table-wrap">
                    <table className="berkas-table">
                        <thead>
                            <tr>
                                <th>Nama Berkas</th>
                                <th>Nomor Berkas</th>
                                <th>Tanggal Upload</th>
                                <th>Status Integritas</th>
                                <th>Retensi</th>
                                <th style={{ textAlign: "center" }}>Aksi</th>
                            </tr>
                        </thead>
                        <tbody>
                            {filteredStages.map(({ stageTitle, berkas: item }) => {
                                if (!item) {
                                    return (
                                        <tr key={stageTitle} className="empty-stage-row">
                                            <td><strong className="berkas-nama">{stageTitle}</strong></td>
                                            <td colSpan={4} className="secondary-text" style={{ fontStyle: "italic" }}>
                                                Belum ada berkas {stageTitle.toLowerCase()}
                                            </td>
                                            <td style={{ textAlign: "center" }}>
                                                {!readOnly ? (
                                                    <button className="secondary-button compact-button" type="button" onClick={onAddBerkas}>
                                                        + Upload
                                                    </button>
                                                ) : (
                                                    <span className="secondary-text">-</span>
                                                )}
                                            </td>
                                        </tr>
                                    );
                                }

                                const badge = integrityBadge(item.status_integritas);

                                return (
                                    <tr key={item.id || stageTitle}>
                                        <td>
                                            <strong className="berkas-nama">{item.jenis_berkas || stageTitle || item.nama_berkas}</strong>
                                        </td>
                                        <td>
                                            <span className="berkas-nomor">{item.nomor_berkas || "-"}</span>
                                        </td>
                                        <td>{formatDate(item.created_at || item.tanggal_berkas)}</td>
                                        <td>
                                            <span className={`badge ${badge.className}`}>{badge.label}</span>
                                        </td>
                                        <td>
                                            <div className="berkas-retensi-cell">
                                                <span>Aktif: {item.masa_retensi_aktif != null ? `${item.masa_retensi_aktif} th` : "-"}</span>
                                                <span className="secondary-text">Inaktif: {item.masa_retensi_inaktif != null ? `${item.masa_retensi_inaktif} th` : "-"}</span>
                                            </div>
                                        </td>
                                        <td style={{ textAlign: "center" }}>
                                            <button
                                                className="secondary-button compact-button"
                                                type="button"
                                                onClick={() => setSelectedBerkas(item)}
                                            >
                                                Detail
                                            </button>
                                        </td>
                                    </tr>
                                );
                            })}
                        </tbody>
                    </table>
                </div>
            </section>

            {/* RIWAYAT PEMINJAMAN */}
            <section className="panel">
                <div className="panel-heading"><h2>Riwayat Peminjaman</h2></div>
                {peminjaman.length === 0 ? (
                    <p className="secondary-text" style={{ padding: "8px 0" }}>Belum ada riwayat peminjaman.</p>
                ) : (
                    <div className="table-wrap">
                        <table>
                            <thead>
                                <tr>
                                    <th>Tanggal Pinjam</th>
                                    <th>Nama Berkas</th>
                                    <th>Peminjam</th>
                                    <th>Tanggal Kembali</th>
                                    <th>Status</th>
                                </tr>
                            </thead>
                            <tbody>
                                {peminjaman.map((item) => (
                                    <tr key={item.id}>
                                        <td>{formatDate(item.tanggal_pinjam)}</td>
                                        <td>{item.nama_berkas || item.nomor_berkas || "-"}</td>
                                        <td>{item.pemohon_nama_lengkap || item.nama_peminjam || item.pemohon_username || item.username || "-"}</td>
                                        <td>{formatDate(item.tanggal_kembali)}</td>
                                        <td><span className="badge neutral">{item.status || "-"}</span></td>
                                    </tr>
                                ))}
                            </tbody>
                        </table>
                    </div>
                )}
            </section>

            {/* DETAIL BERKAS MODAL */}
            {selectedBerkas && (
                <BerkasDetailModal
                    berkas={selectedBerkas}
                    canVerify={canVerifyIntegrity}
                    verifying={String(verifyingBerkasId) === String(selectedBerkas?.id)}
                    onClose={() => setSelectedBerkas(null)}
                    onOpenPdf={onOpenPdf}
                    onVerifyIntegrity={onVerifyIntegrity}
                />
            )}
        </>
    );
}

export default DetailPerkaraPage;



