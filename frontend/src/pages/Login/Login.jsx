import "./Login.css";
import logoKejaksaan from "../../assets/logo-kejaksaan.png";
import { useState } from "react";
import { Link } from "react-router-dom";
import { loginUser } from "../../services/authService";
import { useNavigate } from "react-router-dom";

function Login() {
    const navigate = useNavigate();
    const [username, setUsername] = useState("");
    const [password, setPassword] = useState("");
    const [showPassword, setShowPassword] = useState(false);
    const [error, setError] = useState("");
    const isValid = username.trim().length > 0 && password.length > 0;

    const persistPendingUser = (result) => {
        localStorage.setItem("pendingAuthToken", result.pendingToken);
        localStorage.setItem("userId", result.userId);
        localStorage.setItem("username", result.username);
        localStorage.setItem("role", result.role);
    };

    const handleLogin = async (event) => {
        event.preventDefault();

        if (!isValid) {
            setError("Username dan password wajib diisi");
            return;
        }

        try {
            const result = await loginUser({ username, password });

            if (result.require2FA) {
                persistPendingUser(result);
                navigate("/otp");
                return;
            }

            if (result.requireSetup2FA) {
                persistPendingUser(result);
                navigate("/setup-2fa");
                return;
            }

            if (result.token) {
                localStorage.setItem("token", result.token);
                localStorage.setItem("userId", result.user.id);
                localStorage.setItem("username", result.user.username);
                localStorage.setItem("role", result.user.role);
                localStorage.removeItem("pendingAuthToken");
                navigate("/dashboard");
                return;
            }

            setError("Response login tidak valid");
        } catch (requestError) {
            setError(requestError.response?.data?.message || "Login gagal");
        }
    };

    return (
        <div className="login-container">
            <form className="login-card" onSubmit={handleLogin}>
                <img src={logoKejaksaan} alt="Logo Kejaksaan" className="logo" />

                <h1 className="title">Sistem Informasi Arsip Berkas</h1>
                <p className="subtitle">Kejaksaan Negeri Pariaman</p>

                {error && <div className="login-error">{error}</div>}

                <label className="login-field">
                    <span>Username</span>
                    <input
                        type="text"
                        placeholder="Masukkan username"
                        className="input"
                        value={username}
                        onChange={(event) => {
                            setUsername(event.target.value);
                            setError("");
                        }}
                    />
                </label>

                <label className="login-field login-password-field">
                    <span>Password</span>
                    <input
                        type={showPassword ? "text" : "password"}
                        placeholder="Masukkan password"
                        className="input"
                        value={password}
                        onChange={(event) => {
                            setPassword(event.target.value);
                            setError("");
                        }}
                    />
                    <button
                        type="button"
                        className="login-password-toggle"
                        onClick={() => setShowPassword((current) => !current)}
                    >
                        {showPassword ? "Hide" : "Show"}
                    </button>
                </label>

                <button className="login-button" type="submit" disabled={!isValid}>
                    Masuk
                </button>

                <Link to="/forgot-password" className="forgot-password">
                    Lupa Password?
                </Link>
            </form>
        </div>
    );
}

export default Login;
