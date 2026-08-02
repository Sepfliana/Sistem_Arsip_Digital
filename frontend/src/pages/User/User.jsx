import ResourcePage from "../ResourcePage";

function User() {
    return (
        <ResourcePage
            title="User Management"
            subtitle="Kelola akun, role, status aktif, dan reset password"
            endpoint="/users"
            columns={[
                { key: "username", label: "Username" },
                { key: "nama_lengkap", label: "Nama" },
                { key: "email", label: "Email" },
                { key: "nip", label: "NIP" },
                { key: "nama_peran", label: "Role" },
                { key: "is_active", label: "Status", render: (item) => <span className={`badge ${item.is_active ? "success" : "danger"}`}>{item.is_active ? "Aktif" : "Tidak Aktif"}</span> }
            ]}
            fields={[
                { name: "username", label: "Username", required: true },
                { name: "password", label: "Password / Reset Password", type: "password" },
                { name: "nama_lengkap", label: "Nama", required: true },
                { name: "email", label: "Email", type: "email" },
                { name: "nip", label: "NIP" },
                {
                    name: "role_name",
                    label: "Role",
                    required: true,
                    options: [
                        { value: "Arsiparis", label: "Arsiparis" },
                        { value: "User", label: "User" }
                    ]
                },
                {
                    name: "is_active",
                    label: "Status",
                    options: [
                        { value: "true", label: "Aktif" },
                        { value: "false", label: "Tidak Aktif" }
                    ]
                }
            ]}
        />
    );
}

export default User;
