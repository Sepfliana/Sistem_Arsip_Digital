/* eslint-disable react-refresh/only-export-components */
import { useEffect, useRef, useState } from "react";
import { Document, Page, pdfjs } from "react-pdf";
import { api } from "../services/apiService";
import "react-pdf/dist/Page/AnnotationLayer.css";
import "react-pdf/dist/Page/TextLayer.css";

pdfjs.GlobalWorkerOptions.workerSrc = new URL(
    "pdfjs-dist/build/pdf.worker.min.mjs",
    import.meta.url
).toString();

function formatDate(value) {
    if (!value) return "-";
    const date = new Date(value);
    return Number.isNaN(date.getTime()) ? String(value).slice(0, 10) : date.toLocaleDateString("id-ID");
}

export const normalizeIntegrityStatus = (status) => {
    const normalized = String(status || "BELUM_DIVERIFIKASI").toUpperCase();
    if (normalized === "VALID") return "VALID";
    if (["HASH TIDAK SESUAI", "INVALID", "TIDAK_VALID", "TIDAK VALID"].includes(normalized)) return "TIDAK_VALID";
    return "BELUM_DIVERIFIKASI";
};

export const integrityBadge = (status) => {
    const normalized = normalizeIntegrityStatus(status);
    if (normalized === "VALID") return { label: "Valid", className: "success" };
    if (normalized === "TIDAK_VALID") return { label: "Tidak Valid", className: "danger" };
    return { label: "Belum Diverifikasi", className: "warning" };
};

function PdfViewer({ berkas }) {
    const viewerRef = useRef(null);
    const [objectUrl, setObjectUrl] = useState("");
    const [pageNumber, setPageNumber] = useState(1);
    const [numPages, setNumPages] = useState(0);
    const [error, setError] = useState("");
    const [pageWidth, setPageWidth] = useState(320);

    useEffect(() => {
        const viewer = viewerRef.current;
        if (!viewer) return undefined;

        const updatePageWidth = () => {
            const availableWidth = Math.floor(viewer.clientWidth - 32);
            setPageWidth(Math.max(240, Math.min(760, availableWidth)));
        };

        updatePageWidth();
        const observer = new ResizeObserver(updatePageWidth);
        observer.observe(viewer);
        return () => observer.disconnect();
    }, [objectUrl]);

    useEffect(() => {
        let active = true;
        let nextObjectUrl = "";

        api.get(`/berkas/${berkas.id}/file`, { responseType: "blob" })
            .then((response) => {
                if (!active) return;
                nextObjectUrl = URL.createObjectURL(response.data);
                setObjectUrl(nextObjectUrl);
                setPageNumber(1);
                setNumPages(0);
                setError("");
            })
            .catch((requestError) => {
                if (active) {
                    setError(requestError.response?.data?.message || "PDF tidak dapat dimuat.");
                    setObjectUrl("");
                    setPageNumber(1);
                    setNumPages(0);
                }
            });

        return () => {
            active = false;
            if (nextObjectUrl) URL.revokeObjectURL(nextObjectUrl);
        };
    }, [berkas.id]);

    return (
        <section className="berkas-pdf-viewer" aria-label={`Pratinjau PDF ${berkas.nama_berkas || "berkas"}`}>
            {error ? (
                <div className="pdf-loading">{error}</div>
            ) : objectUrl ? (
                <>
                    <div className="pdf-viewer-frame berkas-document-frame" ref={viewerRef}>
                        <Document
                            file={objectUrl}
                            loading={<div className="pdf-loading">Memuat dokumen...</div>}
                            error={<div className="pdf-loading">PDF tidak dapat ditampilkan.</div>}
                            onLoadSuccess={({ numPages: detectedPages }) => {
                                setNumPages(detectedPages);
                                setPageNumber(1);
                            }}
                        >
                            <Page pageNumber={pageNumber} width={pageWidth} renderAnnotationLayer renderTextLayer />
                        </Document>
                    </div>
                    {numPages > 1 && (
                        <div className="pdf-toolbar">
                            <button className="secondary-button" type="button" disabled={pageNumber <= 1} onClick={() => setPageNumber((current) => Math.max(1, current - 1))}>Sebelumnya</button>
                            <span className="pdf-page-indicator">Halaman {pageNumber} / {numPages}</span>
                            <button className="secondary-button" type="button" disabled={pageNumber >= numPages} onClick={() => setPageNumber((current) => Math.min(numPages, current + 1))}>Berikutnya</button>
                        </div>
                    )}
                </>
            ) : (
                <div className="pdf-loading">Memuat dokumen...</div>
            )}
        </section>
    );
}

function BerkasCard({ title, berkas, readOnly = false, canVerify = false, verifying = false, onOpenPdf, onVerifyIntegrity }) {
    if (!berkas) {
        return (
            <article className="berkas-stage-card berkas-empty-card">
                <h2>{title}</h2>
                <div className="berkas-empty-state">
                    <span aria-hidden="true">⌁</span>
                    <strong>Belum ada berkas {title.replace(/\b\w/g, (letter) => letter.toUpperCase())}.</strong>
                    <p>{readOnly ? "Berkas akan tampil di sini setelah diunggah oleh petugas berwenang." : "Silakan tambahkan berkas melalui menu Tambah Berkas."}</p>
                </div>
            </article>
        );
    }

    const badge = integrityBadge(berkas.status_integritas);
    const fields = [
        ["Nama Berkas", berkas.nama_berkas],
        ["Nomor Berkas", berkas.nomor_berkas],
        ["Tanggal Upload", formatDate(berkas.created_at || berkas.tanggal_berkas)],
        ["Status Integritas", badge.label, badge.className],
        ["Retensi Aktif", berkas.masa_retensi_aktif],
        ["Retensi Inaktif", berkas.masa_retensi_inaktif]
    ];

    if (berkas.keterangan) fields.push(["Keterangan", berkas.keterangan]);

    return (
        <article className="berkas-stage-card">
            <header className="berkas-document-header">
                <h2>{title}</h2>
                <p>{berkas.nama_berkas} <span>•</span> {berkas.nomor_berkas} <span>•</span> Diunggah {formatDate(berkas.created_at || berkas.tanggal_berkas)}</p>
            </header>

            <PdfViewer berkas={berkas} />

            <section className="berkas-metadata-card">
                <div className="berkas-metadata-heading">
                    <h3>Detail Berkas</h3>
                    {onOpenPdf && <button className="secondary-button" type="button" onClick={() => onOpenPdf(berkas)}>Buka PDF</button>}
                </div>
                <dl className="berkas-metadata-grid">
                    {fields.map(([label, value, className]) => (
                        <div className="berkas-metadata-item" key={label}>
                            <dt>{label}</dt>
                            <dd>{className ? <span className={`badge ${className}`}>{value}</span> : value || "-"}</dd>
                        </div>
                    ))}
                </dl>
                {canVerify && normalizeIntegrityStatus(berkas.status_integritas) === "BELUM_DIVERIFIKASI" && (
                    <div className="berkas-integrity-action">
                        <button className="secondary-button" type="button" disabled={verifying} onClick={() => onVerifyIntegrity?.(berkas)}>
                            {verifying ? "Memverifikasi..." : "Verifikasi Integritas"}
                        </button>
                    </div>
                )}
            </section>
        </article>
    );
}

export default BerkasCard;
