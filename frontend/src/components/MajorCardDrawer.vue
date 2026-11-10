<script setup lang="ts">
import { ref, watch } from "vue";
import { AlertCircle, BookOpen, Briefcase, Compass, Info, UserRound } from "lucide-vue-next";
import { api } from "../api";
import type { MajorCard } from "../api/types";
import { riasecLabel } from "../utils/decision";
const props = defineProps<{ name: string | null }>();
const open = defineModel<boolean>({ required: true });
const card = ref<MajorCard | null>(null);
const loading = ref(false);
const missing = ref(false);
async function load(name: string | null) {
  if (!name) return;
  loading.value = true;
  missing.value = false;
  card.value = null;
  try {
    card.value = (await api.majorDetail(name)).data;
  } catch {
    missing.value = true;
  } finally {
    loading.value = false;
  }
}
watch(
  () => [open.value, props.name] as const,
  ([isOpen, name]) => {
    if (isOpen) void load(name);
  },
);
</script>
<template>
  <el-drawer
    v-model="open"
    :title="name ? `专业介绍卡 · ${name}` : '专业介绍卡'"
    size="min(560px, 100%)"
    append-to-body
  >
    <div v-if="loading" v-loading="true" class="major-card-loading">
      正在读取已收录的专业卡…
    </div>
    <div v-else-if="card" class="major-card-body">
      <header class="major-card-head">
        <h2>
          {{ card.name }}<small>{{ card.code }}</small>
        </h2>
        <div class="major-card-tags">
          <span class="tag">{{ card.category }}</span>
          <span class="tag">{{ card.major_class }}</span>
          <span class="tag subtle">as_of {{ card.as_of }}</span>
        </div>
      </header>
      <section class="major-section">
        <h3><BookOpen :size="16" />学什么</h3>
        <p>{{ card.study_what }}</p>
      </section>
      <section class="major-section">
        <h3><UserRound :size="16" />适合谁</h3>
        <p>{{ card.fit_for }}</p>
      </section>
      <section class="major-section">
        <h3><AlertCircle :size="16" />难在哪</h3>
        <p>{{ card.hard_where }}</p>
      </section>
      <section class="major-section">
        <h3><Briefcase :size="16" />去哪里</h3>
        <p>{{ card.career_where }}</p>
      </section>
      <section class="major-section">
        <h3><Compass :size="16" />兴趣类型（RIASEC）</h3>
        <div class="major-riasec">
          <span v-for="key in card.riasec_main" :key="`main-${key}`" class="tag warm"
            >主 · {{ riasecLabel(key) }}</span
          >
          <span
            v-for="key in card.riasec_secondary"
            :key="`second-${key}`"
            class="tag"
            >次 · {{ riasecLabel(key) }}</span
          >
        </div>
      </section>
      <p class="major-source">
        来源：{{ card.source }} · 更新于 {{ card.as_of }}
      </p>
      <div class="major-disclaimer">
        <Info :size="14" />{{ card.disclaimer }}
      </div>
    </div>
    <el-empty v-else description="该专业暂未收录介绍卡">
      <p class="muted">
        介绍卡只覆盖部分专业；未收录不等于专业不存在，可查看院校专业组或阳光高考专业知识库。
      </p>
    </el-empty>
  </el-drawer>
</template>
