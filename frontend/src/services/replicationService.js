import { api } from "./apiService";

export const getReplicationStatus = async () => {
    const response = await api.get("/replication/status");

    return response.data;
};
