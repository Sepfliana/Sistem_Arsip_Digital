import { useCallback, useEffect, useMemo, useState } from "react";
import { useNavigate, useParams } from "react-router-dom";
import AppShell from "./AppShell";
import ResourcePage from "./ResourcePage";
import { fetchData, updateData } from "../services/apiService";

const statusBadge = (status) => {
    if (status === "Kosong") return "success";
    if (status === "Tersedia") return "warning";
    if (status === "Penuh") return "danger";
    return "neutral";
};

function Lemari() {
    const { lemariId } = useParams();
    const navigate = useNavigate();
    const role = (localStorage.getItem("role") || "").toLowerCase();
    const canDelete = role === "admin";
    const readOnly = role === "user";
    const [selectedLemari, setSelectedLemari] = useState(null);
    const [rak, setRak] = useState([]);
    const [search, setSearch] = useState("");
    const [editingRak, setEditingRak] = useState(null);
    const [rakForm, setRakForm] = useState({ kapasitas: "" });
    const [loading, setLoading] = useState(false);
    const [notice, setNotice] = useState("");
    const [error, setError] = useState("");

    const filteredRak = useMemo(() => {
        const term = search.toLowerCase();
        return rak.filter((item) => !term || [item.nama_rak, item.status].some((value) => String(value || "").toLowerCase().includes(term)));
    }, [rak, search]);

    const loadDetail = useCallback(async () => {
        if (!lemariId) {
            return;
        }

        setLoading(true);

        try {
            const [lemariData, rakData] = await Promise.all([
                fetchData(`/lemari/${lemariId}`),
                fetchData("/rak", { lemari_id: lemariId })
            ]);

            setSelectedLemari(lemariData);
            setRak(Array.isArray(rakData) ? rakData : []);
            setError("");
        } catch (requestError) {
            setError(requestError.response?.data?.message || "Data rak gagal dimuat");
        } finally {
            setLoading(false);
        }
    }, [lemariId]);

    useEffect(() => {
        Promise.resolve().then(loadDetail);
    }, [loadDetail]);

    useEffect(() => {
        if (!notice && !error) {
            return undefined;
        }

        const timerId = window.setTimeout(() => {
            setNotice("");
            setError("");
        }, 1800);

        return () => window.clearTimeout(timerId);
    }, [error, notice]);

    const openEditRak = (item) => {
        setEditingRak(item);
        setRakForm({ kapasitas: item.kapasitas || "" });
    };

    const submitEditRak = async (event) => {
        event.preventDefault();

        try {
            await updateData("/rak", editingRak.id, { kapasitas: rakForm.kapasitas });
            setNotice("Kapasitas rak berhasil diperbarui.");
            setEditingRak(null);
            setRakForm({ kapasitas: "" });
            await loadDetail();
        } catch (requestError) {
            setError(requestError.response?.data?.message || "Kapasitas rak gagal diperbarui");
        }
    };

    if (!lemariId) {
        return (
            <ResourcePage
                title="Lemari"
                subtitle="Pilih lemari untuk melihat rak di dalamnya"
                endpoint="/lemari"
                readOnly={readOnly}
                onOpen={(item) => navigate(`/lemari/${item.id}/rak`)}
                openLabel="Buka Rak"
                addLabel="Tambah Lemari"
                canDelete={canDelete}
                columns={[
                    { key: "nama_lemari", label: "Nama Lemari" },
                    { key: "lokasi", label: "Lokasi" },
                    { key: "jumlah_rak", label: "Jumlah Rak" },
                    { key: "jumlah_terpakai", label: "Rak Terpakai" },
                    { key: "kapasitas_total", label: "Kapasitas Total" },
                    { key: "status", label: "Status", render: (item) => <span className={`badge ${statusBadge(item.status)}`}>{item.status || "Kosong"}</span> }
                ]}
                fields={[
                    { name: "nama_lemari", label: "Nama Lemari", required: true },
                    { name: "lokasi", label: "Lokasi", required: true },
                    { name: "jumlah_rak", label: "Jumlah Rak", type: "number", required: true }
                ]}
            />
        );
    }


    return (
        <AppShell title="Rak" subtitle={selectedLemari ? `Rak pada ${selectedLemari.nama_lemari}` : "Detail lemari"}>
            {notice && <div className="toast success">{notice}</div>}
            {error && <div className="toast error">{error}</div>}
            {loading && <div className="loading-state"><span className="spinner" />Memuat data...</div>}

            <section className="panel detail-panel">
                <div className="panel-heading">
                    <h2>{selectedLemari?.nama_lemari || "Lemari"}</h2>
                    <button className="secondary-button" onClick={() => navigate("/lemari")}>Kembali</button>
                </div>
                <dl className="detail-grid">
                    <div className="detail-row">
                        <dt>Lokasi</dt>
                        <dd>{selectedLemari?.lokasi || "-"}</dd>
                    </div>
                    <div className="detail-row">
                        <dt>Status</dt>
                        <dd><span className={`badge ${statusBadge(selectedLemari?.status)}`}>{selectedLemari?.status || "Kosong"}</span></dd>
                    </div>
                    <div className="detail-row">
                        <dt>Jumlah Rak</dt>
                        <dd>{selectedLemari?.jumlah_rak ?? rak.length}</dd>
                    </div>
                    <div className="detail-row">
                        <dt>Rak Terpakai</dt>
                        <dd>{selectedLemari?.jumlah_terpakai ?? 0}</dd>
                    </div>
                    <div className="detail-row">
                        <dt>Kapasitas Total</dt>
                        <dd>{selectedLemari?.kapasitas_total ?? "-"}</dd>
                    </div>
                </dl>
            </section>

            <section className="panel table-panel">
                <div className="panel-heading">
                    <h2>Daftar Rak</h2>
                    <span className="table-count">{filteredRak.length} data</span>
                </div>
                <div className="filter-vertical-container">
                    <label className="field">
                        <span>Pencarian Rak</span>
                        <input className="search-input" placeholder="Cari rak atau status..." value={search} onChange={(event) => setSearch(event.target.value)} />
                    </label>
                </div>

                <div className="table-wrap">
                    {filteredRak.length === 0 ? (
                        <div className="empty-state"><span>i</span><strong>Belum ada rak.</strong><p>Rak otomatis dibuat saat lemari dibuat.</p></div>
                    ) : (
                        <table>
                            <thead>
                                <tr>
                                    <th>Nama Rak</th>
                                    <th>Kapasitas</th>
                                    <th>Terpakai</th>
                                    <th>Status</th>
                                    {!readOnly && <th>Aksi</th>}
                                </tr>
                            </thead>
                            <tbody>
                                {filteredRak.map((item) => (
                                    <tr
                                        key={item.id}
                                        className="clickable-tr"
                                        onClick={() => navigate(`/lemari/${lemariId}/rak/${item.id}/perkara`)}
                                    >
                                        <td>
                                            <span className="clickable-data">
                                                {item.nama_rak}
                                            </span>
                                        </td>
                                        <td>{item.kapasitas}</td>
                                        <td>{item.jumlah_perkara || 0}</td>
                                        <td><span className={`badge ${statusBadge(item.status)}`}>{item.status || "Kosong"}</span></td>
                                        {!readOnly && (
                                            <td className="action-cell" onClick={(e) => e.stopPropagation()}>
                                                <button className="secondary-button" onClick={(e) => { e.stopPropagation(); openEditRak(item); }}>Edit</button>
                                            </td>
                                        )}
                                    </tr>
                                ))}
                            </tbody>
                        </table>
                    )}
                </div>
            </section>

            {editingRak && (
                <div className="modal-backdrop">
                    <form className="modal-card" onSubmit={submitEditRak}>
                        <div className="panel-heading">
                            <h2>Edit Kapasitas Rak</h2>
                            <button className="secondary-button" type="button" onClick={() => setEditingRak(null)}>Tutup</button>
                        </div>
                        <div className="modal-form-grid">
                            <label className="field"><span>Nama Rak</span><input value={editingRak.nama_rak} readOnly /></label>
                            <label className="field"><span>Kapasitas</span><input type="number" min="1" value={rakForm.kapasitas} onChange={(event) => setRakForm({ kapasitas: event.target.value })} required /></label>
                        </div>
                        <div className="modal-actions">
                            <button className="secondary-button" type="button" onClick={() => setEditingRak(null)}>Batal</button>
                            <button className="primary-button" type="submit">Simpan</button>
                        </div>
                    </form>
                </div>
            )}
        </AppShell>
    );
}

export default Lemari;
