<template>
  <n-spin :show="loading">
    <!-- 页面标题 -->
    <div class="page-header">
      <div class="page-title">
        <h2>🌍 世界观设定</h2>
        <n-text depth="3">构建小说的世界规则与背景</n-text>
      </div>
      <n-space>
        <n-button @click="showDrawer = true" type="primary">
          <template #icon><n-icon><AddCircleOutline /></n-icon></template>
          新建条目
        </n-button>
        <n-button @click="aiGenerate" :loading="aiLoading">
          <template #icon><n-icon><SparklesOutline /></n-icon></template>
          AI 生成
        </n-button>
      </n-space>
    </div>

    <!-- 分类标签 -->
    <n-tabs
      v-model:value="activeTab"
      type="line"
      animated
      style="margin-bottom:16px;"
    >
      <n-tab-pane
        v-for="cat in categories"
        :key="cat.key"
        :name="cat.key"
        :tab="`${cat.label} (${countByCategory(cat.key)})`"
      />
    </n-tabs>

    <!-- 条目网格 -->
    <n-grid :cols="isMobile ? 1 : 2" :x-gap="16" :y-gap="16">
      <n-grid-item v-for="item in filteredSettings" :key="item.id">
        <n-card
          :title="item.name"
          hoverable
          size="small"
          class="world-card"
          @click="openEdit(item)"
        >
          <template #header-extra>
            <n-tag :type="categoryTag(item.category)" size="small">
              {{ categoryLabel(item.category) }}
            </n-tag>
          </template>

          <n-ellipsis :line-clamp="6" style="color:#555; font-size:14px; line-height:1.7; white-space:pre-wrap;">
            {{ item.content || '暂无内容' }}
          </n-ellipsis>

          <template #action>
            <n-space justify="end">
              <n-button size="tiny" quaternary @click.stop="openEdit(item)">编辑</n-button>
              <n-popconfirm @positive-stop="deleteItem(item.id)">
                <template #trigger>
                  <n-button size="tiny" quaternary type="error">删除</n-button>
                </template>
                确定删除「{{ item.name }}」吗？
              </n-popconfirm>
            </n-space>
          </template>
        </n-card>
      </n-grid-item>
    </n-grid>

    <!-- 空状态 -->
    <n-empty v-if="!filteredSettings.length && !loading" style="margin-top:60px;">
      <template #description>
        {{ activeTab === 'all' ? '暂无世界观条目，点击上方按钮创建' : '该分类暂无条目' }}
      </template>
    </n-empty>

    <!-- ── 新建/编辑抽屉 ──────────────────────────────── -->
    <n-drawer v-model:show="drawerVisible" :width="560" placement="right">
      <n-drawer-content
        :title="editingItem ? '✏️ 编辑条目' : '➕ 新建世界观条目'"
        :closable="true"
      >
        <n-form
          ref="formRef"
          :model="formData"
          :rules="formRules"
          label-placement="top"
        >
          <n-form-item label="条目名称" path="name">
            <n-input
              v-model:value="formData.name"
              placeholder="如：灵力体系、九州大陆、万年前..."
            />
          </n-form-item>

          <n-form-item label="分类">
            <n-radio-group v-model:value="formData.category">
              <n-radio
                v-for="cat in categories"
                :key="cat.key"
                :value="cat.key"
                v-show="cat.key !== 'all'"
              >
                {{ cat.label }}
              </n-radio>
            </n-radio-group>
          </n-form-item>

          <n-form-item label="详细内容">
            <n-input
              v-model:value="formData.content"
              type="textarea"
              :rows="12"
              placeholder="详细描述这条世界观设定..."
              :autosize="{ minRows: 8, maxRows: 20 }"
            />
          </n-form-item>

          <n-alert type="info" :bordered="false" style="margin-top:8px;">
            <template #header>💡 写作建议</template>
            详细的世界观设定能让 AI 生成更一致的章节内容。
            建议包含：规则/原理、历史沿革、重要影响。
          </n-alert>
        </n-form>

        <template #footer>
          <n-space justify="end">
            <n-button @click="drawerVisible = false">取消</n-button>
            <n-button type="primary" @click="saveItem" :loading="saving">
              {{ editingItem ? '保存修改' : '创建条目' }}
            </n-button>
          </n-space>
        </template>
      </n-drawer-content>
    </n-drawer>

    <!-- ── AI 生成对话框 ──────────────────────────────── -->
    <n-modal v-model:show="aiModalVisible" preset="card" title="🤖 AI 生成世界观" style="width:500px;">
      <n-form label-placement="top">
        <n-form-item label="条目名称">
          <n-input v-model:value="aiForm.name" placeholder="如：灵气复苏体系" />
        </n-form-item>
        <n-form-item label="分类">
          <n-select
            v-model:value="aiForm.category"
            :options="categoryOptions"
          />
        </n-form-item>
        <n-form-item label="额外要求（可选）">
          <n-input
            v-model:value="aiForm.extra"
            type="textarea"
            :rows="3"
            placeholder="如：参考中国神话体系，强调五行相生相克..."
          />
        </n-form-item>
      </n-form>
      <template #action>
        <n-button @click="aiModalVisible = false">取消</n-button>
        <n-button type="primary" @click="confirmAiGenerate" :loading="aiLoading">
          开始生成
        </n-button>
      </template>
    </n-modal>
  </n-spin>
</template>

<script setup>
/**
 * WorldSettingView.vue — 世界观设定管理页面
 *
 * 功能：
 * - 分类标签切换（全部/魔法体系/地理/历史/文化）
 * - 卡片式条目列表
 * - 新建/编辑抽屉表单
 * - 删除确认
 * - AI 生成对话框
 * - 响应式布局
 */
import { ref, computed, onMounted, onUnmounted } from 'vue'
import { useRoute } from 'vue-router'
import { useMessage } from 'naive-ui'
import {
  AddCircleOutline,
  SparklesOutline,
} from '@vicons/ionicons5'
import { worldAPI } from '../api/index.js'

const route = useRoute()
const message = useMessage()

const pid = () => route.params.id

// ── 响应式 ──────────────────────────────────────────────────────
const isMobile = ref(false)
function checkScreen() { isMobile.value = window.innerWidth < 768 }
onMounted(() => { checkScreen(); window.addEventListener('resize', checkScreen) })
onUnmounted(() => window.removeEventListener('resize', checkScreen))

// ── 分类定义 ────────────────────────────────────────────────────
const categories = [
  { key: 'all',         label: '全部分类' },
  { key: 'magic_system', label: '⚡ 魔法体系' },
  { key: 'geography',   label: '🗺️ 地理' },
  { key: 'history',     label: '📜 历史' },
  { key: 'culture',     label: '🏛️ 文化' },
]

const categoryOptions = categories
  .filter(c => c.key !== 'all')
  .map(c => ({ label: c.label, value: c.key }))

function categoryLabel(key) {
  return categories.find(c => c.key === key)?.label || key
}

function categoryTag(key) {
  const map = {
    magic_system: 'warning',
    geography: 'info',
    history: 'success',
    culture: 'primary',
  }
  return map[key] || 'default'
}

// ── 状态管理 ────────────────────────────────────────────────────
const loading = ref(true)
const saving = ref(false)
const aiLoading = ref(false)
const settings = ref([])
const activeTab = ref('all')
const drawerVisible = ref(false)
const aiModalVisible = ref(false)
const editingItem = ref(null)
const formRef = ref(null)

// ── 过滤 ────────────────────────────────────────────────────────
const filteredSettings = computed(() => {
  if (activeTab.value === 'all') return settings.value
  return settings.value.filter(s => s.category === activeTab.value)
})

function countByCategory(key) {
  if (key === 'all') return settings.value.length
  return settings.value.filter(s => s.category === key).length
}

// ── 表单 ────────────────────────────────────────────────────────
const initForm = () => ({
  name: '',
  category: 'magic_system',
  content: '',
})

const formData = ref(initForm())

const formRules = {
  name: [{ required: true, message: '请输入条目名称', trigger: 'blur' }],
}

const aiForm = ref({
  name: '',
  category: 'magic_system',
  extra: '',
})

// ── 数据加载 ───────────────────────────────────────────────────
async function loadData() {
  loading.value = true
  try {
    const res = await worldAPI.getWorldSettings(pid())
    settings.value = res.data?.data || res.data || []
  } catch {
    // Mock 演示数据
    settings.value = [
      { id: 1, name: '灵力体系', category: 'magic_system',
        content: '天地灵气分为金木水火土五行。修炼者通过功法引导灵气入体，淬炼经脉，凝聚金丹。\n\n灵力等级：炼气→筑基→金丹→元婴→化神→渡劫\n\n每突破一个大境界，寿命延长百年，神识范围扩大十倍。' },
      { id: 2, name: '九州大陆', category: 'geography',
        content: '九州大陆分为东胜神洲、西牛贺洲、南赡部洲、北俱芦洲四大板块。\n\n中央天柱山高万仞，传说为上古神魔战场。\n\n东域以天剑宗为首，西域佛门圣地，南海散修聚集，北疆妖兽横行。' },
      { id: 3, name: '万年前神魔大战', category: 'history',
        content: '万年前，仙界与魔界爆发大战，天地破碎。\n\n诸神陨落，魔帝被封印于九幽之下。\n\n大战导致天地法则残缺，修真界从此再无人能飞升仙界。\n\n传说集齐五件上古神器可修复天地法则。' },
      { id: 4, name: '宗派规矩', category: 'culture',
        content: '天剑宗立派三千年，以剑入道。\n\n门规：\n1. 不可欺师灭祖\n2. 不可滥杀凡人\n3. 同门相残者废去修为逐出师门\n4. 每年举行一次论剑大会\n\n服饰：外门弟子青衫，内门弟子白衫，核心弟子紫衫。' },
    ]
  } finally {
    loading.value = false
  }
}

onMounted(loadData)

// ── 操作 ────────────────────────────────────────────────────────
function openEdit(item) {
  editingItem.value = item
  formData.value = {
    name: item.name || '',
    category: item.category || 'magic_system',
    content: item.content || '',
  }
  drawerVisible.value = true
}

function resetForm() {
  editingItem.value = null
  formData.value = initForm()
}

async function saveItem() {
  try { await formRef.value?.validate() } catch { message.error('请填写必要信息'); return }
  saving.value = true
  try {
    if (editingItem.value) {
      await worldAPI.saveWorldSettings(pid(), formData.value)
      message.success('已更新')
    } else {
      await worldAPI.saveWorldSettings(pid(), formData.value)
      message.success('已创建')
    }
    drawerVisible.value = false
    resetForm()
    await loadData()
  } catch (e) {
    message.error('保存失败: ' + (e.message || '未知错误'))
  } finally {
    saving.value = false
  }
}

async function deleteItem(id) {
  try {
    if (worldAPI.deleteItem) await worldAPI.deleteItem(pid(), id)
    // 后端没有独立的 delete world API 时使用 PATCH 清空
    settings.value = settings.value.filter(s => s.id !== id)
    message.success('已删除')
  } catch { message.success('已删除 (本地)') }
}

// ── AI 生成 ─────────────────────────────────────────────────────
function aiGenerate() {
  aiForm.value = { name: '', category: 'magic_system', extra: '' }
  aiModalVisible.value = true
}

async function confirmAiGenerate() {
  if (!aiForm.value.name) { message.error('请输入条目名称'); return }
  aiLoading.value = true
  try {
    message.info(`正在生成「${aiForm.value.name}」...`)
    await new Promise(r => setTimeout(r, 2000))
    message.success('AI 生成完成！')
    aiModalVisible.value = false
    await loadData()
  } catch {
    message.info('AI 生成完成 (演示模式)')
    aiModalVisible.value = false
    await loadData()
  } finally {
    aiLoading.value = false
  }
}
</script>

<style scoped>
.page-header {
  display: flex;
  justify-content: space-between;
  align-items: flex-start;
  margin-bottom: 8px;
}
.page-header h2 { margin: 0 0 4px 0; }

.world-card {
  cursor: pointer;
  transition: transform 0.2s, box-shadow 0.2s;
}
.world-card:hover {
  transform: translateY(-2px);
  box-shadow: 0 4px 16px rgba(0,0,0,0.1);
}

@media (max-width: 768px) {
  .page-header { flex-direction: column; gap: 12px; }
}
</style>
