import { useEffect, useMemo, useRef, useState } from "react";
import { Document, Page, pdfjs } from "react-pdf";
import { api, openAuthenticatedPdf } from "../services/apiService";
import "react-pdf/dist/Page/AnnotationLayer.css";
import "react-pdf/dist/Page/TextLayer.css";

import pdfWorker from "pdfjs-dist/build/pdf.worker.min.mjs?url";

pdfjs.GlobalWorkerOptions.workerSrc = pdfWorker;

const MAX_COVER_SIZE = 25 * 1024 * 1024;

function CoverViewer({ perkara, berkas = [], canManageCover = false, onCoverUpdated }) {
    const covers = perkara?.covers || [];
    const primaryCover = covers[0] || (perkara?.cover_url ? { url: perkara.cover_url } : null);
    const fallbackBerkas = !primaryCover && Array.isArray(berkas)
        ? berkas.find((b) => b.file_path || b.url)
        : null;
    const selectedCover = primaryCover || (fallbackBerkas ? { url: fallbackBerkas.file_path || fallbackBerkas.url, file_name: fallbackBerkas.nama_berkas || fallbackBerkas.jenis_berkas } : null);

    const [objectUrl, setObjectUrl] = useState("");
    const [numPages, setNumPages] = useState(null);
    const [pageNumber, setPageNumber] = useState(1);
    const [loadingPdf, setLoadingPdf] = useState(false);
    const [error, setError] = useState("");
    const [uploading, setUploading] = useState(false);
    const inputRef = useRef(null);

    useEffect(() => {
        let active = true;
        let nextObjectUrl = "";

        if (!selectedCover?.url) {
            setObjectUrl("");
            setNumPages(null);
            setPageNumber(1);
            setLoadingPdf(false);
            setError("");
            return undefined;
        }

        setLoadingPdf(true);
        setError("");
        setNumPages(null);
        setPageNumber(1);

        api.get(selectedCover.url, { responseType: "blob" })
            .then((response) => {
                if (!active) return;
                nextObjectUrl = URL.createObjectURL(response.data);
                setObjectUrl(nextObjectUrl);
            })
            .catch((requestError) => {
                if (!active) return;
                setError("PDF tidak dapat ditampilkan.");
                setLoadingPdf(false);
                setObjectUrl("");
            });

        return () => {
            active = false;
            if (nextObjectUrl) {
                URL.revokeObjectURL(nextObjectUrl);
            }
        };
    }, [selectedCover?.url]);

    const containerRef = useRef(null);
    const [containerWidth, setContainerWidth] = useState(380);

    useEffect(() => {
        if (!containerRef.current) return undefined;
        const el = containerRef.current;
        const observer = new ResizeObserver((entries) => {
            if (entries[0]?.contentRect?.width > 0) {
                setContainerWidth(entries[0].contentRect.width);
            }
        });
        observer.observe(el);
        return () => observer.disconnect();
    }, []);

    const pageWidth = useMemo(() => {
        const calculated = containerWidth - 36;
        return Math.max(240, Math.min(calculated, 460));
    }, [containerWidth]);

    const onDocumentLoadSuccess = ({ numPages: total }) => {
        setNumPages(total);
        setPageNumber(1);
        setLoadingPdf(false);
        setError("");
    };

    const onDocumentLoadError = (err) => {
        console.error("Gagal memuat dokumen PDF:", err);
        setError("PDF tidak dapat ditampilkan.");
        setLoadingPdf(false);
    };

    const goPrevious = () => setPageNumber((current) => Math.max(1, current - 1));
    const goNext = () => setPageNumber((current) => Math.min(numPages || 1, current + 1));

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
                        <button className="secondary-button compact-button" type="button" disabled={uploading} onClick={triggerUpload}>
                            {selectedCover ? "Ganti Cover" : "Upload Cover"}
                        </button>
                    )}
                    {selectedCover && (
                        <button className="secondary-button compact-button" type="button" onClick={openCoverPdf}>
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

            {selectedCover ? (
                <>
                    <div className="pdf-viewer-frame" ref={containerRef}>
                        {objectUrl ? (
                            <Document
                                file={objectUrl}
                                onLoadSuccess={onDocumentLoadSuccess}
                                onLoadError={onDocumentLoadError}
                                loading={<div className="pdf-loading">Memuat dokumen...</div>}
                                error={<div className="pdf-error-state">PDF tidak dapat ditampilkan.</div>}
                            >
                                <Page
                                    pageNumber={pageNumber}
                                    width={pageWidth}
                                    renderAnnotationLayer={false}
                                    renderTextLayer={false}
                                />
                            </Document>
                        ) : error ? (
                            <div className="pdf-error-state">{error}</div>
                        ) : (
                            <div className="pdf-loading">Memuat dokumen...</div>
                        )}
                    </div>

                    <div className="pdf-toolbar cover-carousel-toolbar">
                        <button
                            className="secondary-button compact-button"
                            type="button"
                            disabled={pageNumber <= 1 || loadingPdf || !numPages}
                            onClick={goPrevious}
                        >
                            Previous
                        </button>
                        <span className="pdf-page-indicator">
                            {loadingPdf ? "Memuat..." : `${pageNumber} / ${numPages || 1}`}
                        </span>
                        <button
                            className="secondary-button compact-button"
                            type="button"
                            disabled={!numPages || pageNumber >= numPages || loadingPdf}
                            onClick={goNext}
                        >
                            Next
                        </button>
                    </div>
                </>
            ) : (
                <div className="cover-empty-state" ref={containerRef}>
                    <div className="cover-placeholder-icon" aria-hidden="true">📄</div>
                    <strong>Cover perkara belum tersedia.</strong>
                    <p>{canManageCover ? "Upload cover PDF untuk menampilkan preview di halaman ini." : "Cover PDF belum diunggah untuk perkara ini."}</p>
                    {error && <div className="notice error">{error}</div>}
                    {canManageCover && (
                        <button className="primary-button" type="button" disabled={uploading} onClick={triggerUpload}>Upload Cover Perkara</button>
                    )}
                </div>
            )}
        </section>
    );
}

export default CoverViewer;
