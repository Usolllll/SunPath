import { api } from "../api";
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
export async function exportPlan(id: number) {
  const blob = (await api.exportPlan(id)).data;
  const url = URL.createObjectURL(blob);
  const a = document.createElement("a");
  a.href = url;
  a.download = `SunPath-志愿方案-${id}.csv`;
  a.click();
  setTimeout(() => URL.revokeObjectURL(url), 1000);
}
