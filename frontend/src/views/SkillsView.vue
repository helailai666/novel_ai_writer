<template>
  <n-spin :show="loading">
    <div class="page-header">
      <div class="page-title">
        <div class="page-title-icon">🎯</div>
        <div>
          <h2>技能包</h2>
          <n-text depth="3">全局技能包管理 · 文件 CRUD（skills/&lt;name&gt;/SKILL.md）</n-text>
        </div>
      </div>
      <div class="page-actions">
        <n-button @click="load">
          <template #icon><n-icon><RefreshOutline /></n-icon></template>
          刷新
        </n-button>
        <n-button type="primary" @click="openCreate">
          <template #icon><n-icon><AddOutline /></n-icon></template>
          新建技能
        </n-button>
      </div>
    </div>

    <n-card size="small" :bordered="false">
      <n-data-table
        :columns="columns"
        :data="skills"
        :loading="loading"
        :row-key="(s) => s.name"
        :pagination="{ pageSize: 12 }"
      />
      <n-empty v-if="!skills.length && !loading" description="暂无技能包。点击「新建技能」创建第一个技能" style="margin-top:40px" />
    </n-card>

    <!-- 新建/编辑弹窗 -->
    <n-modal v-model:show="showModal" preset="card" :title="editing ? `编辑技能 · ${editing.name}` : '新建技能包'" style="width: 640px; max-width: 94vw">
      <n-form label-placement="left" label-width="100" size="small">
        <n-form-item label="技能名" required>
          <n-input v-model:value="form.name" :disabled="!!editing" placeholder="字母/数字/下划线/连字符，1-64 字符" />
        </n-form-item>
        <n-form-item label="描述">
          <n-input v-model:value="form.description" placeholder="一句话说明用途" />
        </n-form-item>
        <n-form-item label="版本">
          <n-input v-model:value="form.version" placeholder="1.0.0" style="width: 160px" />
        </n-form-item>
        <n-form-item label="工具白名单">
          <n-input v-model:value="form.toolsText" placeholder="逗号分隔，如 web_search, knowledge_retrieve（可留空）" />
        </n-form-item>
        <n-form-item label="知识类别">
          <n-input v-model:value="form.refsText" placeholder="逗号分隔，如 world, character（可留空）" />
        </n-form-item>
        <n-form-item label="启用">
          <n-switch v-model:value="form.enabled" />
        </n-form-item>
        <n-form-item label="注入内容">
          <n-input
            v-model:value="form.prompt"
            type="textarea"
            :rows="8"
            placeholder="将注入 system prompt 的技能正文（Markdown）"
          />
        </n-form-item>
      </n-form>
      <template #footer>
        <n-space justify="end">
          <n-button @click="showModal = false">取消</n-button>
          <n-button type="primary" :loading="saving" @click="save">保存</n-button>
        </n-space>
      </template>
    </n-modal>
  </n-spin>
</template>

<script setup>
/**
 * SkillsView.vue — 技能包管理（H4）
 * 列表 + 新建/编辑弹窗 + 启用开关 + 删除
 */
import { ref, computed, h, onMounted } from 'vue'
import { useMessage, NTag, NButton, NIcon, NSwitch, NPopconfirm } from 'naive-ui'
import { AddOutline, RefreshOutline, CreateOutline, TrashOutline } from '@vicons/ionicons5'
import { skillsAPI } from '../api/index.js'

const message = useMessage()

const loading = ref(false)
const saving = ref(false)
const skills = ref([])

const showModal = ref(false)
const editing = ref(null)
const form = ref(emptyForm())

function emptyForm() {
  return { name: '', description: '', version: '1.0.0', prompt: '', toolsText: '', refsText: '', enabled: true }
}

// ── 表格 ─────────────────────────────────────────────────────────
const columns = [
  {
    title: '技能名', key: 'name', width: 160,
    render: (s) => h('span', { style: 'font-weight:600' }, s.name),
  },
  {
    title: '版本', key: 'version', width: 80,
    render: (s) => h('span', { style: 'font-size:12px;color:#888' }, s.version),
  },
  {
    title: '描述', key: 'description',
    render: (s) => h('span', { style: 'font-size:12px' }, s.description || '—'),
  },
  {
    title: '工具', key: 'tools', width: 150,
    render: (s) => h(NTag, { size: 'tiny', type: 'warning' }, { default: () => (s.tools || []).length ? s.tools.join(', ') : '—' }),
  },
  {
    title: '启用', key: 'enabled', width: 80,
    render: (s) => h(NSwitch, {
      size: 'small',
      value: s.enabled,
      onUpdateValue: (v) => toggleEnabled(s, v),
    }),
  },
  {
    title: '操作', key: 'actions', width: 130,
    render: (s) => h('span', [
      h(NButton, { size: 'tiny', quaternary: true, onClick: () => openEdit(s) }, {
        default: () => h('span', [h(NIcon, { size: 14 }, { default: () => h(CreateOutline) }), ' 编辑']),
      }),
      h(NPopconfirm, { onPositiveClick: () => remove(s) }, {
        trigger: () => h(NButton, { size: 'tiny', quaternary: true, type: 'error' }, {
          default: () => h('span', [h(NIcon, { size: 14 }, { default: () => h(TrashOutline) }), ' 删除']),
        }),
        default: () => `确认删除技能「${s.name}」？该操作会删除磁盘文件。`,
      }),
    ]),
  },
]

// ── 加载 ─────────────────────────────────────────────────────────
onMounted(load)

async function load() {
  loading.value = true
  try {
    const res = await skillsAPI.list()
    skills.value = res.data.skills || []
  } catch (e) {
    message.error(e.message || '加载失败')
  } finally {
    loading.value = false
  }
}

// ── 新建 / 编辑 ──────────────────────────────────────────────────
function openCreate() {
  editing.value = null
  form.value = emptyForm()
  showModal.value = true
}

function openEdit(s) {
  editing.value = s
  form.value = {
    name: s.name,
    description: s.description || '',
    version: s.version || '1.0.0',
    prompt: s.prompt || '',
    toolsText: (s.tools || []).join(', '),
    refsText: (s.knowledge_refs || []).join(', '),
    enabled: s.enabled !== false,
  }
  showModal.value = true
}

function splitList(text) {
  return String(text || '').split(/[,，]/).map((t) => t.trim()).filter(Boolean)
}

async function save() {
  if (!form.value.name?.trim()) {
    message.warning('技能名必填')
    return
  }
  saving.value = true
  try {
    const payload = {
      name: form.value.name.trim(),
      description: form.value.description,
      version: form.value.version || '1.0.0',
      prompt: form.value.prompt,
      tools: splitList(form.value.toolsText),
      knowledge_refs: splitList(form.value.refsText),
      enabled: form.value.enabled,
    }
    if (editing.value) {
      await skillsAPI.update(editing.value.name, payload)
      message.success('技能已更新')
    } else {
      await skillsAPI.create(payload)
      message.success('技能已创建')
    }
    showModal.value = false
    await load()
  } catch (e) {
    message.error(e.message || '保存失败')
  } finally {
    saving.value = false
  }
}

async function toggleEnabled(s, v) {
  try {
    await skillsAPI.setEnabled(s.name, v)
    s.enabled = v
    message.success(`已${v ? '启用' : '禁用'}「${s.name}」`)
  } catch (e) {
    message.error(e.message || '操作失败')
  }
}

async function remove(s) {
  try {
    await skillsAPI.remove(s.name)
    message.success(`已删除「${s.name}」`)
    await load()
  } catch (e) {
    message.error(e.message || '删除失败')
  }
}
</script>

<style scoped>
.page-header {
  display: flex;
  align-items: center;
  justify-content: space-between;
  flex-wrap: wrap;
  gap: 12px;
  margin-bottom: 16px;
}
.page-title {
  display: flex;
  align-items: center;
  gap: 12px;
}
.page-title h2 {
  margin: 0 0 3px;
}
</style>
