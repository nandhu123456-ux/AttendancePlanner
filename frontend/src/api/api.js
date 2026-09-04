import axios from "axios";

// baseURL is set at build time via VITE_API_URL. When unset, use a relative
// path so the API is served from the same origin as the frontend (this is how
// production works when the backend hosts the built React app).
const API = axios.create({ baseURL: import.meta.env.VITE_API_URL || "" });
API.interceptors.request.use((config) => {
  const token = localStorage.getItem("token");
  if (token) config.headers.Authorization = `Bearer ${token}`;
  return config;
});
API.interceptors.response.use((response) => response, (error) => {
  if (error.response?.status === 401) {
    localStorage.removeItem("token");
    localStorage.removeItem("student_id");
  }
  return Promise.reject(error);
});

export const loginInit = (credentials) => API.post("/login/init", credentials);
export const loginComplete = (data) => API.post("/login/complete", data);
export const refreshCaptcha = (data) => API.post("/login/refresh-captcha", data);
export const sync = (studentId) => API.post(`/sync/${studentId}`);
export const getPlanner = (studentId) => API.get(`/planner/${studentId}`);
export const getHistory = (studentId) => API.get(`/history/${studentId}`);
export const getSettings = (studentId) => API.get(`/settings/${studentId}`);
export const updateSettings = (studentId, settings) => API.put(`/settings/${studentId}`, settings);
export const simulatePlanner = (studentId, options) => API.post(`/planner/simulate/${studentId}`, options);
export const saveCustomAdjustment = (studentId, adjustment) => API.post(`/custom-adjustment/${studentId}`, adjustment);
export const setTargetType = (studentId, targetData) => API.post(`/target-type/${studentId}`, targetData);
