<script setup lang="ts">
import { computed, onMounted, ref } from "vue";
import {
  Bell,
  CalendarClock,
  CheckCheck,
  FolderHeart,
  Info,
  Mail,
  Megaphone,
  Newspaper,
  RefreshCw,
  ShieldCheck,
  Sparkles,
} from "lucide-vue-next";
import { useRouter } from "vue-router";
import { ElMessage } from "element-plus/es/components/message/index";
import { api } from "../api";
import type {
  MessageItem,
  MessageRefreshResult,
  MessageSubscription,
} from "../api/types";
import { useMessages } from "../stores/messages";
import { date } from "../utils/format";
import {
  MESSAGE_TYPE_OPTIONS,
  messageTypeLabel,
  newMessagesCount,
} from "../utils/process";

const router = useRouter();
const messageStore = useMessages();
const items = ref<MessageItem[]>([]);
const unread = ref(0);
const onlyUnread = ref(false);
const busy = ref(false);
const failed = ref(false);
const refreshing = ref(false);
const markingAll = ref(false);
const reading = ref<number[]>([]);
const subscription = ref<MessageSubscription | null>(null);
const subscriptionBusy = ref(false);
const saving = ref(false);
const types = ref<string[]>([]);
const channel = ref("site");
const leadDays = ref(3);
/** 后端 channel 取值：site（站内）/ email / both，展示时不要露出原始英文 */
const CHANNEL_OPTIONS = [
  { value: "site", label: "站内消息" },
  { value: "email", label: "邮件提醒" },
  { value: "both", label: "站内 + 邮件" },
];
const channelOptions = computed(() => {
  const value = channel.value?.trim();
  if (value && !CHANNEL_OPTIONS.some((item) => item.value === value))
    return [...CHANNEL_OPTIONS, { value, label: value }];
  return CHANNEL_OPTIONS;
});
const channelLabel = computed(
  () =>
    channelOptions.value.find((item) => item.value === channel.value)?.label ??
    channel.value ??
    "",
);
const unreadCount = computed(() => unread.value);

const TYPE_ICONS: Record<string, typeof Bell> = {
  collection: CalendarClock,
  plan: FolderHeart,
  policy: Newspaper,
  lecture: Megaphone,
  quality: ShieldCheck,
  // 兼容历史消息里出现过的旧取值
  notice: Newspaper,
  data_quality: ShieldCheck,
};
function typeIcon(type: string) {
  return TYPE_ICONS[type] ?? Bell;
}
function isReading(id: number) {
  return reading.value.includes(id);
}
async function loadMessages() {
  busy.value = true;
  failed.value = false;
  try {
    const { data } = await api.messages(onlyUnread.value);
    items.value = data.items ?? [];
    unread.value = data.unread ?? 0;
    messageStore.setUnread(unread.value);
  } catch {
    failed.value = true;
  } finally {
    busy.value = false;
  }
}
async function loadSubscription() {
  subscriptionBusy.value = true;
  try {
    const { data } = await api.messageSubscription();
    subscription.value = data;
    types.value = [...(data.types ?? [])];
    channel.value = data.channel || "inapp";
    leadDays.value =
      typeof data.lead_days === "number" ? data.lead_days : 3;
  } catch {
    subscription.value = null;
  } finally {
    subscriptionBusy.value = false;
  }
}
async function markRead(item: MessageItem) {
  if (item.read_at || isReading(item.id)) return;
  reading.value = [...reading.value, item.id];
  try {
    await api.readMessage(item.id);
    item.read_at = new Date().toISOString();
    unread.value = Math.max(0, unread.value - 1);
    messageStore.markRead(1);
  } catch {
    /* 拦截器已提示 */
  } finally {
    reading.value = reading.value.filter((id) => id !== item.id);
  }
}
async function markAllRead() {
  if (markingAll.value || !unread.value) return;
  markingAll.value = true;
  try {
    await api.readAllMessages();
    const now = new Date().toISOString();
    items.value = items.value.map((item) => ({
      ...item,
      read_at: item.read_at ?? now,
    }));
    unread.value = 0;
    messageStore.clearUnread();
    ElMessage.success("已全部标记为已读");
  } catch {
    /* 拦截器已提示 */
  } finally {
    markingAll.value = false;
  }
}
async function refreshMessages() {
  if (refreshing.value) return;
  refreshing.value = true;
  try {
    const { data } = await api.refreshMessages();
    const created = newMessagesCount(
      (data ?? {}) as MessageRefreshResult & Record<string, unknown>,
    );
    ElMessage.success(
      created > 0 ? `新增 ${created} 条提醒` : "已检查完成，暂无新增提醒",
    );
    await loadMessages();
  } catch {
    /* 拦截器已提示 */
  } finally {
    refreshing.value = false;
  }
}
async function saveSubscription() {
  if (saving.value) return;
  if (!types.value.length) {
    ElMessage.warning("请至少选择一种提醒类型");
    return;
  }
  if (
    !Number.isInteger(leadDays.value) ||
    leadDays.value < 0 ||
    leadDays.value > 14
  ) {
    ElMessage.warning("提前提醒天数需为 0–14 的整数");
    return;
  }
  saving.value = true;
  try {
    const { data } = await api.saveMessageSubscription({
      types: [...types.value],
      channel: channel.value,
      lead_days: leadDays.value,
    });
    subscription.value = data;
    ElMessage.success("订阅设置已保存");
  } catch {
    /* 拦截器已提示 */
  } finally {
    saving.value = false;
  }
}
function toggleUnread(next: boolean) {
  onlyUnread.value = next;
  void loadMessages();
}
function openLink(item: MessageItem) {
  const link = (item.link ?? "").trim();
  if (!link) return;
  if (link.startsWith("/")) {
    void router.push(link);
    return;
  }
  if (/^https?:\/\//i.test(link))
    window.open(link, "_blank", "noopener,noreferrer");
}
onMounted(() => {
  void loadMessages();
  void loadSubscription();
});
</script>

<template>
  <div class="page-heading">
    <div>
      <div class="eyebrow">STAY INFORMED, STAY READY</div>
      <h1>重要提醒，不错过每一个时间点</h1>
      <p>
        消息中心汇总征集志愿、方案提交、政策公告与数据质量提醒；所有提醒只作时间与进度提示。
      </p>
    </div>
    <div class="heading-actions">
      <el-button
        :loading="refreshing"
        @click="refreshMessages"
        ><RefreshCw :size="15" />刷新提醒</el-button
      ><el-button :loading="markingAll" :disabled="!unread" @click="markAllRead"
        ><CheckCheck :size="15" />全部已读</el-button
      >
    </div>
  </div>

  <div class="messages-layout">
    <section class="panel messages-panel">
      <div class="messages-head">
        <div>
          <h3><Mail :size="16" />消息列表</h3>
          <p>
            未读 <strong>{{ unreadCount }}</strong> 条 · 共
            {{ items.length }} 条<template v-if="onlyUnread">（仅看未读）</template>
          </p>
        </div>
        <el-checkbox
          :model-value="onlyUnread"
          @change="toggleUnread(!!$event)"
          >仅看未读</el-checkbox
        >
      </div>
      <div v-loading="busy" class="messages-body">
        <div v-if="failed" class="empty-state">
          <p>消息加载失败</p>
          <el-button @click="loadMessages">重新加载</el-button>
        </div>
        <template v-else-if="items.length">
          <article
            v-for="item in items"
            :key="item.id"
            :class="['message-item', { unread: !item.read_at }]"
            @click="markRead(item)"
          >
            <span
              :class="['message-icon', `type-${item.type}`]"
              :title="messageTypeLabel(item.type)"
            >
              <component :is="typeIcon(item.type)" :size="16" />
            </span>
            <div class="message-main">
              <div class="message-title-line">
                <strong>{{ item.title }}</strong>
                <span v-if="!item.read_at" class="unread-dot"></span>
                <span class="message-type-tag">{{
                  messageTypeLabel(item.type)
                }}</span>
              </div>
              <p class="message-body">{{ item.body }}</p>
              <div class="message-meta">
                <span>{{ date(item.created_at) }}</span>
                <span v-if="item.read_at" class="read-state">已读</span>
                <button
                  v-if="item.link"
                  class="message-link"
                  @click.stop="openLink(item)"
                >
                  查看相关页面
                </button>
              </div>
            </div>
            <el-button
              size="small"
              :loading="isReading(item.id)"
              :disabled="!!item.read_at"
              @click.stop="markRead(item)"
              >{{ item.read_at ? "已读" : "标记已读" }}</el-button
            >
          </article>
        </template>
        <el-empty
          v-else
          :description="
            onlyUnread
              ? '没有未读消息，所有提醒都已处理'
              : '还没有消息，提交方案或关注征集提醒后会在这里通知你'
          "
        ></el-empty>
      </div>
    </section>

    <aside class="messages-aside">
      <section id="subscription" class="panel subscription-panel">
        <div class="subscription-head">
          <h3><Bell :size="16" />提醒订阅</h3>
          <span class="tag subtle">演示设置</span>
        </div>
        <p class="subscription-tip">
          选择需要的提醒类型与提前提醒天数；当前为站内模拟提醒，不会真的发送邮件或短信。
        </p>
        <div v-loading="subscriptionBusy" class="subscription-body">
          <label class="subscription-label">提醒类型</label>
          <el-checkbox-group v-model="types" class="subscription-types">
            <el-checkbox
              v-for="option in MESSAGE_TYPE_OPTIONS"
              :key="option.value"
              :value="option.value"
              >{{ option.label }}</el-checkbox
            >
          </el-checkbox-group>
          <label class="subscription-label">提醒渠道</label>
          <el-select v-model="channel" aria-label="提醒渠道">
            <el-option
              v-for="option in channelOptions"
              :key="option.value"
              :value="option.value"
              :label="option.label"
            />
          </el-select>
          <label class="subscription-label"
            >提前提醒天数（0–14 天）</label
          >
          <el-input-number
            v-model="leadDays"
            :min="0"
            :max="14"
            :step="1"
            controls-position="right"
            aria-label="提前提醒天数"
          />
        </div>
        <el-button
          type="primary"
          :loading="saving"
          :disabled="subscriptionBusy"
          @click="saveSubscription"
          ><Sparkles :size="14" />保存订阅设置</el-button
        >
        <p v-if="subscription" class="subscription-current">
          当前订阅：{{
            subscription.types.map((type) => messageTypeLabel(type)).join("、") ||
            "无"
          }}
          · 渠道 {{ channelLabel }} · 提前 {{ subscription.lead_days }} 天
        </p>
      </section>
      <div class="notice compact messages-note">
        <strong>提醒只是时间工具</strong>
        <p>
          消息内容来自系统规则与公开资讯摘要，不构成录取承诺或报考建议；关键时间以省考试院公告为准。
        </p>
      </div>
      <p class="messages-footnote">
        <Info :size="12" />未读数会在顶部铃铛与侧栏同步显示。
      </p>
    </aside>
  </div>
</template>

<style scoped>
.messages-layout {
  display: grid;
  grid-template-columns: minmax(0, 1.85fr) minmax(280px, 0.75fr);
  gap: 18px;
  align-items: start;
}
.messages-panel {
  padding: 19px 20px;
}
.messages-head {
  display: flex;
  align-items: flex-start;
  justify-content: space-between;
  gap: 12px;
  padding-bottom: 13px;
  border-bottom: 1px solid var(--line);
}
.messages-head h3 {
  display: flex;
  align-items: center;
  gap: 7px;
  font-size: 14px;
  color: #46618a;
}
.messages-head h3 > svg {
  color: #6c8fc6;
}
.messages-head p {
  font-size: 10px;
  color: #98a4b5;
  margin-top: 6px;
}
.messages-head p strong {
  color: #c47d4d;
}
.messages-body {
  min-height: 240px;
  padding-top: 6px;
}
.message-item {
  display: flex;
  align-items: flex-start;
  gap: 12px;
  padding: 14px 4px;
  border-bottom: 1px solid #f1f4f8;
  cursor: pointer;
  transition: background 0.15s;
}
.message-item:hover {
  background: #fafcff;
}
.message-item.unread {
  background: #fbfdff;
}
.message-icon {
  flex-shrink: 0;
  width: 34px;
  height: 34px;
  border-radius: 9px;
  display: inline-flex;
  align-items: center;
  justify-content: center;
  background: #eef3fa;
  color: #6c8fc6;
}
.message-icon.type-collection {
  color: #b6894f;
  background: #fbf4e9;
}
.message-icon.type-plan {
  color: #6c8fc6;
  background: #eef3fa;
}
.message-icon.type-notice {
  color: #5f8a74;
  background: #edf6f0;
}
.message-icon.type-data_quality {
  color: #8a7fa8;
  background: #f3f1fa;
}
.message-main {
  flex: 1;
  min-width: 0;
}
.message-title-line {
  display: flex;
  align-items: center;
  gap: 7px;
  flex-wrap: wrap;
}
.message-title-line strong {
  font-size: 12px;
  font-weight: 500;
  color: #3f5674;
}
.unread-dot {
  width: 6px;
  height: 6px;
  border-radius: 50%;
  background: #d97b6c;
  flex-shrink: 0;
}
.message-type-tag {
  font-size: 8px;
  color: #93a1b3;
  background: #f2f5fa;
  border-radius: 3px;
  padding: 1px 6px;
}
.message-body {
  font-size: 10px;
  color: #8b9bb1;
  line-height: 1.85;
  margin-top: 5px;
}
.message-meta {
  display: flex;
  align-items: center;
  gap: 10px;
  flex-wrap: wrap;
  font-size: 9px;
  color: #a2afc0;
  margin-top: 6px;
}
.read-state {
  color: #a9b3c1;
}
.message-link {
  background: none;
  color: #4f7fbe;
  font-size: 9px;
  padding: 0;
}
.message-link:hover {
  text-decoration: underline;
}
.message-item > .el-button {
  flex-shrink: 0;
  font-size: 10px;
}
.messages-aside {
  display: flex;
  flex-direction: column;
  gap: 14px;
}
.subscription-panel {
  padding: 19px 20px;
}
.subscription-head {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 10px;
}
.subscription-head h3 {
  display: flex;
  align-items: center;
  gap: 7px;
  font-size: 13px;
  color: #46618a;
}
.subscription-head h3 > svg {
  color: #c79a5f;
}
.subscription-tip {
  font-size: 9px;
  color: #a2afc0;
  line-height: 1.8;
  margin: 10px 0 6px;
}
.subscription-body {
  display: flex;
  flex-direction: column;
  gap: 7px;
  margin-bottom: 14px;
}
.subscription-label {
  font-size: 10px;
  color: #8391a5;
  margin-top: 4px;
}
.subscription-types {
  display: flex;
  flex-wrap: wrap;
  gap: 6px 14px;
}
.subscription-types :deep(.el-checkbox) {
  margin-right: 0;
}
.subscription-types :deep(.el-checkbox__label) {
  font-size: 11px;
}
.subscription-current {
  font-size: 9px;
  color: #9aa8ba;
  margin-top: 10px;
  line-height: 1.7;
}
.messages-note {
  margin: 0;
}
.messages-note strong {
  font-size: 11px;
}
.messages-note p {
  font-size: 10px;
}
.messages-footnote {
  display: flex;
  align-items: center;
  gap: 5px;
  font-size: 9px;
  color: #a2afc0;
  padding: 0 3px;
}
@media (max-width: 1100px) {
  .messages-layout {
    grid-template-columns: minmax(0, 1fr);
  }
}
</style>
