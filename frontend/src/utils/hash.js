export const formatBytes = (bytes = 0) => {
    const value = Number(bytes || 0);

    if (!value) return "0 B";

    const units = ["B", "KB", "MB", "GB"];
    const index = Math.min(Math.floor(Math.log(value) / Math.log(1024)), units.length - 1);
    const size = value / (1024 ** index);

    return `${size.toFixed(size >= 10 || index === 0 ? 0 : 1)} ${units[index]}`;
};

export const shortenHash = (hash = "") => {
    if (!hash || hash.length <= 18) return hash || "-";

    return `${hash.slice(0, 8)}...${hash.slice(-7)}`;
};

export const calculateSha256 = async (file) => {
    const buffer = await file.arrayBuffer();
    const digest = await crypto.subtle.digest("SHA-256", buffer);

    return Array.from(new Uint8Array(digest))
        .map((byte) => byte.toString(16).padStart(2, "0"))
        .join("");
};
