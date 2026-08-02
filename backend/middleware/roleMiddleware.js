const authorizeRoles = (...allowedRoles) => {
    return (req, res, next) => {

        if (!req.user) {
            return res.status(401).json({
                message: "User tidak terautentikasi"
            });
        }

        const userRole = String(req.user.role || "").toLowerCase();
        const normalizedAllowedRoles = allowedRoles.map((role) =>
            String(role).toLowerCase()
        );

        if (!normalizedAllowedRoles.includes(userRole)) {
            return res.status(403).json({
                message: "Akses ditolak"
            });
        }

        next();
    };
};

module.exports = {
    authorizeRoles
};
