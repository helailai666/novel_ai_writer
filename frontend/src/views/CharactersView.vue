<template>
  <n-spin :show="loading">
    <!-- 页面标题与操作栏 -->
    <div class="page-header">
      <div class="page-title">
        <h2>🎭 角色管理</h2>
        <n-text depth="3">管理小说中的角色档案</n-text>
      </div>
      <n-space>
        <n-button @click="showCreateDrawer = true" type="primary">
          <template #icon><n-icon><PersonAddOutline /></n-icon></template>
          新建角色
        </n-button>
        <n-button @click="aiGenerateCharacters" :loading="aiLoading">
          <template #icon><n-icon><SparklesOutline /></n-icon></template>
          AI 生成角色
        </n-button>
      </n-space>
    </div>

    <!-- 角色网格 -->
    <n-grid :cols="isMobile ? 1 : isTablet ? 2 : 3" :x-gap="16" :y-gap="16">
      <n-grid-item v-for="char in characters" :key="char.id">
        <n-card
          :title="char.name"
          hoverable
          class="character-card"
          @click="openEditDrawer(char)"
        >
          <template #header-extra>
            <n-tag :type="roleTypeTag(char.role)" size="small">
              {{ char.role || '未设定' }}
            </n-tag>
          </template>

          <n-descriptions :column="1" label-placement="left" size="small">
            <n-descriptions-item label="别称">{{ char.alias || '无' }}</n-descriptions-item>
            <n-descriptions-item label="境界">{{ char.realm || '无' }}</n-descriptions-item>
            <n-descriptions-item label="阵营">{{ char.faction || '无' }}</n-descriptions-item>
          </n-descriptions>

          <n-ellipsis :line-clamp="3" style="margin-top:8px; color:#666;">
            {{ char.description || '暂无简介' }}
          </n-ellipsis>

          <template #action>
            <n-space justify="end">
              <n-button size="tiny" quaternary @click.stop="openEditDrawer(char)">编辑</n-button>
              <n-popconfirm @positive-stop="deleteCharacter(char.id)">
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
    <n-drawer v-model:show="drawerVisible" :width="520" placement="right">
      <n-drawer-content
        :title="editingChar ? '✏️ 编辑角色' : '➕ 新建角色'"
        :closable="true"
      >
        <n-form
          ref="formRef"
          :model="formData"
          :rules="formRules"
          label-placement="top"
        >
          <n-form-item label="角色名" path="name">
            <n-input v-model:value="formData.name" placeholder="如：林玄" />
          </n-form-item>

          <n-form-item label="别称/绰号">
            <n-input v-model:value="formData.alias" placeholder="如：剑仙" />
          </n-form-item>

          <n-form-item label="角色定位">
            <n-radio-group v-model:value="formData.role" style="flex-wrap:wrap;">
              <n-radio value="主角">主角</n-radio>
              <n-radio value="配角">配角</n-radio>
              <n-radio value="反派">反派</n-radio>
              <n-radio value="导师">导师</n-radio>
              <n-radio value="爱人">爱人</n-radio>
              <n-radio value="其他">其他</n-radio>
            </n-radio-group>
          </n-form-item>

          <n-row :gutter="16">
            <n-col :span="12">
              <n-form-item label="境界/实力">
                <n-input v-model:value="formData.realm" placeholder="如：筑基期" />
              </n-form-item>
            </n-col>
            <n-col :span="12">
              <n-form-item label="阵营">
                <n-input v-model:value="formData.faction" placeholder="如：天剑宗" />
              </n-form-item>
            </n-col>
          </n-row>

          <n-form-item label="性别">
            <n-radio-group v-model:value="formData.gender">
              <n-radio value="男">男</n-radio>
              <n-radio value="女">女</n-radio>
              <n-radio value="未知">未知</n-radio>
            </n-radio-group>
          </n-form-item>

          <n-form-item label="外貌描述">
            <n-input
              v-model:value="formData.appearance"
              type="textarea"
              :rows="2"
              placeholder="角色的外貌特征..."
            />
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

          <n-form-item label="简介">
            <n-input
              v-model:value="formData.description"
              type="textarea"
              :rows="2"
              placeholder="一句话简介..."
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
 *
 * 功能：
 * - 卡片网格展示所有角色
 * - 新建/编辑角色（抽屉表单）
 * - 删除角色
 * - AI 辅助生成角色
 * - 响应式布局（手机/平板/桌面）
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
    '主角': 'success',
    '反派': 'error',
    '导师': 'warning',
    '爱人': 'info',
    '配角': 'default',
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

function resetForm() {
  editingChar.value = null
  formData.value = initForm()
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
    resetForm()
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
.page-header {
  display: flex;
  justify-content: space-between;
  align-items: flex-start;
  margin-bottom: 24px;
}

.page-header h2 {
  margin: 0 0 4px 0;
}

.character-card {
  cursor: pointer;
  transition: transform 0.2s, box-shadow 0.2s;
}

.character-card:hover {
  transform: translateY(-2px);
  box-shadow: 0 4px 16px rgba(0,0,0,0.1);
}

@media (max-width: 768px) {
  .page-header {
    flex-direction: column;
    gap: 12px;
  }
}
</style>
