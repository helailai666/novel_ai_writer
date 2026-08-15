<template>
  <div class="dashboard">
    <div class="page-header">
      <div class="page-title">
        <h2>📊 项目仪表盘</h2>
        <n-text depth="3">全局数据总览</n-text>
      </div>
      <n-button @click="loadData" :loading="loading">🔄 刷新</n-button>
    </div>

    <!-- 统计卡片 -->
    <n-grid :cols="isMobile ? 2 : 4" :x-gap="16" :y-gap="16">
      <n-grid-item v-for="card in statCards" :key="card.label">
        <n-card :title="card.label" size="small" hoverable>
          <div class="stat-value" :style="{ color: card.color }">{{ card.value }}</div>
          <n-text depth="3" style="font-size:13px;">{{ card.sub }}</n-text>
        </n-card>
      </n-grid-item>
    </n-grid>

    <!-- 进度条 -->
    <n-card title="📈 创作进度" style="margin-top:16px;">
      <n-space vertical>
        <div v-for="item in progressItems" :key="item.label" class="progress-item">
          <div class="progress-label">
            <span>{{ item.label }}</span>
            <span>{{ item.current }}/{{ item.total }}</span>
          </div>
          <n-progress type="line" :percentage="item.pct" :indicator-placement="'inside'" :color="item.color" />
        </div>
      </n-space>
    </n-card>

    <!-- 快速概览 -->
    <n-grid :cols="isMobile ? 1 : 2" :x-gap="16" style="margin-top:16px;">
      <n-grid-item>
        <n-card title="🕐 近期活动">
          <template v-if="activities.length">
            <n-thing v-for="act in activities" :key="act.time" style="margin-bottom:8px;">
              <template #description>{{ act.time }}</template>
              {{ act.text }}
            </n-thing>
          </template>
          <n-empty v-else description="暂无活动记录" />
        </n-card>
      </n-grid-item>
      <n-grid-item>
        <n-card title="⚠️ 待办事项">
          <n-checkbox-group v-model:value="checkedTodos">
            <n-space vertical>
              <n-checkbox v-for="t in todos" :key="t.id" :value="t.id" :style="{ textDecoration: checkedTodos.includes(t.id) ? 'line-through' : 'none' }">
                {{ t.text }}
              </n-checkbox>
            </n-space>
          </n-checkbox-group>
        </n-card>
      </n-grid-item>
    </n-grid>
  </div>
</template>

<script setup>
import { ref, onMounted, onUnmounted } from 'vue'
import { useRoute } from 'vue-router'
import { projectAPI, writingAPI, settingsAPI } from '../api/index.js'

const route = useRoute()
const pid = () => route.params.id

const isMobile = ref(false)
function check() { isMobile.value = window.innerWidth < 768 }
onMounted(() => { check(); window.addEventListener('resize', check) })
onUnmounted(() => window.removeEventListener('resize', check))

const loading = ref(true)
const checkedTodos = ref([])

// 统计卡片
const statCards = ref([
  { label: '📖 章节数', value: '--', sub: '总章节', color: '#e94560' },
  { label: '🎭 角色数', value: '--', sub: '已创建', color: '#18a058' },
  { label: '🌍 世界观', value: '--', sub: '条目', color: '#2080f0' },
  { label: '🏛️ 势力数', value: '--', sub: '阵营', color: '#f0a020' },
])

// 进度项
const progressItems = ref([
  { label: '章节创作', current: 0, total: 0, pct: 0, color: '#e94560' },
  { label: '角色设定', current: 0, total: 0, pct: 0, color: '#18a058' },
  { label: '世界观', current: 0, total: 0, pct: 0, color: '#2080f0' },
  { label: '势力', current: 0, total: 0, pct: 0, color: '#f0a020' },
])

const activities = ref([
  { time: '刚刚', text: '仪表盘加载完成，数据就绪' },
])
const todos = ref([
  { id: 1, text: '完善世界观设定' },
  { id: 2, text: '创建主要角色档案' },
  { id: 3, text: '编写前三章大纲' },
  { id: 4, text: '检查章节一致性' },
])

async function loadData() {
  loading.value = true
  try {
    const [chaptersRes, charactersRes, worldRes, factionsRes] = await Promise.all([
      writingAPI.getChapters(pid()).catch(() => ({ data: [] })),
      settingsAPI.getCharacters(pid()).catch(() => ({ data: [] })),
      settingsAPI.getWorldSettings(pid()).catch(() => ({ data: [] })),
      settingsAPI.getFactions(pid()).catch(() => ({ data: [] })),
    ])

    const chapters = chaptersRes.data || []
    const characters = charactersRes.data || []
    const world = worldRes.data || []
    const factions = factionsRes.data || []

    statCards.value = [
      { label: '📖 章节数', value: String(chapters.length), sub: '总章节', color: '#e94560' },
      { label: '🎭 角色数', value: String(characters.length), sub: '已创建', color: '#18a058' },
      { label: '🌍 世界观', value: String(world.length), sub: '条目', color: '#2080f0' },
      { label: '🏛️ 势力数', value: String(factions.length), sub: '阵营', color: '#f0a020' },
    ]

    const totalChapters = Math.max(chapters.length, 10)
    const doneChapters = chapters.filter(c => c.status === 'done').length
    progressItems.value = [
      { label: '章节创作', current: doneChapters, total: totalChapters, pct: Math.round(doneChapters / totalChapters * 100), color: '#e94560' },
      { label: '角色设定', current: characters.length, total: Math.max(characters.length, 5), pct: characters.length > 0 ? 100 : 0, color: '#18a058' },
      { label: '世界观', current: world.length, total: Math.max(world.length, 4), pct: world.length > 0 ? 100 : 0, color: '#2080f0' },
      { label: '势力', current: factions.length, total: Math.max(factions.length, 3), pct: factions.length > 0 ? 100 : 0, color: '#f0a020' },
    ]
  } catch (e) {
    // 保持默认值
  } finally { loading.value = false }
}
onMounted(loadData)
</script>

<style scoped>
.page-header { display:flex; justify-content:space-between; align-items:flex-start; margin-bottom:16px; }
.page-header h2 { margin:0 0 4px 0; }
.stat-value { font-size:32px; font-weight:700; line-height:1.2; }
.progress-item { margin-bottom:12px; }
.progress-label { display:flex; justify-content:space-between; margin-bottom:4px; font-size:14px; }
@media (max-width:768px) { .page-header { flex-direction:column; gap:12px; } }
</style>
