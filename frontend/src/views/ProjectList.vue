<template>
  <div>
    <div class="page-header">
      <div class="page-title">
        <div class="page-title-icon">📚</div>
        <div>
          <h2>小说项目</h2>
          <n-text depth="3">管理你的全部创作项目</n-text>
        </div>
      </div>
      <div class="page-actions">
        <n-button secondary @click="importFileRef?.click()">
          <template #icon><n-icon><CloudUploadOutline /></n-icon></template>
          导入备份
        </n-button>
        <input
          ref="importFileRef"
          type="file"
          accept=".json,application/json"
          style="display:none"
          @change="handleImportFile"
        />
        <n-button type="primary" @click="openCreate">
          <template #icon><n-icon><AddOutline /></n-icon></template>
          新建项目
        </n-button>
      </div>
    </div>

    <!-- 统计卡片 -->
    <n-grid :cols="isMobile ? 2 : 4" :x-gap="14" :y-gap="14" style="margin-bottom: 22px;">
      <n-grid-item v-for="s in statItems" :key="s.label">
        <n-card size="small" :bordered="false" class="stat-card">
          <div class="stat-icon" :style="{ background: s.bg, color: s.color }">{{ s.icon }}</div>
          <div class="stat-body">
            <div class="stat-value" :style="{ color: s.color }">{{ s.value }}</div>
            <div class="stat-label">{{ s.label }}</div>
          </div>
        </n-card>
      </n-grid-item>
    </n-grid>

    <!-- 搜索 -->
    <n-input v-model:value="search" placeholder="搜索项目标题 / 类型..." clearable class="search-input">
      <template #prefix><n-icon><SearchOutline /></n-icon></template>
    </n-input>

    <!-- 新建对话框 -->
    <n-modal v-model:show="showCreate" preset="card" title="✍️ 新建小说" style="width: 500px; max-width: 94vw;" :mask-closable="false">
      <n-form :model="form" :rules="rules" ref="formRef" label-placement="top">
        <n-form-item label="作品标题" path="title">
          <n-input v-model:value="form.title" placeholder="如：凡人修仙传" @keyup.enter="handleCreate" />
        </n-form-item>
        <n-form-item label="类型" path="genre">
          <n-select v-model:value="form.genre" :options="genreOpts" filterable />
        </n-form-item>
        <n-form-item label="简介">
          <n-input v-model:value="form.synopsis" type="textarea" :rows="4" placeholder="一句话介绍你的故事..." />
        </n-form-item>
      </n-form>
      <template #footer>
        <n-button @click="showCreate = false" quaternary>取消</n-button>
        <n-button type="primary" @click="handleCreate" :loading="creating">创建作品</n-button>
      </template>
    </n-modal>

    <!-- 项目卡片 -->
    <n-grid v-if="filtered.length" :cols="isMobile ? 1 : isTablet ? 2 : 3" :x-gap="18" :y-gap="18">
      <n-grid-item v-for="p in filtered" :key="p.id">
        <n-card class="project-card hover-card" :bordered="true" @click="$router.push(`/projects/${p.id}`)">
          <template #header>
            <div class="project-card-head">
              <span class="project-card-title">{{ p.title }}</span>
              <n-tag size="small" :type="statusMeta(p.status).type" :bordered="false" round>
                {{ statusMeta(p.status).label }}
              </n-tag>
            </div>
          </template>
          <template #header-extra>
            <n-tag size="small" :bordered="false" type="info" round>{{ genreLabel(p.genre) }}</n-tag>
          </template>

          <n-ellipsis :line-clamp="3" class="project-synopsis">
            {{ p.synopsis || '（暂无简介，点击进入创作工作台开始写作）' }}
          </n-ellipsis>

          <div class="project-meta">
            <span>📅 {{ fmtDate(p.created_at) }}</span>
            <span v-if="p.skill_packs" class="skill-chip">🎯 {{ p.skill_packs }}</span>
          </div>

          <template #action>
            <div class="project-card-foot">
              <span class="foot-hint">进入创作工作台 →</span>
              <n-button size="tiny" quaternary type="error" @click.stop="removeProject(p)">
                <template #icon><n-icon><TrashOutline /></n-icon></template>
                删除
              </n-button>
            </div>
          </template>
        </n-card>
      </n-grid-item>
    </n-grid>
    <n-empty v-else-if="!loading" description="暂无项目，点击「新建项目」开始创作" style="margin-top:70px;" />

    <div class="list-loading" v-if="loading">
      <n-spin size="large" />
    </div>
  </div>
</template>

<script setup>
/**
 * ProjectList.vue — 项目列表
 * 适配后端 ProjectResponse: id/title/genre/synopsis/status(draft|writing|completed)/skill_packs/created_at/updated_at
 */
import { ref, computed, onMounted, onUnmounted } from 'vue'
import { useRouter } from 'vue-router'
import { useDialog, useMessage } from 'naive-ui'
import {
  AddOutline,
  CloudUploadOutline,
  SearchOutline,
  TrashOutline,
} from '@vicons/ionicons5'
import { projectAPI } from '../api/index.js'

const router = useRouter()
const message = useMessage()
const dialog = useDialog()
const importFileRef = ref(null)
const importing = ref(false)
const projects = ref([])
const loading = ref(true)
const showCreate = ref(false)
const creating = ref(false)
const search = ref('')
const formRef = ref(null)
const form = ref({ title: '', genre: 'fantasy', synopsis: '' })

const isMobile = ref(false)
const isTablet = ref(false)
function checkScreen() {
  const w = window.innerWidth
  isMobile.value = w < 768
  isTablet.value = w >= 768 && w < 1100
}
onMounted(() => { checkScreen(); window.addEventListener('resize', checkScreen) })
onUnmounted(() => window.removeEventListener('resize', checkScreen))

const genreOpts = [
  { label: '奇幻', value: 'fantasy' },
  { label: '玄幻', value: 'xuanhuan' },
  { label: '修仙', value: 'xiuxian' },
  { label: '言情', value: 'romance' },
  { label: '科幻', value: 'scifi' },
  { label: '悬疑', value: 'mystery' },
  { label: '都市', value: 'urban' },
  { label: '历史', value: 'history' },
  { label: '武侠', value: 'wuxia' },
  { label: '其他', value: 'other' },
]
function genreLabel(g) {
  return genreOpts.find((o) => o.value === g)?.label || g || '奇幻'
}
const rules = {
  title: [{ required: true, message: '请输入作品标题', trigger: 'blur' }],
}

const statusMeta = (s) => ({
  draft: { label: '草稿', type: 'default' },
  writing: { label: '创作中', type: 'warning' },
  completed: { label: '已完成', type: 'success' },
}[s] || { label: s || '草稿', type: 'default' })

const statItems = computed(() => {
  const all = projects.value
  const writing = all.filter((p) => p.status === 'writing').length
  const done = all.filter((p) => p.status === 'completed').length
  const draft = all.filter((p) => !p.status || p.status === 'draft').length
  return [
    { icon: '📚', label: '总项目', value: all.length, color: '#6C5CE7', bg: 'rgba(108,92,231,.12)' },
    { icon: '✍️', label: '创作中', value: writing, color: '#F59E0B', bg: 'rgba(245,158,11,.14)' },
    { icon: '📋', label: '草稿', value: draft, color: '#6B7280', bg: 'rgba(107,114,128,.12)' },
    { icon: '✅', label: '已完成', value: done, color: '#10B981', bg: 'rgba(16,185,129,.12)' },
  ]
})

const filtered = computed(() => {
  const q = search.value?.trim().toLowerCase()
  if (!q) return projects.value
  return projects.value.filter(
    (p) => p.title?.toLowerCase().includes(q) || genreLabel(p.genre).includes(q) || (p.synopsis || '').includes(q)
  )
})

function fmtDate(ts) {
  return ts ? String(ts).slice(0, 10) : '—'
}

function openCreate() {
  form.value = { title: '', genre: 'fantasy', synopsis: '' }
  showCreate.value = true
}

async function load() {
  loading.value = true
  try {
    const res = await projectAPI.getProjects()
    projects.value = res.data?.data || res.data || []
  } catch {
    projects.value = []
  } finally {
    loading.value = false
  }
}

async function handleCreate() {
  try {
    await formRef.value?.validate()
  } catch {
    return
  }
  creating.value = true
  try {
    const res = await projectAPI.createProject({ ...form.value })
    message.success('项目创建成功，开始创作吧 ✨')
    showCreate.value = false
    router.push(`/projects/${res.data.id}`)
  } catch {
    /* handled by interceptor */
  } finally {
    creating.value = false
  }
}

function removeProject(p) {
  dialog.warning({
    title: '删除项目',
    content: `确定删除「${p.title}」吗？该项目下的全部章节、设定、知识库数据都会被级联删除，不可恢复。`,
    positiveText: '删除',
    negativeText: '取消',
    onPositiveClick: async () => {
      try {
        await projectAPI.deleteProject(p.id)
        message.success('项目已删除')
        await load()
      } catch {
        message.error('删除失败')
      }
    },
  })
}

async function handleImportFile(e) {
  const file = e.target.files?.[0]
  e.target.value = ''
  if (!file) return
  if (importing.value) return
  importing.value = true
  try {
    const text = await file.text()
    const backup = JSON.parse(text)
    if (!backup?.project?.title) throw new Error('不是有效的备份文件（缺少 project.title）')
    const res = await projectAPI.importProject(backup)
    message.success(`已导入「${res.data?.title || backup.project.title}」`)
    router.push(`/projects/${res.data.id}`)
  } catch (err) {
    message.error(err.message || '导入失败，请选择导出的 JSON 备份')
  } finally {
    importing.value = false
  }
}

onMounted(load)
</script>

<style scoped>
.stat-card {
  display: flex;
  align-items: center;
  gap: 12px;
  background: #fff;
}

.stat-icon {
  width: 42px;
  height: 42px;
  border-radius: 12px;
  display: flex;
  align-items: center;
  justify-content: center;
  font-size: 20px;
  flex-shrink: 0;
}

.stat-body {
  min-width: 0;
}

.stat-value {
  font-size: 24px;
  font-weight: 700;
  line-height: 1.15;
}

.stat-label {
  font-size: 12px;
  color: #8a8f98;
}

.search-input {
  margin-bottom: 18px;
  max-width: 380px;
}

.project-card {
  border-radius: 14px;
}

.project-card-head {
  display: flex;
  align-items: center;
  gap: 8px;
  min-width: 0;
}

.project-card-title {
  font-weight: 700;
  font-size: 15px;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.project-synopsis {
  color: #6b7280;
  font-size: 13px;
  line-height: 1.7;
  min-height: 62px;
}

.project-meta {
  display: flex;
  align-items: center;
  gap: 10px;
  flex-wrap: wrap;
  margin-top: 10px;
  font-size: 12px;
  color: #9ca3af;
}

.skill-chip {
  background: rgba(245, 158, 11, 0.12);
  color: #b45309;
  padding: 1px 8px;
  border-radius: 999px;
}

.project-card-foot {
  display: flex;
  justify-content: space-between;
  align-items: center;
}

.foot-hint {
  font-size: 12px;
  color: #6c5ce7;
  font-weight: 500;
}

.list-loading {
  display: flex;
  justify-content: center;
  padding: 60px 0;
}
</style>
