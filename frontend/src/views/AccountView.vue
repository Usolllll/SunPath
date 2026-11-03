<script setup lang="ts">
import { reactive, ref } from "vue";
import {
  Save,
  ShieldCheck,
  LogOut,
  ArrowRight,
  Mail,
  UserRound,
} from "lucide-vue-next";
import { ElMessage } from "element-plus/es/components/message/index";
import { ElMessageBox } from "element-plus/es/components/message-box/index";
import { useRouter } from "vue-router";
import { useAuth } from "../stores/auth";
import { api } from "../api";
const auth = useAuth();
const router = useRouter();
const name = ref(auth.user?.name || "");
const password = reactive({
  current_password: "",
  new_password: "",
  confirm: "",
});
const saving = ref(false);
const changing = ref(false);
async function saveName() {
  if (!name.value.trim()) return ElMessage.warning("请输入你的称呼");
  saving.value = true;
  try {
    auth.user = (await api.name(name.value)).data;
    ElMessage.success("个人资料已更新");
  } catch {
    /* API handles error */
  } finally {
    saving.value = false;
  }
}
async function changePassword() {
  if (password.new_password !== password.confirm)
    return ElMessage.warning("两次输入的新密码不一致");
  if (password.new_password.length < 8)
    return ElMessage.warning("新密码至少 8 位");
  changing.value = true;
  try {
    await api.password(password);
    auth.clear();
    ElMessage.success("密码已修改，请重新登录");
    await router.replace("/login");
  } catch {
    /* API handles error */
  } finally {
    changing.value = false;
  }
}
async function logout() {
  try {
    await ElMessageBox.confirm("确定退出当前账号？", "退出登录", {
      confirmButtonText: "退出",
      cancelButtonText: "取消",
    });
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
</script>
<template>
  <div class="page-heading">
    <div>
      <div class="eyebrow">A LITTLE SPACE, ALL YOURS</div>
      <h1>我的账号与个人资料</h1>
      <p>管理你的个人信息，安心规划下一步。</p>
    </div>
  </div>
  <div class="account-layout">
    <section class="panel account-overview">
      <span class="preview-avatar">{{ auth.user?.name.slice(0, 1) }}</span>
      <h2>{{ auth.user?.name }}</h2>
      <p><Mail :size="14" />{{ auth.user?.email }}</p>
      <div class="account-links">
        <RouterLink to="/profile"
          ><UserRound :size="17" />我的考生画像<ArrowRight
            :size="15" /></RouterLink
        ><RouterLink to="/plans"
          ><Save :size="17" />我的志愿方案<ArrowRight :size="15"
        /></RouterLink>
      </div>
      <el-button @click="logout"><LogOut :size="16" />退出登录</el-button>
    </section>
    <div class="account-forms">
      <form class="panel form-panel" @submit.prevent="saveName">
        <div class="section-heading">
          <div>
            <h3>基本资料</h3>
            <p>让我们知道该如何称呼你</p>
          </div>
        </div>
        <label class="field-label">你的称呼</label
        ><el-input
          v-model="name"
          maxlength="40"
          show-word-limit
          placeholder="输入你的称呼"
        /><label class="field-label">登录邮箱</label
        ><el-input :model-value="auth.user?.email" disabled />
        <div class="form-actions">
          <span>邮箱作为当前账号的登录标识</span
          ><el-button type="primary" native-type="submit" :loading="saving"
            >保存资料</el-button
          >
        </div>
      </form>
      <form class="panel form-panel" @submit.prevent="changePassword">
        <div class="section-heading">
          <div>
            <h3><ShieldCheck :size="18" />账号安全</h3>
            <p>修改密码后，所有现有登录状态将失效</p>
          </div>
        </div>
        <label class="field-label">当前密码</label
        ><el-input
          v-model="password.current_password"
          type="password"
          show-password
          autocomplete="current-password"
          maxlength="128"
        /><label class="field-label">新密码</label
        ><el-input
          v-model="password.new_password"
          type="password"
          show-password
          autocomplete="new-password"
          maxlength="128"
          placeholder="至少 8 位字符"
        /><label class="field-label">确认新密码</label
        ><el-input
          v-model="password.confirm"
          type="password"
          show-password
          autocomplete="new-password"
          maxlength="128"
        />
        <div class="form-actions">
          <span>请使用与其他网站不同的密码</span
          ><el-button type="primary" native-type="submit" :loading="changing"
            >修改密码</el-button
          >
        </div>
      </form>
    </div>
  </div>
</template>
