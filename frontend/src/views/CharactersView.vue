<template>
  <n-spin :show="loading">
    <!-- 页面标题与操作栏 -->
    <div class="page-header">
      <div class="page-title">
        <div class="page-title-icon">🎭</div>
        <div>
          <h2>角色管理</h2>
          <n-text depth="3">管理小说中的角色档案（name / role / gender / age / 性格 / 背景 / 外貌 / 能力 / 关系）</n-text>
        </div>
      </div>
      <div class="page-actions">
        <n-button @click="aiGenerateCharacters" :loading="aiLoading">
          <template #icon><n-icon><SparklesOutline /></n-icon></template>
          AI 生成角色
        </n-button>
        <n-button type="primary" @click="openCreate">
          <template #icon><n-icon><PersonAddOutline /></n-icon></template>
          新建角色
        </n-button>
      </div>
    </div>

    <!-- 角色网格 -->
    <n-grid :cols="isMobile ? 1 : isTablet ? 2 : 3" :x-gap="16" :y-gap="16">
      <n-grid-item v-for="char in characters" :key="char.id">
        <n-card
          class="character-card hover-card"
          @click="openEditDrawer(char)"
        >
          <template #header>
            <div class="char-head">
              <div class="char-avatar">{{ char.name?.slice(0, 1) || '?' }}</div>
              <div class="char-head-text">
                <div class="char-name">{{ char.name }}</div>
                <n-tag :type="roleTypeTag(char.role)" size="tiny" :bordered="false" round>
                  {{ roleLabel(char.role) }}
                </n-tag>
              </div>
            </div>
          </template>
          <template #header-extra>
            <n-tag size="tiny" :bordered="false" type="default" round>{{ genderLabel(char.gender) }}</n-tag>
          </template>

          <div class="char-facts">
            <span v-if="char.age" class="fact-chip">🎂 {{ char.age }} 岁</span>
          </div>

          <n-ellipsis :line-clamp="4" class="char-desc">
            {{ char.personality || char.background || '（暂无性格/背景描述）' }}
          </n-ellipsis>

          <template #action>
            <n-space justify="end">
              <n-button size="tiny" quaternary @click.stop="openEditDrawer(char)">编辑</n-button>
              <n-popconfirm @positive-click="deleteCharacter(char.id)">
                <template #trigger>
                  <n-button size="tiny" quaternary type="error">删除</n-button>
                </template>
                确定删除角色「{{ char.name }}」吗？
              </n-popconfirm>
            </n-space>
          </template>
        </n-card>
      </n-grid-item>
    </n-grid>

    <!-- 空状态 -->
    <n-empty v-if="!characters.length && !loading" description="暂无角色，点击上方按钮创建" style="margin-top:60px;" />

    <!-- ── 新建/编辑抽屉 ────────────────────────────────── -->
    <n-drawer v-model:show="drawerVisible" :width="560" placement="right">
      <n-drawer-content
        :title="editingChar ? `✏️ 编辑角色 · ${editingChar.name}` : '➕ 新建角色'"
        :closable="true"
      >
        <n-form
          ref="formRef"
          :model="formData"
          :rules="formRules"
          label-placement="top"
          size="small"
        >
          <n-form-item label="角色名" path="name">
            <n-input v-model:value="formData.name" placeholder="如：林玄" />
          </n-form-item>

          <n-row :gutter="14">
            <n-col :span="12">
              <n-form-item label="角色定位">
                <n-select v-model:value="formData.role" :options="roleOptions" />
              </n-form-item>
            </n-col>
            <n-col :span="12">
              <n-form-item label="性别">
                <n-select v-model:value="formData.gender" :options="genderOptions" />
              </n-form-item>
            </n-col>
          </n-row>

          <n-form-item label="年龄">
            <n-input-number v-model:value="formData.age" :min="0" style="width: 120px" />
          </n-form-item>

          <n-form-item label="性格特征">
            <n-input
              v-model:value="formData.personality"
              type="textarea"
              :rows="2"
              placeholder="如：坚毅隐忍，重情重义"
            />
          </n-form-item>

          <n-form-item label="背景故事">
            <n-input
              v-model:value="formData.background"
              type="textarea"
              :rows="3"
              placeholder="角色的身世和过往经历..."
            />
          </n-form-item>

          <n-form-item label="外貌描述">
            <n-input
              v-model:value="formData.appearance"
              type="textarea"
              :rows="2"
              placeholder="角色的外貌特征..."
            />
          </n-form-item>

          <n-form-item label="能力 / 特长">
            <n-input
              v-model:value="formData.abilities"
              type="textarea"
              :rows="2"
              placeholder="功法、技能、特长..."
            />
          </n-form-item>

          <n-form-item label="人物关系">
            <n-input
              v-model:value="formData.relationships"
              type="textarea"
              :rows="2"
              placeholder="与其他角色的关系..."
            />
          </n-form-item>
        </n-form>

        <template #footer>
          <n-space justify="end">
            <n-button @click="drawerVisible = false">取消</n-button>
            <n-button type="primary" @click="saveCharacter" :loading="saving">
              {{ editingChar ? '保存修改' : '创建角色' }}
            </n-button>
          </n-space>
        </template>
      </n-drawer-content>
    </n-drawer>
  </n-spin>
</template>

<script setup>
/**
 * CharactersView.vue — 角色管理页面
 * 字段完全对齐后端 Character: name/role/gender/age/personality/background/appearance/abilities/relationships
 */
import { ref, onMounted, onUnmounted } from 'vue'
import { useRoute } from 'vue-router'
import { useMessage } from 'naive-ui'
import {
  PersonAddOutline,
  SparklesOutline,
} from '@vicons/ionicons5'
import { settingsAPI, aiGenerateAPI } from '../api/index.js'

const route = useRoute()
const message = useMessage()

const pid = () => route.params.id

// ── 响应式检测 ──────────────────────────────────────────────────
const isMobile = ref(false)
const isTablet = ref(false)

function checkScreen() {
  const w = window.innerWidth
  isMobile.value = w < 768
  isTablet.value = w >= 768 && w < 1024
}

onMounted(() => {
  checkScreen()
  window.addEventListener('resize', checkScreen)
})
onUnmounted(() => window.removeEventListener('resize', checkScreen))

// ── 状态 ────────────────────────────────────────────────────────
const loading = ref(true)
const saving = ref(false)
const aiLoading = ref(false)
const characters = ref([])
const drawerVisible = ref(false)
const editingChar = ref(null)
const formRef = ref(null)

// ── 选项 ────────────────────────────────────────────────────────
const roleOptions = [
  { label: '主角', value: 'protagonist' },
  { label: '配角', value: 'supporting' },
  { label: '反派', value: 'antagonist' },
  { label: '导师', value: 'mentor' },
  { label: '爱人', value: 'love_interest' },
  { label: '其他', value: 'other' },
]
const roleMap = Object.fromEntries(roleOptions.map((o) => [o.value, o.label]))
function roleLabel(r) { return roleMap[r] || r || '未设定' }

const genderOptions = [
  { label: '男', value: 'male' },
  { label: '女', value: 'female' },
  { label: '未知', value: 'unknown' },
]
const genderMap = Object.fromEntries(genderOptions.map((o) => [o.value, o.label]))
function genderLabel(g) { return genderMap[g] || g || '未知' }

// ── 表单 ────────────────────────────────────────────────────────
const initForm = () => ({
  name: '',
  role: 'supporting',
  gender: 'unknown',
  age: 0,
  personality: '',
  background: '',
  appearance: '',
  abilities: '',
  relationships: '',
})

const formData = ref(initForm())

const formRules = {
  name: [{ required: true, message: '请输入角色名', trigger: 'blur' }],
}

// ── 角色类型标签颜色 ────────────────────────────────────────────
function roleTypeTag(role) {
  const map = {
    protagonist: 'success',
    antagonist: 'error',
    mentor: 'warning',
    love_interest: 'info',
    supporting: 'default',
    other: 'default',
  }
  return map[role] || 'default'
}

// ── 数据加载 ────────────────────────────────────────────────────
async function loadCharacters() {
  loading.value = true
  try {
    const res = await settingsAPI.getCharacters(pid())
    characters.value = res.data?.data || res.data || []
  } catch {
    characters.value = []
  } finally {
    loading.value = false
  }
}

onMounted(loadCharacters)

// ── 打开编辑抽屉 ────────────────────────────────────────────────
function openEditDrawer(char) {
  editingChar.value = char
  formData.value = {
    name: char.name || '',
    role: char.role || 'supporting',
    gender: char.gender || 'unknown',
    age: char.age || 0,
    personality: char.personality || '',
    background: char.background || '',
    appearance: char.appearance || '',
    abilities: char.abilities || '',
    relationships: char.relationships || '',
  }
  drawerVisible.value = true
}

function openCreate() {
  editingChar.value = null
  formData.value = initForm()
  drawerVisible.value = true
}

// ── 保存角色 ────────────────────────────────────────────────────
async function saveCharacter() {
  try {
    await formRef.value?.validate()
  } catch {
    message.error('请填写必要信息')
    return
  }

  saving.value = true
  try {
    if (editingChar.value) {
      await settingsAPI.updateCharacter(pid(), editingChar.value.id, formData.value)
      message.success('角色已更新')
    } else {
      await settingsAPI.createCharacter(pid(), formData.value)
      message.success('角色已创建')
    }
    drawerVisible.value = false
    await loadCharacters()
  } catch (e) {
    message.error('保存失败: ' + (e.message || '未知错误'))
  } finally {
    saving.value = false
  }
}

// ── 删除角色 ────────────────────────────────────────────────────
async function deleteCharacter(id) {
  try {
    await settingsAPI.deleteCharacter(pid(), id)
    message.success('角色已删除')
    await loadCharacters()
  } catch (e) {
    message.error('删除失败')
  }
}

// ── AI 生成角色 ─────────────────────────────────────────────────
async function aiGenerateCharacters() {
  aiLoading.value = true
  message.info('正在生成角色设定...')
  try {
    await aiGenerateAPI.generateCharacter(pid(), {
      name: '新角色',
      role: 'supporting',
      category: 'general',
      extra: '请生成一个有深度的角色设定',
    })
    message.success('AI 角色生成完成！')
    await loadCharacters()
  } catch (e) {
    message.error('AI 生成失败: ' + (e.message || '未知错误'))
  } finally {
    aiLoading.value = false
  }
}
</script>

<style scoped>
.character-card {
  border-radius: 14px;
}

.char-head {
  display: flex;
  align-items: center;
  gap: 10px;
}

.char-avatar {
  width: 38px;
  height: 38px;
  border-radius: 11px;
  display: flex;
  align-items: center;
  justify-content: center;
  font-size: 17px;
  font-weight: 700;
  color: #fff;
  background: linear-gradient(135deg, #6c5ce7, #8b5cf6);
  flex-shrink: 0;
}

.char-head-text {
  min-width: 0;
}

.char-name {
  font-weight: 700;
  font-size: 15px;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.char-facts {
  display: flex;
  gap: 6px;
  flex-wrap: wrap;
  margin-bottom: 8px;
}

.fact-chip {
  font-size: 11px;
  color: #6b7280;
  background: #f4f3ff;
  padding: 1px 8px;
  border-radius: 999px;
}

.char-desc {
  color: #6b7280;
  font-size: 13px;
  line-height: 1.7;
  min-height: 64px;
}
</style>
