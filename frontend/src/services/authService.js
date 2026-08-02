import axios from "axios";
import { API_URL } from "./apiService";

const getPendingAuthHeader = () => {
    const pendingToken = localStorage.getItem("pendingAuthToken");

    return {
        Authorization: `Bearer ${pendingToken}`
    };
};

export const loginUser = async (data) => {
    const response = await axios.post(
        `${API_URL}/auth/login`,
        data
    );

    return response.data;
};

export const requestPasswordReset = async (data) => {
    const response = await axios.post(
        `${API_URL}/auth/forgot-password`,
        data
    );

    return response.data;
};

export const resetPassword = async (data) => {
    const response = await axios.post(
        `${API_URL}/auth/reset-password`,
        data
    );

    return response.data;
};

export const verifyOTP = async (data) => {
    const url = `${API_URL}/auth/verify-login-otp`;
    console.log("[OTP] Payload:", data);
    console.log("[OTP] URL:", url);
    try {
        const response = await axios.post(url, data);
        console.log("[OTP] Success:", response.data);
        return response.data;
    } catch (error) {
        console.error("[OTP] Error:", error);
        console.error(error.response?.data);
        throw error;
    }
};

export const generate2FA = async () => {
    const url = `${API_URL}/totp/generate`;
    try {
        const response = await axios.post(
            url,
            {},
            {
                headers: getPendingAuthHeader()
            }
        );
        return response.data;
    } catch (error) {
        console.error("[OTP Setup Generate] Error:", error);
        console.error(error.response?.data);
        throw error;
    }
};

export const verifySetup2FA = async (data) => {
    const url = `${API_URL}/totp/verify`;
    console.log("[OTP] Payload:", data);
    console.log("[OTP] URL:", url);
    try {
        const response = await axios.post(
            url,
            data,
            {
                headers: getPendingAuthHeader()
            }
        );
        console.log("[OTP] Success:", response.data);
        return response.data;
    } catch (error) {
        console.error("[OTP] Error:", error);
        console.error(error.response?.data);
        throw error;
    }
};
