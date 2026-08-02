import { useCallback, useEffect, useMemo, useState } from "react";
import AppShell from "./AppShell";
import { createData, deleteData, fetchData, updateData } from "../services/apiService";

const EMPTY_OBJECT = {};

function ResourcePage({
    title,
    subtitle,
    endpoint,
    columns,
    fields,
    canDelete = true,
    readOnly = false,
    onOpen,
    queryParams = EMPTY_OBJECT,
    initialForm = EMPTY_OBJECT,
    addLabel = "Tambah Data"
}) {
    const [items, setItems] = useState([]);
    const [form, setForm] = useState({});
    const [editingId, setEditingId] = useState(null);
    const [search, setSearch] = useState("");
    const [filterColumn, setFilterColumn] = useState(columns[0]?.key || "");
    const [filterValue, setFilterValue] = useState("");
    const [page, setPage] = useState(1);
    const [modalOpen, setModalOpen] = useState(false);
    const [deleteTarget, setDeleteTarget] = useState(null);
    const [loading, setLoading] = useState(false);
    const [notice, setNotice] = useState("");
    const [error, setError] = useState("");
    const pageSize = 8;

    const visibleItems = useMemo(() => {
        const term = search.toLowerCase();
        const filterTerm = filterValue.toLowerCase();

        return items.filter((item) =>
            (!term ||
                Object.values(item).some((value) =>
                    String(value || "").toLowerCase().includes(term)
                )) &&
            (!filterTerm ||
                String(item[filterColumn] || "").toLowerCase().includes(filterTerm))
        );
    }, [filterColumn, filterValue, items, search]);

    const totalPages = Math.max(1, Math.ceil(visibleItems.length / pageSize));
    const pagedItems = visibleItems.slice((page - 1) * pageSize, page * pageSize);

    const loadItems = useCallback(async () => {
        setLoading(true);

        try {
            const data = await fetchData(endpoint, queryParams);
            setItems(Array.isArray(data) ? data : []);
        } catch (error) {
            setError(error.response?.data?.message || `Gagal memuat ${title}`);
        } finally {
            setLoading(false);
        }
    }, [endpoint, queryParams, title]);

    useEffect(() => {
        Promise.resolve().then(loadItems);
    }, [loadItems]);

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

    const handleChange = (field, value) => {
        setForm((current) => ({
            ...current,
            [field]: value
        }));
    };

    const resetForm = () => {
        setForm({ ...initialForm });
        setEditingId(null);
        setModalOpen(false);
    };

    const openCreateModal = () => {
        setForm({ ...initialForm });
        setEditingId(null);
        setModalOpen(true);
    };

    const handleSubmit = async (event) => {
        event.preventDefault();

        try {
            if (editingId) {
                await updateData(endpoint, editingId, form);
                setNotice("Data berhasil diperbarui.");
            } else {
                await createData(endpoint, form);
                setNotice("Data berhasil ditambahkan.");
            }

            setError("");
            resetForm();
            loadItems();
        } catch (error) {
            setError(error.response?.data?.message || "Data gagal disimpan");
        }
    };

    const handleEdit = (item) => {
        setEditingId(item.id);

        const nextForm = {};
        fields.forEach((field) => {
            nextForm[field.name] = item[field.name] ?? "";
        });

        setForm(nextForm);
        setModalOpen(true);
    };

    const handleDelete = async () => {
        try {
            await deleteData(endpoint, deleteTarget);
            setNotice("Data berhasil dihapus.");
            setError("");
            setDeleteTarget(null);
            loadItems();
        } catch (error) {
            setError(error.response?.data?.message || "Data gagal dihapus");
        }
    };

    return (
        <AppShell title={title} subtitle={subtitle}>
            {notice && <div className="toast success">{notice}</div>}
            {error && <div className="toast error">{error}</div>}
            <section>
                <section className="panel table-panel">
                    <div className="panel-heading">
                        <h2>Daftar Data</h2>
                        {!readOnly && (
                            <button className="primary-button" onClick={openCreateModal}>
                                {addLabel}
                            </button>
                        )}
                    </div>

                    <div className="filter-vertical-container">
                        <label className="field">
                            <span>Pencarian Data</span>
                            <input
                                className="search-input"
                                placeholder="Cari data..."
                                value={search}
                                onChange={(event) => {
                                    setSearch(event.target.value);
                                    setPage(1);
                                }}
                            />
                        </label>
                        <label className="field">
                            <span>Kategori Filter</span>
                            <select
                                value={filterColumn}
                                onChange={(event) => setFilterColumn(event.target.value)}
                            >
                                {columns.map((column) => (
                                    <option key={column.key} value={column.key}>
                                        Filter {column.label}
                                    </option>
                                ))}
                            </select>
                        </label>
                        <label className="field">
                            <span>Nilai Filter</span>
                            <input
                                className="search-input"
                                placeholder="Nilai filter..."
                                value={filterValue}
                                onChange={(event) => {
                                    setFilterValue(event.target.value);
                                    setPage(1);
                                }}
                            />
                        </label>
                    </div>

                    <div className="table-wrap">
                        {loading ? (
                            <div className="loading-state"><span className="spinner" />Memuat data...</div>
                        ) : visibleItems.length === 0 ? (
                            <div className="empty-state"><span>i</span><strong>Belum ada data.</strong><p>{readOnly ? "Data akan tampil di sini saat tersedia." : "Gunakan tombol tambah untuk membuat data pertama."}</p></div>
                        ) : (
                            <table>
                                <thead>
                                    <tr>
                                        {columns.map((column) => (
                                            <th key={column.key}>{column.label}</th>
                                        ))}
                                        {!readOnly && <th>Aksi</th>}
                                    </tr>
                                </thead>
                                <tbody>
                                    {pagedItems.map((item) => (
                                        <tr
                                            key={item.id}
                                            className={onOpen ? "clickable-tr" : ""}
                                            onClick={onOpen ? () => onOpen(item) : undefined}
                                        >
                                            {columns.map((column) => {
                                                const content = column.render ? column.render(item) : String(item[column.key] ?? "-");
                                                return <td key={column.key}>{content}</td>;
                                            })}
                                            {!readOnly && (
                                                <td className="action-cell" onClick={(e) => e.stopPropagation()}>
                                                    <button className="secondary-button" onClick={(e) => { e.stopPropagation(); handleEdit(item); }}>
                                                        Edit
                                                    </button>
                                                    {canDelete && (
                                                        <button className="danger-button" onClick={(e) => { e.stopPropagation(); setDeleteTarget(item.id); }}>
                                                            Hapus
                                                        </button>
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
                            <button className="secondary-button" disabled={page === 1} onClick={() => setPage((current) => current - 1)}>
                                Sebelumnya
                            </button>
                            <button className="secondary-button" disabled={page === totalPages} onClick={() => setPage((current) => current + 1)}>
                                Berikutnya
                            </button>
                        </div>
                    )}
                </section>
            </section>

            {modalOpen && (
                <div className="modal-backdrop">
                    <form className="modal-card" onSubmit={handleSubmit}>
                        <div className="panel-heading">
                            <h2>{editingId ? "Edit Data" : "Tambah Data"}</h2>
                            <button type="button" className="secondary-button" onClick={resetForm}>
                                Tutup
                            </button>
                        </div>

                        <div className="modal-form-grid">
                            {fields.map((field) => (
                                field.type === "hidden" ? (
                                    <input
                                        key={field.name}
                                        type="hidden"
                                        value={form[field.name] ?? ""}
                                        readOnly
                                    />
                                ) : (
                                    <label key={field.name} className="field">
                                        <span>{field.label}</span>
                                        {field.options ? (
                                        <select
                                            value={form[field.name] ?? ""}
                                            onChange={(event) => handleChange(field.name, event.target.value)}
                                            required={field.required}
                                        >
                                            <option value="">Pilih {field.label}</option>
                                            {field.options.map((option) => (
                                                <option key={option.value} value={option.value}>{option.label}</option>
                                            ))}
                                        </select>
                                        ) : field.type === "password" ? (
                                        <div className="password-field">
                                            <input
                                                type={form[`__show_${field.name}`] ? "text" : "password"}
                                                placeholder={field.label}
                                                value={form[field.name] ?? ""}
                                                onChange={(event) => handleChange(field.name, event.target.value)}
                                                required={field.required}
                                            />
                                            <button
                                                type="button"
                                                className="password-toggle"
                                                onClick={() => handleChange(`__show_${field.name}`, !form[`__show_${field.name}`])}
                                                aria-label={form[`__show_${field.name}`] ? "Hide Password" : "Show Password"}
                                            >
                                                👁
                                            </button>
                                        </div>
                                        ) : (
                                        <input
                                            type={field.type || "text"}
                                            placeholder={field.label}
                                            value={form[field.name] ?? ""}
                                            onChange={(event) => handleChange(field.name, event.target.value)}
                                            required={field.required}
                                        />
                                        )}
                                    </label>
                                )
                            ))}
                        </div>

                        <div className="modal-actions">
                            <button className="secondary-button" type="button" onClick={resetForm}>
                                Batal
                            </button>
                            <button className="primary-button" type="submit">
                                {editingId ? "Simpan Perubahan" : "Tambah"}
                            </button>
                        </div>
                    </form>
                </div>
            )}

            {deleteTarget && (
                <div className="modal-backdrop">
                    <div className="modal-card confirm-card">
                        <h2>Konfirmasi Hapus</h2>
                        <p>Data yang dihapus tidak dapat dikembalikan dari halaman ini.</p>
                        <div className="modal-actions">
                            <button className="secondary-button" onClick={() => setDeleteTarget(null)}>
                                Batal
                            </button>
                            <button className="danger-button" onClick={handleDelete}>
                                Hapus
                            </button>
                        </div>
                    </div>
                </div>
            )}
        </AppShell>
    );
}

export default ResourcePage;
