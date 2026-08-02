import { useEffect, useState } from "react";
import { useNavigate } from "react-router-dom";
import { verifyOTP } from "../../services/authService";
import logoKejaksaan from "../../assets/logo-kejaksaan.png";

import "./OtpVerification.css";

function OtpVerification() {
    const [otp, setOtp] = useState("");
    const [countdown, setCountdown] = useState(30);
    const [error, setError] = useState("");
    const navigate = useNavigate();
    const isValid = otp.length === 6;

    useEffect(() => {
        const timer = window.setInterval(() => {
            setCountdown((current) => (current === 1 ? 30 : current - 1));
        }, 1000);

        return () => window.clearInterval(timer);
    }, []);

    const handleVerifyOTP = async (event) => {
        event.preventDefault();
        console.log("[OTP] Button clicked");

        if (!isValid) {
            setError("Kode OTP harus 6 digit");
            return;
        }

        try {
            const userId = localStorage.getItem("userId");
            const pendingToken = localStorage.getItem("pendingAuthToken");

            if (!userId || !pendingToken) {
                navigate("/");
                return;
            }

            const result = await verifyOTP({ userId, token: otp, pendingToken });

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
        <div className="otp-container">
            <section className="otp-shell">
                <div className="otp-illustration" aria-hidden="true">
                    <div className="phone-shape">
                        <div className="phone-notch" />
                        <img src={logoKejaksaan} alt="" />
                        <span>Authenticator</span>
                        <strong>{otp.padEnd(6, "0").replace(/(.{3})/, "$1 ")}</strong>
                    </div>
                </div>

                <form className="otp-card" onSubmit={handleVerifyOTP}>
                    <span className="auth-kicker">Verifikasi keamanan</span>
                    <h2>Verifikasi TOTP</h2>
                    <p>Masukkan kode OTP 6 digit dari aplikasi authenticator.</p>

                    {error && <div className="otp-error">{error}</div>}

                    <label className="otp-field">
                        <span>Kode OTP</span>
                        <input
                            type="text"
                            inputMode="numeric"
                            maxLength={6}
                            placeholder="000000"
                            className="otp-input"
                            value={otp}
                            onChange={(event) => {
                                setOtp(event.target.value.replace(/\D/g, "").slice(0, 6));
                                setError("");
                            }}
                        />
                    </label>

                    <div className="countdown-card">
                        <span>Countdown kode</span>
                        <strong>{String(countdown).padStart(2, "0")} detik</strong>
                    </div>

                    <button className="otp-button" type="submit" disabled={!isValid}>
                        Verifikasi
                    </button>
                    <button className="otp-back-button" type="button" onClick={() => navigate("/") }>
                        Kembali
                    </button>
                </form>
            </section>
        </div>
    );
}

export default OtpVerification;
