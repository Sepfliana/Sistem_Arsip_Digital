import { useCallback, useEffect, useMemo, useState } from "react";
import { Link, useNavigate, useParams } from "react-router-dom";
import AppShell from "./AppShell";
import { api, createData, fetchData, openAuthenticatedPdf, updateData } from "../services/apiService";
import { calculateSha256, formatBytes, shortenHash } from "../utils/hash";
import DetailPerkaraPage from "./DetailPerkaraPage";

const JENIS_BERKAS_OPTIONS = ["Pra Penuntutan", "Penuntutan", "Eksekusi"];
const STATUS_BERKAS_OPTIONS = ["AKTIF", "INAKTIF", "PERMANEN", "MUSNAH"];

const emptyForm = {
    nomor_perkara: "",
    jaksa_id: "",
    jenis_pidana_id: "",
    jenis_perkara_id: "",
    instansi_penyidik_id: "",
    melanggar_pasal: "",
    tanggal_mulai_perkara: "",
    tanggal_selesai_perkara: "",
    keterangan: "",
    lemari_id: "",
    rak_id: "",
    cover_files: [],
    existing_cover_file: "",
    terdakwa: [{ nama_terdakwa: "" }]
};

const emptyFilter = {
    nomor_perkara: "",
    nama_terdakwa: "",
    jaksa_id: "",
    jenis_pidana_id: "",
    jenis_perkara_id: "",
    instansi_penyidik_id: "",
    tahun: ""
};

const emptyBerkasForm = {
    jenis_berkas: "Pra Penuntutan",
    nomor_berkas: "",
    nama_berkas: "",
    file: null,
    masa_retensi_aktif: 1,
    masa_retensi_inaktif: 1,
    status_berkas: ""
};

const todayValue = () => new Date().toISOString().slice(0, 10);

const isRakAvailable = (item) => String(item.status || "").toLowerCase() !== "penuh" && Number(item.jumlah_perkara || 0) < Number(item.kapasitas || 0);

const locationStatusBadge = (status) => {
    if (status === "Kosong") return "success";
    if (status === "Tersedia") return "warning";
    if (status === "Penuh") return "danger";
    return "neutral";
};

const normalizeFormTerdakwa = (terdakwa = []) => {
    const normalized = terdakwa
        .map((item) => ({
            id: item.id,
            nama_terdakwa: item.nama_terdakwa || item.nama || ""
        }));

    return normalized.length > 0 ? normalized : [{ nama_terdakwa: "" }];
};

const getNamaTerdakwa = (perkara) => perkara?.terdakwa?.map((item) => item.nama_terdakwa).filter(Boolean).join(", ") || perkara?.nama_terdakwa || "-";

const makeOption = (item, labelKey) => ({
    value: String(item.id),
    label: item[labelKey] || "-"
});

const findOptionByLabel = (items, labelKey, label) => items.find((item) => String(item[labelKey] || "") === String(label || ""));

function SearchableDropdown({ label, value, options, onChange, placeholder = "Pilih data", disabled = false, loading = false, required = false }) {
    const [open, setOpen] = useState(false);
    const [query, setQuery] = useState("");
    const selectedOption = options.find((option) => String(option.value) === String(value));
    const visibleOptions = options.filter((option) => option.label.toLowerCase().includes(query.toLowerCase()));

    useEffect(() => {
        Promise.resolve().then(() => setQuery(selectedOption?.label || ""));
    }, [selectedOption]);

    return (
        <label className="field searchable-field">
            <span>{label}</span>
            <div className="searchable-select">
                <input
                    value={query}
                    disabled={disabled || loading}
                    required={required && !value}
                    placeholder={loading ? "Memuat data..." : placeholder}
                    onFocus={() => !disabled && !loading && setOpen(true)}
                    onChange={(event) => {
                        setQuery(event.target.value);
                        onChange("");
                        setOpen(true);
                    }}
                    onBlur={() => window.setTimeout(() => setOpen(false), 120)}
                />
                {open && !disabled && !loading && (
                    <div className="searchable-options">
                        {visibleOptions.length === 0 ? (
                            <div className="searchable-empty">Tidak ada data</div>
                        ) : visibleOptions.map((option) => (
                            <button
                                type="button"
                                key={option.value}
                                className="searchable-option"
                                onMouseDown={(event) => event.preventDefault()}
                                onClick={() => {
                                    onChange(option.value);
                                    setQuery(option.label);
                                    setOpen(false);
                                }}
                            >
                                {option.label}
                            </button>
                        ))}
                    </div>
                )}
            </div>
        </label>
    );
}

function PickerModal({ title, items, searchKeys, renderItem, onClose, onSelect }) {
    const [search, setSearch] = useState("");
    const visibleItems = items.filter((item) => {
        const term = search.toLowerCase();
        return !term || searchKeys.some((key) => String(item[key] || "").toLowerCase().includes(term));
    });

    return (
        <div className="modal-backdrop">
            <div className="modal-card">
                <div className="panel-heading">
                    <h2>{title}</h2>
                    <button className="secondary-button" type="button" onClick={onClose}>Tutup</button>
                </div>
                <input className="search-input" value={search} onChange={(event) => setSearch(event.target.value)} placeholder="Cari..." />
                <div className="picker-list">
                    {visibleItems.map((item) => (
                        <button className="picker-item" type="button" key={item.id} onClick={() => onSelect(item)}>
                            {renderItem(item)}
                        </button>
                    ))}
                </div>
            </div>
        </div>
    );
}

function BerkasPerkara() {
    const { perkaraId } = useParams();
    const navigate = useNavigate();
    const role = (localStorage.getItem("role") || "").toLowerCase();
    const isAdmin = role === "admin";
    const readOnly = role === "user";
    const [perkara, setPerkara] = useState(null);
    const [berkas, setBerkas] = useState([]);
    const [peminjaman, setPeminjaman] = useState([]);
    const [berkasModalOpen, setBerkasModalOpen] = useState(false);
    const [berkasForm, setBerkasForm] = useState(emptyBerkasForm);
    const [notice, setNotice] = useState("");
    const [error, setError] = useState("");
    const [hashingStatus, setHashingStatus] = useState("idle");
    const [generatedHash, setGeneratedHash] = useState("");
    const [verifyingBerkasId, setVerifyingBerkasId] = useState("");

    const loadData = useCallback(async () => {
        try {
            const [perkaraData, peminjamanData] = await Promise.all([
                fetchData(`/perkara/${perkaraId}`),
                fetchData("/peminjaman").catch(() => [])
            ]);
            const perkaraBerkas = perkaraData.berkas || [];
            const berkasIds = new Set(perkaraBerkas.map((item) => String(item.id)));

            setPerkara(perkaraData);
            setBerkas(perkaraBerkas);
            setPeminjaman((Array.isArray(peminjamanData) ? peminjamanData : []).filter((item) => berkasIds.has(String(item.berkas_id))));
            setError("");
        } catch (requestError) {
            setError(requestError.response?.data?.message || "Berkas perkara gagal dimuat");
        }
    }, [perkaraId]);

    useEffect(() => {
        Promise.resolve().then(loadData);
    }, [loadData]);

    const handleOpenPdf = async (item) => {
        try {
            await openAuthenticatedPdf(`/berkas/${item.id}/file`, item.nama_file || `berkas-${item.id}.pdf`);
            setError("");
        } catch (requestError) {
            setError(requestError.response?.data?.message || "File PDF gagal dibuka");
        }
    };

    const verifyBerkasIntegrity = async (item) => {
        if (!item?.id) return;

        setVerifyingBerkasId(String(item.id));
        try {
            const response = await api.post(`/berkas/${item.id}/verify`);
            const nextStatus = response.data?.integrity_status || response.data?.status || item.status_integritas;
            const verifiedAt = response.data?.verified_at || new Date().toISOString();
            const updateItem = (currentItem) => String(currentItem.id) === String(item.id)
                ? { ...currentItem, status_integritas: nextStatus, tanggal_verifikasi_terakhir: verifiedAt }
                : currentItem;

            setBerkas((current) => current.map(updateItem));
            setPerkara((current) => current ? {
                ...current,
                berkas: (current.berkas || []).map(updateItem),
                berkas_by_jenis: Object.fromEntries(Object.entries(current.berkas_by_jenis || {}).map(([jenis, berkasItem]) => [jenis, berkasItem ? updateItem(berkasItem) : berkasItem]))
            } : current);
            setNotice(response.data?.message || "Verifikasi integritas selesai.");
            setError("");
        } catch (requestError) {
            setError(requestError.response?.data?.message || "Verifikasi integritas gagal");
        } finally {
            setVerifyingBerkasId("");
        }
    };

    const openAddBerkas = () => {
        setBerkasForm(emptyBerkasForm);
        setBerkasModalOpen(true);
        setError("");
    };

    const updateBerkasForm = (name, value) => {
        setBerkasForm((current) => ({ ...current, [name]: value }));
    };

    const handleBerkasFile = async (file) => {
        updateBerkasForm("file", file || null);
        setGeneratedHash("");

        if (!file) {
            setHashingStatus("idle");
            return;
        }

        setHashingStatus("loading");

        try {
            const hash = await calculateSha256(file);
            setGeneratedHash(hash);
            setHashingStatus("success");
        } catch {
            setHashingStatus("error");
            setError("SHA-256 gagal dihitung pada file yang dipilih");
        }
    };

    const copyHash = async (value) => {
        if (!value) return;

        await navigator.clipboard.writeText(value);
        setNotice("Hash lengkap berhasil disalin.");
    };

    const submitBerkas = async (event) => {
        event.preventDefault();

        if (!berkasForm.file) {
            setError("File PDF wajib diunggah");
            return;
        }

        if (berkasForm.file.type !== "application/pdf" || !berkasForm.file.name.toLowerCase().endsWith(".pdf")) {
            setError("Upload hanya menerima file PDF");
            return;
        }

        try {
            const payload = new FormData();
            payload.append("perkara_id", perkaraId);
            payload.append("jenis_berkas", berkasForm.jenis_berkas);
            payload.append("nomor_berkas", berkasForm.nomor_berkas);
            payload.append("nama_berkas", berkasForm.nama_berkas);
            payload.append("masa_retensi_aktif", berkasForm.masa_retensi_aktif);
            payload.append("masa_retensi_inaktif", berkasForm.masa_retensi_inaktif);
            payload.append("tanggal_mulai_aktif", todayValue());
            if (berkasForm.status_berkas) {
                payload.append("status_berkas", berkasForm.status_berkas);
            }
            payload.append("file", berkasForm.file);

            await api.post("/berkas", payload);
            setNotice("Berkas berhasil ditambahkan.");
            setError("");
            setBerkasModalOpen(false);
            setBerkasForm(emptyBerkasForm);
            loadData();
        } catch (requestError) {
            setError(requestError.response?.data?.message || "Berkas gagal ditambahkan");
        }
    };

    return (
        <AppShell title="Berkas" subtitle={perkara ? `${perkara.nomor_perkara} - ${getNamaTerdakwa(perkara)}` : "Daftar berkas perkara"}>
            {notice && <div className="toast success">{notice}</div>}
            {error && <div className="toast error">{error}</div>}

            <DetailPerkaraPage perkara={perkara} berkas={berkas} peminjaman={peminjaman} readOnly={readOnly} canManageCover={!readOnly} canVerifyIntegrity={isAdmin} verifyingBerkasId={verifyingBerkasId} onAddBerkas={openAddBerkas} onBack={() => navigate(-1)} onOpenPdf={handleOpenPdf} onCoverUpdated={loadData} onVerifyIntegrity={verifyBerkasIntegrity} />

            {berkasModalOpen && (
                <div className="modal-backdrop">
                    <form className="modal-card" onSubmit={submitBerkas}>
                        <div className="panel-heading">
                            <h2>Tambah Berkas</h2>
                            <button className="secondary-button" type="button" onClick={() => setBerkasModalOpen(false)}>Tutup</button>
                        </div>
                        <div className="modal-form-grid">
                            <label className="field">
                                <span>Jenis Berkas</span>
                                <select value={berkasForm.jenis_berkas} onChange={(event) => updateBerkasForm("jenis_berkas", event.target.value)} required>
                                    {JENIS_BERKAS_OPTIONS.map((jenis) => <option key={jenis} value={jenis}>{jenis}</option>)}
                                </select>
                            </label>
                            <label className="field"><span>Nomor Berkas</span><input value={berkasForm.nomor_berkas} onChange={(event) => updateBerkasForm("nomor_berkas", event.target.value)} required /></label>
                            <label className="field"><span>Nama Berkas</span><input value={berkasForm.nama_berkas} onChange={(event) => updateBerkasForm("nama_berkas", event.target.value)} required /></label>
                            <label
                                className="field file-dropzone"
                                onDragOver={(event) => event.preventDefault()}
                                onDrop={(event) => {
                                    event.preventDefault();
                                    handleBerkasFile(event.dataTransfer.files?.[0] || null);
                                }}
                            >
                                <span>Pilih Berkas</span>
                                <input type="file" accept="application/pdf,.pdf" onChange={(event) => handleBerkasFile(event.target.files?.[0] || null)} required />
                                <small>Drag & drop atau browse file PDF.</small>
                                {berkasForm.file && (
                                    <div className="file-meta">
                                        <strong>{berkasForm.file.name}</strong>
                                        <span>{formatBytes(berkasForm.file.size)} - {berkasForm.file.type || "unknown"}</span>
                                    </div>
                                )}
                            </label>
                            <label className="field"><span>Masa Retensi Aktif</span><input type="number" min="1" value={berkasForm.masa_retensi_aktif} onChange={(event) => updateBerkasForm("masa_retensi_aktif", event.target.value)} required /></label>
                            <label className="field"><span>Masa Retensi Inaktif</span><input type="number" min="1" value={berkasForm.masa_retensi_inaktif} onChange={(event) => updateBerkasForm("masa_retensi_inaktif", event.target.value)} required /></label>
                            <label className="field">
                                <span>Status Berkas</span>
                                <select value={berkasForm.status_berkas} onChange={(event) => updateBerkasForm("status_berkas", event.target.value)}>
                                    <option value="">Ditentukan sistem</option>
                                    {STATUS_BERKAS_OPTIONS.map((status) => <option key={status} value={status}>{status}</option>)}
                                </select>
                            </label>
                        </div>
                        {isAdmin && berkasForm.file && (
                            <div className="hash-panel">
                                <div className="hash-icon" aria-hidden="true">#</div>
                                <div>
                                    <div className="hash-title"><strong>Sidik Jari Digital</strong><span className="badge neutral">SHA-256</span></div>
                                    {hashingStatus === "loading" && <p><span className="spinner" />Generating SHA-256...</p>}
                                    {hashingStatus === "success" && <p className="hash-success">✓ SHA-256 generated successfully</p>}
                                    {hashingStatus === "error" && <p className="hash-error">SHA-256 gagal dihitung</p>}
                                    {generatedHash && <code>{shortenHash(generatedHash)}</code>}
                                </div>
                                <button className="secondary-button" type="button" disabled={!generatedHash} onClick={() => copyHash(generatedHash)}>Copy Hash</button>
                            </div>
                        )}
                        <div className="modal-actions"><button className="primary-button" type="submit" disabled={hashingStatus === "loading"}>Upload PDF</button></div>
                    </form>
                </div>
            )}

        </AppShell>
    );
}

function Perkara() {
    const { lemariId, rakId, perkaraId } = useParams();
    const navigate = useNavigate();
    const role = (localStorage.getItem("role") || "").toLowerCase();
    const readOnly = role === "user";
    const [items, setItems] = useState([]);
    const [lemari, setLemari] = useState([]);
    const [rak, setRak] = useState([]);
    const [form, setForm] = useState(emptyForm);
    const [editingId, setEditingId] = useState(null);
    const [modalOpen, setModalOpen] = useState(false);
    const [picker, setPicker] = useState(null);
    const [filters, setFilters] = useState(emptyFilter);
    const [jaksaOptions, setJaksaOptions] = useState([]);
    const [jenisPidanaOptions, setJenisPidanaOptions] = useState([]);
    const [jenisPerkaraOptions, setJenisPerkaraOptions] = useState([]);
    const [filterJenisPerkaraOptions, setFilterJenisPerkaraOptions] = useState([]);
    const [instansiOptions, setInstansiOptions] = useState([]);
    const [masterLoading, setMasterLoading] = useState(false);
    const [jenisPerkaraLoading, setJenisPerkaraLoading] = useState(false);
    const [filterJenisPerkaraLoading, setFilterJenisPerkaraLoading] = useState(false);
    const [notice, setNotice] = useState("");
    const [error, setError] = useState("");

    const selectedLemari = lemari.find((item) => String(item.id) === String(form.lemari_id));
    const rakUntukLemari = useMemo(
        () => rak.filter((item) => (!form.lemari_id || String(item.lemari_id) === String(form.lemari_id)) && ((editingId && String(item.id) === String(form.rak_id)) || isRakAvailable(item))),
        [editingId, form.lemari_id, form.rak_id, rak]
    );
    const rakTersedia = useMemo(
        () => rak.filter((item) => (!lemariId || String(item.lemari_id) === String(lemariId)) && isRakAvailable(item)),
        [lemariId, rak]
    );
    const selectedRak = rak.find((item) => String(item.id) === String(form.rak_id));

    const loadData = useCallback(async () => {
        try {
            const params = Object.fromEntries(
                Object.entries(filters).filter(([, value]) => value !== "")
            );
            if (lemariId) params.lemari_id = lemariId;
            if (rakId) params.rak_id = rakId;

            const [perkaraData, lemariData, rakData] = await Promise.all([
                fetchData("/perkara", params),
                fetchData("/lemari"),
                fetchData("/rak")
            ]);

            setItems(Array.isArray(perkaraData) ? perkaraData : []);
            setLemari(Array.isArray(lemariData) ? lemariData : []);
            setRak(Array.isArray(rakData) ? rakData : []);
        } catch (requestError) {
            setError(requestError.response?.data?.message || "Data perkara gagal dimuat");
        }
    }, [filters, lemariId, rakId]);

    const loadMasterData = useCallback(async () => {
        setMasterLoading(true);

        try {
            const [jaksaData, jenisPidanaData, instansiData] = await Promise.all([
                fetchData("/jaksa"),
                fetchData("/jenis-pidana"),
                fetchData("/instansi-penyidik")
            ]);

            setJaksaOptions(Array.isArray(jaksaData) ? jaksaData : []);
            setJenisPidanaOptions(Array.isArray(jenisPidanaData) ? jenisPidanaData : []);
            setInstansiOptions(Array.isArray(instansiData) ? instansiData : []);
        } catch (requestError) {
            setError(requestError.response?.data?.message || "Master data gagal dimuat");
        } finally {
            setMasterLoading(false);
        }
    }, []);

    const loadJenisPerkaraOptions = useCallback(async (jenisPidanaId, target = "form") => {
        if (!jenisPidanaId) {
            if (target === "filter") {
                setFilterJenisPerkaraOptions([]);
            } else {
                setJenisPerkaraOptions([]);
            }
            return [];
        }

        if (target === "filter") {
            setFilterJenisPerkaraLoading(true);
        } else {
            setJenisPerkaraLoading(true);
        }

        try {
            const data = await fetchData(`/jenis-perkara/${jenisPidanaId}`);
            const normalizedData = Array.isArray(data) ? data : [];

            if (target === "filter") {
                setFilterJenisPerkaraOptions(normalizedData);
            } else {
                setJenisPerkaraOptions(normalizedData);
            }

            return normalizedData;
        } catch (requestError) {
            setError(requestError.response?.data?.message || "Jenis perkara gagal dimuat");
            return [];
        } finally {
            if (target === "filter") {
                setFilterJenisPerkaraLoading(false);
            } else {
                setJenisPerkaraLoading(false);
            }
        }
    }, []);

    useEffect(() => {
        Promise.resolve().then(loadData);
    }, [loadData]);

    useEffect(() => {
        Promise.resolve().then(loadMasterData);
    }, [loadMasterData]);

    useEffect(() => {
        Promise.resolve().then(() => loadJenisPerkaraOptions(filters.jenis_pidana_id, "filter"));
    }, [filters.jenis_pidana_id, loadJenisPerkaraOptions]);

    const pickDefaultLocation = () => {
        const fallbackRak = rak.find((item) => (!lemariId || String(item.lemari_id) === String(lemariId)) && isRakAvailable(item));
        return {
            lemari_id: lemariId || fallbackRak?.lemari_id || "",
            rak_id: rakId || fallbackRak?.id || ""
        };
    };

    const openAdd = () => {
        const defaultLocation = pickDefaultLocation();

        if (!defaultLocation.rak_id) {
            setError("Tidak ada rak yang tersedia.");
            return;
        }

        setEditingId(null);
        setJenisPerkaraOptions([]);
        setForm({ ...emptyForm, tanggal_mulai_perkara: todayValue(), ...defaultLocation, terdakwa: [{ nama_terdakwa: "" }] });
        setModalOpen(true);
    };

    const openEdit = async (item) => {
        try {
            const detail = await fetchData(`/perkara/${item.id}`);
            const jaksa = findOptionByLabel(jaksaOptions, "nama_jaksa", detail.nama_jaksa);
            const jenisPidana = findOptionByLabel(jenisPidanaOptions, "nama_jenis_pidana", detail.nama_jenis_pidana);
            const instansi = findOptionByLabel(instansiOptions, "nama_instansi", detail.nama_instansi);
            const jenisPidanaId = detail.jenis_pidana_id || jenisPidana?.id || "";
            const perkaraOptions = jenisPidanaId ? await loadJenisPerkaraOptions(jenisPidanaId, "form") : [];
            const jenisPerkara = findOptionByLabel(perkaraOptions, "nama_jenis_perkara", detail.nama_jenis_perkara);
            const lemariDetail = findOptionByLabel(lemari, "nama_lemari", detail.lemari || detail.nama_lemari);
            const rakDetail = findOptionByLabel(rak, "nama_rak", detail.rak || detail.nama_rak);

            setEditingId(item.id);
            setForm({
                nomor_perkara: detail.nomor_perkara || "",
                jaksa_id: detail.jaksa_id || jaksa?.id || "",
                jenis_pidana_id: jenisPidanaId,
                jenis_perkara_id: detail.jenis_perkara_id || jenisPerkara?.id || "",
                instansi_penyidik_id: detail.instansi_penyidik_id || instansi?.id || "",
                melanggar_pasal: detail.melanggar_pasal || "",
                tanggal_mulai_perkara: detail.tanggal_mulai?.slice(0, 10) || todayValue(),
                tanggal_selesai_perkara: detail.tanggal_selesai?.slice(0, 10) || "",
                keterangan: detail.keterangan || "",
                lemari_id: detail.lemari_id || lemariDetail?.id || item.lemari_id || "",
                rak_id: detail.rak_id || rakDetail?.id || item.rak_id || "",
                cover_files: [],
                existing_cover_file: detail.cover_file || detail.covers?.[0]?.file_name || "",
                terdakwa: normalizeFormTerdakwa(detail.terdakwa)
            });
            setModalOpen(true);
        } catch (requestError) {
            setError(requestError.response?.data?.message || "Detail perkara gagal dimuat");
        }
    };

    const updateForm = (name, value) => {
        setForm((current) => {
            if (name === "jenis_pidana_id") {
                return { ...current, jenis_pidana_id: value, jenis_perkara_id: "" };
            }

            return { ...current, [name]: value };
        });
    };

    useEffect(() => {
        Promise.resolve().then(() => loadJenisPerkaraOptions(form.jenis_pidana_id, "form"));
    }, [form.jenis_pidana_id, loadJenisPerkaraOptions]);

    const updateFilter = (name, value) => {
        setFilters((current) => {
            if (name === "jenis_pidana_id") {
                return { ...current, jenis_pidana_id: value, jenis_perkara_id: "" };
            }

            return { ...current, [name]: value };
        });
    };

    const resetFilters = () => {
        setFilters(emptyFilter);
    };

    const closePerkaraModal = () => {
        setModalOpen(false);
        setPicker(null);
    };

    const updateTerdakwa = (index, value) => {
        setForm((current) => ({
            ...current,
            terdakwa: current.terdakwa.map((item, itemIndex) => (
                itemIndex === index ? { ...item, nama_terdakwa: value } : item
            ))
        }));
    };

    const addTerdakwa = () => {
        setForm((current) => ({
            ...current,
            terdakwa: [...current.terdakwa, { nama_terdakwa: "" }]
        }));
    };

    const removeTerdakwa = (index) => {
        setForm((current) => {
            if (current.terdakwa.length === 1) {
                return current;
            }

            return {
                ...current,
                terdakwa: current.terdakwa.filter((_, itemIndex) => itemIndex !== index)
            };
        });
    };

    const submitForm = async (event) => {
        event.preventDefault();
        const terdakwaPayload = form.terdakwa
            .map((item) => ({
                id: item.id,
                nama_terdakwa: item.nama_terdakwa.trim()
            }))
            .filter((item) => item.nama_terdakwa);

        if (terdakwaPayload.length === 0) {
            setError("Minimal satu terdakwa wajib diisi");
            return;
        }

        if (!editingId && selectedRak && !isRakAvailable(selectedRak)) {
            setError("Rak penuh dan tidak dapat dipilih");
            return;
        }

        const coverFiles = Array.isArray(form.cover_files) ? form.cover_files : [];
        const invalidCover = coverFiles.find((file) => file.type !== "application/pdf" || !file.name.toLowerCase().endsWith(".pdf"));
        if (invalidCover) {
            setError("Cover Perkara hanya menerima file PDF");
            return;
        }

        try {
            const payload = new FormData();
            payload.append("nomor_perkara", form.nomor_perkara);
            payload.append("nama_terdakwa", terdakwaPayload.map((item) => item.nama_terdakwa).join(", "));
            payload.append("jaksa_id", form.jaksa_id);
            payload.append("jenis_pidana_id", form.jenis_pidana_id);
            payload.append("jenis_perkara_id", form.jenis_perkara_id);
            payload.append("instansi_penyidik_id", form.instansi_penyidik_id);
            payload.append("melanggar_pasal", form.melanggar_pasal);
            payload.append("tanggal_mulai", form.tanggal_mulai_perkara);
            payload.append("tanggal_selesai", form.tanggal_selesai_perkara);
            payload.append("keterangan", form.keterangan);
            payload.append("lemari_id", form.lemari_id || "");
            payload.append("rak_id", form.rak_id || "");
            payload.append("terdakwa", JSON.stringify(terdakwaPayload));
            coverFiles.forEach((file) => payload.append("cover", file));

            if (editingId) {
                await updateData("/perkara", editingId, payload);
            } else {
                await createData("/perkara", payload);
            }

            setNotice(editingId ? "Perkara berhasil diperbarui." : "Perkara berhasil ditambahkan.");
            setError("");
            setModalOpen(false);
            loadData();
        } catch (requestError) {
            setError(requestError.response?.data?.message || "Perkara gagal disimpan");
        }
    };

    if (perkaraId) {
        return <BerkasPerkara />;
    }

    return (
        <AppShell title="Perkara" subtitle={rakId ? "Perkara pada rak terpilih" : "Daftar seluruh perkara"}>
            {notice && <div className="toast success">{notice}</div>}
            {error && <div className="toast error">{error}</div>}
            <section className="panel">
                <div className="panel-heading">
                    <h2>Daftar Perkara</h2>
                    <div className="action-cell">
                        {rakId && <button className="secondary-button" onClick={() => navigate(`/lemari/${lemariId}/rak`)}>Kembali</button>}
                        {!readOnly && <button className="primary-button" disabled={rakTersedia.length === 0} onClick={openAdd}>Tambah Perkara</button>}
                    </div>
                </div>
                <div className="perkara-filter-grid">
                    <label className="field"><span>Nomor Perkara</span><input value={filters.nomor_perkara} onChange={(event) => updateFilter("nomor_perkara", event.target.value)} placeholder="Nomor perkara" /></label>
                    <label className="field"><span>Nama Terdakwa</span><input value={filters.nama_terdakwa} onChange={(event) => updateFilter("nama_terdakwa", event.target.value)} placeholder="Nama terdakwa" /></label>
                    <SearchableDropdown label="Jaksa" value={filters.jaksa_id} options={jaksaOptions.map((item) => makeOption(item, "nama_jaksa"))} onChange={(value) => updateFilter("jaksa_id", value)} loading={masterLoading} placeholder="Semua jaksa" />
                    <SearchableDropdown label="Jenis Pidana" value={filters.jenis_pidana_id} options={jenisPidanaOptions.map((item) => makeOption(item, "nama_jenis_pidana"))} onChange={(value) => updateFilter("jenis_pidana_id", value)} loading={masterLoading} placeholder="Semua jenis pidana" />
                    <SearchableDropdown label="Jenis Perkara" value={filters.jenis_perkara_id} options={filterJenisPerkaraOptions.map((item) => makeOption(item, "nama_jenis_perkara"))} onChange={(value) => updateFilter("jenis_perkara_id", value)} disabled={!filters.jenis_pidana_id} loading={filterJenisPerkaraLoading} placeholder="Pilih jenis pidana dulu" />
                    <SearchableDropdown label="Instansi Penyidik" value={filters.instansi_penyidik_id} options={instansiOptions.map((item) => makeOption(item, "nama_instansi"))} onChange={(value) => updateFilter("instansi_penyidik_id", value)} loading={masterLoading} placeholder="Semua instansi" />
                    <label className="field field-tahun"><span>Tahun</span><input value={filters.tahun} onChange={(event) => updateFilter("tahun", event.target.value)} placeholder="2026" inputMode="numeric" /></label>
                    <div className="filter-actions-row">
                        <button className="secondary-button" type="button" onClick={resetFilters}>Reset Filter</button>
                        <span className="table-count">{items.length} data</span>
                    </div>
                </div>

                <div className="table-wrap">
                    {items.length === 0 ? (
                        <div className="empty-state"><span>i</span><strong>{rakId ? "Belum ada perkara pada rak ini." : "Belum ada perkara."}</strong><p>Perkara akan tampil di sini.</p></div>
                    ) : (
                        <table>
                            <thead>
                                <tr>
                                    <th>Nomor Perkara</th>
                                    <th>Nama Terdakwa</th>
                                    <th>Tahun</th>
                                    <th>Jaksa</th>
                                    <th>Jenis Pidana</th>
                                    <th>Jenis Perkara</th>
                                    <th>Instansi Penyidik</th>
                                    {!readOnly && <th>Aksi</th>}
                                </tr>
                            </thead>
                            <tbody>
                                {items.map((item) => (
                                    <tr
                                        key={item.id}
                                        className="clickable-tr"
                                        onClick={() => navigate(`/perkara/${item.id}/berkas`)}
                                    >
                                        <td>
                                            <span className="clickable-data">
                                                {item.nomor_perkara}
                                            </span>
                                        </td>
                                        <td>
                                            <span className="clickable-data">
                                                {getNamaTerdakwa(item)}
                                            </span>
                                        </td>
                                        <td>{item.tanggal_mulai?.slice(0, 4) || "-"}</td>
                                        <td>{item.nama_jaksa || "-"}</td>
                                        <td>{item.nama_jenis_pidana || "-"}</td>
                                        <td>{item.nama_jenis_perkara || "-"}</td>
                                        <td>{item.nama_instansi || "-"}</td>
                                        {!readOnly && (
                                            <td className="action-cell" onClick={(e) => e.stopPropagation()}>
                                                <button className="secondary-button" onClick={(e) => { e.stopPropagation(); openEdit(item); }}>Edit</button>
                                            </td>
                                        )}
                                    </tr>
                                ))}
                            </tbody>
                        </table>
                    )}
                </div>
            </section>

            {modalOpen && (
                <div className="modal-backdrop" onClick={closePerkaraModal}>
                    <form className="modal-card" onSubmit={submitForm} onClick={(event) => event.stopPropagation()}>
                        <div className="panel-heading">
                            <h2>{editingId ? "Edit Perkara" : "Tambah Perkara"}</h2>
                            <button className="secondary-button" type="button" onClick={closePerkaraModal}>Tutup</button>
                        </div>
                        <div className="modal-form-grid">
                            <label className="field"><span>Nomor Perkara</span><input value={form.nomor_perkara} onChange={(event) => updateForm("nomor_perkara", event.target.value)} required /></label>
                            <SearchableDropdown label="Jaksa" value={form.jaksa_id} options={jaksaOptions.map((item) => makeOption(item, "nama_jaksa"))} onChange={(value) => updateForm("jaksa_id", value)} loading={masterLoading} required />
                            <SearchableDropdown label="Jenis Pidana" value={form.jenis_pidana_id} options={jenisPidanaOptions.map((item) => makeOption(item, "nama_jenis_pidana"))} onChange={(value) => updateForm("jenis_pidana_id", value)} loading={masterLoading} required />
                            <SearchableDropdown label="Jenis Perkara" value={form.jenis_perkara_id} options={jenisPerkaraOptions.map((item) => makeOption(item, "nama_jenis_perkara"))} onChange={(value) => updateForm("jenis_perkara_id", value)} disabled={!form.jenis_pidana_id} loading={jenisPerkaraLoading} placeholder="Pilih jenis pidana dulu" required />
                            <SearchableDropdown label="Instansi Penyidik" value={form.instansi_penyidik_id} options={instansiOptions.map((item) => makeOption(item, "nama_instansi"))} onChange={(value) => updateForm("instansi_penyidik_id", value)} loading={masterLoading} required />
                            <label className="field"><span>Melanggar Pasal</span><input value={form.melanggar_pasal} onChange={(event) => updateForm("melanggar_pasal", event.target.value)} required /></label>
                            <label className="field"><span>Tanggal Mulai</span><input type="date" value={form.tanggal_mulai_perkara} onChange={(event) => updateForm("tanggal_mulai_perkara", event.target.value)} required /></label>
                            <label className="field"><span>Tanggal Selesai</span><input type="date" value={form.tanggal_selesai_perkara} onChange={(event) => updateForm("tanggal_selesai_perkara", event.target.value)} /></label>
                            <label className="field"><span>Keterangan</span><input value={form.keterangan} onChange={(event) => updateForm("keterangan", event.target.value)} /></label>
                            <label className="field file-dropzone">
                                <span>Cover Perkara (PDF)</span>
                                <input type="file" accept="application/pdf,.pdf" multiple onChange={(event) => updateForm("cover_files", Array.from(event.target.files || []))} />
                                <small>{form.existing_cover_file ? `Cover saat ini: ${form.existing_cover_file.split(/[\\/]/).pop()}` : "Upload file PDF sebagai cover perkara."}</small>
                                {form.cover_files?.length > 0 && (
                                    <div className="file-meta">
                                        <strong>{form.cover_files.length} cover dipilih</strong>
                                        <span>{form.cover_files.map((file) => `${file.name} (${formatBytes(file.size)})`).join(", ")}</span>
                                    </div>
                                )}
                            </label>
                            <div className="field location-field"><span>Lemari</span><strong>{selectedLemari?.nama_lemari || "Otomatis"}</strong><button className="secondary-button" type="button" onClick={() => setPicker("lemari")}>Ubah</button></div>
                            <div className="field location-field"><span>Rak</span><strong>{selectedRak?.nama_rak || "Otomatis"}</strong>{selectedRak && <small>{selectedRak.jumlah_perkara || 0} / {selectedRak.kapasitas} perkara</small>}<button className="secondary-button" type="button" onClick={() => setPicker("rak")}>Ubah</button></div>
                        </div>

                        <section className="form-section">
                            <div className="panel-heading compact-heading">
                                <h2>Data Terdakwa</h2>
                                <button className="secondary-button" type="button" onClick={addTerdakwa}>+ Tambah Terdakwa</button>
                            </div>
                            <div className="terdakwa-list">
                                {form.terdakwa.map((item, index) => (
                                    <div className="terdakwa-row" key={item.id || `new-${index}`}>
                                        <label className="field"><span>Nama Terdakwa</span><input value={item.nama_terdakwa} onChange={(event) => updateTerdakwa(index, event.target.value)} required /></label>
                                        <button className="secondary-button" type="button" disabled={form.terdakwa.length === 1} onClick={() => removeTerdakwa(index)}>Hapus</button>
                                    </div>
                                ))}
                            </div>
                        </section>

                        <div className="modal-actions">
                            <button className="secondary-button" type="button" onClick={closePerkaraModal}>Batal</button>
                            <button className="primary-button" type="submit">Simpan</button>
                        </div>
                    </form>
                </div>
            )}

            {picker === "lemari" && (
                <PickerModal
                    title="Pilih Lemari"
                    items={lemari}
                    searchKeys={["nama_lemari", "lokasi"]}
                    renderItem={(item) => <><strong>{item.nama_lemari}</strong><span>{item.lokasi} - {item.status || "Kosong"}</span></>}
                    onClose={() => setPicker(null)}
                    onSelect={(item) => {
                        const nextRak = rak.find((rakItem) => String(rakItem.lemari_id) === String(item.id) && isRakAvailable(rakItem));
                        setForm((current) => ({ ...current, lemari_id: item.id, rak_id: nextRak?.id || "" }));
                        setPicker(null);
                    }}
                />
            )}

            {picker === "rak" && (
                <PickerModal
                    title="Pilih Rak"
                    items={rakUntukLemari}
                    searchKeys={["nama_rak", "nama_lemari"]}
                    renderItem={(item) => <><strong>{item.nama_rak}</strong><span>{item.nama_lemari} - {item.jumlah_perkara || 0} / {item.kapasitas} perkara</span><span className={`badge ${locationStatusBadge(item.status)}`}>{item.status || "Kosong"}</span></>}
                    onClose={() => setPicker(null)}
                    onSelect={(item) => {
                        setForm((current) => ({ ...current, lemari_id: item.lemari_id, rak_id: item.id }));
                        setPicker(null);
                    }}
                />
            )}
        </AppShell>
    );
}

export default Perkara;



