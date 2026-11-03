import axios from "axios";
import { ElMessage } from "element-plus/es/components/message/index";

export const http = axios.create({
  baseURL: import.meta.env.VITE_API_BASE_URL || "/api",
  timeout: 20000,
});
http.interceptors.request.use((config) => {
  const token = localStorage.getItem("sunpath.token");
  if (token) config.headers.Authorization = `Bearer ${token}`;
  return config;
});
http.interceptors.response.use(
  (response) => response,
  (error) => {
    const detail = error.response?.data?.detail;
    const message =
      typeof detail === "string"
        ? detail
        : Array.isArray(detail)
          ? detail
              .map((d: { msg: string }) => d.msg.replace("Value error, ", ""))
              .join("；")
          : "连接服务失败，请检查后端是否启动";
    ElMessage.error(message);
    if (
      error.response?.status === 401 &&
      !error.config.url?.includes("/login")
    ) {
      localStorage.removeItem("sunpath.token");
      window.dispatchEvent(new Event("sunpath:unauthorized"));
    }
    return Promise.reject(error);
  },
);
