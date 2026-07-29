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
    // 模拟从多个 API 聚合数据
    await new Promise(r => setTimeout(r, 800))
    statCards.value = [
      { label: '📖 章节数', value: '12', sub: '总章节', color: '#e94560' },
      { label: '🎭 角色数', value: '8', sub: '已创建', color: '#18a058' },
      { label: '🌍 世界观', value: '6', sub: '条目', color: '#2080f0' },
      { label: '🏛️ 势力数', value: '4', sub: '阵营', color: '#f0a020' },
    ]
    progressItems.value = [
      { label: '章节创作', current: 3, total: 12, pct: 25, color: '#e94560' },
      { label: '角色设定', current: 5, total: 8, pct: 62, color: '#18a058' },
      { label: '世界观', current: 4, total: 6, pct: 66, color: '#2080f0' },
      { label: '势力', current: 2, total: 4, pct: 50, color: '#f0a020' },
    ]
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
