function PerkaraInformation({ perkara }) {
    const namaTerdakwa = perkara?.terdakwa?.map((item) => item.nama_terdakwa).filter(Boolean).join(", ") || perkara?.nama_terdakwa;

    const formatDate = (value) => {
        if (!value) return "-";
        const date = new Date(value);
        if (Number.isNaN(date.getTime())) return String(value).slice(0, 10);
        return date.toLocaleDateString("id-ID", { day: "numeric", month: "long", year: "numeric" });
    };

    const groups = [
        {
            title: "INFORMASI PERKARA",
            fields: [
                ["Nomor Perkara", perkara?.nomor_perkara],
                ["Nama Terdakwa", namaTerdakwa],
                ["Jenis Pidana", perkara?.nama_jenis_pidana],
                ["Jenis Perkara", perkara?.nama_jenis_perkara]
            ]
        },
        {
            title: "PENANGANAN PERKARA",
            fields: [
                ["Jaksa", perkara?.nama_jaksa],
                ["Instansi Penyidik", perkara?.nama_instansi],
                ["Pasal", perkara?.melanggar_pasal]
            ]
        },
        {
            title: "WAKTU DAN STATUS",
            fields: [
                ["Tanggal Mulai", formatDate(perkara?.tanggal_mulai)],
                ["Tanggal Selesai", formatDate(perkara?.tanggal_selesai)],
                ["Status", perkara?.status],
                ["Keterangan", perkara?.keterangan]
            ]
        }
    ];

    const renderValue = (label, value) => {
        if (!value || value === "-") return "-";
        if (label === "Status") {
            return <span className="badge neutral">{value}</span>;
        }
        return value;
    };

    return (
        <section className="panel white-panel perkara-information">
            <div className="panel-heading">
                <h2>Detail Perkara</h2>
            </div>
            <div className="perkara-groups-container">
                {groups.map((group) => (
                    <div className="detail-group" key={group.title}>
                        <h3 className="detail-group-title">{group.title}</h3>
                        <dl className="detail-grid perkara-detail-grid">
                            {group.fields.map(([label, value]) => (
                                <div className="detail-row" key={label}>
                                    <dt className="detail-label">{label}</dt>
                                    <span className="detail-colon">:</span>
                                    <dd className="detail-value">{renderValue(label, value)}</dd>
                                </div>
                            ))}
                        </dl>
                    </div>
                ))}
            </div>
        </section>
    );
}

export default PerkaraInformation;
