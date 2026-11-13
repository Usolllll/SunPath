<script setup lang="ts">
import { computed, onMounted, ref } from "vue";
import { Info, LockKeyhole, Settings, ShieldCheck, Users } from "lucide-vue-next";
import { api } from "../api";
import type { PermissionAudit, SystemConfig } from "../api/types";
import { number } from "../utils/format";

const config = ref<SystemConfig | null>(null);
const permissions = ref<PermissionAudit | null>(null);
const loading = ref(false);
const forbidden = ref(false);
const failed = ref(false);

const configRows = computed(() => {
  const cfg = config.value;
  if (!cfg) return [];
  return [
    { group: "运行环境", label: "应用", value: `${cfg.app.name} ${cfg.app.version}` },
    { group: "运行环境", label: "Python", value: cfg.app.python },
    { group: "运行环境", label: ".env", value: cfg.app.env_file ? "已加载" : "未找到（使用默认值）" },
    {
      group: "数据库",
      label: "后端",
      value: cfg.database.host ? `${cfg.database.backend} · ${cfg.database.host}` : cfg.database.backend,
    },
    {
      group: "数据库",
      label: cfg.database.location ? "文件" : "库名",
      value: cfg.database.location || cfg.database.database || "—",
    },
    { group: "安全", label: "JWT 有效期", value: `${cfg.security.jwt_expire_minutes} 分钟` },
    { group: "安全", label: "CORS 来源", value: cfg.security.cors_origins.join(" / ") || "未配置" },
    { group: "安全", label: "管理员", value: `${cfg.security.admin_count} 个（${cfg.security.admin_emails.join("、") || "无"}）` },
    { group: "安全", label: "演示账号", value: cfg.security.demo_account ? "已启用" : "未启用" },
    {
      group: "AI 接口",
      label: "提供方",
      value: cfg.ai.provider,
    },
    { group: "AI 接口", label: "模型", value: `${cfg.ai.model_label}（${cfg.ai.model}）` },
    { group: "AI 接口", label: "地址", value: cfg.ai.base_url_host },
    {
      group: "AI 接口",
      label: "可用状态",
      value: cfg.ai.ready
        ? cfg.ai.keyless_channel
          ? "可用（免 Key 通道）"
          : "可用（已配置 Key）"
        : "未配置",
    },
    { group: "AI 接口", label: "超时", value: `${cfg.ai.timeout_seconds} 秒` },
    {
      group: "地图",
      label: "底图",
      value:
        cfg.map.provider === "tianditu"
          ? "天地图（强制）"
          : cfg.map.provider === "schematic"
            ? "内置示意底图（零 Key）"
            : cfg.map.tianditu_key_configured
              ? "天地图（已配置 Key）"
              : "内置示意底图（零 Key）",
    },
    { group: "地图", label: "天地图 Key", value: cfg.map.tianditu_key_configured ? "已配置" : "未配置" },
  ];
});
const groupedRows = computed(() => {
  const groups = new Map<string, { label: string; value: string }[]>();
  for (const row of configRows.value) {
    if (!groups.has(row.group)) groups.set(row.group, []);
    groups.get(row.group)!.push({ label: row.label, value: row.value });
  }
  return [...groups.entries()];
});
function timeText(value: string | null) {
  return value ? value.replace("T", " ").slice(0, 16) : "—";
}

async function load() {
  loading.value = true;
  forbidden.value = false;
  failed.value = false;
  try {
    const [cfg, perms] = await Promise.all([api.systemConfig(), api.permissionAudit()]);
    config.value = cfg.data;
    permissions.value = perms.data;
  } catch (error: unknown) {
    const code = (error as { response?: { status?: number } })?.response?.status;
    if (code === 403) forbidden.value = true;
    else failed.value = true;
  } finally {
    loading.value = false;
  }
}
onMounted(load);
</script>

<template>
  <section class="panel quality-card quality-wide system-card">
    <div class="quality-card-head">
      <h3><Settings :size="16" />系统参数与接口配置</h3>
      <span class="tag subtle">只读 · 敏感值已隐藏 · 仅管理员</span>
    </div>
    <p v-if="forbidden" class="quality-note">
      当前账号没有系统配置查看权限（仅管理员可查看）。
    </p>
    <template v-else>
      <div v-loading="loading" class="config-groups">
        <div v-for="[group, rows] in groupedRows" :key="group" class="config-group">
          <h4>{{ group }}</h4>
          <div v-for="row in rows" :key="`${group}-${row.label}`" class="config-row">
            <span>{{ row.label }}</span>
            <strong>{{ row.value }}</strong>
          </div>
        </div>
      </div>
      <p class="quality-note">
        <Info :size="12" />{{ config?.note || "只读总览。" }}
      </p>

      <div class="permission-head">
        <h4><Users :size="15" />权限审计</h4>
        <span class="tag subtle">邮箱已脱敏</span>
      </div>
      <div v-if="permissions" class="permission-metrics">
        <div>
          <strong>{{ number(permissions.users.total) }}</strong><span>账号总数</span>
        </div>
        <div>
          <strong>{{ number(permissions.users.admins) }}</strong><span>管理员</span>
        </div>
        <div>
          <strong>{{ number(permissions.users.candidates) }}</strong><span>考生</span>
        </div>
        <div>
          <strong>{{ number(permissions.denied_count) }}</strong><span>被拒绝次数</span>
        </div>
      </div>
      <div v-if="permissions" class="permission-columns">
        <div>
          <h5><ShieldCheck :size="13" />最近登录（脱敏）</h5>
          <ul v-if="permissions.recent_logins.length">
            <li v-for="(item, index) in permissions.recent_logins" :key="index">
              <span>{{ item.email }}</span><em>{{ timeText(item.at) }}</em>
            </li>
          </ul>
          <p v-else class="muted">暂无登录记录。</p>
        </div>
        <div>
          <h5><LockKeyhole :size="13" />管理员操作留痕</h5>
          <ul v-if="permissions.admin_actions.length">
            <li v-for="(item, index) in permissions.admin_actions" :key="index">
              <span>{{ item.action }}</span>
              <em>{{ item.email }} · {{ timeText(item.at) }}</em>
            </li>
          </ul>
          <p v-else class="muted">暂无管理员操作记录。</p>
        </div>
      </div>
      <p class="quality-note">
        <Info :size="12" />{{ permissions?.note || "" }} 配置修改仍通过 backend/.env + 重启服务完成，避免把密钥写进数据库或浏览器。
      </p>
    </template>
  </section>
</template>

<style scoped>
.config-groups {
  display: grid;
  grid-template-columns: repeat(auto-fit, minmax(260px, 1fr));
  gap: 14px;
  min-height: 80px;
}
.config-group h4 {
  font-size: 11px;
  color: #5b7294;
  margin-bottom: 8px;
  padding-bottom: 5px;
  border-bottom: 1px dashed #e9edf4;
}
.config-row {
  display: flex;
  justify-content: space-between;
  gap: 12px;
  font-size: 10px;
  padding: 4px 0;
  line-height: 1.6;
}
.config-row span {
  color: #93a0b2;
  white-space: nowrap;
}
.config-row strong {
  color: #4d6a8f;
  font-weight: 500;
  text-align: right;
  word-break: break-all;
}
.permission-head {
  display: flex;
  align-items: center;
  gap: 8px;
  margin: 18px 0 10px;
  padding-top: 14px;
  border-top: 1px dashed #e9edf4;
}
.permission-head h4 {
  display: flex;
  align-items: center;
  gap: 6px;
  font-size: 12px;
  color: #5b7294;
}
.permission-metrics {
  display: grid;
  grid-template-columns: repeat(auto-fit, minmax(110px, 1fr));
  gap: 10px;
}
.permission-metrics > div {
  background: #f8fafd;
  border: 1px solid #edf1f7;
  border-radius: 7px;
  padding: 9px 12px;
}
.permission-metrics strong {
  display: block;
  font-size: 17px;
  color: #40628c;
  font-weight: 600;
}
.permission-metrics span {
  font-size: 9px;
  color: #98a4b5;
}
.permission-columns {
  display: grid;
  grid-template-columns: 1fr 1fr;
  gap: 18px;
  margin-top: 14px;
}
.permission-columns h5 {
  display: flex;
  align-items: center;
  gap: 5px;
  font-size: 10px;
  color: #7e8da2;
  margin-bottom: 7px;
}
.permission-columns ul {
  list-style: none;
  margin: 0;
  padding: 0;
}
.permission-columns li {
  display: flex;
  justify-content: space-between;
  gap: 10px;
  font-size: 9px;
  color: #7d8ea6;
  padding: 4px 0;
  border-bottom: 1px dashed #f0f3f8;
}
.permission-columns em {
  font-style: normal;
  color: #a3afbf;
}
.quality-note svg {
  vertical-align: -2px;
}
@media (max-width: 720px) {
  .permission-columns {
    grid-template-columns: 1fr;
  }
}
</style>
