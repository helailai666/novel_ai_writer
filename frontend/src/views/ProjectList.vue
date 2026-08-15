<template>
  <div>
    <div style="display: flex; justify-content: space-between; align-items: center; margin-bottom: 20px;">
      <n-h2>📋 小说项目</n-h2>
      <n-button type="primary" @click="showCreate = true">➕ 新建项目</n-button>
    </div>

    <!-- 统计卡片 -->
    <n-grid :cols="4" :x-gap="12" style="margin-bottom: 20px;">
      <n-grid-item><n-statistic label="总项目" :value="stats.total" /></n-grid-item>
      <n-grid-item><n-statistic label="创作中" :value="stats.active" /></n-grid-item>
      <n-grid-item><n-statistic label="已完成" :value="stats.done" /></n-grid-item>
      <n-grid-item><n-statistic label="总字数" :value="stats.words" /></n-grid-item>
    </n-grid>

    <!-- 搜索 -->
    <n-input v-model:value="search" placeholder="搜索项目..." clearable style="margin-bottom: 16px;" />

    <!-- 新建对话框 -->
    <n-modal v-model:show="showCreate" title="新建小说" preset="card" style="width: 480px;" :mask-closable="false">
      <n-form :model="form" :rules="rules" ref="formRef">
        <n-form-item label="标题" path="title">
          <n-input v-model:value="form.title" placeholder="输入小说名称" />
        </n-form-item>
        <n-form-item label="类型" path="genre">
          <n-select v-model:value="form.genre" :options="genreOpts" />
        </n-form-item>
        <n-form-item label="简介">
          <n-input v-model:value="form.synopsis" type="textarea" :rows="3" placeholder="输入小说简介..." />
        </n-form-item>
      </n-form>
      <template #footer>
        <n-button @click="showCreate = false" quaternary>取消</n-button>
        <n-button type="primary" @click="handleCreate" :loading="creating">创建</n-button>
      </template>
    </n-modal>

    <!-- 项目卡片 -->
    <n-grid :cols="3" :x-gap="16" :y-gap="16">
      <n-grid-item v-for="p in filtered" :key="p.id">
        <n-card :title="p.title" hoverable @click="$router.push(`/projects/${p.id}`)">
          <template #header-extra><n-tag size="small">{{ p.genre }}</n-tag></template>
          <p style="color:#888;font-size:13px;">
            风格: {{ p.style || '未设' }}<br/>
            章节: {{ p.chapter_count || 0 }} / {{ p.total_chapters || '?' }}<br/>
            创建: {{ p.created_at?.slice(0,10) || '-' }}
          </p>
          <template #footer>
            <n-progress type="line" :percentage="p.progress || 0" :indicator-placement="'inside'" />
          </template>
        </n-card>
      </n-grid-item>
    </n-grid>
    <n-empty v-if="!loading && filtered.length === 0" description="暂无项目" style="margin-top:60px;" />
    <n-spin v-if="loading" style="margin-top:60px;" />
  </div>
</template>

<script setup>
import { ref, computed, onMounted } from 'vue'
import { useRouter } from 'vue-router'
import { projectAPI } from '../api/index.js'

const router = useRouter()
const projects = ref([])
const loading = ref(true)
const showCreate = ref(false)
const creating = ref(false)
const search = ref('')
const formRef = ref(null)
const form = ref({ title: '', genre: '玄幻', synopsis: '' })

const genreOpts = '玄幻,修仙,言情,科幻,悬疑,都市,历史,武侠'.split(',').map(v => ({ label: v, value: v }))
const rules = { title: { required: true, message: '请输入标题', trigger: 'blur' }, genre: { required: true, message: '请选择类型', trigger: 'change' } }

const stats = computed(() => {
  const all = projects.value
  return { total: all.length, active: all.filter(p => (p.progress || 0) < 100).length, done: all.filter(p => (p.progress || 0) >= 100).length, words: all.reduce((s, p) => s + (p.word_count || 0), 0) }
})
const filtered = computed(() => {
  const q = search.value?.toLowerCase()
  return q ? projects.value.filter(p => p.title?.toLowerCase().includes(q) || p.genre?.includes(q)) : projects.value
})

async function load() {
  loading.value = true
  try {
    const res = await projectAPI.getProjects()
    projects.value = res.data?.data || res.data || []
  } catch { projects.value = [] }
  finally { loading.value = false }
}

async function handleCreate() {
  creating.value = true
  try {
    await projectAPI.createProject({ title: form.value.title, genre: form.value.genre, synopsis: form.value.synopsis })
    showCreate.value = false
    form.value = { title: '', genre: '玄幻', synopsis: '' }
    await load()
  } catch { /* handled by interceptor */ }
  finally { creating.value = false }
}

onMounted(load)
</script>
