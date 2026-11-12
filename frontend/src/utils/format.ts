import { api } from "../api";
import { filenameFromDisposition } from "./process";
export const number = (n: number | null | undefined) =>
  n == null ? "暂无" : n.toLocaleString("zh-CN");
export const riskLabels = { reach: "冲刺", steady: "稳妥", safe: "保底" };
export const date = (value: string) =>
  new Date(
    /Z$|[+-]\d\d:\d\d$/.test(value) ? value : `${value}Z`,
  ).toLocaleString("zh-CN", {
    timeZone: "Asia/Shanghai",
    month: "2-digit",
    day: "2-digit",
    hour: "2-digit",
    minute: "2-digit",
  });
/** 用 blob 触发浏览器下载；文件名优先取后端 Content-Disposition */
export function downloadBlob(blob: Blob, filename: string) {
  const url = URL.createObjectURL(blob);
  const a = document.createElement("a");
  a.href = url;
  a.download = filename;
  a.click();
  setTimeout(() => URL.revokeObjectURL(url), 1000);
}
export async function exportPlan(id: number) {
  const blob = (await api.exportPlan(id)).data;
  downloadBlob(blob, `SunPath-志愿方案-${id}.csv`);
}
/** M7：导出模拟投档结果 CSV（文件名使用后端 Content-Disposition） */
export async function exportProcessResults(planId: number) {
  const response = await api.processResultsExport(planId);
  const filename =
    filenameFromDisposition(
      (response.headers?.["content-disposition"] as string) ?? null,
    ) ?? `SunPath-模拟投档结果-${planId}.csv`;
  downloadBlob(response.data, filename);
  return filename;
}
