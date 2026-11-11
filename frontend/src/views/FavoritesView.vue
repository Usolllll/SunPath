<script setup lang="ts">
import { computed, onMounted, ref } from "vue";
import {
  ArrowRight,
  Heart,
  Info,
  MapPin,
  RotateCcw,
  Sparkles,
  Trash2,
} from "lucide-vue-next";
import { useRouter } from "vue-router";
import { api } from "../api";
import type { Favorite } from "../api/types";
import { useFavorites } from "../stores/favorites";
import { date } from "../utils/format";
const router = useRouter();
const favorites = useFavorites();
const items = ref<Favorite[]>([]);
const busy = ref(false);
const failed = ref(false);
const removing = ref<number | null>(null);
const count = computed(() => items.value.length);
async function load() {
  busy.value = true;
  failed.value = false;
  try {
    items.value = (await api.favorites()).data;
    favorites.sync(items.value.map((item) => item.university.id));
  } catch {
    failed.value = true;
  } finally {
    busy.value = false;
  }
}
/** 取消收藏：先从列表移除，store 失败会回滚收藏状态，再重新拉列表保持一致 */
async function unfavorite(item: Favorite) {
  const id = item.university.id;
  if (removing.value === id) return;
  removing.value = id;
  const before = items.value;
  items.value = items.value.filter((x) => x.university.id !== id);
  const state = await favorites.remove(id, item.university.name);
  if (state === true) items.value = before;
  removing.value = null;
}
onMounted(() => {
  void favorites.load(true);
  void load();
});
</script>
<template>
  <div class="page-heading">
    <div>
      <div class="eyebrow">SAVE WHAT MOVES YOU</div>
      <h1>值得留意的大学，先收进自己的清单</h1>
      <p>
        收藏是真实账号行为（不是模拟数据），方便你回到智能匹配时快速找到心仪院校。
      </p>
    </div>
    <div class="heading-actions">
      <el-button type="primary" size="large" @click="router.push('/analysis')"
        ><Sparkles :size="16" />继续智能匹配</el-button
      >
    </div>
  </div>
  <div v-loading="busy" class="favorites-area">
    <div v-if="failed" class="empty-state">
      <p>收藏列表加载失败</p>
      <el-button @click="load">重新加载</el-button>
    </div>
    <div v-else-if="count" class="favorites-grid">
      <article
        v-for="item in items"
        :key="item.id"
        class="panel favorite-card"
      >
        <div class="favorite-top">
          <span class="favorite-avatar">{{
            item.university.name.slice(0, 1)
          }}</span>
          <div class="favorite-headline">
            <h3>{{ item.university.name }}</h3>
            <p>
              <MapPin :size="12" />{{ item.university.region }} ·
              {{ item.university.city }} · {{ item.university.category }}
            </p>
          </div>
          <Heart :size="15" fill="currentColor" class="favorite-heart" />
        </div>
        <div class="favorite-tags">
          <span
            v-for="level in item.university.level.split(' / ')"
            :key="level"
            class="tag"
            >{{ level }}</span
          >
          <span
            v-if="item.university.level_tier != null"
            class="tag tier-tag"
            :title="`院校层次分 ${item.university.level_tier}（仅内部排序参考）`"
            >层次 {{ item.university.level_tier }}</span
          >
        </div>
        <p class="favorite-time">收藏于 {{ date(item.created_at) }}</p>
        <div class="favorite-actions">
          <el-button @click="router.push('/analysis')"
            ><ArrowRight :size="14" />查看匹配</el-button
          ><button
            class="remove-favorite"
            :disabled="removing === item.university.id"
            :aria-label="`取消收藏${item.university.name}`"
            @click="unfavorite(item)"
          >
            <Trash2 :size="14" />取消收藏
          </button>
        </div>
      </article>
    </div>
    <el-empty
      v-else
      description="还没有收藏的院校，在智能匹配结果里点一下心形即可收藏"
      ><el-button type="primary" @click="router.push('/analysis')"
        >去智能匹配看看<ArrowRight :size="16" /></el-button
    ></el-empty>
  </div>
  <div class="data-disclaimer">
    <Info :size="15" />收藏记录保存在账号下（真实用户行为）；院校资料与匹配结果仍为模拟样本，仅供演示。
  </div>
</template>

<style scoped>
.favorites-area {
  min-height: 260px;
}
.favorites-grid {
  display: grid;
  grid-template-columns: repeat(auto-fill, minmax(300px, 1fr));
  gap: 18px;
}
.favorite-card {
  padding: 19px 20px 15px;
  display: flex;
  flex-direction: column;
  gap: 11px;
}
.favorite-top {
  display: flex;
  align-items: flex-start;
  gap: 12px;
}
.favorite-avatar {
  flex-shrink: 0;
  width: 44px;
  height: 44px;
  border-radius: 50%;
  display: inline-flex;
  align-items: center;
  justify-content: center;
  font-family: serif;
  font-size: 18px;
  font-weight: 700;
  color: #4f6b8f;
  background: #eef3fa;
  border: 1px solid #dfe9f5;
}
.favorite-headline {
  min-width: 0;
  flex: 1;
}
.favorite-headline h3 {
  font-size: 15px;
  color: #344c6c;
}
.favorite-headline p {
  display: flex;
  align-items: center;
  gap: 3px;
  flex-wrap: wrap;
  font-size: 10px;
  color: #94a1b3;
  margin-top: 5px;
}
.favorite-heart {
  color: #d57d8b;
  flex-shrink: 0;
}
.favorite-tags {
  display: flex;
  gap: 5px;
  flex-wrap: wrap;
}
.favorite-tags .tag {
  font-size: 9px;
}
.tier-tag {
  color: #9a8564 !important;
  background: #f8f4ec !important;
}
.favorite-time {
  font-size: 10px;
  color: #a5b0bf;
}
.favorite-actions {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 10px;
  border-top: 1px solid #f1f4f8;
  padding-top: 12px;
  margin-top: auto;
}
.favorite-actions .el-button {
  font-size: 11px;
}
.remove-favorite {
  display: inline-flex;
  align-items: center;
  gap: 5px;
  font-size: 10px;
  color: #a6afbd;
  background: none;
  padding: 4px 2px;
}
.remove-favorite:hover {
  color: #cf6a6a;
}
.remove-favorite:disabled {
  opacity: 0.5;
}
</style>
