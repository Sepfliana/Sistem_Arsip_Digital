const { AsyncLocalStorage } = require("async_hooks");
const net = require("net");

const auditRequestStorage = new AsyncLocalStorage();

const firstForwardedAddress = (value) => Array.isArray(value)
    ? value[0]
    : typeof value === "string"
        ? value.split(",")[0].trim()
        : null;

const normalizeIpv4 = (value) => {
    if (typeof value !== "string") return null;
    let candidate = value.trim();
    if (candidate.startsWith("::ffff:")) candidate = candidate.slice(7);
    if (candidate === "::1") candidate = "127.0.0.1";
    return net.isIP(candidate) === 4 ? candidate : null;
};

const requestAuditContext = (req, _res, next) => {
    const requested = firstForwardedAddress(req.headers["x-forwarded-for"])
        || req.ip
        || req.socket?.remoteAddress
        || null;
    auditRequestStorage.run({
        ipAddress: normalizeIpv4(requested),
        rawIpAddress: requested,
        device: String(req.headers["user-agent"] || "unknown").trim() || "unknown",
    }, next);
};

const getAuditRequestContext = () => auditRequestStorage.getStore() || {};

module.exports = { getAuditRequestContext, normalizeIpv4, requestAuditContext };
