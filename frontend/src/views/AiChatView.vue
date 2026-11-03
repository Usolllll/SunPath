<script setup lang="ts">
import {
  computed,
  ref,
  onMounted,
  onBeforeUnmount,
  nextTick,
  watch,
} from "vue";
import axios from "axios";
import MarkdownContent from "../components/MarkdownContent.vue";
import {
  Sparkles,
  ArrowUpRight,
  ArrowUp,
  Compass,
  School,
  BookOpen,
  Route,
  MessageCircle,
  X,
  ContactRound,
  Plus,
  Square,
} from "lucide-vue-next";
import { useAuth } from "../stores/auth";
import { api } from "../api";
import type {
  ChatMessage,
  ChatAvailableContext,
  ChatContextSummary,
} from "../api/types";

const auth = useAuth();
const question = ref("");
const input = ref<{ focus: () => void }>();
const profile = computed(() => auth.user?.profile);
const messages = ref<ChatMessage[]>([]);
const busy = ref(false);
const configured = ref(false);
const loadingConfig = ref(true);
const configFailed = ref(false);
const useProfile = ref(true);
const useSavedPlans = ref(true);
const selectedPlanIds = ref<number[]>([]);
const availableContext = ref<ChatAvailableContext | null>(null);
const contextUsed = ref<ChatContextSummary | null>(null);
const modelLabel = ref("DeepSeek-V4.1-Flash-1017");
const error = ref("");
const truncated = ref(false);
const transcript = ref<HTMLDivElement>();
let controller: AbortController | undefined;
const suggestions = [
  {
    icon: School,
    title: "院校怎么选",
    text: "选择大学时，应该重点考虑哪些因素？",
  },
  {
    icon: BookOpen,
    title: "专业怎么挑",
    text: "计算机科学与技术和软件工程有什么区别？",
  },
  {
    icon: Route,
    title: "方案怎么看",
    text: "请结合我的当前画像，分析已保存方案的冲稳保分布，并指出历史快照与当前画像的差异。",
  },
  {
    icon: Compass,
    title: "方向怎么找",
    text: "如何结合自己的兴趣，确定适合的专业方向？",
  },
];

function chooseQuestion(text: string) {
  question.value = text;
  input.value?.focus();
}
async function loadConfig() {
  loadingConfig.value = true;
  configFailed.value = false;
  try {
    const [configResponse, contextResponse] = await Promise.all([
      api.chatConfig(),
      api.chatContext(),
    ]);
    configured.value = configResponse.data.configured;
    modelLabel.value = configResponse.data.model_label;
    availableContext.value = contextResponse.data;
  } catch {
    configFailed.value = true;
  } finally {
    loadingConfig.value = false;
  }
}
async function scrollToEnd() {
  await nextTick();
  if (transcript.value)
    transcript.value.scrollTop = transcript.value.scrollHeight;
}
async function send() {
  const text = question.value.trim();
  if (!text || busy.value || !configured.value || loadingConfig.value) return;
  const context: ChatMessage[] = [
    ...messages.value.slice(-20),
    { role: "user", content: text },
  ];
  messages.value.push({ role: "user", content: text });
  question.value = "";
  error.value = "";
  truncated.value = false;
  busy.value = true;
  controller = new AbortController();
  await scrollToEnd();
  try {
    const { data } = await api.chat(
      context,
      {
        use_profile: useProfile.value,
        use_saved_plans: useSavedPlans.value,
        plan_ids: selectedPlanIds.value.length
          ? [...selectedPlanIds.value]
          : null,
      },
      controller.signal,
    );
    messages.value.push({ role: "assistant", content: data.content });
    modelLabel.value = data.model_label;
    contextUsed.value = data.context || null;
    truncated.value = data.finish_reason === "length";
  } catch (failure) {
    messages.value.pop();
    question.value = text;
    if (!axios.isCancel(failure)) {
      const detail = axios.isAxiosError(failure)
        ? failure.response?.data?.detail
        : undefined;
      error.value =
        typeof detail === "string"
          ? detail
          : "发送失败，问题已保留，可以重试。";
    }
  } finally {
    busy.value = false;
    controller = undefined;
    await scrollToEnd();
  }
}
function newConversation() {
  if (busy.value) return;
  messages.value = [];
  question.value = "";
  error.value = "";
  truncated.value = false;
  contextUsed.value = null;
}
watch(
  [useProfile, useSavedPlans, selectedPlanIds],
  () => {
    if (busy.value) return;
    messages.value = [];
    contextUsed.value = null;
    error.value = "";
    truncated.value = false;
  },
  { deep: true },
);
function onKeydown(event: KeyboardEvent) {
  if (event.key === "Enter" && !event.shiftKey && !event.isComposing) {
    event.preventDefault();
    void send();
  }
}
onMounted(loadConfig);
onBeforeUnmount(() => controller?.abort());
</script>

<template>
  <div class="page-heading">
    <div>
      <div class="eyebrow">A LITTLE CLARITY FOR EVERY CHOICE</div>
      <h1>关于未来的疑问，都可以从这里开始</h1>
      <p>聊聊院校、专业与志愿规划，让每一个选择更清晰。</p>
    </div>
    <el-button :disabled="busy || !messages.length" @click="newConversation"
      ><Plus :size="15" />新对话</el-button
    >
  </div>

  <div class="ai-chat-layout">
    <section class="panel ai-conversation" aria-label="AI 升学问答">
      <header class="ai-conversation-header">
        <div class="ai-assistant-identity">
          <span class="ai-small-avatar"><Sparkles :size="18" /></span>
          <div>
            <h3>SunPath 升学助手</h3>
            <p>陪你梳理选择，探索更多可能</p>
          </div>
        </div>
        <span class="ai-coming-soon"
          ><span class="status-dot"></span
          >{{
            loadingConfig
              ? "正在读取配置"
              : configured
                ? modelLabel
                : "服务未配置"
          }}</span
        >
      </header>

      <div v-if="!messages.length" class="ai-welcome">
        <div class="ai-welcome-mark">
          <Sparkles :size="34" :stroke-width="1.4" />
        </div>
        <span class="eyebrow">HELLO, FUTURE EXPLORER</span>
        <h2>{{ auth.user?.name }}，今天想了解什么？</h2>
        <p>
          面对重要的选择，有疑问很正常。<br />先选一个你关心的话题，或写下自己的问题。
        </p>
        <div class="ai-question-grid">
          <button
            v-for="item in suggestions"
            :key="item.title"
            class="ai-question"
            @click="chooseQuestion(item.text)"
          >
            <span class="ai-question-title"
              ><component :is="item.icon" :size="17" />{{ item.title
              }}<ArrowUpRight :size="14"
            /></span>
            <span class="ai-question-text">{{ item.text }}</span>
          </button>
        </div>
      </div>

      <div
        v-else
        ref="transcript"
        class="ai-transcript"
        role="log"
        aria-label="对话记录"
        aria-live="polite"
        :aria-busy="busy"
      >
        <article
          v-for="(message, index) in messages"
          :key="index"
          :class="['ai-chat-message', message.role]"
        >
          <span class="ai-message-author">{{
            message.role === "user" ? "我" : "SunPath 升学助手"
          }}</span>
          <MarkdownContent
            v-if="message.role === 'assistant'"
            class="ai-message-body"
            :content="message.content"
          />
          <p v-else>{{ message.content }}</p>
        </article>
        <div v-if="busy" class="ai-waiting">
          <Sparkles :size="15" />正在整理回答，请稍候…
        </div>
      </div>

      <div class="ai-composer-area">
        <div v-if="configFailed" class="notice compact">
          无法读取问答配置。<button class="text-button" @click="loadConfig">
            重新加载
          </button>
        </div>
        <div v-else-if="!loadingConfig && !configured" class="notice compact">
          问答服务尚未配置，请在后端设置 DeepSeek 密钥和接口地址。
        </div>
        <div v-if="error" role="alert" class="notice compact">{{ error }}</div>
        <div v-if="contextUsed" class="ai-used-context" role="status">
          本次已附带：{{
            contextUsed.profile_included ? "当前考生画像" : "未附带当前画像"
          }}
          · {{ contextUsed.included_plan_count }} 份已保存方案<span
            v-if="contextUsed.omitted_plan_count"
            >；另
            {{
              contextUsed.omitted_plan_count
            }}
            份未附带，可选择指定方案后重新提问。</span
          >
          <p v-if="contextUsed.plan_names.length">
            {{ contextUsed.plan_names.join("、") }}
          </p>
        </div>
        <p v-if="truncated" class="ai-composer-caption">
          本次回答达到长度上限，可发送“请继续”接着提问。
        </p>
        <el-checkbox
          v-if="profile"
          v-model="useProfile"
          :disabled="busy"
          class="ai-profile-toggle"
          >结合我的考生画像（将省份、成绩、选科和偏好发送给
          DeepSeek）</el-checkbox
        >
        <el-checkbox
          v-model="useSavedPlans"
          :disabled="busy"
          class="ai-profile-toggle"
          >结合我的已保存方案及其画像快照（发送给 DeepSeek）</el-checkbox
        >
        <p class="ai-composer-caption ai-scope-caption">
          更改参考范围会开启新对话；本机未保存的志愿草稿不会附带。
        </p>
        <div class="ai-composer">
          <el-input
            ref="input"
            v-model="question"
            type="textarea"
            :rows="3"
            maxlength="1000"
            resize="none"
            :disabled="busy"
            aria-label="你的升学问题"
            placeholder="写下你的升学问题，例如：如何合理搭配冲稳保志愿？"
            @keydown="onKeydown"
          />
          <div class="ai-composer-toolbar">
            <span>Enter 发送 · Shift+Enter 换行</span>
            <div class="ai-composer-actions">
              <span class="ai-character-count"
                >{{ question.length }} / 1000</span
              >
              <button
                v-if="question && !busy"
                class="icon-button"
                aria-label="清空问题"
                @click="
                  question = '';
                  input?.focus();
                "
              >
                <X :size="16" />
              </button>
              <el-button
                v-if="busy"
                aria-label="停止等待回答"
                @click="controller?.abort()"
                ><Square :size="14" />停止等待</el-button
              >
              <el-button
                v-else
                type="primary"
                :disabled="
                  !question.trim() ||
                  !configured ||
                  loadingConfig ||
                  configFailed
                "
                aria-label="发送问题"
                @click="send"
                ><ArrowUp :size="16" />发送</el-button
              >
            </div>
          </div>
        </div>
        <p class="ai-composer-caption">
          回答由
          {{ modelLabel }}
          生成，可能有误；具体招生信息请以官方公布为准。本站不保存对话记录。
        </p>
      </div>
    </section>

    <aside class="ai-chat-aside">
      <section class="panel ai-context-card">
        <span class="metric-icon blue"><ContactRound :size="19" /></span>
        <h3>从了解你开始</h3>
        <p>完善考生画像，先为自己的选择整理一份清晰的参考。</p>
        <div v-if="profile" class="ai-profile-context">
          <span>{{ profile.province }} · {{ profile.exam_year }} 届</span>
          <strong
            >{{ profile.score }}<small> 分</small
            ><span
              >全省 {{ profile.rank.toLocaleString("zh-CN") }} 位</span
            ></strong
          >
          <div>
            <span
              v-for="subject in profile.subjects"
              :key="subject"
              class="tag"
              >{{ subject }}</span
            >
          </div>
        </div>
        <RouterLink to="/profile" class="text-button"
          >{{ profile ? "查看我的考生画像" : "完善我的考生画像"
          }}<ArrowUpRight :size="14"
        /></RouterLink>
      </section>
      <section class="panel ai-context-card ai-plan-context">
        <span class="metric-icon orange"><Route :size="19" /></span>
        <h3>
          我的已存方案
          <span class="tag"
            >{{ availableContext?.saved_plan_count || 0 }} 份</span
          >
        </h3>
        <p>
          默认参考最近
          {{
            availableContext?.max_plans || 10
          }}
          份，也可以选择本次要分析的方案。
        </p>
        <el-select
          v-if="availableContext?.plans.length"
          v-model="selectedPlanIds"
          multiple
          filterable
          clearable
          :multiple-limit="availableContext.max_plans"
          :disabled="busy || !useSavedPlans"
          placeholder="默认附带最近保存的方案"
          aria-label="本次参考的已保存方案"
          ><el-option
            v-for="plan in availableContext.plans"
            :key="plan.id"
            :value="plan.id"
            :label="`${plan.name}（${plan.group_count} 个志愿）`"
        /></el-select>
        <p v-else>还没有已保存方案，保存后即可让助手结合方案分析。</p>
        <p v-if="availableContext?.options_truncated">
          选择列表仅显示最近 50 份方案。
        </p>
        <RouterLink to="/plans" class="text-button"
          >查看我的已保存方案<ArrowUpRight :size="14"
        /></RouterLink>
      </section>
      <section class="ai-explore-note">
        <span class="ai-note-icon"><MessageCircle :size="19" /></span>
        <h3>好问题，是好选择的起点</h3>
        <p>
          可以先想想：你更在意学习的内容、大学所在的城市，还是未来想从事的工作？
        </p>
        <RouterLink to="/data" class="text-button"
          >先去探索院校与专业<ArrowUpRight :size="14"
        /></RouterLink>
      </section>
    </aside>
  </div>
</template>

<style scoped>
.ai-used-context {
  padding: 10px 12px;
  color: #779185;
  background: #f0f7f3;
  border-radius: 6px;
  font-size: 10px;
  line-height: 1.8;
  margin-bottom: 12px;
  overflow-wrap: anywhere;
}
.ai-used-context p {
  color: #96a79e;
  font-size: 9px;
  margin-top: 4px;
}
.ai-plan-context {
  margin-top: 18px;
}
.ai-plan-context .el-select {
  margin-top: 15px;
}
.ai-scope-caption {
  text-align: left;
  margin: 0 0 10px;
}
.ai-profile-toggle {
  display: flex;
}
.ai-transcript {
  max-height: 510px;
  min-height: 350px;
  overflow-y: auto;
  padding: 25px;
  display: flex;
  flex-direction: column;
  gap: 22px;
}
.ai-chat-message {
  max-width: 92%;
  align-self: flex-start;
  min-width: 0;
}
.ai-chat-message.user {
  align-self: flex-end;
}
.ai-message-author {
  display: block;
  color: #91a0b4;
  font-size: 10px;
  margin-bottom: 7px;
}
.ai-chat-message.user .ai-message-author {
  text-align: right;
}
.ai-chat-message > p,
.ai-chat-message > .ai-message-body {
  background: #f5f7fb;
  color: #4d627f;
  padding: 15px 18px;
  border: 1px solid #e9edf4;
  border-radius: 10px;
  font-size: 13px;
  line-height: 1.95;
  overflow-wrap: anywhere;
}
.ai-chat-message > p {
  white-space: pre-wrap;
}
.ai-chat-message.user p {
  background: #eaf1fc;
  border-color: #dce7f8;
}
.ai-waiting {
  color: #99a7b9;
  font-size: 11px;
  display: flex;
  align-items: center;
  gap: 8px;
}
.ai-profile-toggle {
  margin: 3px 0 10px;
  height: auto;
  align-items: flex-start;
}
.ai-profile-toggle :deep(.el-checkbox__label) {
  font-size: 10px;
  color: #8e9db2;
  white-space: normal;
  line-height: 1.6;
}
.ai-profile-toggle :deep(.el-checkbox__input) {
  margin-top: 2px;
}
.ai-coming-soon {
  overflow-wrap: anywhere;
  max-width: 48%;
  text-align: right;
}
.ai-preview-label {
  gap: 6px;
  padding: 6px 10px;
}
.ai-chat-layout {
  display: grid;
  grid-template-columns: minmax(0, 1fr) 260px;
  gap: 23px;
  padding-bottom: 20px;
  align-items: start;
}
.ai-conversation {
  overflow: hidden;
}
.ai-conversation-header {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 12px;
  padding: 19px 25px;
  border-bottom: 1px solid var(--line);
}
.ai-assistant-identity {
  display: flex;
  align-items: center;
  gap: 11px;
}
.ai-small-avatar {
  display: inline-flex;
  align-items: center;
  justify-content: center;
  width: 35px;
  height: 35px;
  border-radius: 10px;
  background: #f8f0e4;
  color: #bd965e;
}
.ai-assistant-identity h3 {
  font-size: 12px;
}
.ai-assistant-identity p {
  font-size: 10px;
  color: #9aa6b7;
  margin-top: 2px;
}
.ai-coming-soon {
  display: flex;
  align-items: center;
  gap: 6px;
  font-size: 10px;
  color: #a4947b;
  white-space: nowrap;
}
.ai-coming-soon .status-dot {
  width: 5px;
  height: 5px;
}
.ai-welcome {
  max-width: 680px;
  margin: 0 auto;
  padding: 43px 32px 30px;
  text-align: center;
}
.ai-welcome-mark {
  display: flex;
  align-items: center;
  justify-content: center;
  width: 70px;
  height: 70px;
  border: 1px solid #f2e5cf;
  border-radius: 21px;
  color: #c6a06b;
  background: linear-gradient(145deg, #fff9ee, #f3f6fc);
  margin: 0 auto 22px;
}
.ai-welcome > .eyebrow {
  display: block;
  font-size: 8px;
  letter-spacing: 1.7px;
  margin-bottom: 11px;
}
.ai-welcome h2 {
  font-size: 23px;
  color: #365171;
}
.ai-welcome > p {
  font-size: 11px;
  color: #96a3b7;
  margin-top: 13px;
  line-height: 1.9;
}
.ai-question-grid {
  display: grid;
  grid-template-columns: 1fr 1fr;
  gap: 13px;
  margin-top: 30px;
  text-align: left;
}
.ai-question {
  padding: 17px 16px;
  border-radius: 8px;
  border: 1px solid #e8edf5;
  background: #fbfcfe;
  text-align: left;
  transition:
    border-color 0.15s,
    background 0.15s;
}
.ai-question:hover {
  border-color: #b5cae9;
  background: #f4f7fd;
}
.ai-question-title {
  display: flex;
  align-items: center;
  gap: 9px;
  color: #6882a4;
  font-size: 11px;
}
.ai-question-title > svg:last-child {
  margin-left: auto;
  color: #acbace;
}
.ai-question-text {
  display: block;
  font-size: 10px;
  color: #9aa8ba;
  line-height: 1.9;
  margin-top: 10px;
}
.ai-composer-area {
  padding: 8px 25px 19px;
}
.ai-composer {
  border: 1px solid #e0e7f1;
  border-radius: 9px;
  padding: 6px 12px 10px;
  background: #fff;
}
.ai-composer:focus-within {
  border-color: #a4bcde;
  box-shadow: 0 0 0 3px #f4f7fc;
}
.ai-composer :deep(.el-textarea__inner) {
  box-shadow: none;
  font-family: inherit;
  font-size: 12px;
  padding: 10px 2px;
  background: transparent;
  line-height: 1.9;
  color: #536a88;
}
.ai-composer :deep(.el-textarea__inner::placeholder) {
  color: #a7b2c2;
  font-size: 11px;
}
.ai-composer-toolbar {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 8px;
}
.ai-composer-toolbar > span {
  font-size: 9px;
  color: #a7b1c0;
}
.ai-composer-actions {
  display: flex;
  align-items: center;
  gap: 8px;
}
.ai-character-count {
  font-size: 9px;
  color: #b0baca;
  white-space: nowrap;
}
.ai-composer-actions .el-button {
  font-size: 11px;
}
.ai-composer-actions .icon-button {
  width: 25px;
  height: 27px;
}
.ai-composer-caption {
  margin-top: 12px;
  text-align: center;
  font-size: 9px;
  color: #a6b0be;
}
.ai-context-card {
  padding: 24px 22px;
}
.ai-context-card h3 {
  font-size: 14px;
  margin-top: 16px;
}
.ai-context-card > p {
  color: #97a4b6;
  font-size: 11px;
  margin-top: 8px;
}
.ai-profile-context {
  margin: 22px 0;
  padding-top: 18px;
  border-top: 1px solid var(--line);
}
.ai-profile-context > span {
  font-size: 10px;
  color: #8d9eb5;
}
.ai-profile-context > strong {
  display: block;
  font-weight: 500;
  color: #456285;
  font-size: 27px;
  margin: 9px 0 14px;
}
.ai-profile-context small {
  font-weight: 400;
  color: #9aaabd;
  font-size: 10px;
}
.ai-profile-context strong > span {
  display: block;
  color: #8f9eb3;
  font-size: 10px;
  margin-top: 5px;
  font-weight: 400;
}
.ai-profile-context > div {
  display: flex;
  gap: 6px;
  flex-wrap: wrap;
}
.ai-context-card > .text-button {
  margin-top: 18px;
  font-size: 11px;
}
.ai-profile-context + .text-button {
  margin-top: 0;
}
.ai-explore-note {
  padding: 27px 14px;
}
.ai-note-icon {
  color: #b7a17f;
}
.ai-explore-note h3 {
  font-size: 12px;
  color: #7d8da4;
  margin-top: 12px;
}
.ai-explore-note p {
  font-size: 10px;
  color: #9ba8ba;
  margin-top: 9px;
  line-height: 2;
}
.ai-explore-note .text-button {
  font-size: 10px;
  margin-top: 17px;
}
@media (max-width: 1250px) {
  .ai-chat-layout {
    grid-template-columns: minmax(0, 1fr) 225px;
    gap: 18px;
  }
  .ai-welcome {
    padding: 35px 22px 26px;
  }
  .ai-welcome h2 {
    font-size: 21px;
  }
  .ai-composer-toolbar {
    flex-wrap: wrap;
  }
  .ai-composer-actions {
    margin-left: auto;
  }
}
@media (max-width: 1020px) {
  .ai-chat-layout {
    grid-template-columns: minmax(0, 1fr);
  }
  .ai-chat-aside {
    display: grid;
    grid-template-columns: 1fr 1fr;
    gap: 18px;
  }
  .ai-context-card {
    padding: 22px;
  }
  .ai-profile-context {
    margin: 16px 0;
  }
  .ai-explore-note {
    padding: 22px 14px;
  }
}
@media (max-width: 760px) {
  .ai-transcript {
    padding: 18px 14px;
    min-height: 300px;
    max-height: 450px;
  }
  .ai-chat-message {
    max-width: 96%;
  }
  .ai-chat-message > p,
  .ai-chat-message > .ai-message-body {
    font-size: 12px;
    padding: 12px;
  }
  .ai-coming-soon {
    font-size: 8px;
    white-space: normal;
  }
  .ai-conversation-header {
    padding: 17px;
  }
  .ai-assistant-identity h3 {
    font-size: 11px;
  }
  .ai-assistant-identity p {
    font-size: 9px;
  }
  .ai-coming-soon {
    font-size: 9px;
  }
  .ai-welcome {
    padding: 31px 17px 22px;
  }
  .ai-welcome h2 {
    font-size: 19px;
    overflow-wrap: anywhere;
  }
  .ai-welcome > p {
    font-size: 10px;
  }
  .ai-question-grid {
    gap: 10px;
    margin-top: 24px;
  }
  .ai-question {
    padding: 14px 12px;
  }
  .ai-question-title {
    font-size: 10px;
    gap: 6px;
  }
  .ai-question-text {
    font-size: 9px;
  }
  .ai-composer-area {
    padding: 4px 14px 17px;
  }
  .ai-composer-toolbar > span {
    font-size: 8px;
  }
  .ai-composer-caption {
    font-size: 8px;
  }
  .ai-chat-aside {
    grid-template-columns: minmax(0, 1fr);
    gap: 0;
  }
  .ai-explore-note {
    padding: 22px 8px 0;
  }
}
</style>
