import { useCallback, useEffect, useMemo, useState } from "react";
import AppShell from "./AppShell";
import { api, fetchData } from "../services/apiService";

const pageSize = 8;

const normalizeStatus = (status) => String(status || "").toUpperCase();

const statusLabels = {
    MENUNGGU: "Menunggu Persetujuan Arsiparis",
    DISETUJUI: "Disetujui",
    DIPINJAM: "Sedang Dipinjam",
    DITOLAK: "Ditolak",
    DIKEMBALIKAN: "Sudah Dikembalikan"
};

const getStatusLabel = (status) => statusLabels[normalizeStatus(status)] || status || "-";

function Peminjaman() {
    const role = (localStorage.getItem("role") || "").toLowerCase();
    const [items, setItems] = useState([]);
    const [search, setSearch] = useState("");
    const [statusFilter, setStatusFilter] = useState("");
    const [page, setPage] = useState(1);
    const [loading, setLoading] = useState(false);
    const [notice, setNotice] = useState("");
    const [error, setError] = useState("");

    const visibleItems = useMemo(() => {
        const term = search.toLowerCase();

        return items.filter((item) => {
            const matchesSearch = !term || [
                item.nomor_berkas,
                item.nomor_perkara,
                item.nama_berkas,
                item.nama_peminjam,
                item.peminjam,
                item.keperluan,
                item.status
            ].some((value) => String(value || "").toLowerCase().includes(term));
            const matchesStatus = !statusFilter || normalizeStatus(item.status) === statusFilter;

            return matchesSearch && matchesStatus;
        });
    }, [items, search, statusFilter]);

    const totalPages = Math.max(1, Math.ceil(visibleItems.length / pageSize));
    const pagedItems = visibleItems.slice((page - 1) * pageSize, page * pageSize);

    const loadItems = useCallback(async () => {
        setLoading(true);
        try {
            const data = await fetchData("/peminjaman");
            setItems(Array.isArray(data) ? data : []);
            setError("");
        } catch (requestError) {
            setError(requestError.response?.data?.message || "Gagal memuat peminjaman");
        } finally {
            setLoading(false);
        }
    }, []);

    useEffect(() => {
        Promise.resolve().then(loadItems);
    }, [loadItems]);

    useEffect(() => {
        if (!notice && !error) return undefined;

        const timerId = window.setTimeout(() => {
            setNotice("");
            setError("");
        }, 1000);

        return () => window.clearTimeout(timerId);
    }, [error, notice]);

    const updateStatus = async (id, action) => {
        try {
            await api.put(`/peminjaman/${id}/${action}`);
            setNotice("Status peminjaman berhasil diperbarui.");
            setError("");
            loadItems();
        } catch (requestError) {
            setError(requestError.response?.data?.message || "Status peminjaman gagal diperbarui");
        }
    };

    const statusBadge = (status) => {
        const normalized = normalizeStatus(status);
        if (["DISETUJUI", "DIPINJAM", "DIKEMBALIKAN"].includes(normalized)) return "success";
        if (normalized === "MENUNGGU") return "warning";
        if (normalized === "DITOLAK") return "danger";
        return "neutral";
    };

    return (
        <AppShell
            title={role === "user" ? "Riwayat Peminjaman" : "Peminjaman"}
            subtitle="Workflow peminjaman arsip: diajukan, disetujui, dipinjam, dikembalikan"
        >
            {notice && <div className="toast success">{notice}</div>}
            {error && <div className="toast error">{error}</div>}

            <section className="panel table-panel">
                <div className="panel-heading">
                    <h2>Daftar Peminjaman</h2>
                    <span className="table-count">{visibleItems.length} data</span>
                </div>

                {role !== "user" && (
                    <div className="workflow">
                        <span>Menunggu Persetujuan Arsiparis</span>
                        <span>Disetujui</span>
                        <span>Sedang Dipinjam</span>
                        <span>Sudah Dikembalikan</span>
                        <span>Ditolak</span>
                    </div>
                )}

                <div className="filter-vertical-container">
                    <label className="field">
                        <span>Pencarian Peminjaman</span>
                        <input
                            className="search-input"
                            placeholder="Cari nomor, berkas, peminjam..."
                            value={search}
                            onChange={(event) => {
                                setSearch(event.target.value);
                                setPage(1);
                            }}
                        />
                    </label>
                    <label className="field">
                        <span>Filter Status</span>
                        <select
                            value={statusFilter}
                            onChange={(event) => {
                                setStatusFilter(event.target.value);
                                setPage(1);
                            }}
                        >
                            <option value="">Semua Status</option>
                            <option value="MENUNGGU">Menunggu Persetujuan Arsiparis</option>
                            <option value="DISETUJUI">Disetujui</option>
                            <option value="DIPINJAM">Sedang Dipinjam</option>
                            <option value="DIKEMBALIKAN">Sudah Dikembalikan</option>
                            <option value="DITOLAK">Ditolak</option>
                        </select>
                    </label>
                </div>

                <div className="table-wrap">
                    {loading ? (
                        <div className="loading-state"><span className="spinner" />Memuat peminjaman...</div>
                    ) : visibleItems.length === 0 ? (
                        <div className="empty-state"><span>i</span><strong>Belum ada data peminjaman.</strong><p>Pengajuan peminjaman berkas akan tampil di sini.</p></div>
                    ) : (
                        <table>
                            <thead>
                                <tr>
                                    <th>Nomor Berkas</th>
                                    <th>Nama Berkas</th>
                                    {role !== "user" && <th>Peminjam</th>}
                                    <th>Tanggal</th>
                                    <th>Status</th>
                                    {role === "user" && <th>Riwayat</th>}
                                    {role !== "user" && <th>Aksi</th>}
                                </tr>
                            </thead>
                            <tbody>
                                {pagedItems.map((item) => (
                                    <tr key={item.id}>
                                        <td>{item.nomor_berkas || item.nomor_perkara || "-"}</td>
                                        <td>{item.nama_berkas}</td>
                                        {role !== "user" && <td>{item.nama_peminjam || item.peminjam || "-"}</td>}
                                        <td>{item.tanggal_pinjam?.slice(0, 10)} - {item.tanggal_kembali?.slice(0, 10) || "-"}</td>
                                        <td><span className={`badge ${statusBadge(item.status)}`}>{getStatusLabel(item.status)}</span></td>
                                        {role === "user" && <td>{getStatusLabel(item.status)}</td>}
                                        {role !== "user" && (
                                            <td className="action-cell">
                                                {normalizeStatus(item.status) === "MENUNGGU" && (
                                                    <button className="secondary-button" onClick={() => updateStatus(item.id, "setujui")}>Setujui</button>
                                                )}
                                                {normalizeStatus(item.status) === "MENUNGGU" && (
                                                    <button className="danger-button" onClick={() => updateStatus(item.id, "tolak")}>Tolak</button>
                                                )}
                                                {normalizeStatus(item.status) === "DIPINJAM" && (
                                                    <button className="secondary-button" onClick={() => updateStatus(item.id, "kembalikan")}>Tandai Sudah Dikembalikan</button>
                                                )}
                                            </td>
                                        )}
                                    </tr>
                                ))}
                            </tbody>
                        </table>
                    )}
                </div>

                {visibleItems.length > 0 && (
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

export default Peminjaman;
