import { useEffect, useMemo, useRef, useState } from "react";
import { Document, Page, pdfjs } from "react-pdf";
import { api, openAuthenticatedPdf } from "../services/apiService";
import "react-pdf/dist/Page/AnnotationLayer.css";
import "react-pdf/dist/Page/TextLayer.css";

pdfjs.GlobalWorkerOptions.workerSrc = new URL(
    "pdfjs-dist/build/pdf.worker.min.mjs",
    import.meta.url
).toString();

const MAX_COVER_SIZE = 25 * 1024 * 1024;

function CoverViewer({ perkara, canManageCover = false, onCoverUpdated }) {
    const covers = perkara?.covers || [];
    const [coverIndex, setCoverIndex] = useState(0);
    const [numPages, setNumPages] = useState(0);
    const [pageNumber, setPageNumber] = useState(1);
    const [objectUrl, setObjectUrl] = useState("");
    const [error, setError] = useState("");
    const [uploading, setUploading] = useState(false);
    const inputRef = useRef(null);
    const selectedCover = covers[coverIndex] || null;

    useEffect(() => {
        // eslint-disable-next-line react-hooks/set-state-in-effect
        setCoverIndex(0);
    }, [perkara?.id, covers.length]);

    useEffect(() => {
        let active = true;
        let nextObjectUrl = "";

        if (!selectedCover?.url) {
            return undefined;
        }

        api.get(selectedCover.url, { responseType: "blob" })
            .then((response) => {
                if (!active) return;
                nextObjectUrl = URL.createObjectURL(response.data);
                setObjectUrl(nextObjectUrl);
                setNumPages(0);
                setPageNumber(1);
                setError("");
            })
            .catch((requestError) => {
                if (!active) return;
                setError(requestError.response?.data?.message || "Cover PDF gagal dimuat");
                setObjectUrl("");
                setNumPages(0);
                setPageNumber(1);
            });

        return () => {
            active = false;
            if (nextObjectUrl) {
                URL.revokeObjectURL(nextObjectUrl);
            }
        };
    }, [selectedCover?.url]);

    const pageWidth = useMemo(() => 560, []);

    const goPrevious = () => setCoverIndex((current) => Math.max(0, current - 1));
    const goNext = () => setCoverIndex((current) => Math.min(covers.length - 1, current + 1));

    const triggerUpload = () => {
        inputRef.current?.click();
    };

    const openCoverPdf = async () => {
        if (!selectedCover?.url) return;
        await openAuthenticatedPdf(selectedCover.url, selectedCover.file_name || `cover-perkara-${perkara?.id || ""}.pdf`);
    };

    const uploadCover = async (file) => {
        if (!file) return;

        if (file.type !== "application/pdf" || !file.name.toLowerCase().endsWith(".pdf")) {
            setError("Cover Perkara hanya menerima file PDF");
            return;
        }

        if (file.size > MAX_COVER_SIZE) {
            setError("Ukuran file cover terlalu besar. Maksimal 25 MB.");
            return;
        }

        setUploading(true);
        setError("");

        try {
            const payload = new FormData();
            payload.append("nomor_perkara", perkara.nomor_perkara || "");
            payload.append("nama_terdakwa", perkara.nama_terdakwa || "");
            payload.append("jaksa_id", perkara.jaksa_id || "");
            payload.append("jenis_pidana_id", perkara.jenis_pidana_id || "");
            payload.append("jenis_perkara_id", perkara.jenis_perkara_id || "");
            payload.append("instansi_penyidik_id", perkara.instansi_penyidik_id || "");
            payload.append("melanggar_pasal", perkara.melanggar_pasal || "");
            payload.append("tanggal_mulai", perkara.tanggal_mulai?.slice(0, 10) || "");
            payload.append("tanggal_selesai", perkara.tanggal_selesai?.slice(0, 10) || "");
            payload.append("lemari_id", perkara.lemari_id || "");
            payload.append("rak_id", perkara.rak_id || "");
            payload.append("keterangan", perkara.keterangan || "");
            payload.append("replace_cover", "true");
            payload.append("cover", file);
            if (Array.isArray(perkara.terdakwa)) {
                payload.append("terdakwa", JSON.stringify(perkara.terdakwa));
            }

            await api.put(`/perkara/${perkara.id}`, payload);
            await onCoverUpdated?.();
        } catch (requestError) {
            setError(requestError.response?.data?.message || "Upload cover gagal");
        } finally {
            setUploading(false);
            if (inputRef.current) {
                inputRef.current.value = "";
            }
        }
    };

    return (
        <section className="panel cover-panel">
            <div className="panel-heading">
                <h2>Cover Perkara</h2>
                <div className="action-cell">
                    {canManageCover && (
                        <button className="secondary-button" type="button" disabled={uploading} onClick={triggerUpload}>
                            {selectedCover ? "Ganti Cover" : "Upload Cover Perkara"}
                        </button>
                    )}
                    {selectedCover && (
                        <button className="secondary-button" type="button" onClick={openCoverPdf}>
                            Buka PDF
                        </button>
                    )}
                </div>
            </div>

            {canManageCover && (
                <input
                    ref={inputRef}
                    type="file"
                    accept="application/pdf,.pdf"
                    hidden
                    onChange={(event) => uploadCover(event.target.files?.[0] || null)}
                />
            )}

            {error && <div className="notice error">{error}</div>}

            {selectedCover ? (
                <>
                    <div className="pdf-viewer-frame">
                        {objectUrl && (
                            <Document
                                file={objectUrl}
                                loading={<div className="pdf-loading">Memuat cover...</div>}
                                error={<div className="pdf-loading">Cover PDF tidak dapat ditampilkan.</div>}
                                onLoadSuccess={({ numPages: detectedPages }) => {
                                    setNumPages(detectedPages);
                                    setPageNumber(1);
                                }}
                            >
                                <Page pageNumber={pageNumber} width={pageWidth} renderAnnotationLayer renderTextLayer />
                            </Document>
                        )}
                    </div>

                    {numPages > 1 && (
                        <div className="pdf-toolbar">
                            <button className="secondary-button" type="button" disabled={pageNumber <= 1} onClick={() => setPageNumber((current) => Math.max(1, current - 1))}>Previous</button>
                            <span className="pdf-page-indicator">Halaman {pageNumber} / {numPages}</span>
                            <button className="secondary-button" type="button" disabled={pageNumber >= numPages} onClick={() => setPageNumber((current) => Math.min(numPages, current + 1))}>Next</button>
                        </div>
                    )}

                    <div className="panel-heading compact-heading"><h2>Carousel Cover</h2></div>
                    <div className="pdf-toolbar">
                        <button className="secondary-button" type="button" disabled={coverIndex === 0} onClick={goPrevious}>Previous</button>
                        <span className="pdf-page-indicator">{covers.length ? `${coverIndex + 1} / ${covers.length}` : "0 / 0"}</span>
                        <button className="secondary-button" type="button" disabled={coverIndex >= covers.length - 1} onClick={goNext}>Next</button>
                    </div>
                </>
            ) : (
                <div className="cover-empty-state">
                    <div className="cover-placeholder-icon" aria-hidden="true">📄</div>
                    <strong>Cover perkara belum tersedia.</strong>
                    <p>{canManageCover ? "Upload cover PDF untuk menampilkan preview di halaman ini." : "Cover PDF belum diunggah untuk perkara ini."}</p>
                    {canManageCover && (
                        <button className="primary-button" type="button" disabled={uploading} onClick={triggerUpload}>Upload Cover Perkara</button>
                    )}
                </div>
            )}
        </section>
    );
}

export default CoverViewer;

