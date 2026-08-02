import CoverViewer from "./CoverViewer";
import PerkaraInformation from "./PerkaraInformation";
import BerkasCard from "./BerkasCard";

const JENIS_BERKAS_OPTIONS = ["Pra Penuntutan", "Penuntutan", "Eksekusi"];

const formatDate = (value) => value ? new Date(value).toLocaleDateString("id-ID") : "-";

const normalizeJenisBerkas = (jenis) => String(jenis || "").trim().toLowerCase();

const getBerkasByJenis = (perkara, berkas, jenis) => {
    const mapped = perkara?.berkas_by_jenis?.[jenis];
    if (mapped) return mapped;
    return berkas.find((item) => normalizeJenisBerkas(item.jenis_berkas) === normalizeJenisBerkas(jenis)) || null;
};

function DetailPerkaraPage({ perkara, berkas, peminjaman = [], readOnly, canManageCover = false, canVerifyIntegrity = false, verifyingBerkasId = "", onAddBerkas, onBack, onOpenPdf, onCoverUpdated, onVerifyIntegrity }) {
    const berkasByJenis = JENIS_BERKAS_OPTIONS.reduce((map, jenis) => {
        map[jenis] = getBerkasByJenis(perkara, berkas, jenis);
        return map;
    }, {});

    const activeStages = JENIS_BERKAS_OPTIONS.filter((jenis) => Boolean(berkasByJenis[jenis]));

    if (!perkara) {
        return null;
    }

    return (
        <>
            <div className="detail-page-heading">
                <div className="action-cell">
                    {!readOnly && <button className="primary-button" type="button" onClick={onAddBerkas}>Tambah Berkas</button>}
                    <button className="secondary-button" type="button" onClick={onBack}>Kembali</button>
                </div>
            </div>

            <div className="combined-perkara-layout">
                <CoverViewer perkara={perkara} canManageCover={canManageCover} onCoverUpdated={onCoverUpdated} />
                <PerkaraInformation perkara={perkara} />
            </div>

            <section className="panel">
                <div className="panel-heading"><h2>Daftar Berkas</h2></div>
                {activeStages.length === 0 ? (
                    <p className="secondary-text" style={{ padding: "8px 0" }}>Belum ada berkas perkara.</p>
                ) : (
                    <div className="berkas-stage-stack">
                        {activeStages.map((jenis) => (
                            <BerkasCard key={jenis} title={jenis} berkas={berkasByJenis[jenis]} readOnly={readOnly} canVerify={canVerifyIntegrity} verifying={String(verifyingBerkasId) === String(berkasByJenis[jenis]?.id)} onOpenPdf={onOpenPdf} onVerifyIntegrity={onVerifyIntegrity} />
                        ))}
                    </div>
                )}
            </section>

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
        </>
    );
}

export default DetailPerkaraPage;


