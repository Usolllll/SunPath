import { createRouter, createWebHistory } from "vue-router";
import { useAuth } from "../stores/auth";
const router = createRouter({
  history: createWebHistory(),
  routes: [
    {
      path: "/login",
      component: () => import("../views/AuthView.vue"),
      meta: { public: true, title: "登录" },
    },
    {
      path: "/",
      component: () => import("../layouts/AppLayout.vue"),
      children: [
        {
          path: "",
          name: "dashboard",
          component: () => import("../views/DashboardView.vue"),
          meta: { title: "规划概览", subtitle: "DASHBOARD" },
        },
        {
          path: "profile",
          component: () => import("../views/ProfileView.vue"),
          meta: { title: "考生画像", subtitle: "MY PROFILE" },
        },
        {
          path: "data",
          component: () => import("../views/DataView.vue"),
          meta: { title: "招生数据中心", subtitle: "EXPLORER" },
        },
        {
          path: "analysis",
          component: () => import("../views/AnalysisView.vue"),
          meta: { title: "智能院校匹配", subtitle: "SMART MATCH" },
        },
        {
          path: "ai-chat",
          component: () => import("../views/AiChatView.vue"),
          meta: { title: "AI 问答", subtitle: "AI ASSISTANT" },
        },
        {
          path: "planner",
          component: () => import("../views/PlannerView.vue"),
          meta: { title: "志愿规划中心", subtitle: "MY PATH" },
        },
        {
          path: "plans",
          component: () => import("../views/PlansView.vue"),
          meta: { title: "我的志愿方案", subtitle: "SAVED PLANS" },
        },
        {
          path: "account",
          component: () => import("../views/AccountView.vue"),
          meta: { title: "个人中心", subtitle: "ACCOUNT" },
        },
      ],
    },
    { path: "/:pathMatch(.*)*", redirect: "/" },
  ],
});
router.beforeEach(async (to) => {
  const auth = useAuth();
  await auth.load();
  if (!to.meta.public && !auth.token)
    return { path: "/login", query: { redirect: to.fullPath } };
  if (to.path === "/login" && auth.token) return "/";
  document.title = `${to.meta.title || "阳光志愿"} · SunPath`;
});
export default router;
