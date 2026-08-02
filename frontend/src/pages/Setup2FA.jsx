import { useEffect, useState } from "react";
import { useNavigate } from "react-router-dom";
import { generate2FA, verifySetup2FA } from "../services/authService";
import logoKejaksaan from "../assets/logo-kejaksaan.png";
import "./Login/Login.css";

const steps = [
    ["Langkah 1", "Install Google Authenticator atau Authy di smartphone."],
    ["Langkah 2", "Scan QR Code yang tampil pada panel kanan."],
    ["Langkah 3", "Masukkan kode OTP 6 digit dari aplikasi authenticator."],
    ["Langkah 4", "Klik Konfirmasi Setup untuk mengaktifkan keamanan akun."]
];

function Setup2FA() {
    const [qr, setQr] = useState("");
    const [secret, setSecret] = useState("");
    const [otp, setOtp] = useState("");
    const [error, setError] = useState("");
    const navigate = useNavigate();
    const isValid = otp.length === 6;

    useEffect(() => {
        const getQR = async () => {
            try {
                const pendingToken = localStorage.getItem("pendingAuthToken");

                if (!pendingToken) {
                    navigate("/");
                    return;
                }

                const result = await generate2FA();
                setQr(result.qrCode);
                setSecret(result.secret);
            } catch (requestError) {
                setError(requestError.response?.data?.message || "Gagal membuat QR Code 2FA");
            }
        };

        Promise.resolve().then(getQR);
    }, [navigate]);

    const handleActivate = async (event) => {
        event.preventDefault();
        console.log("[OTP] Button clicked");

        if (!isValid) {
            setError("Kode OTP harus 6 digit");
            return;
        }

        try {
            const result = await verifySetup2FA({ token: otp });

            localStorage.setItem("token", result.token);
            localStorage.setItem("userId", result.user.id);
            localStorage.setItem("username", result.user.username);
            localStorage.setItem("role", result.user.role);
            localStorage.removeItem("pendingAuthToken");

            navigate("/dashboard");
        } catch (requestError) {
            setError(requestError.response?.data?.message || "Kode OTP tidak valid");
        }
    };

    return (
        <div className="auth-page setup-page">
            <section className="setup-shell">
                <div className="setup-guide">
                    <img src={logoKejaksaan} alt="Logo Kejaksaan" className="setup-logo" />
                    <span className="auth-kicker">Wizard keamanan akun</span>
                    <h1>Setup Two-Factor Authentication</h1>
                    <p>Ikuti langkah berikut untuk mengamankan akses Sistem Arsip Digital.</p>

                    <div className="setup-steps">
                        {steps.map(([title, description]) => (
                            <div className="setup-step" key={title}>
                                <strong>{title}</strong>
                                <span>{description}</span>
                            </div>
                        ))}
                    </div>
                </div>

                <form className="setup-panel" onSubmit={handleActivate}>
                    <div className="panel-heading">
                        <h2>Konfirmasi Setup</h2>
                    </div>

                    {error && <div className="login-error">{error}</div>}

                    <div className="qr-frame">
                        {qr ? <img src={qr} alt="QR Code 2FA" /> : <span className="spinner" />}
                    </div>

                    <label className="login-field">
                        <span>Secret Key</span>
                        <code className="secret-box">{secret || "Memuat secret key..."}</code>
                    </label>

                    <label className="login-field">
                        <span>Kode OTP</span>
                        <input
                            className="input otp-code-input"
                            inputMode="numeric"
                            maxLength={6}
                            placeholder="000000"
                            value={otp}
                            onChange={(event) => {
                                setOtp(event.target.value.replace(/\D/g, "").slice(0, 6));
                                setError("");
                            }}
                        />
                    </label>

                    <button className="login-button" type="submit" disabled={!isValid}>
                        Konfirmasi Setup
                    </button>
                </form>
            </section>
        </div>
    );
}

export default Setup2FA;
