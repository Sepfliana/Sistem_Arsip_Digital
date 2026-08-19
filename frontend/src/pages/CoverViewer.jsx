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

function CoverViewer({ perkara, berkas = [], canManageCover = false, onCoverUpdated }) {
    const covers = perkara?.covers || [];
    const primaryCover = covers[0] || (perkara?.cover_url ? { url: perkara.cover_url } : null);
    const fallbackBerkas = !primaryCover && Array.isArray(berkas)
        ? berkas.find((b) => b.file_path || b.url)
        : null;
    const selectedCover = primaryCover || (fallbackBerkas ? { url: fallbackBerkas.file_path || fallbackBerkas.url, file_name: fallbackBerkas.nama_berkas || fallbackBerkas.jenis_berkas } : null);

    const [pdfBlob, setPdfBlob] = useState(null);
    const [numPages, setNumPages] = useState(null);
    const [pageNumber, setPageNumber] = useState(1);
    const [loadingPdf, setLoadingPdf] = useState(false);
    const [error, setError] = useState("");
    const [uploading, setUploading] = useState(false);
    const inputRef = useRef(null);

    const targetUrl = selectedCover?.url || "";

    useEffect(() => {
        let isCancelled = false;

        if (!targetUrl) {
            setPdfBlob(null);
            setNumPages(null);
            setPageNumber(1);
            setLoadingPdf(false);
            setError("");
            return undefined;
        }

        setLoadingPdf(true);
        setError("");

        api.get(targetUrl, { responseType: "blob" })
            .then(async (response) => {
                if (isCancelled) return;

                const blob = response.data;
                if (!(blob instanceof Blob)) {
                    console.error("[CoverViewer] Response data is not a Blob:", blob);
                    setError("PDF tidak dapat ditampilkan.");
                    setLoadingPdf(false);
                    setPdfBlob(null);
                    return;
                }

                try {
                    const headerBuffer = await blob.slice(0, 8).arrayBuffer();
                    const headerStr = new TextDecoder().decode(headerBuffer);
                    if (!headerStr.startsWith("%PDF-")) {
                        console.error("[CoverViewer] Invalid PDF signature:", headerStr);
                        setError("File bukan dokumen PDF yang valid.");
                        setLoadingPdf(false);
                        setPdfBlob(null);
                        return;
                    }
                } catch (sigErr) {
                    console.warn("[CoverViewer] Could not verify PDF magic header:", sigErr);
                }

                setPdfBlob(blob);
                setPageNumber(1);
                setNumPages(null);
                setError("");
                setLoadingPdf(false);
            })
            .catch((requestError) => {
                if (isCancelled) return;
                console.error("[CoverViewer] HTTP GET Blob error:", requestError);
                setError(requestError.response?.data?.message || "PDF tidak dapat ditampilkan.");
                setLoadingPdf(false);
                setPdfBlob(null);
            });

        return () => {
            isCancelled = true;
        };
    }, [targetUrl]);

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
        const calculated = containerWidth - 32;
        return Math.max(240, Math.min(calculated, 540));
    }, [containerWidth]);

    const onDocumentLoadSuccess = (pdf) => {
        const total = pdf?.numPages || 1;
        console.log("[CoverViewer] PDF LOAD SUCCESS", { numPages: total });
        setNumPages(total);
        setPageNumber(1);
        setLoadingPdf(false);
        setError("");
    };

    const onDocumentLoadError = (err) => {
        console.error("[CoverViewer] PDF LOAD ERROR:", {
            name: err?.name,
            message: err?.message,
            stack: err?.stack,
            fullError: err
        });
        setError(`PDF tidak dapat ditampilkan. (${err?.message || "Error PDF.js"})`);
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
            {(canManageCover || selectedCover) && (
                <div className="pdf-viewer-header">
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
            )}

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
                <div className="pdf-viewer-container">
                    <div className="pdf-viewer-frame" ref={containerRef}>
                        {pdfBlob ? (
                            <Document
                                file={pdfBlob}
                                onLoadSuccess={onDocumentLoadSuccess}
                                onLoadError={onDocumentLoadError}
                                loading={<div className="pdf-loading">Memuat dokumen...</div>}
                                error={<div className="pdf-error-state">PDF tidak dapat ditampilkan.</div>}
                            >
                                <Page
                                    pageNumber={pageNumber}
                                    width={pageWidth}
                                    renderAnnotationLayer
                                    renderTextLayer
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
                            className="secondary-button compact-button pdf-nav-btn"
                            type="button"
                            disabled={pageNumber <= 1 || loadingPdf || !numPages}
                            onClick={goPrevious}
                        >
                            ‹ Previous
                        </button>
                        <span className="pdf-page-indicator">
                            {loadingPdf ? "Memuat..." : `${pageNumber} / ${numPages || 1}`}
                        </span>
                        <button
                            className="secondary-button compact-button pdf-nav-btn"
                            type="button"
                            disabled={!numPages || pageNumber >= numPages || loadingPdf}
                            onClick={goNext}
                        >
                            Next ›
                        </button>
                    </div>
                </div>
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
