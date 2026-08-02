import { useState } from "react";
import { Link, useNavigate } from "react-router-dom";
import logoKejaksaan from "../assets/logo-kejaksaan.png";
import { requestPasswordReset, resetPassword } from "../services/authService";
import "./Login/Login.css";

function ForgotPassword() {
    const navigate = useNavigate();
    const [username, setUsername] = useState("");
    const [email, setEmail] = useState("");
    const [password, setPassword] = useState("");
    const [confirmPassword, setConfirmPassword] = useState("");
    const [resetToken, setResetToken] = useState("");
    const [message, setMessage] = useState("");
    const [error, setError] = useState("");
    const [loading, setLoading] = useState(false);

    const canRequest = username.trim() && email.trim();
    const canReset = password.length >= 6 && password === confirmPassword;

    const handleRequestReset = async (event) => {
        event.preventDefault();

        if (!canRequest) {
            setError("Username dan email wajib diisi");
            return;
        }

        setLoading(true);
        try {
            const result = await requestPasswordReset({ username, email });
            setResetToken(result.resetToken);
            setMessage("Akun terverifikasi. Silakan masukkan password baru.");
            setError("");
        } catch (requestError) {
            setError(requestError.response?.data?.message || "Gagal memverifikasi akun");
            setMessage("");
        } finally {
            setLoading(false);
        }
    };

    const handleResetPassword = async (event) => {
        event.preventDefault();

        if (!canReset) {
            setError("Password minimal 6 karakter dan konfirmasi harus sama");
            return;
        }

        setLoading(true);
        try {
            await resetPassword({ resetToken, password });
            setMessage("Password berhasil diperbarui. Silakan login kembali.");
            setError("");
            window.setTimeout(() => navigate("/"), 900);
        } catch (requestError) {
            setError(requestError.response?.data?.message || "Gagal mengubah password");
        } finally {
            setLoading(false);
        }
    };

    return (
        <div className="login-container">
            <form className="login-card" onSubmit={resetToken ? handleResetPassword : handleRequestReset}>
                <img src={logoKejaksaan} alt="Logo Kejaksaan" className="logo" />
                <h1 className="title">Lupa Password</h1>
                <p className="subtitle">Verifikasi akun intranet untuk membuat password baru.</p>

                {error && <div className="login-error">{error}</div>}
                {message && <div className="login-success">{message}</div>}

                {!resetToken ? (
                    <>
                        <label className="login-field">
                            <span>Username</span>
                            <input className="input" value={username} onChange={(event) => setUsername(event.target.value)} />
                        </label>
                        <label className="login-field">
                            <span>Email</span>
                            <input className="input" type="email" value={email} onChange={(event) => setEmail(event.target.value)} />
                        </label>
                    </>
                ) : (
                    <>
                        <label className="login-field">
                            <span>Password Baru</span>
                            <input className="input" type="password" value={password} onChange={(event) => setPassword(event.target.value)} />
                        </label>
                        <label className="login-field">
                            <span>Konfirmasi Password</span>
                            <input className="input" type="password" value={confirmPassword} onChange={(event) => setConfirmPassword(event.target.value)} />
                        </label>
                    </>
                )}

                <button className="login-button" type="submit" disabled={loading || (!resetToken && !canRequest) || (resetToken && !canReset)}>
                    {resetToken ? "Simpan Password" : "Verifikasi Akun"}
                </button>

                <Link to="/" className="forgot-password">Kembali ke Login</Link>
            </form>
        </div>
    );
}

export default ForgotPassword;
