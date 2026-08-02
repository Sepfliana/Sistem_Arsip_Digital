const jwt = require("jsonwebtoken");

const verifyToken = (req, res, next) => {
    try {

        const authHeader = req.headers.authorization;

        if (!authHeader) {
            return res.status(401).json({
                message: "Token tidak ditemukan"
            });
        }

        const token = authHeader.split(" ")[1];

        const decoded = jwt.verify(
            token,
            process.env.JWT_SECRET
        );

        req.user = decoded;

        next();

    } catch (error) {
        return res.status(401).json({
            message: "Token tidak valid"
        });
    }
};

const verifyPendingAuth = (requiredState) => {
    return (req, res, next) => {
        try {
            verifyToken(req, res, () => {
                const user = req.user || {};

                if (user.type !== "pending_auth") {
                    return res.status(403).json({
                        message: "Aksi tidak diizinkan"
                    });
                }

                if (user.purpose !== requiredState) {
                    return res.status(403).json({
                        message: "Aksi tidak sesuai"
                    });
                }

                next();
            });
        } catch (error) {
            return res.status(401).json({
                message: "Token tidak valid"
            });
        }
    };
};

module.exports = {
    verifyToken,
    verifyPendingAuth
};

