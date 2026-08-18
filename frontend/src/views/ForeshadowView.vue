<template>
  <n-spin :show="loading">
    <div class="page-header">
      <div class="page-title">
        <h2>🎯 伏笔管理</h2>
        <n-text depth="3">跟踪埋设与回收，避免烂尾伏笔</n-text>
      </div>
      <n-space>
        <n-button @click="openCreate" type="primary">
          <template #icon><n-icon><AddCircleOutline /></n-icon></template>
          新增伏笔
        </n-button>
      </n-space>
    </div>

    <!-- 状态筛选 -->
    <n-tabs v-model:value="statusFilter" type="line" animated style="margin-bottom:16px;">
      <n-tab-pane name="all" :tab="`全部 (${foreshadows.length})`" />
      <n-tab-pane name="planted" :tab="`待回收 (${countByStatus('planted')})`" />
      <n-tab-pane name="revealed" :tab="`已回收 (${countByStatus('revealed')})`" />
    </n-tabs>

    <!-- 伏笔列表 -->
    <n-data-table
      :columns="columns"
      :data="filtered"
      :bordered="false"
      :pagination="{ pageSize: 10 }"
    />

    <!-- 编辑抽屉 -->
    <n-drawer v-model:show="showDrawer" :width="460">
      <n-drawer-content :title="editing ? '编辑伏笔' : '新增伏笔'" closable>
        <n-form label-placement="top">
          <n-form-item label="伏笔内容 *">
            <n-input v-model:value="form.description" type="textarea" :rows="4" placeholder="埋下的线索，如：主角的玉佩会发光" />
          </n-form-item>
          <n-form-item label="状态">
            <n-select v-model:value="form.status" :options="statusOptions" />
          </n-form-item>
          <n-form-item label="埋设章节">
            <n-select
              v-model:value="form.plant_chapter_id"
              clearable
              filterable
              :options="chapterOptions"
              placeholder="选择章节（可选）"
            />
          </n-form-item>
          <n-form-item label="回收章节">
            <n-select
              v-model:value="form.reveal_chapter_id"
              clearable
              filterable
              :options="chapterOptions"
              placeholder="选择章节（可选）"
            />
          </n-form-item>
          <n-form-item label="涉及角色">
            <n-input v-model:value="form.related_characters" placeholder="逗号分隔的角色名" />
          </n-form-item>
        </n-form>
        <template #footer>
          <n-space justify="end">
            <n-button @click="showDrawer = false">取消</n-button>
            <n-button type="primary" :loading="saving" @click="save">保存</n-button>
          </n-space>
        </template>
      </n-drawer-content>
    </n-drawer>
  </n-spin>
</template>

<script setup>
/**
 * ForeshadowView.vue — 伏笔管理（M 轮）
 * 状态筛选 + 表格 + CRUD 抽屉 + planted→revealed 状态流转（章节选择器）
 */
import { ref, reactive, computed, onMounted, h } from 'vue'
import { useRoute } from 'vue-router'
import { useMessage, NButton, NPopconfirm } from 'naive-ui'
import { AddCircleOutline } from '@vicons/ionicons5'
import { settingsAPI, writingAPI } from '../api/index.js'

const route = useRoute()
const message = useMessage()
const pid = computed(() => route.params.id)

const loading = ref(false)
const saving = ref(false)
const foreshadows = ref([])
const chapters = ref([])
const statusFilter = ref('all')
const showDrawer = ref(false)
const editing = ref(null)
const form = reactive({
  description: '', status: 'planted',
  plant_chapter_id: null, reveal_chapter_id: null, related_characters: '',
})

const statusOptions = [
  { label: '待回收（已埋设）', value: 'planted' },
  { label: '已回收（揭晓）', value: 'revealed' },
]

const chapterOptions = computed(() =>
  chapters.value.map((ch) => ({ label: `第${ch.chapter_number}章 ${ch.title || ''}`.trim(), value: ch.id }))
)

const filtered = computed(() => {
  if (statusFilter.value === 'all') return foreshadows.value
  return foreshadows.value.filter((f) => f.status === statusFilter.value)
})

function countByStatus(s) {
  return foreshadows.value.filter((f) => f.status === s).length
}

function chapterTitle(id) {
  const ch = chapters.value.find((c) => c.id === id)
  return ch ? `第${ch.chapter_number}章 ${ch.title || ''}`.trim() : '—'
}

const columns = [
  { title: '伏笔内容', key: 'description', ellipsis: { tooltip: true } },
  {
    title: '状态', key: 'status', width: 100,
    render: (row) => h('span', row.status === 'revealed'
      ? h('span', { style: 'color:#18a058' }, '✅ 已回收')
      : h('span', { style: 'color:#d03050' }, '⏳ 待回收')),
  },
  { title: '埋设章节', key: 'plant_chapter_id', width: 150, render: (row) => chapterTitle(row.plant_chapter_id) },
  { title: '回收章节', key: 'reveal_chapter_id', width: 150, render: (row) => chapterTitle(row.reveal_chapter_id) },
  { title: '涉及角色', key: 'related_characters', width: 140, ellipsis: { tooltip: true } },
  {
    title: '操作', key: 'actions', width: 190,
    render: (row) => h('div', { style: 'display:flex;gap:6px;align-items:center' }, [
      row.status === 'planted'
        ? h(NButton, { size: 'tiny', type: 'success', onClick: () => reveal(row) }, () => '标记回收')
        : null,
      h(NButton, { size: 'tiny', quaternary: true, onClick: () => openEdit(row) }, () => '编辑'),
      h(NPopconfirm, { onPositiveClick: () => deleteItem(row.id) }, {
        trigger: () => h(NButton, { size: 'tiny', quaternary: true, type: 'error' }, () => '删除'),
        default: () => '确认删除该伏笔？',
      }),
    ]),
  },
]

async function load() {
  loading.value = true
  try {
    foreshadows.value = await settingsAPI.getForeshadows(pid.value)
    chapters.value = (await writingAPI.getChapters(pid.value)) || []
  } catch (e) {
    message.error(e.message || '加载失败')
  } finally {
    loading.value = false
  }
}

function openCreate() {
  editing.value = null
  Object.assign(form, {
    description: '', status: 'planted',
    plant_chapter_id: null, reveal_chapter_id: null, related_characters: '',
  })
  showDrawer.value = true
}

function openEdit(f) {
  editing.value = f
  Object.assign(form, {
    description: f.description || '', status: f.status || 'planted',
    plant_chapter_id: f.plant_chapter_id || null, reveal_chapter_id: f.reveal_chapter_id || null,
    related_characters: f.related_characters || '',
  })
  showDrawer.value = true
}

async function save() {
  if (!form.description) {
    message.warning('请填写伏笔内容')
    return
  }
  saving.value = true
  try {
    if (editing.value) {
      await settingsAPI.updateForeshadow(pid.value, editing.value.id, { ...form })
      message.success('已更新')
    } else {
      await settingsAPI.createForeshadow(pid.value, { ...form })
      message.success('已添加')
    }
    showDrawer.value = false
    load()
  } catch (e) {
    message.error(e.message || '保存失败')
  } finally {
    saving.value = false
  }
}

async function reveal(f) {
  try {
    await settingsAPI.updateForeshadow(pid.value, f.id, { status: 'revealed' })
    message.success('已标记回收')
    load()
  } catch (e) {
    message.error(e.message || '操作失败')
  }
}

async function deleteItem(id) {
  try {
    await settingsAPI.deleteForeshadow(pid.value, id)
    message.success('已删除')
    load()
  } catch (e) {
    message.error(e.message || '删除失败')
  }
}

onMounted(load)
</script>

<style scoped>
.page-header { display: flex; justify-content: space-between; align-items: flex-start; margin-bottom: 16px; }
.page-title h2 { margin: 0 0 4px; }
</style>
