<script setup lang="ts">
import { computed, reactive, ref } from "vue";
import {
  ArrowRight,
  Save,
  ContactRound,
  MapPin,
  Heart,
  Check,
} from "lucide-vue-next";
import { ElMessage } from "element-plus/es/components/message/index";
import { api } from "../api";
import { useAuth } from "../stores/auth";
import type { Profile } from "../api/types";
const auth = useAuth();
const busy = ref(false);
const form = reactive<Profile>(
  auth.user?.profile
    ? JSON.parse(JSON.stringify(auth.user.profile))
    : {
        province: "浙江",
        exam_year: 2026,
        score: 600,
        rank: 30000,
        subjects: [],
        regions: [],
        majors: [],
      },
);
const subjects = ["物理", "化学", "生物", "历史", "政治", "地理"];
const complete = computed(() => form.subjects.length === 3 && form.rank > 0);
async function save() {
  if (!complete.value)
    return ElMessage.warning("请填写有效位次并选择三门选考科目");
  busy.value = true;
  try {
    auth.user = (await api.profile(form)).data;
    ElMessage.success("考生画像已保存，推荐将按最新画像计算");
  } catch {
    /* API handles error */
  } finally {
    busy.value = false;
  }
}
</script>
<template>
  <div class="page-heading">
    <div>
      <div class="eyebrow">KNOW YOURSELF, FIND YOUR PATH</div>
      <h1>每条适合的路，都从了解你开始</h1>
      <p>填写你的成绩与兴趣，让推荐更贴近你的期待。</p>
    </div>
  </div>
  <div class="profile-layout">
    <form class="panel form-panel" @submit.prevent="save">
      <div class="form-section-title">
        <span class="metric-icon blue"><ContactRound :size="20" /></span>
        <div>
          <h3>我的高考信息</h3>
          <p>我们将使用同省位次进行匹配，分数仅作展示参考</p>
        </div>
      </div>
      <div class="form-grid">
        <label
          >高考省份<el-select v-model="form.province"
            ><el-option
              v-for="p in ['浙江', '江苏', '山东', '广东', '河南', '四川']"
              :key="p"
              :label="p"
              :value="p" /></el-select></label
        ><label
          >考试年份<el-select v-model="form.exam_year"
            ><el-option
              v-for="year in [2026, 2027]"
              :key="year"
              :label="`${year} 年`"
              :value="year" /></el-select></label
        ><label
          >高考总分<el-input-number
            v-model="form.score"
            :min="0"
            :max="750"
            controls-position="right"
          /><small>满分按 750 分模拟</small></label
        ><label
          >全省位次<el-input-number
            v-model="form.rank"
            :min="1"
            :max="2000000"
            controls-position="right"
          /><small>位次越小，排名越靠前</small></label
        >
      </div>
      <label class="field-label"
        >选考科目
        <span class="muted">已选 {{ form.subjects.length }} / 3</span></label
      ><el-checkbox-group
        v-model="form.subjects"
        :max="3"
        class="subject-options"
        ><el-checkbox-button v-for="s in subjects" :key="s" :value="s">{{
          s
        }}</el-checkbox-button></el-checkbox-group
      >
      <div class="form-section-title second">
        <span class="metric-icon orange"><Heart :size="20" /></span>
        <div>
          <h3>我的心之所向</h3>
          <p>偏好会影响推荐顺序，不会排除其他符合条件的院校</p>
        </div>
      </div>
      <label class="field-label">目标地区 <small>可多选</small></label
      ><el-select
        v-model="form.regions"
        multiple
        filterable
        placeholder="选择你想去的地方"
        ><el-option
          v-for="region in [
            '浙江',
            '上海',
            '江苏',
            '安徽',
            '湖北',
            '四川',
            '广东',
          ]"
          :key="region"
          :label="region"
          :value="region" /></el-select
      ><label class="field-label"
        >专业兴趣 <small>可多选，也可输入自定义方向</small></label
      ><el-select
        v-model="form.majors"
        multiple
        filterable
        allow-create
        default-first-option
        :multiple-limit="10"
        placeholder="选择或输入专业关键词"
        ><el-option
          v-for="major in [
            '计算机',
            '软件',
            '人工智能',
            '电子信息',
            '通信',
            '自动化',
            '经济',
            '工商管理',
            '新闻',
          ]"
          :key="major"
          :label="major"
          :value="major"
      /></el-select>
      <div class="form-actions">
        <span><Check :size="14" />仅用于你的专属志愿规划</span
        ><el-button
          type="primary"
          native-type="submit"
          size="large"
          :loading="busy"
          ><Save :size="16" />保存考生画像</el-button
        >
      </div>
    </form>
    <aside>
      <div class="profile-preview panel">
        <span class="preview-avatar">{{ auth.user?.name.slice(0, 1) }}</span>
        <h3>{{ auth.user?.name }}</h3>
        <p>
          <MapPin :size="13" />{{ form.province }} · {{ form.exam_year }} 届考生
        </p>
        <div class="profile-preview-score">
          <div>
            <strong>{{ form.score }}</strong
            ><small>高考总分</small>
          </div>
          <div>
            <strong>{{ form.rank?.toLocaleString() }}</strong
            ><small>全省位次</small>
          </div>
        </div>
        <div class="preview-tags">
          <span v-for="s in form.subjects" :key="s" class="tag">{{ s }}</span>
        </div>
        <RouterLink to="/analysis" class="primary-button"
          >前往智能匹配<ArrowRight :size="16"
        /></RouterLink>
      </div>
      <div class="notice">
        <strong>关于模拟数据</strong>
        <p>
          当前包含六省 2026 年招生计划及 2023–2025 年录取样本。选择 2027
          年时暂无招生计划，系统会明确返回空结果。
        </p>
        <p>专业组选科与数据均为演示用途，不能替代当地考试院正式规则。</p>
      </div>
    </aside>
  </div>
</template>
