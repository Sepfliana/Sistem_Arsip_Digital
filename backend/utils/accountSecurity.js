const EMAIL_INVALID_MESSAGE = "Email akun belum valid. Hubungi Administrator untuk memperbarui email sebelum mengaktifkan autentikasi dua faktor.";

const normalizeEmail = (email) => {
    if (typeof email !== "string") {
        return "";
    }

    return email.trim().toLowerCase();
};

const isValidEmail = (email) => {
    const normalizedEmail = normalizeEmail(email);

    if (!normalizedEmail) {
        return false;
    }

    return /^[^\s@]+@[^\s@]+\.[^\s@]+$/.test(normalizedEmail);
};

const createTotpSecretPayload = ({ secret, email }) => {
    return JSON.stringify({
        version: 1,
        secret,
        email: normalizeEmail(email)
    });
};

const parseTotpSecretPayload = (storedSecret) => {
    if (!storedSecret) {
        return {
            secret: null,
            email: null,
            isLegacy: false
        };
    }

    try {
        const parsedSecret = JSON.parse(storedSecret);

        return {
            secret: parsedSecret.secret || null,
            email: normalizeEmail(parsedSecret.email),
            isLegacy: false
        };
    } catch (error) {
        return {
            secret: storedSecret,
            email: null,
            isLegacy: true
        };
    }
};

const isTotpSecretBoundToEmail = ({ storedSecret, email }) => {
    const parsedSecret = parseTotpSecretPayload(storedSecret);
    const normalizedEmail = normalizeEmail(email);

    return Boolean(
        parsedSecret.secret &&
        parsedSecret.email &&
        parsedSecret.email === normalizedEmail &&
        !parsedSecret.isLegacy
    );
};

module.exports = {
    EMAIL_INVALID_MESSAGE,
    normalizeEmail,
    isValidEmail,
    createTotpSecretPayload,
    parseTotpSecretPayload,
    isTotpSecretBoundToEmail
};
