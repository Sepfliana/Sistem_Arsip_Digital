function PerkaraInformation({ perkara }) {
    const namaTerdakwa = perkara?.terdakwa?.map((item) => item.nama_terdakwa).filter(Boolean).join(", ") || perkara?.nama_terdakwa;
    const fields = [
        ["Nomor Perkara", perkara?.nomor_perkara],
        ["Nama Terdakwa", namaTerdakwa],
        ["Jaksa", perkara?.nama_jaksa],
        ["Jenis Pidana", perkara?.nama_jenis_pidana],
        ["Jenis Perkara", perkara?.nama_jenis_perkara],
        ["Instansi Penyidik", perkara?.nama_instansi],
        ["Pasal", perkara?.melanggar_pasal],
        ["Tanggal Mulai", perkara?.tanggal_mulai?.slice(0, 10)],
        ["Tanggal Selesai", perkara?.tanggal_selesai?.slice(0, 10)],
        ["Status", perkara?.status],
        ["Keterangan", perkara?.keterangan]
    ];

    return (
        <section className="panel white-panel perkara-information">
            <div className="panel-heading">
                <h2>Detail Perkara</h2>
            </div>
            <dl className="detail-grid">
                {fields.map(([label, value]) => (
                    <div className="detail-row" key={label}>
                        <dt>{label}</dt>
                        <dd>{value || "-"}</dd>
                    </div>
                ))}
            </dl>
        </section>
    );
}

export default PerkaraInformation;

