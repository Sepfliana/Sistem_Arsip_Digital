const http = require("http");
const app = require("./app");

const PORT = process.env.PORT || 3000;

const server = http.createServer(app);

server.on("error", (error) => {
    if (error.code === "EADDRINUSE") {
        console.error(`Port ${PORT} sudah digunakan. Tutup proses lama atau gunakan PORT lain.`);
        process.exit(1);
    }

    console.error("Server gagal dijalankan:", error.message);
    process.exit(1);
});

server.listen(PORT, () => {
    console.log(`Server berjalan di port ${PORT}`);
});

module.exports = server;
