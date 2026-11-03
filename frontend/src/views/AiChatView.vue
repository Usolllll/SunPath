<script setup lang="ts">
import { computed, ref } from "vue";
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
} from "lucide-vue-next";
import { useAuth } from "../stores/auth";

const auth = useAuth();
const question = ref("");
const input = ref<{ focus: () => void }>();
const profile = computed(() => auth.user?.profile);
const suggestions = [
  { icon: School, title: "院校怎么选", text: "选择大学时，应该重点考虑哪些因素？" },
  { icon: BookOpen, title: "专业怎么挑", text: "计算机科学与技术和软件工程有什么区别？" },
  { icon: Route, title: "梯度怎么排", text: "冲、稳、保志愿应该怎样合理搭配？" },
  { icon: Compass, title: "方向怎么找", text: "如何结合自己的兴趣，确定适合的专业方向？" },
];

function chooseQuestion(text: string) {
  question.value = text;
  input.value?.focus();
}
</script>

<template>
  <div class="page-heading">
    <div>
      <div class="eyebrow">A LITTLE CLARITY FOR EVERY CHOICE</div>
      <h1>关于未来的疑问，都可以从这里开始</h1>
      <p>聊聊院校、专业与志愿规划，让每一个选择更清晰。</p>
    </div>
    <span class="tag warm ai-preview-label"><Sparkles :size="13" />功能预览</span>
  </div>

  <div class="ai-chat-layout">
    <section class="panel ai-conversation" aria-label="AI 问答预览">
      <header class="ai-conversation-header">
        <div class="ai-assistant-identity">
          <span class="ai-small-avatar"><Sparkles :size="18" /></span>
          <div><h3>SunPath 升学助手</h3><p>陪你梳理选择，探索更多可能</p></div>
        </div>
        <span class="ai-coming-soon"><span class="status-dot"></span>即将开放</span>
      </header>

      <div class="ai-welcome">
        <div class="ai-welcome-mark"><Sparkles :size="34" :stroke-width="1.4" /></div>
        <span class="eyebrow">HELLO, FUTURE EXPLORER</span>
        <h2>{{ auth.user?.name }}，今天想了解什么？</h2>
        <p>面对重要的选择，有疑问很正常。<br />先选一个你关心的话题，或写下自己的问题。</p>
        <div class="ai-question-grid">
          <button v-for="item in suggestions" :key="item.title" class="ai-question" @click="chooseQuestion(item.text)">
            <span class="ai-question-title"><component :is="item.icon" :size="17" />{{ item.title }}<ArrowUpRight :size="14" /></span>
            <span class="ai-question-text">{{ item.text }}</span>
          </button>
        </div>
      </div>

      <div class="ai-composer-area">
        <div class="ai-composer">
          <el-input ref="input" v-model="question" type="textarea" :rows="3" maxlength="1000" resize="none" aria-label="你的升学问题" placeholder="写下你的升学问题，例如：我的位次适合哪些院校？" />
          <div class="ai-composer-toolbar">
            <span>问答服务尚未接入，当前无法发送问题</span>
            <div class="ai-composer-actions">
              <span class="ai-character-count">{{ question.length }} / 1000</span>
              <button v-if="question" class="icon-button" aria-label="清空问题" @click="question = ''; input?.focus()"><X :size="16" /></button>
              <el-button type="primary" disabled aria-label="发送问题（功能尚未开放）"><ArrowUp :size="16" />发送</el-button>
            </div>
          </div>
        </div>
        <p class="ai-composer-caption">当前仅展示界面，输入内容不会发送；离开页面后不保留。</p>
      </div>
    </section>

    <aside class="ai-chat-aside">
      <section class="panel ai-context-card">
        <span class="metric-icon blue"><ContactRound :size="19" /></span>
        <h3>从了解你开始</h3>
        <p>完善考生画像，先为自己的选择整理一份清晰的参考。</p>
        <div v-if="profile" class="ai-profile-context">
          <span>{{ profile.province }} · {{ profile.exam_year }} 届</span>
          <strong>{{ profile.score }}<small> 分</small><span>全省 {{ profile.rank.toLocaleString('zh-CN') }} 位</span></strong>
          <div><span v-for="subject in profile.subjects" :key="subject" class="tag">{{ subject }}</span></div>
        </div>
        <RouterLink to="/profile" class="text-button">{{ profile ? '查看我的考生画像' : '完善我的考生画像' }}<ArrowUpRight :size="14" /></RouterLink>
      </section>
      <section class="ai-explore-note">
        <span class="ai-note-icon"><MessageCircle :size="19" /></span>
        <h3>好问题，是好选择的起点</h3>
        <p>可以先想想：你更在意学习的内容、大学所在的城市，还是未来想从事的工作？</p>
        <RouterLink to="/data" class="text-button">先去探索院校与专业<ArrowUpRight :size="14" /></RouterLink>
      </section>
    </aside>
  </div>
</template>

<style scoped>
.ai-preview-label { gap: 6px; padding: 6px 10px; }
.ai-chat-layout { display: grid; grid-template-columns: minmax(0, 1fr) 260px; gap: 23px; padding-bottom: 20px; align-items: start; }
.ai-conversation { overflow: hidden; }
.ai-conversation-header { display: flex; align-items: center; justify-content: space-between; gap: 12px; padding: 19px 25px; border-bottom: 1px solid var(--line); }
.ai-assistant-identity { display: flex; align-items: center; gap: 11px; }
.ai-small-avatar { display: inline-flex; align-items: center; justify-content: center; width: 35px; height: 35px; border-radius: 10px; background: #f8f0e4; color: #bd965e; }
.ai-assistant-identity h3 { font-size: 12px; }
.ai-assistant-identity p { font-size: 10px; color: #9aa6b7; margin-top: 2px; }
.ai-coming-soon { display: flex; align-items: center; gap: 6px; font-size: 10px; color: #a4947b; white-space: nowrap; }
.ai-coming-soon .status-dot { width: 5px; height: 5px; }
.ai-welcome { max-width: 680px; margin: 0 auto; padding: 43px 32px 30px; text-align: center; }
.ai-welcome-mark { display: flex; align-items: center; justify-content: center; width: 70px; height: 70px; border: 1px solid #f2e5cf; border-radius: 21px; color: #c6a06b; background: linear-gradient(145deg, #fff9ee, #f3f6fc); margin: 0 auto 22px; }
.ai-welcome > .eyebrow { display: block; font-size: 8px; letter-spacing: 1.7px; margin-bottom: 11px; }
.ai-welcome h2 { font-size: 23px; color: #365171; }
.ai-welcome > p { font-size: 11px; color: #96a3b7; margin-top: 13px; line-height: 1.9; }
.ai-question-grid { display: grid; grid-template-columns: 1fr 1fr; gap: 13px; margin-top: 30px; text-align: left; }
.ai-question { padding: 17px 16px; border-radius: 8px; border: 1px solid #e8edf5; background: #fbfcfe; text-align: left; transition: border-color .15s, background .15s; }
.ai-question:hover { border-color: #b5cae9; background: #f4f7fd; }
.ai-question-title { display: flex; align-items: center; gap: 9px; color: #6882a4; font-size: 11px; }
.ai-question-title > svg:last-child { margin-left: auto; color: #acbace; }
.ai-question-text { display: block; font-size: 10px; color: #9aa8ba; line-height: 1.9; margin-top: 10px; }
.ai-composer-area { padding: 8px 25px 19px; }
.ai-composer { border: 1px solid #e0e7f1; border-radius: 9px; padding: 6px 12px 10px; background: #fff; }
.ai-composer:focus-within { border-color: #a4bcde; box-shadow: 0 0 0 3px #f4f7fc; }
.ai-composer :deep(.el-textarea__inner) { box-shadow: none; font-family: inherit; font-size: 12px; padding: 10px 2px; background: transparent; line-height: 1.9; color: #536a88; }
.ai-composer :deep(.el-textarea__inner::placeholder) { color: #a7b2c2; font-size: 11px; }
.ai-composer-toolbar { display: flex; align-items: center; justify-content: space-between; gap: 8px; }
.ai-composer-toolbar > span { font-size: 9px; color: #a7b1c0; }
.ai-composer-actions { display: flex; align-items: center; gap: 8px; }
.ai-character-count { font-size: 9px; color: #b0baca; white-space: nowrap; }
.ai-composer-actions .el-button { font-size: 11px; }
.ai-composer-actions .icon-button { width: 25px; height: 27px; }
.ai-composer-caption { margin-top: 12px; text-align: center; font-size: 9px; color: #a6b0be; }
.ai-context-card { padding: 24px 22px; }
.ai-context-card h3 { font-size: 14px; margin-top: 16px; }
.ai-context-card > p { color: #97a4b6; font-size: 11px; margin-top: 8px; }
.ai-profile-context { margin: 22px 0; padding-top: 18px; border-top: 1px solid var(--line); }
.ai-profile-context > span { font-size: 10px; color: #8d9eb5; }
.ai-profile-context > strong { display: block; font-weight: 500; color: #456285; font-size: 27px; margin: 9px 0 14px; }
.ai-profile-context small { font-weight: 400; color: #9aaabd; font-size: 10px; }
.ai-profile-context strong > span { display: block; color: #8f9eb3; font-size: 10px; margin-top: 5px; font-weight: 400; }
.ai-profile-context > div { display: flex; gap: 6px; flex-wrap: wrap; }
.ai-context-card > .text-button { margin-top: 18px; font-size: 11px; }
.ai-profile-context + .text-button { margin-top: 0; }
.ai-explore-note { padding: 27px 14px; }
.ai-note-icon { color: #b7a17f; }
.ai-explore-note h3 { font-size: 12px; color: #7d8da4; margin-top: 12px; }
.ai-explore-note p { font-size: 10px; color: #9ba8ba; margin-top: 9px; line-height: 2; }
.ai-explore-note .text-button { font-size: 10px; margin-top: 17px; }
@media (max-width: 1250px) {
  .ai-chat-layout { grid-template-columns: minmax(0, 1fr) 225px; gap: 18px; }
  .ai-welcome { padding: 35px 22px 26px; }
  .ai-welcome h2 { font-size: 21px; }
  .ai-composer-toolbar { flex-wrap: wrap; }
  .ai-composer-actions { margin-left: auto; }
}
@media (max-width: 1020px) {
  .ai-chat-layout { grid-template-columns: minmax(0, 1fr); }
  .ai-chat-aside { display: grid; grid-template-columns: 1fr 1fr; gap: 18px; }
  .ai-context-card { padding: 22px; }
  .ai-profile-context { margin: 16px 0; }
  .ai-explore-note { padding: 22px 14px; }
}
@media (max-width: 760px) {
  .ai-conversation-header { padding: 17px; }
  .ai-assistant-identity h3 { font-size: 11px; }
  .ai-assistant-identity p { font-size: 9px; }
  .ai-coming-soon { font-size: 9px; }
  .ai-welcome { padding: 31px 17px 22px; }
  .ai-welcome h2 { font-size: 19px; overflow-wrap: anywhere; }
  .ai-welcome > p { font-size: 10px; }
  .ai-question-grid { gap: 10px; margin-top: 24px; }
  .ai-question { padding: 14px 12px; }
  .ai-question-title { font-size: 10px; gap: 6px; }
  .ai-question-text { font-size: 9px; }
  .ai-composer-area { padding: 4px 14px 17px; }
  .ai-composer-toolbar > span { font-size: 8px; }
  .ai-composer-caption { font-size: 8px; }
  .ai-chat-aside { grid-template-columns: minmax(0, 1fr); gap: 0; }
  .ai-explore-note { padding: 22px 8px 0; }
}
</style>
