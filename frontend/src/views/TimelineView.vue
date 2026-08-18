<template>
  <n-spin :show="loading">
    <!-- 页面标题 -->
    <div class="page-header">
      <div class="page-title">
        <div class="page-title-icon">🕐</div>
        <div>
          <h2>时间线</h2>
          <n-text depth="3">管理小说世界的时间事件脉络</n-text>
        </div>
      </div>
      <div class="page-actions">
        <n-button @click="aiModal = true" :loading="aiLoading">
          <template #icon><n-icon><SparklesOutline /></n-icon></template>
          AI 生成事件
        </n-button>
        <n-button type="primary" @click="openCreate">
          <template #icon><n-icon><AddCircleOutline /></n-icon></template>
          新增事件
        </n-button>
      </div>
    </div>

    <!-- 时代筛选 -->
    <n-tabs v-model:value="eraFilter" type="line" animated style="margin-bottom:16px;">
      <n-tab-pane :name="'all'" :tab="`全部 (${timelines.length})`" />
      <n-tab-pane
        v-for="era in eras"
        :key="era"
        :name="era"
        :tab="`${era || '未分类'} (${countByEra(era)})`"
      />
    </n-tabs>

    <!-- 事件列表 -->
    <n-timeline v-if="filtered.length">
      <n-timeline-item
        v-for="t in filtered"
        :key="t.id"
        :type="t.event_date ? 'success' : 'info'"
        :title="t.event"
        :content="t.description || '（无描述）'"
        :time="`${t.era || 'present'}${t.event_date ? ' · ' + t.event_date : ''}`"
      >
        <template #footer>
          <n-space align="center" size="small">
            <n-tag v-if="t.involved_characters" size="tiny" type="warning">🧑 {{ t.involved_characters }}</n-tag>
            <n-button size="tiny" quaternary @click="openEdit(t)">编辑</n-button>
            <n-popconfirm @positive-click="deleteItem(t.id)">
              <template #trigger>
                <n-button size="tiny" quaternary type="error">删除</n-button>
              </template>
              确认删除该时间线事件？
            </n-popconfirm>
          </n-space>
        </template>
      </n-timeline-item>
    </n-timeline>
    <n-empty v-else description="暂无时间线事件" style="margin-top:60px" />

    <!-- AI 生成弹窗 -->
    <n-modal v-model:show="aiModal" preset="card" title="✨ AI 生成时间线事件" style="width:520px">
      <n-form label-placement="top">
        <n-form-item label="事件名">
          <n-input v-model:value="aiForm.name" placeholder="如：天玄门立宗之战" />
        </n-form-item>
        <n-form-item label="时代/纪元">
          <n-input v-model:value="aiForm.category" placeholder="如：上古 / 近世（默认 present）" />
        </n-form-item>
        <n-form-item label="补充要求（可选）">
          <n-input v-model:value="aiForm.extra" type="textarea" :rows="2" placeholder="希望事件包含哪些要素" />
        </n-form-item>
      </n-form>
      <template #footer>
        <n-space justify="end">
          <n-button @click="aiModal = false">取消</n-button>
          <n-button type="primary" :loading="aiLoading" @click="aiGenerate">生成并保存</n-button>
        </n-space>
      </template>
    </n-modal>

    <!-- 编辑抽屉 -->
    <n-drawer v-model:show="showDrawer" :width="420">
      <n-drawer-content :title="editing ? '编辑时间线事件' : '新增时间线事件'" closable>
        <n-form label-placement="top">
          <n-form-item label="事件名 *">
            <n-input v-model:value="form.event" placeholder="事件的简要名称" />
          </n-form-item>
          <n-form-item label="时代/纪元">
            <n-input v-model:value="form.era" placeholder="present / 上古 / 近世…" />
          </n-form-item>
          <n-form-item label="事件日期">
            <n-input v-model:value="form.event_date" placeholder="如：天启三年春（可选）" />
          </n-form-item>
          <n-form-item label="排序">
            <n-input-number v-model:value="form.sort_order" :min="0" style="width:120px" />
          </n-form-item>
          <n-form-item label="详细描述">
            <n-input v-model:value="form.description" type="textarea" :rows="5" placeholder="事件的前因后果与影响" />
          </n-form-item>
          <n-form-item label="涉及角色">
            <n-input v-model:value="form.involved_characters" placeholder="逗号分隔的角色名" />
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
 * TimelineView.vue — 时间线管理（M 轮）
 * 时代筛选 + 事件时间线列表 + CRUD 抽屉 + AI 生成事件
 */
import { ref, reactive, computed, onMounted } from 'vue'
import { useRoute } from 'vue-router'
import { useMessage } from 'naive-ui'
import { AddCircleOutline, SparklesOutline } from '@vicons/ionicons5'
import { settingsAPI, aiGenerateAPI } from '../api/index.js'

const route = useRoute()
const message = useMessage()
const pid = computed(() => route.params.id)

const loading = ref(false)
const saving = ref(false)
const aiLoading = ref(false)
const timelines = ref([])
const eraFilter = ref('all')
const showDrawer = ref(false)
const editing = ref(null)
const aiModal = ref(false)
const aiForm = reactive({ name: '', category: 'present', extra: '' })
const form = reactive({ event: '', era: 'present', event_date: '', sort_order: 0, description: '', involved_characters: '' })

const eras = computed(() => [...new Set(timelines.value.map((t) => t.era || 'present'))])
const filtered = computed(() => {
  if (eraFilter.value === 'all') return timelines.value
  return timelines.value.filter((t) => (t.era || 'present') === eraFilter.value)
})
function countByEra(era) {
  return timelines.value.filter((t) => (t.era || 'present') === era).length
}

async function load() {
  loading.value = true
  try {
    const res = await settingsAPI.getTimelines(pid.value)
    timelines.value = res.data?.data || res.data || []
  } catch (e) {
    message.error(e.message || '加载失败')
  } finally {
    loading.value = false
  }
}

function openCreate() {
  editing.value = null
  Object.assign(form, { event: '', era: 'present', event_date: '', sort_order: 0, description: '', involved_characters: '' })
  showDrawer.value = true
}

function openEdit(t) {
  editing.value = t
  Object.assign(form, {
    event: t.event, era: t.era || 'present', event_date: t.event_date || '',
    sort_order: t.sort_order || 0, description: t.description || '', involved_characters: t.involved_characters || '',
  })
  showDrawer.value = true
}

async function save() {
  if (!form.event) {
    message.warning('请填写事件名')
    return
  }
  saving.value = true
  try {
    if (editing.value) {
      await settingsAPI.updateTimeline(pid.value, editing.value.id, { ...form })
      message.success('已更新')
    } else {
      await settingsAPI.createTimeline(pid.value, { ...form })
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

async function deleteItem(id) {
  try {
    await settingsAPI.deleteTimeline(pid.value, id)
    message.success('已删除')
    load()
  } catch (e) {
    message.error(e.message || '删除失败')
  }
}

async function aiGenerate() {
  if (!aiForm.name) {
    message.warning('请填写事件名')
    return
  }
  aiLoading.value = true
  try {
    const r = await aiGenerateAPI.generateTimeline(pid.value, {
      name: aiForm.name, category: aiForm.category || 'present', extra: aiForm.extra,
    })
    message.success(r.data?.is_mock ? '已生成（Mock 模式，配置 LLM Key 后为真实内容）' : '已生成并保存')
    aiModal.value = false
    load()
  } catch (e) {
    message.error(e.message || '生成失败')
  } finally {
    aiLoading.value = false
  }
}

onMounted(load)
</script>

<style scoped>
.page-header { display: flex; justify-content: space-between; align-items: flex-start; margin-bottom: 16px; }
.page-title { display: flex; align-items: center; gap: 12px; }
.page-title h2 { margin: 0 0 3px; }
</style>
