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
    if (axios.isCancel(error)) return Promise.reject(error);
    // 专业卡未收录属于正常缺数据，由抽屉展示“未收录”，不弹全局错误提示
    const missingMajorCard =
      error.response?.status === 404 &&
      (error.config?.url || "").startsWith("/majors/");
    if (missingMajorCard) return Promise.reject(error);
    // 官方真实投档未收录省份属于正常缺数据，由「官方真实投档」页内展示“该省官方数据尚未收录”，不弹全局错误
    const missingRealData =
      error.response?.status === 422 &&
      (error.config?.url || "").startsWith("/real-data/");
    if (missingRealData) return Promise.reject(error);
    // 已提交方案不可编辑（409）由页面提示「已提交的方案不可编辑，请先撤回」，不重复弹通用错误
    const lockedPlan =
      error.response?.status === 409 &&
      (error.config?.url || "").startsWith("/plans/");
    if (lockedPlan) return Promise.reject(error);
    const detail = error.response?.data?.detail;
    const missingAiRoute =
      error.response?.status === 404 &&
      (error.config.url?.includes("/recommendations/ai") ||
        error.config.url?.startsWith("/chat"));
    const message = missingAiRoute
      ? "当前后端尚未加载最新 AI 接口，请关闭原启动窗口并重新运行 start.bat"
      : typeof detail === "string"
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
