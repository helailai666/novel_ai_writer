<template>
  <div class="dashboard">
    <div class="page-header">
      <div class="page-title">
        <div class="page-title-icon">📊</div>
        <div>
          <h2>项目仪表盘</h2>
          <n-text depth="3">全局数据总览</n-text>
        </div>
      </div>
      <div class="page-actions">
        <n-button secondary :loading="loading" @click="loadData">
          <template #icon><n-icon><RefreshOutline /></n-icon></template>
          刷新
        </n-button>
      </div>
    </div>

    <!-- 统计卡片 -->
    <n-grid :cols="isMobile ? 2 : 4" :x-gap="14" :y-gap="14">
      <n-grid-item v-for="card in statCards" :key="card.label">
        <n-card size="small" :bordered="false" class="stat-card">
          <div class="stat-icon" :style="{ background: card.bg, color: card.color }">{{ card.icon }}</div>
          <div class="stat-body">
            <div class="stat-value" :style="{ color: card.color }">{{ card.value }}</div>
            <div class="stat-label">{{ card.label }}</div>
          </div>
        </n-card>
      </n-grid-item>
    </n-grid>

    <!-- 进度条 -->
    <n-card title="📈 创作进度" size="small" style="margin-top:16px; border-radius: 12px;">
      <n-space vertical>
        <div v-for="item in progressItems" :key="item.label" class="progress-item">
          <div class="progress-label">
            <span>{{ item.label }}</span>
            <span>{{ item.current }}/{{ item.total }}</span>
          </div>
          <n-progress type="line" :percentage="item.pct" :indicator-placement="'inside'" :color="item.color" :height="10" :border-radius="5" />
        </div>
      </n-space>
    </n-card>

    <!-- 快速概览 -->
    <n-grid :cols="isMobile ? 1 : 2" :x-gap="16" style="margin-top:16px;">
      <n-grid-item>
        <n-card title="📑 最近章节" size="small" style="border-radius: 12px;">
          <template v-if="recentChapters.length">
            <n-thing
              v-for="ch in recentChapters"
              :key="ch.id"
              style="margin-bottom:10px;"
            >
              <template #header>
                <span style="font-weight:600;">第{{ ch.chapter_number }}章 {{ ch.title || '' }}</span>
                <n-tag size="tiny" :bordered="false" round style="margin-left:8px">{{ ch.word_count || 0 }}字</n-tag>
              </template>
              <n-text depth="3" style="font-size:12px">{{ (ch.content || '').slice(0, 60) }}…</n-text>
            </n-thing>
          </template>
          <n-empty v-else description="暂无章节" size="small" />
        </n-card>
      </n-grid-item>
      <n-grid-item>
        <n-card title="🔍 待办建议" size="small" style="border-radius: 12px;">
          <n-space vertical>
            <n-checkbox v-for="t in todos" :key="t.id" :checked="t.done" @update:checked="(v) => toggleTodo(t, v)" style="line-height: 1.8;">
              {{ t.text }}
            </n-checkbox>
          </n-space>
        </n-card>
      </n-grid-item>
    </n-grid>
  </div>
</template>

<script setup>
/**
 * DashboardView.vue — 项目仪表盘
 * 数据来自真实后端: 章节/角色/世界观/势力/大纲 计数
 */
import { ref, computed, onMounted, onUnmounted } from 'vue'
import { useRoute } from 'vue-router'
import { useMessage } from 'naive-ui'
import { RefreshOutline } from '@vicons/ionicons5'
import { projectAPI, writingAPI, settingsAPI } from '../api/index.js'

const route = useRoute()
const message = useMessage()
const pid = () => route.params.id

const isMobile = ref(false)
function check() { isMobile.value = window.innerWidth < 768 }
onMounted(() => { check(); window.addEventListener('resize', check) })
onUnmounted(() => window.removeEventListener('resize', check))

const loading = ref(true)
const project = ref({})

const statCards = ref([
  { icon: '📖', label: '章节数', value: '--', color: '#6C5CE7', bg: 'rgba(108,92,231,.12)' },
  { icon: '🎭', label: '角色数', value: '--', color: '#10B981', bg: 'rgba(16,185,129,.12)' },
  { icon: '🌍', label: '世界观条目', value: '--', color: '#3B82F6', bg: 'rgba(59,130,246,.12)' },
  { icon: '🏛️', label: '势力数', value: '--', color: '#F59E0B', bg: 'rgba(245,158,11,.14)' },
])

const progressItems = ref([
  { label: '章节创作', current: 0, total: 0, pct: 0, color: '#6C5CE7' },
  { label: '角色设定', current: 0, total: 0, pct: 0, color: '#10B981' },
  { label: '世界观', current: 0, total: 0, pct: 0, color: '#3B82F6' },
  { label: '势力', current: 0, total: 0, pct: 0, color: '#F59E0B' },
])

const recentChapters = ref([])

const todos = ref([
  { id: 1, text: '完善世界观设定', done: false },
  { id: 2, text: '创建主要角色档案', done: false },
  { id: 3, text: '编写前三章大纲', done: false },
  { id: 4, text: '检查章节一致性', done: false },
])

function toggleTodo(t, v) {
  t.done = v
}

async function loadData() {
  loading.value = true
  try {
    const [pRes, chaptersRes, charactersRes, worldRes, factionsRes, outlinesRes] = await Promise.all([
      projectAPI.getProject(pid()).catch(() => ({ data: {} })),
      writingAPI.getChapters(pid()).catch(() => ({ data: [] })),
      settingsAPI.getCharacters(pid()).catch(() => ({ data: [] })),
      settingsAPI.getWorldSettings(pid()).catch(() => ({ data: [] })),
      settingsAPI.getFactions(pid()).catch(() => ({ data: [] })),
      settingsAPI.getOutlines(pid()).catch(() => ({ data: [] })),
    ])

    project.value = pRes.data?.data || pRes.data || {}
    const chapters = chaptersRes.data?.data || chaptersRes.data || []
    const characters = charactersRes.data?.data || charactersRes.data || []
    const world = worldRes.data?.data || worldRes.data || []
    const factions = factionsRes.data?.data || factionsRes.data || []
    const outlines = outlinesRes.data?.data || outlinesRes.data || []

    statCards.value = [
      { icon: '📖', label: '章节数', value: String(chapters.length), color: '#6C5CE7', bg: 'rgba(108,92,231,.12)' },
      { icon: '🎭', label: '角色数', value: String(characters.length), color: '#10B981', bg: 'rgba(16,185,129,.12)' },
      { icon: '🌍', label: '世界观条目', value: String(world.length), color: '#3B82F6', bg: 'rgba(59,130,246,.12)' },
      { icon: '🏛️', label: '势力数', value: String(factions.length), color: '#F59E0B', bg: 'rgba(245,158,11,.14)' },
    ]

    const doneChapters = chapters.filter(c => c.status === 'done').length
    progressItems.value = [
      { label: '章节创作', current: doneChapters, total: Math.max(chapters.length, 10), pct: Math.round(doneChapters / Math.max(chapters.length, 10) * 100), color: '#6C5CE7' },
      { label: '角色设定', current: characters.length, total: Math.max(characters.length, 5), pct: Math.min(100, Math.round(characters.length / 5 * 100)), color: '#10B981' },
      { label: '世界观', current: world.length, total: Math.max(world.length, 4), pct: Math.min(100, Math.round(world.length / 4 * 100)), color: '#3B82F6' },
      { label: '大纲节点', current: outlines.length, total: Math.max(outlines.length, 4), pct: Math.min(100, Math.round(outlines.length / 4 * 100)), color: '#F59E0B' },
    ]

    recentChapters.value = [...chapters].reverse().slice(0, 5)
  } catch (e) {
    message.error(e.message || '加载失败')
  } finally {
    loading.value = false
  }
}
onMounted(loadData)
</script>

<style scoped>
.stat-card {
  display: flex;
  align-items: center;
  gap: 12px;
  background: #fff;
  border-radius: 12px;
}
.stat-icon {
  width: 40px;
  height: 40px;
  border-radius: 11px;
  display: flex;
  align-items: center;
  justify-content: center;
  font-size: 19px;
  flex-shrink: 0;
}
.stat-value { font-size: 23px; font-weight: 700; line-height: 1.2; }
.stat-label { font-size: 12px; color: #8a8f98; }
.progress-item { margin-bottom: 12px; }
.progress-label { display: flex; justify-content: space-between; margin-bottom: 4px; font-size: 13px; }
</style>
