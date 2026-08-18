<template>
  <n-spin :show="loading">
    <div class="page-header">
      <div class="page-title">
        <div class="page-title-icon">😂</div>
        <div>
          <h2>热梗库</h2>
          <n-text depth="3">网络流行语 · 供写作自然融入对话与场景</n-text>
        </div>
      </div>
      <div class="page-actions">
        <n-input v-model:value="keyword" placeholder="搜索热梗…" clearable style="width:200px" @update:value="loadMemes" />
        <n-button type="primary" @click="openCreate">
          <template #icon><n-icon><AddCircleOutline /></n-icon></template>
          新增热梗
        </n-button>
      </div>
    </div>

    <n-grid :cols="4" :x-gap="12" :y-gap="12" responsive="screen" item-responsive>
      <n-grid-item v-for="m in memes" :key="m.id" span="4 s:4 m:2 l:1">
        <n-card size="small" hoverable class="meme-card">
          <template #header>
            <n-space align="center" justify="space-between">
              <b>{{ m.phrase }}</b>
              <n-tag size="tiny" type="warning">{{ m.category }}</n-tag>
            </n-space>
          </template>
          <n-text depth="2">{{ m.meaning }}</n-text>
          <template #footer>
            <n-text depth="3" style="font-size:12px">例：{{ m.usage_example }}</n-text>
            <n-space style="margin-top:4px">
              <n-button size="tiny" quaternary @click="openEdit(m)">
                <template #icon><n-icon><CreateOutline /></n-icon></template>
                编辑
              </n-button>
              <n-button size="tiny" quaternary type="error" @click="removeMeme(m)">
                <template #icon><n-icon><TrashOutline /></n-icon></template>
                删除
              </n-button>
            </n-space>
          </template>
        </n-card>
      </n-grid-item>
    </n-grid>
    <n-empty v-if="!memes.length && !loading" description="暂无热梗，点击「新增热梗」添加" style="margin-top:48px" />

    <!-- 新增/编辑抽屉 -->
    <n-drawer v-model:show="showCreate" :width="480" placement="right">
      <n-drawer-content :title="editing ? `编辑热梗 · ${editing.phrase}` : '新增热梗'">
        <n-form label-placement="top">
          <n-form-item label="梗语"><n-input v-model:value="form.phrase" placeholder="如：破防了" /></n-form-item>
          <n-form-item label="含义"><n-input v-model:value="form.meaning" placeholder="这个梗是什么意思" /></n-form-item>
          <n-form-item label="用法示例"><n-input v-model:value="form.usage_example" type="textarea" :rows="3" placeholder="在小说中的用法示例" /></n-form-item>
          <n-space>
            <n-input v-model:value="form.category" placeholder="类别(搞笑/吐槽/战斗…)" style="width:200px" />
            <n-input v-model:value="form.tags" placeholder="标签(逗号分隔)" />
          </n-space>
          <n-space justify="end" style="margin-top:16px">
            <n-button type="primary" :loading="saving" @click="saveMeme">{{ editing ? '保存修改' : '保存' }}</n-button>
          </n-space>
        </n-form>
      </n-drawer-content>
    </n-drawer>
  </n-spin>
</template>

<script setup>
import { ref, reactive, computed, onMounted } from 'vue'
import { useRoute } from 'vue-router'
import { useMessage } from 'naive-ui'
import { AddCircleOutline, CreateOutline, TrashOutline } from '@vicons/ionicons5'
import { hotMemeAPI } from '../api/index.js'

const route = useRoute()
const message = useMessage()
const projectId = computed(() => route.params.id)

const loading = ref(false)
const saving = ref(false)
const memes = ref([])
const keyword = ref('')
const showCreate = ref(false)
const editing = ref(null)
const form = reactive({ phrase: '', meaning: '', usage_example: '', category: 'general', tags: '' })

onMounted(loadMemes)

async function loadMemes() {
  loading.value = true
  try {
    if (keyword.value.trim()) {
      const res = await hotMemeAPI.search(keyword.value.trim(), projectId.value)
      memes.value = res.data
    } else {
      const res = await hotMemeAPI.list(projectId.value)
      memes.value = res.data
    }
  } catch (e) {
    message.error(e.message || '加载失败')
  } finally {
    loading.value = false
  }
}

async function saveMeme() {
  if (!form.phrase) {
    message.warning('请填写梗语')
    return
  }
  saving.value = true
  try {
    if (editing.value) {
      await hotMemeAPI.update(editing.value.id, { ...form })
      message.success('已更新')
    } else {
      await hotMemeAPI.create({ ...form }, projectId.value)
      message.success('已添加')
    }
    showCreate.value = false
    editing.value = null
    Object.assign(form, { phrase: '', meaning: '', usage_example: '', category: 'general', tags: '' })
    loadMemes()
  } catch (e) {
    message.error(e.message || '保存失败')
  } finally {
    saving.value = false
  }
}

function openCreate() {
  editing.value = null
  Object.assign(form, { phrase: '', meaning: '', usage_example: '', category: 'general', tags: '' })
  showCreate.value = true
}

function openEdit(m) {
  editing.value = m
  Object.assign(form, {
    phrase: m.phrase, meaning: m.meaning || '', usage_example: m.usage_example || '',
    category: m.category || 'general', tags: m.tags || '',
  })
  showCreate.value = true
}

async function removeMeme(m) {
  const ok = await window.confirm(`确认删除「${m.phrase}」？`)
  if (!ok) return
  try {
    await hotMemeAPI.remove(m.id)
    message.success('已删除')
    loadMemes()
  } catch (e) {
    message.error(e.message || '删除失败')
  }
}
</script>

<style scoped>
.page-header {
  display: flex;
  justify-content: space-between;
  align-items: flex-start;
  margin-bottom: 16px;
}
.page-title { display: flex; align-items: center; gap: 12px; }
.page-header h2 { margin: 0 0 3px 0; }
.meme-card { height: 100%; border-radius: 12px; }
</style>
