<template>
  <n-spin :show="loading">
    <div class="page-header">
      <div class="page-title">
        <h2>🏛️ 势力管理</h2>
        <n-text depth="3">管理阵营、门派、家族等势力组织</n-text>
      </div>
      <n-space>
        <n-button @click="openCreate" type="primary">
          <template #icon><n-icon><AddCircleOutline /></n-icon></template>
          新建势力
        </n-button>
        <n-button @click="aiGenerate" :loading="aiLoading">
          <template #icon><n-icon><SparklesOutline /></n-icon></template>
          AI 生成
        </n-button>
      </n-space>
    </div>

    <!-- 势力网格 -->
    <n-grid :cols="isMobile ? 1 : 2" :x-gap="16" :y-gap="16">
      <n-grid-item v-for="f in factions" :key="f.id">
        <n-card :title="f.name" hoverable size="small" class="faction-card" @click="openEdit(f)">
          <template #header-extra>
            <n-tag :type="typeTag(f.type)" size="small">{{ typeLabel(f.type) }}</n-tag>
          </template>
          <n-descriptions :column="1" label-placement="left" size="small">
            <n-descriptions-item label="目标"><n-ellipsis :line-clamp="2">{{ f.goal || '无' }}</n-ellipsis></n-descriptions-item>
            <n-descriptions-item label="组织架构"><n-ellipsis :line-clamp="2">{{ f.structure || '无' }}</n-ellipsis></n-descriptions-item>
            <n-descriptions-item label="重要成员"><n-ellipsis :line-clamp="2">{{ f.notable_members || '无' }}</n-ellipsis></n-descriptions-item>
          </n-descriptions>
          <template #action>
            <n-space justify="end">
              <n-button size="tiny" quaternary @click.stop="openEdit(f)">编辑</n-button>
              <n-popconfirm @positive-stop="deleteFaction(f.id)">
                <template #trigger><n-button size="tiny" quaternary type="error">删除</n-button></template>
                确定删除势力「{{ f.name }}」吗？
              </n-popconfirm>
            </n-space>
          </template>
        </n-card>
      </n-grid-item>
    </n-grid>
    <n-empty v-if="!factions.length && !loading" description="暂无势力，点击上方按钮创建" style="margin-top:60px;" />

    <!-- 编辑抽屉 -->
    <n-drawer v-model:show="drawerVisible" :width="520" placement="right">
      <n-drawer-content :title="editing ? '✏️ 编辑势力' : '➕ 新建势力'" :closable="true">
        <n-form ref="formRef" :model="form" :rules="rules" label-placement="top">
          <n-form-item label="势力名称" path="name">
            <n-input v-model:value="form.name" placeholder="如：天剑宗" />
          </n-form-item>
          <n-form-item label="类型">
            <n-radio-group v-model:value="form.type">
              <n-radio value="kingdom">🏰 王国</n-radio>
              <n-radio value="sect">⚔️ 门派</n-radio>
              <n-radio value="clan">🏮 家族</n-radio>
              <n-radio value="holy">✨ 神圣组织</n-radio>
              <n-radio value="merchant">💰 商盟</n-radio>
              <n-radio value="other">❓ 其他</n-radio>
            </n-radio-group>
          </n-form-item>
          <n-form-item label="奋斗目标">
            <n-input v-model:value="form.goal" type="textarea" :rows="2" placeholder="势力的核心目标..." />
          </n-form-item>
          <n-form-item label="组织架构">
            <n-input v-model:value="form.structure" type="textarea" :rows="3" placeholder="等级制度、权力结构..." />
          </n-form-item>
          <n-form-item label="重要成员">
            <n-input v-model:value="form.notable_members" type="textarea" :rows="3" placeholder="列出关键人物及职务..." />
          </n-form-item>
        </n-form>
        <template #footer>
          <n-space justify="end">
            <n-button @click="drawerVisible = false">取消</n-button>
            <n-button type="primary" @click="save" :loading="saving">{{ editing ? '保存修改' : '创建' }}</n-button>
          </n-space>
        </template>
      </n-drawer-content>
    </n-drawer>

    <!-- AI 生成对话框 -->
    <n-modal v-model:show="aiModal" preset="card" title="🤖 AI 生成势力设定" style="width:480px;">
      <n-form label-placement="top">
        <n-form-item label="势力名称"><n-input v-model:value="aiForm.name" placeholder="如：天机阁" /></n-form-item>
        <n-form-item label="类型">
          <n-select v-model:value="aiForm.type" :options="typeOptions" />
        </n-form-item>
      </n-form>
      <template #action>
        <n-button @click="aiModal = false">取消</n-button>
        <n-button type="primary" @click="confirmAi" :loading="aiLoading">开始生成</n-button>
      </template>
    </n-modal>
  </n-spin>
</template>

<script setup>
import { ref, onMounted, onUnmounted } from 'vue'
import { useRoute } from 'vue-router'
import { useMessage } from 'naive-ui'
import { AddCircleOutline, SparklesOutline } from '@vicons/ionicons5'
import { settingsAPI, aiGenerateAPI } from '../api/index.js'

const route = useRoute()
const message = useMessage()
const pid = () => route.params.id

const isMobile = ref(false)
function check() { isMobile.value = window.innerWidth < 768 }
onMounted(() => { check(); window.addEventListener('resize', check) })
onUnmounted(() => window.removeEventListener('resize', check))

const loading = ref(true), saving = ref(false), aiLoading = ref(false)
const factions = ref([]), drawerVisible = ref(false), aiModal = ref(false)
const editing = ref(null)
const formRef = ref(null)

const init = () => ({ name: '', type: 'sect', goal: '', structure: '', notable_members: '' })
const form = ref(init())
const rules = { name: [{ required: true, message: '请输入势力名称', trigger: 'blur' }] }
const aiForm = ref({ name: '', type: 'sect' })

const typeOptions = [
  { label: '🏰 王国', value: 'kingdom' }, { label: '⚔️ 门派', value: 'sect' },
  { label: '🏮 家族', value: 'clan' }, { label: '✨ 神圣组织', value: 'holy' },
  { label: '💰 商盟', value: 'merchant' }, { label: '❓ 其他', value: 'other' },
]
function typeLabel(t) { return typeOptions.find(o => o.value === t)?.label || t }
function typeTag(t) { return { kingdom:'success', sect:'warning', clan:'info', holy:'primary', merchant:'error' }[t] || 'default' }

async function load() {
  loading.value = true
  try {
    const res = await settingsAPI.getFactions(pid())
    factions.value = res.data?.data || res.data || []
  } catch {
    factions.value = []
  } finally { loading.value = false }
}
onMounted(load)

function openEdit(f) { editing.value = f; form.value = { ...f }; drawerVisible.value = true }
function openCreate() { editing.value = null; form.value = init(); drawerVisible.value = true }
function reset() { editing.value = null; form.value = init() }

async function save() {
  try { await formRef.value?.validate() } catch { return }
  saving.value = true
  try {
    if (editing.value) {
      // 后端没有 faction update 端点，先删除再创建
      await settingsAPI.deleteFaction(pid(), editing.value.id)
      await settingsAPI.createFaction(pid(), form.value)
      message.success('已更新')
    } else {
      await settingsAPI.createFaction(pid(), form.value)
      message.success('已创建')
    }
    drawerVisible.value = false; reset(); await load()
  } catch (e) { message.error('保存失败: ' + (e.message || ''))
  } finally { saving.value = false }
}
async function deleteFaction(id) {
  try {
    await settingsAPI.deleteFaction(pid(), id)
    message.success('已删除')
    await load()
  } catch (e) { message.error('删除失败') }
}
function aiGenerate() { aiForm.value = { name:'', type:'sect' }; aiModal.value = true }
async function confirmAi() {
  if (!aiForm.value.name) { message.error('请输入名称'); return }
  aiLoading.value = true
  try {
    await aiGenerateAPI.generateFaction(pid(), {
      name: aiForm.value.name,
      category: aiForm.value.type,
    })
    message.success(`「${aiForm.value.name}」生成完成！`)
    aiModal.value = false
    await load()
  } catch (e) {
    message.error('生成失败: ' + (e.message || ''))
  } finally {
    aiLoading.value = false
  }
}
</script>

<style scoped>
.page-header { display:flex; justify-content:space-between; align-items:flex-start; margin-bottom:16px; }
.page-header h2 { margin:0 0 4px 0; }
.faction-card { cursor:pointer; transition:transform .2s,box-shadow .2s; }
.faction-card:hover { transform:translateY(-2px); box-shadow:0 4px 16px rgba(0,0,0,.1); }
@media (max-width:768px) { .page-header { flex-direction:column; gap:12px; } }
</style>
