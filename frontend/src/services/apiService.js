import axios from "axios";

export const API_URL = import.meta.env.VITE_API_URL || "http://localhost:3000";

export const api = axios.create({
    baseURL: API_URL
});

api.interceptors.request.use((config) => {
    const token = localStorage.getItem("token");

    if (token) {
        config.headers.Authorization = `Bearer ${token}`;
    }

    return config;
});

export const fetchData = async (endpoint, params = {}) => {
    const response = await api.get(endpoint, {
        params
    });

    return response.data;
};

export const createData = async (endpoint, data) => {
    const response = await api.post(endpoint, data);

    return response.data;
};

export const updateData = async (endpoint, id, data) => {
    const response = await api.put(`${endpoint}/${id}`, data);

    return response.data;
};

export const deleteData = async (endpoint, id) => {
    const response = await api.delete(`${endpoint}/${id}`);

    return response.data;
};

export const openAuthenticatedPdf = async (endpoint, fallbackName = "berkas.pdf") => {
    const response = await api.get(endpoint, {
        responseType: "blob"
    });

    const contentType = response.headers["content-type"] || "application/pdf";
    const blob = new Blob([response.data], { type: contentType });
    const blobUrl = window.URL.createObjectURL(blob);
    const openedWindow = window.open(blobUrl, "_blank", "noopener,noreferrer");

    if (!openedWindow) {
        const link = document.createElement("a");
        link.href = blobUrl;
        link.download = fallbackName;
        document.body.appendChild(link);
        link.click();
        link.remove();
    }

    window.setTimeout(() => window.URL.revokeObjectURL(blobUrl), 60000);
};
