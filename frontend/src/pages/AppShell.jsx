import { Link, useLocation, useNavigate } from "react-router-dom";
import { useEffect, useState } from "react";
import { FiArchive, FiBarChart2, FiBookOpen, FiCheckCircle, FiClock, FiFileText, FiGrid, FiLogOut, FiMenu, FiSettings, FiShield, FiUsers, FiX } from "react-icons/fi";
import logoKejaksaan from "../assets/logo-kejaksaan.png";
import { api } from "../services/apiService";

const menusByRole = {
    admin: [
        { label: "Dashboard", path: "/dashboard", icon: FiGrid },
        { label: "Lemari", path: "/lemari", icon: FiArchive },
        { label: "Perkara", path: "/perkara", icon: FiBookOpen },
        { label: "Riwayat Verifikasi Integritas", path: "/verifikasi-integritas", icon: FiCheckCircle },
        { label: "User Management", path: "/users", icon: FiUsers },
        { label: "Audit Log", path: "/audit-log", icon: FiShield },
        { label: "Anomali", path: "/anomali", icon: FiBarChart2, badge: "anomali" },
        { label: "Pengaturan", path: "/pengaturan", icon: FiSettings }
    ],
    arsiparis: [
        { label: "Dashboard", path: "/dashboard", icon: FiGrid },
        { label: "Lemari", path: "/lemari", icon: FiArchive },
        { label: "Perkara", path: "/perkara", icon: FiBookOpen },
        { label: "Peminjaman", path: "/peminjaman", icon: FiClock },
        { label: "Pengaturan", path: "/pengaturan", icon: FiSettings }
    ],
    user: [
        { label: "Dashboard", path: "/dashboard", icon: FiGrid },
        { label: "Perkara", path: "/perkara", icon: FiBookOpen },
        { label: "Riwayat Peminjaman", path: "/peminjaman", icon: FiClock },
        { label: "Lemari", path: "/lemari", icon: FiArchive },
        { label: "Pengaturan", path: "/pengaturan", icon: FiSettings }
    ]
};

const normalizeRole = (role) => (role || "").toLowerCase();

let anomalyBadgeCache = { count: null, timestamp: 0 };

function AppShell({ title, subtitle, children }) {
    const navigate = useNavigate();
    const location = useLocation();
    const username = localStorage.getItem("username");
    const role = localStorage.getItem("role");
    const normalizedRole = normalizeRole(role);
    const menus = menusByRole[normalizedRole] || menusByRole.user;
    const [highRiskCount, setHighRiskCount] = useState(0);
    const [mobileMenuOpen, setMobileMenuOpen] = useState(false);

    useEffect(() => {
        setMobileMenuOpen(false);
    }, [location.pathname]);

    useEffect(() => {
        if (normalizedRole !== "admin") {
            return undefined;
        }

        const now = Date.now();
        if (anomalyBadgeCache.count !== null && now - anomalyBadgeCache.timestamp < 30000) {
            setHighRiskCount(anomalyBadgeCache.count);
            return undefined;
        }

        let mounted = true;
        api.get("/audit-log/anomali")
            .then((response) => {
                if (!mounted) return;
                const data = Array.isArray(response.data) ? response.data : [];
                const count = data.filter((item) => ["SEDANG", "TINGGI", "MEDIUM", "HIGH"].includes(String(item.tingkat_risiko || "").toUpperCase())).length;
                anomalyBadgeCache = { count, timestamp: Date.now() };
                setHighRiskCount(count);
            })
            .catch(() => setHighRiskCount(0));

        return () => {
            mounted = false;
        };
    }, [normalizedRole]);

    const handleLogout = async () => {
        try {
            await api.post("/auth/logout");
        } catch (error) {
            console.error(error);
        } finally {
            localStorage.clear();
            navigate("/");
        }
    };

    return (
        <div className="app-shell">
            {mobileMenuOpen && (
                <div
                    className="sidebar-backdrop"
                    onClick={() => setMobileMenuOpen(false)}
                    aria-hidden="true"
                />
            )}

            <aside className={`sidebar ${mobileMenuOpen ? "is-mobile-open" : ""}`}>
                <div className="brand">
                    <img src={logoKejaksaan} alt="Logo Kejaksaan" />
                    <div>
                        <strong>Sistem Arsip Digital</strong>
                        <span>Kejaksaan Negeri Pariaman</span>
                    </div>
                    <button
                        type="button"
                        className="mobile-close-button"
                        onClick={() => setMobileMenuOpen(false)}
                        aria-label="Tutup Menu"
                    >
                        <FiX aria-hidden="true" />
                    </button>
                </div>

                <nav className="side-nav">
                    {menus.map((menu) => {
                        const Icon = menu.icon || FiFileText;
                        return (
                            <Link
                                key={menu.path}
                                className={location.pathname === menu.path ? "active" : ""}
                                to={menu.path}
                                onClick={() => setMobileMenuOpen(false)}
                            >
                                <Icon aria-hidden="true" />
                                <span>{menu.label}</span>
                                {menu.badge === "anomali" && highRiskCount > 0 && (
                                    <em className="menu-badge">{highRiskCount}</em>
                                )}
                            </Link>
                        );
                    })}
                </nav>
            </aside>

            <main className="workspace">
                <header className="topbar">
                    <div className="topbar-left">
                        <button
                            type="button"
                            className="mobile-menu-toggle"
                            onClick={() => setMobileMenuOpen(true)}
                            aria-label="Buka Menu"
                        >
                            <FiMenu aria-hidden="true" />
                        </button>
                        <div>
                            <h1>{title}</h1>
                            {subtitle && <p>{subtitle}</p>}
                        </div>
                    </div>
                    <div className="account-chip">
                        <span>{username}</span>
                        <strong>{role}</strong>
                        <button className="ghost-button" onClick={handleLogout}>
                            <FiLogOut aria-hidden="true" />
                            Logout
                        </button>
                    </div>
                </header>

                {children}
            </main>
        </div>
    );
}

export default AppShell;

