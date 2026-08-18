<template>
  <n-spin :show="loading">
    <div class="page-header">
      <div class="page-title">
        <div class="page-title-icon">📜</div>
        <div>
          <h2>大纲编辑器</h2>
          <n-text depth="3">规划章节结构与剧情走向</n-text>
        </div>
      </div>
      <div class="page-actions">
        <n-button @click="aiGenerateOutline" :loading="aiLoading">
          <template #icon><n-icon><SparklesOutline /></n-icon></template>
          AI 生成大纲
        </n-button>
        <n-button type="primary" @click="openCreate">
          <template #icon><n-icon><AddCircleOutline /></n-icon></template>
          新建节点
        </n-button>
      </div>
    </div>

    <!-- 统计栏 -->
    <n-alert type="info" :bordered="false" closable style="margin-bottom:16px;">
      {{ outlineStats }}
    </n-alert>

    <!-- 大纲树 -->
    <n-card v-if="treeData.length" size="small" style="overflow:auto;">
      <n-tree
        :data="treeData"
        :default-expand-all="true"
        block-line
        :render-label="renderLabel"
        :render-prefix="renderPrefix"
      />
    </n-card>
    <n-empty v-else description="暂无大纲节点，点击上方按钮创建" style="margin-top:80px;" />

    <!-- 新建/编辑抽屉 -->
    <n-drawer v-model:show="drawerVisible" :width="480" placement="right">
      <n-drawer-content :title="editing ? '✏️ 编辑节点' : '➕ 新建大纲节点'" :closable="true">
        <n-form ref="formRef" :model="form" :rules="rules" label-placement="top">
          <n-form-item label="标题" path="title">
            <n-input v-model:value="form.title" placeholder="如：第三章·初入仙门" />
          </n-form-item>
          <n-form-item label="级别">
            <n-radio-group v-model:value="form.level">
              <n-radio :value="1">📖 卷</n-radio>
              <n-radio :value="2">📑 章</n-radio>
              <n-radio :value="3">📄 节</n-radio>
              <n-radio :value="4">📌 要点</n-radio>
            </n-radio-group>
          </n-form-item>
          <n-form-item label="状态">
            <n-radio-group v-model:value="form.status">
              <n-radio value="planned">📋 计划</n-radio>
              <n-radio value="writing">✍️ 写作中</n-radio>
              <n-radio value="done">✅ 已完成</n-radio>
            </n-radio-group>
          </n-form-item>
          <n-form-item label="排序">
            <n-input-number v-model:value="form.sort_order" :min="0" />
          </n-form-item>
          <n-form-item label="概要">
            <n-input v-model:value="form.summary" type="textarea" :rows="5" placeholder="剧情概要、关键事件..." />
          </n-form-item>
        </n-form>
        <template #footer>
          <n-space justify="end">
            <n-button @click="drawerVisible = false">取消</n-button>
            <n-button type="primary" @click="save" :loading="saving">{{ editing ? '保存' : '创建' }}</n-button>
          </n-space>
        </template>
      </n-drawer-content>
    </n-drawer>
  </n-spin>
</template>

<script setup>
import { ref, computed, h, onMounted } from 'vue'
import { useRoute } from 'vue-router'
import { useMessage } from 'naive-ui'
import { AddCircleOutline, SparklesOutline } from '@vicons/ionicons5'
import { settingsAPI, aiGenerateAPI } from '../api/index.js'

const route = useRoute()
const message = useMessage()
const pid = () => route.params.id

const loading = ref(true), saving = ref(false), aiLoading = ref(false)
const outlines = ref([]), drawerVisible = ref(false), editing = ref(null)
const formRef = ref(null)

const init = () => ({ title: '', level: 2, sort_order: 0, summary: '', status: 'planned' })
const form = ref(init())
const rules = { title: [{ required: true, message: '请输入标题', trigger: 'blur' }] }

// ── 构建树形数据 ────────────────────────────────────
const treeData = computed(() => {
  const map = {}
  const roots = []
  // 按 sort_order 排序
  const sorted = [...outlines.value].sort((a, b) => a.sort_order - b.sort_order)
  sorted.forEach(o => { map[o.id] = { ...o, key: o.id, label: o.title, children: [] } })
  sorted.forEach(o => {
    if (o.parent_id && map[o.parent_id]) map[o.parent_id].children.push(map[o.id])
    else if (!o.parent_id) roots.push(map[o.id])
  })
  return roots
})

const outlineStats = computed(() => {
  const total = outlines.value.length
  const done = outlines.value.filter(o => o.status === 'done').length
  const writing = outlines.value.filter(o => o.status === 'writing').length
  return `📊 共 ${total} 个节点 · ✅ 已完成 ${done} · ✍️ 写作中 ${writing} · 📋 计划中 ${total - done - writing}`
})

// ── 渲染函数 ────────────────────────────────────────
const levelLabels = { 1: '📖', 2: '📑', 3: '📄', 4: '📌' }
const statusColors = { planned: 'default', writing: 'warning', done: 'success' }
const statusLabels = { planned: '计划', writing: '写作中', done: '已完成' }

function renderPrefix({ option }) {
  return h('span', { style: 'margin-right:6px;' }, levelLabels[option.level] || '📄')
}

function renderLabel({ option }) {
  const statusTag = h('span', {
    style: `display:inline-block;font-size:11px;padding:0 8px;border-radius:4px;
            margin-left:8px;background:${option.status === 'done' ? '#e8f8e8' : option.status === 'writing' ? '#fff3e0' : '#f0f0f0'};
            color:${option.status === 'done' ? '#18a058' : option.status === 'writing' ? '#f0a020' : '#888'};`
  }, statusLabels[option.status] || '计划')
  return h('span', null, [option.title + ' ', statusTag])
}

// ── 数据 ────────────────────────────────────────────
async function load() {
  loading.value = true
  try {
    const res = await settingsAPI.getOutlines(pid())
    outlines.value = res.data?.data || res.data || []
  } catch {
    outlines.value = []
  } finally { loading.value = false }
}
onMounted(load)

function openCreate() { editing.value = null; form.value = init(); drawerVisible.value = true }
function openEdit(o) { editing.value = o; form.value = { ...o }; drawerVisible.value = true }

async function save() {
  try { await formRef.value?.validate() } catch { return }
  saving.value = true
  try {
    if (editing.value) {
      await settingsAPI.updateOutline(pid(), editing.value.id, form.value)
      message.success('已更新')
    } else {
      await settingsAPI.createOutline(pid(), form.value)
      message.success('已创建')
    }
    drawerVisible.value = false; await load()
  } catch (e) { message.error('保存失败: ' + (e.message || ''))
  } finally { saving.value = false }
}

async function aiGenerateOutline() {
  aiLoading.value = true
  try {
    await aiGenerateAPI.generateOutline(pid(), {
      name: '大纲节点',
      category: '1',
      extra: '请生成一个小说大纲',
    })
    message.success('AI 大纲生成完成！')
    await load()
  } catch (e) {
    message.error('AI 生成失败: ' + (e.message || ''))
  } finally {
    aiLoading.value = false
  }
}
</script>

<style scoped>
.page-header { display:flex; justify-content:space-between; align-items:flex-start; margin-bottom:16px; }
.page-title { display: flex; align-items: center; gap: 12px; }
.page-header h2 { margin:0 0 3px 0; }
@media (max-width:768px) { .page-header { flex-direction:column; gap:12px; } }
:deep(.n-tree-node-content) { min-height:36px; }
</style>
