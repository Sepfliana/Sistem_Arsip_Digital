import { Navigate, Routes, Route } from "react-router-dom";

import Login from "../pages/Login/Login";
import ForgotPassword from "../pages/ForgotPassword";
import Dashboard from "../pages/Dashboard/Dashboard";
import User from "../pages/User/User";
import AuditLog from "../pages/AuditLog/AuditLog";
import Anomali from "../pages/Anomali/Anomali";
import OtpVerification from "../pages/OtpVerification/OtpVerification";
import Setup2FA from "../pages/Setup2FA";
import Lemari from "../pages/Lemari";
import Perkara from "../pages/Perkara";
import Peminjaman from "../pages/Peminjaman";
import Pengaturan from "../pages/Pengaturan";
import VerifikasiIntegritas from "../pages/VerifikasiIntegritas";

const RequireAuth = ({ children }) => {
  const token = localStorage.getItem("token");

  return token ? children : <Navigate to="/" replace />;
};

const RequirePendingAuth = ({ children }) => {
  const pendingToken = localStorage.getItem("pendingAuthToken");

  return pendingToken ? children : <Navigate to="/" replace />;
};

const RequireRole = ({ allowedRoles, children }) => {
  const token = localStorage.getItem("token");
  const role = (localStorage.getItem("role") || "").toLowerCase();

  if (!token) {
    return <Navigate to="/" replace />;
  }

  return allowedRoles.includes(role) ? children : <Navigate to="/dashboard" replace />;
};

function AppRoutes() {
  return (
    <Routes>
      <Route path="/" element={<Login />} />
      <Route path="/forgot-password" element={<ForgotPassword />} />
      <Route
        path="/dashboard"
        element={
          <RequireAuth>
            <Dashboard />
          </RequireAuth>
        }
      />
      <Route
        path="/lemari"
        element={
          <RequireRole allowedRoles={["admin", "arsiparis", "user"]}>
            <Lemari />
          </RequireRole>
        }
      />
      <Route
        path="/lemari/:lemariId/rak"
        element={
          <RequireRole allowedRoles={["admin", "arsiparis", "user"]}>
            <Lemari />
          </RequireRole>
        }
      />
      <Route
        path="/lemari/:lemariId/rak/:rakId/perkara"
        element={
          <RequireRole allowedRoles={["admin", "arsiparis", "user"]}>
            <Perkara />
          </RequireRole>
        }
      />
      <Route
        path="/perkara"
        element={
          <RequireRole allowedRoles={["admin", "arsiparis", "user"]}>
            <Perkara />
          </RequireRole>
        }
      />
      <Route
        path="/perkara/:perkaraId/berkas"
        element={
          <RequireRole allowedRoles={["admin", "arsiparis", "user"]}>
            <Perkara />
          </RequireRole>
        }
      />
      <Route
        path="/peminjaman"
        element={
          <RequireRole allowedRoles={["arsiparis", "user"]}>
            <Peminjaman />
          </RequireRole>
        }
      />
      <Route
        path="/verifikasi-integritas"
        element={
          <RequireRole allowedRoles={["admin"]}>
            <VerifikasiIntegritas />
          </RequireRole>
        }
      />
      <Route
        path="/users"
        element={
          <RequireRole allowedRoles={["admin"]}>
            <User />
          </RequireRole>
        }
      />
      <Route
        path="/audit-log"
        element={
          <RequireRole allowedRoles={["admin"]}>
            <AuditLog />
          </RequireRole>
        }
      />
      <Route
        path="/anomali"
        element={
          <RequireRole allowedRoles={["admin"]}>
            <Anomali />
          </RequireRole>
        }
      />
      <Route
        path="/pengaturan"
        element={
          <RequireRole allowedRoles={["admin", "arsiparis", "user"]}>
            <Pengaturan />
          </RequireRole>
        }
      />
      <Route
        path="/setup-2fa"
        element={
          <RequirePendingAuth>
            <Setup2FA />
          </RequirePendingAuth>
        }
      />
      
      <Route
        path="/otp"
        element={
          <RequirePendingAuth>
            <OtpVerification />
          </RequirePendingAuth>
        }
      />

    </Routes>
  );
}

export default AppRoutes;
