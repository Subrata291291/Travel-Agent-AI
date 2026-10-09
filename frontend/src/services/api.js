import axios from "axios";

const TOKEN_KEY = "travel_agent_token";
const defaultApiBaseUrl = import.meta.env.PROD
  ? ""
  : "http://127.0.0.1:8000";
const configuredBaseUrl = (import.meta.env.VITE_API_BASE_URL || defaultApiBaseUrl).replace(/\/$/, "");
const apiBaseUrl = configuredBaseUrl.endsWith("/api/v1")
  ? configuredBaseUrl
  : configuredBaseUrl
    ? `${configuredBaseUrl}/api/v1`
    : "/api/v1";

const api = axios.create({
  baseURL: apiBaseUrl,

  headers: {
    "Content-Type": "application/json",
  },
});

api.interceptors.request.use(
  (config) => {
    const token = localStorage.getItem(TOKEN_KEY);

    if (token) {
      config.headers.Authorization = `Bearer ${token}`;
    }

    return config;
  },
  (error) => {
    return Promise.reject(error);
  }
);

export default api;
