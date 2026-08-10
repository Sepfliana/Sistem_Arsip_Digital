import AppShell from "./AppShell";
import { useEffect, useState } from "react";
import { fetchData } from "../services/apiService";
import { getReplicationStatus } from "../services/replicationService";

const defaultAvatar = "data:image/svg+xml,%3Csvg xmlns='http://www.w3.org/2000/svg' width='96' height='96' viewBox='0 0 96 96'%3E%3Crect width='96' height='96' rx='48' fill='%23E8F1EC'/%3E%3Ccircle cx='48' cy='36' r='16' fill='%230B6B3A'/%3E%3Cpath d='M20 82c4-18 18-28 28-28s24 10 28 28' fill='%230B6B3A'/%3E%3C/svg%3E";

const statusClass = (value) => {
    const normalized = String(value || "").toUpperCase();

    return ["ONLINE", "STREAMING", "SYNC", "ASYNC", "POTENTIAL"].includes(normalized)
        ? "success"
        : "danger";
};

function Pengaturan() {
    const username = localStorage.getItem("username");
    const role = localStorage.getItem("role");
    const userId = localStorage.getItem("userId");
    const isAdmin = String(role || "").toLowerCase() === "admin";
    const [profile, setProfile] = useState(null);
    const [profileError, setProfileError] = useState("");
    const [replication, setReplication] = useState(null);
    const [replicationError, setReplicationError] = useState("");

    useEffect(() => {
        if (!userId) {
            return;
        }

        let active = true;

        const loadProfile = async () => {
            try {
                const data = await fetchData(`/users/${userId}`);

                if (active) {
                    setProfile(data);
                    setProfileError("");
                }
            } catch (error) {
                if (active) {
                    setProfile(null);
                    setProfileError(error.response?.data?.message || "Gagal memuat profil pengguna");
                }
            }
        };

        loadProfile();

        return () => {
            active = false;
        };
    }, [userId]);

    useEffect(() => {
        if (!isAdmin) {
            return undefined;
        }

        let active = true;

        const loadReplicationStatus = async () => {
            try {
                const data = await getReplicationStatus();

                if (active) {
                    setReplication(data);
                    setReplicationError("");
                }
            } catch (error) {
                if (active) {
                    setReplication(null);
                    setReplicationError(
                        error.response?.data?.message ||
                        "Gagal memuat status replikasi"
                    );
                }
            }
        };

        loadReplicationStatus();
        const intervalId = window.setInterval(loadReplicationStatus, 5000);

        return () => {
            active = false;
            window.clearInterval(intervalId);
        };
    }, [isAdmin]);

    return (
        <AppShell title="Pengaturan Akun" subtitle="Informasi akun dan status keamanan">
            <section className="panel profile-panel">
                <div className="profile-header">
                    <img
                        className="profile-avatar"
                        src={profile?.foto_profil || defaultAvatar}
                        alt="Foto Profil"
                        onError={(event) => {
                            event.currentTarget.src = defaultAvatar;
                        }}
                    />
                    <div>
                        <h2>Profil Pengguna</h2>
                        {profileError && <p className="status-danger">{profileError}</p>}
                    </div>
                </div>
                <div className="profile-info-grid">
                    {/* Kolom Kiri: Nama Lengkap, Username, Role */}
                    <div className="profile-info-column">
                        <div className="profile-info-row">
                            <span className="profile-info-label">Nama Lengkap</span>
                            <span className="profile-info-colon">:</span>
                            <strong className="profile-info-value">{profile?.nama_lengkap || username || "-"}</strong>
                        </div>
                        <div className="profile-info-row">
                            <span className="profile-info-label">Username</span>
                            <span className="profile-info-colon">:</span>
                            <strong className="profile-info-value">{profile?.username || username || "-"}</strong>
                        </div>
                        <div className="profile-info-row">
                            <span className="profile-info-label">Role</span>
                            <span className="profile-info-colon">:</span>
                            <strong className="profile-info-value">{profile?.nama_peran || role || "-"}</strong>
                        </div>
                    </div>

                    {/* Kolom Kanan: NIP, Jabatan */}
                    <div className="profile-info-column">
                        <div className="profile-info-row">
                            <span className="profile-info-label">NIP</span>
                            <span className="profile-info-colon">:</span>
                            <strong className="profile-info-value">{profile?.nip || "-"}</strong>
                        </div>
                        <div className="profile-info-row">
                            <span className="profile-info-label">Jabatan</span>
                            <span className="profile-info-colon">:</span>
                            <strong className="profile-info-value">{profile?.jabatan || profile?.nama_peran || role || "-"}</strong>
                        </div>
                    </div>
                </div>
            </section>

            {isAdmin && (
                <section className="panel profile-panel">
                    <div className="panel-heading">
                        <h2>Monitoring Replikasi PostgreSQL</h2>
                        <span className="badge neutral">Refresh 5 detik</span>
                    </div>

                    {replicationError && (
                        <div className="toast error">{replicationError}</div>
                    )}

                    <dl>
                        <dt>Primary Server</dt>
                        <dd>
                            <span className={`badge ${statusClass(replication?.primary)}`}>
                                {replication?.primary || "UNKNOWN"}
                            </span>
                        </dd>

                        <dt>Secondary Server</dt>
                        <dd>
                            <span className={`badge ${statusClass(replication?.secondary)}`}>
                                {replication?.secondary || "UNKNOWN"}
                            </span>
                        </dd>

                        <dt>Replication Status</dt>
                        <dd>
                            <span className={`badge ${statusClass(replication?.replication)}`}>
                                {replication?.replication || "UNKNOWN"}
                            </span>
                        </dd>

                        <dt>Sync State</dt>
                        <dd>
                            <span className={`badge ${statusClass(replication?.sync_state)}`}>
                                {replication?.sync_state || "-"}
                            </span>
                        </dd>
                    </dl>
                </section>
            )}
        </AppShell>
    );
}

export default Pengaturan;
