<script setup lang="ts">
import { ref, computed } from "vue";
import { useRoute, useRouter } from "vue-router";
import {
  LayoutDashboard,
  ContactRound,
  School,
  Sparkles,
  MessageCircle,
  Route,
  FolderHeart,
  Settings2,
  ArrowUpRight,
  Menu,
  X,
  ChevronDown,
  LogOut,
  CircleHelp,
  Bell,
  CheckCheck,
} from "lucide-vue-next";
import { ElMessageBox } from "element-plus/es/components/message-box/index";
import BrandLogo from "../components/BrandLogo.vue";
import { useAuth } from "../stores/auth";
import { usePlanner } from "../stores/planner";
import { api } from "../api";
const auth = useAuth();
const planner = usePlanner();
const route = useRoute();
const router = useRouter();
const mobileOpen = ref(false);
const showHelp = ref(false);
const notifications = ref(false);
const nav = [
  { path: "/", label: "规划概览", icon: LayoutDashboard },
  { path: "/profile", label: "考生画像", icon: ContactRound },
  { path: "/data", label: "招生数据中心", icon: School },
  { path: "/analysis", label: "智能院校匹配", icon: Sparkles },
  { path: "/ai-chat", label: "AI 问答", icon: MessageCircle },
  { path: "/planner", label: "志愿规划中心", icon: Route },
  { path: "/plans", label: "我的志愿方案", icon: FolderHeart },
];
const profile = computed(() => auth.user?.profile);
async function logout() {
  try {
    await ElMessageBox.confirm(
      "退出后，本机志愿草稿仍会保留。确定退出登录？",
      "退出登录",
      { confirmButtonText: "退出", cancelButtonText: "取消" },
    );
  } catch {
    return;
  }
  try {
    await api.logout();
    auth.clear();
    await router.replace("/login");
  } catch {
    /* API handles error */
  }
}
function command(value: string) {
  if (value === "logout") void logout();
  else void router.push("/account");
}
</script>
<template>
  <div class="app-shell">
    <div
      v-if="mobileOpen"
      class="sidebar-scrim"
      @click="mobileOpen = false"
    ></div>
    <aside :class="['sidebar', { 'is-open': mobileOpen }]">
      <RouterLink to="/" class="brand-link"><BrandLogo /></RouterLink
      ><button
        class="mobile-close icon-button"
        aria-label="收起导航"
        @click="mobileOpen = false"
      >
        <X :size="20" />
      </button>
      <div class="workspace-label">我的升学工作台 <span>2026</span></div>
      <nav class="main-nav">
        <RouterLink
          v-for="item in nav"
          :key="item.path"
          :to="item.path"
          :class="{ active: route.path === item.path }"
          @click="mobileOpen = false"
          ><component :is="item.icon" :size="19" :stroke-width="1.7" /><span>{{
            item.label
          }}</span
          ><span v-if="item.path === '/analysis'" class="nav-new">AI</span
          ><span v-if="item.path === '/ai-chat'" class="nav-new">AI</span
          ><span
            v-if="item.path === '/planner' && planner.items.length"
            class="nav-count"
            >{{ planner.items.length }}</span
          ></RouterLink
        >
      </nav>
      <div class="sidebar-bottom">
        <div class="sidebar-note">
          <span class="tiny-sun">✳</span>
          <h4>每一份热爱，都有方向</h4>
          <p>把选择交给认真思考，<br />把未来交给无限可能。</p>
          <RouterLink to="/analysis"
            >探索适合我的大学 <ArrowUpRight :size="14"
          /></RouterLink>
        </div>
        <button class="sidebar-help" @click="showHelp = true">
          <CircleHelp :size="17" />使用指南 <ArrowUpRight :size="14" /></button
        ><RouterLink to="/account" class="sidebar-help"
          ><Settings2 :size="17" />个人中心</RouterLink
        >
        <div class="sidebar-version">
          <span class="status-dot"></span>SunPath MVP <span>v1.0</span>
        </div>
      </div>
    </aside>
    <div class="main-shell">
      <header class="topbar">
        <div class="breadcrumb">
          <button
            class="icon-button mobile-menu"
            aria-label="展开导航"
            @click="mobileOpen = true"
          >
            <Menu :size="22" /></button
          ><span>工作台</span><span class="crumb-slash">/</span
          ><strong>{{ route.meta.title }}</strong>
        </div>
        <div class="topbar-right">
          <span class="data-status"
            ><span class="status-dot"></span>模拟数据环境</span
          ><el-popover
            v-model:visible="notifications"
            placement="bottom-end"
            :width="310"
            trigger="click"
            ><template #reference
              ><button
                class="icon-button notification-button"
                aria-label="查看通知"
              >
                <Bell :size="19" /><i></i></button
            ></template>
            <div class="notification">
              <CheckCheck :size="23" />
              <div>
                <strong>你的规划工作台已就绪</strong>
                <p>2026 模拟招生样本已加载。完善画像后，即可开始智能匹配。</p>
              </div>
            </div></el-popover
          ><span class="topbar-divider"></span
          ><el-dropdown @command="command"
            ><button class="user-menu">
              <span class="avatar">{{ auth.user?.name.slice(0, 1) }}</span
              ><span>{{ auth.user?.name }}</span
              ><ChevronDown :size="14" /></button
            ><template #dropdown
              ><el-dropdown-menu
                ><el-dropdown-item command="account">个人中心</el-dropdown-item
                ><el-dropdown-item command="logout" divided
                  ><LogOut :size="14" />　退出登录</el-dropdown-item
                ></el-dropdown-menu
              ></template
            ></el-dropdown
          >
        </div>
      </header>
      <main class="main-content"><RouterView /></main>
      <footer class="app-footer">
        <span>© 2026 SunPath 阳光志愿</span
        ><span
          >认真对待每一次选择
          <span class="footer-dot">·</span> 模拟数据仅供演示</span
        >
      </footer>
    </div>
    <el-dialog
      v-model="showHelp"
      title="从这里，开启你的升学规划"
      width="min(560px, 92vw)"
      ><div class="help-steps">
        <p>
          <b>01 · 完善考生画像</b
          ><br />填写生源省份、总分、位次和选科，选择地区与专业偏好。
        </p>
        <p>
          <b>02 · 探索与智能匹配</b
          ><br />浏览院校数据，查看同省近三年位次趋势和冲稳保推荐理由。
        </p>
        <p>
          <b>03 · 规划与保存</b><br />一键生成方案，调整顺序，保存后对比或导出
          CSV。
        </p>
      </div>
      <div class="notice">
        {{
          profile
            ? "你已完成考生画像，可以开始智能匹配。"
            : "你还未填写画像，建议先完成第一步。"
        }}
        <p>样本仅含 2026 计划与 2023–2025 录取记录，所有数据均为模拟。</p>
      </div>
      <template #footer
        ><el-button
          type="primary"
          @click="
            showHelp = false;
            router.push(profile ? '/analysis' : '/profile');
          "
          >开始我的规划</el-button
        ></template
      ></el-dialog
    >
  </div>
</template>
