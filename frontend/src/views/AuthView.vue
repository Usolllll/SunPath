<script setup lang="ts">
import { computed, ref } from "vue";
import { useRoute, useRouter } from "vue-router";
import {
  ArrowRight,
  Sun,
  Compass,
  ShieldCheck,
  Eye,
  EyeOff,
  ArrowUpRight,
} from "lucide-vue-next";
import BrandLogo from "../components/BrandLogo.vue";
import { useAuth } from "../stores/auth";
import { api } from "../api";
import { ElMessage } from "element-plus/es/components/message/index";
const register = ref(false);
const busy = ref(false);
const visible = ref(false);
const form = ref({ name: "", email: "", password: "" });
const auth = useAuth();
const router = useRouter();
const route = useRoute();
const title = computed(() =>
  register.value ? "让未来，从这里启程。" : "欢迎回来，未来的探索者。",
);
async function submit(demo = false) {
  if (busy.value) return;
  busy.value = true;
  try {
    const data = demo
      ? { name: "", email: "demo@sunpath.cn", password: "Sunpath2026!" }
      : form.value;
    const response =
      register.value && !demo
        ? await api.register(data)
        : await api.login(data);
    auth.accept(response.data);
    ElMessage.success(
      demo
        ? "已进入演示工作台"
        : register.value
          ? "注册成功，请完善考生画像"
          : "登录成功",
    );
    const redirect =
      typeof route.query.redirect === "string" &&
      route.query.redirect.startsWith("/") &&
      !route.query.redirect.startsWith("//")
        ? route.query.redirect
        : "/";
    await router.push(auth.user?.profile ? redirect : "/profile");
  } catch {
    /* The API interceptor presents the validation or network error. */
  } finally {
    busy.value = false;
  }
}
</script>
<template>
  <div class="auth-page">
    <section class="auth-story">
      <BrandLogo />
      <div class="auth-story-copy">
        <div class="eyebrow"><span></span>YOUR NEXT CHAPTER</div>
        <h1>每一种可能，<br />都值得<span>被看见。</span></h1>
        <p>
          从了解自己，到找到心之所向。<br />让数据为选择指路，让热爱有迹可循。
        </p>
        <div class="auth-orbit">
          <div class="orbit-circle orbit-one"></div>
          <div class="orbit-circle orbit-two"></div>
          <div class="orbit-sun"><Sun :size="52" :stroke-width="1.3" /></div>
          <div class="orbit-path"></div>
          <span class="orbit-label label-one"
            ><Compass :size="17" />探索你的无限可能</span
          ><span class="orbit-label label-two"
            ><span class="status-dot"></span>下一站，理想大学
            <ArrowUpRight :size="15"
          /></span>
        </div>
      </div>
      <div class="auth-story-footer">
        SUNPATH · 为每一个认真选择的你 <span>EST. 2026</span>
      </div>
    </section>
    <section class="auth-form-panel">
      <div class="auth-mobile-brand"><BrandLogo /></div>
      <div class="auth-form-wrap">
        <span class="auth-kicker">{{
          register ? "CREATE YOUR ACCOUNT" : "WELCOME TO SUNPATH"
        }}</span>
        <h2>{{ title }}</h2>
        <p class="auth-description">
          {{
            register
              ? "创建账号，开启属于你的志愿规划之旅。"
              : "登录阳光志愿，继续规划你的理想未来。"
          }}
        </p>
        <div class="auth-tabs">
          <button :class="{ active: !register }" @click="register = false">
            登录账号</button
          ><button :class="{ active: register }" @click="register = true">
            创建账号
          </button>
        </div>
        <form @submit.prevent="submit()">
          <label v-if="register"
            >你的称呼<input
              v-model="form.name"
              required
              maxlength="40"
              autocomplete="name"
              placeholder="例如：林同学" /></label
          ><label
            >邮箱地址<input
              v-model="form.email"
              type="email"
              required
              maxlength="254"
              autocomplete="email"
              placeholder="请输入你的邮箱" /></label
          ><label
            >登录密码
            <div class="password-input">
              <input
                v-model="form.password"
                :type="visible ? 'text' : 'password'"
                required
                minlength="8"
                maxlength="128"
                :autocomplete="register ? 'new-password' : 'current-password'"
                placeholder="至少 8 位字符"
              /><button
                type="button"
                :aria-label="visible ? '隐藏密码' : '显示密码'"
                @click="visible = !visible"
              >
                <EyeOff v-if="visible" :size="18" /><Eye v-else :size="18" />
              </button></div
          ></label>
          <p class="auth-persist">
            <ShieldCheck :size="14" />登录状态将在本机保留，请妥善保管账号
          </p>
          <button
            class="primary-button auth-submit"
            :disabled="busy"
            type="submit"
          >
            {{
              busy
                ? "正在连接…"
                : register
                  ? "创建账号，开始规划"
                  : "登录，继续我的规划"
            }}<ArrowRight :size="18" />
          </button>
        </form>
        <div class="auth-or"><span></span>先了解一下 SunPath<span></span></div>
        <button class="demo-button" :disabled="busy" @click="submit(true)">
          <Compass :size="17" />体验演示账号<ArrowUpRight :size="16" />
        </button>
        <p class="auth-disclaimer">
          MVP 原型 · 招生与录取数据均为模拟样本<br />为你的选择提供参考，不作录取承诺。
        </p>
      </div>
      <footer>© 2026 SunPath 阳光志愿 · 让每个选择更有方向</footer>
    </section>
  </div>
</template>
