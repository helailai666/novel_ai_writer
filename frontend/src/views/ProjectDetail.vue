<template>
  <n-spin :show="loading">
    <!-- ══ 项目头 ══ -->
    <div class="project-hero">
      <div class="hero-main">
        <div class="hero-icon">📖</div>
        <div class="hero-text">
          <div class="hero-title-row">
            <h2>{{ project?.title || '创作工作台' }}</h2>
            <n-tag size="small" :type="statusMeta(project?.status).type" :bordered="false" round>
              {{ statusMeta(project?.status).label }}
            </n-tag>
            <n-tag size="small" :bordered="false" type="info" round>{{ genreLabel(project?.genre) }}</n-tag>
          </div>
          <n-text depth="3" class="hero-synopsis">{{ project?.synopsis || '暂无简介' }}</n-text>
        </div>
      </div>
      <div class="hero-actions">
        <n-button size="small" secondary @click="$router.push(`/projects/${pid()}/dashboard`)">
          <template #icon><n-icon><StatsChartOutline /></n-icon></template>
          总览
        </n-button>
        <n-button size="small" secondary @click="$router.push(`/projects/${pid()}/outline`)">
          <template #icon><n-icon><ListOutline /></n-icon></template>
          大纲
        </n-button>
        <n-dropdown trigger="click" :options="moreActions" @select="handleMoreAction">
          <n-button size="small" secondary>
            <template #icon><n-icon><EllipsisHorizontalOutline /></n-icon></template>
            更多
          </n-button>
        </n-dropdown>
      </div>
    </div>

    <n-grid :cols="isMobile ? 1 : 3" :x-gap="18" responsive="screen">
      <n-grid-item span="3 m:2">
        <!-- ══ 创作区 ══ -->
        <n-card class="workspace-card">
          <template #header>
            <span class="card-title">✍️ 创作生成</span>
          </template>
          <template #header-extra>
            <n-tag size="tiny" :bordered="false" round>{{ wordCountText }}字目标</n-tag>
          </template>

          <div class="gen-row">
            <div class="gen-field">
              <span class="gen-label">章节号</span>
              <n-input-number v-model:value="chNum" :min="1" size="small" style="width: 76px" />
            </div>
            <div class="gen-field grow">
              <span class="gen-label">章节标题 / 提示</span>
              <n-input
                v-model:value="chTitle"
                size="small"
                placeholder="如：初入仙途，拜入宗门（可选）"
                @keyup.enter="streamGenerate"
              />
            </div>
            <div class="gen-field">
              <span class="gen-label">卷</span>
              <n-select v-model:value="volumeId" size="small" clearable placeholder="不分组" :options="volumeOptions" style="width: 110px" />
            </div>
            <div class="gen-field">
              <span class="gen-label">目标字数</span>
              <n-input-number v-model:value="targetWords" :min="100" :max="10000" :step="500" size="small" style="width: 110px" />
            </div>
            <n-button
              type="primary"
              :disabled="streaming"
              :loading="streaming"
              @click="streamGenerate"
            >
              <template #icon><n-icon><SparklesOutline /></n-icon></template>
              {{ streaming ? '生成中...' : '流式生成' }}
            </n-button>
          </div>

          <n-divider style="margin: 14px 0" />

          <div class="batch-row">
            <n-input-number v-model:value="batchStart" :min="1" size="small" style="width: 72px" />
            <n-text depth="3">—</n-text>
            <n-input-number v-model:value="batchEnd" :min="1" size="small" style="width: 72px" />
            <n-button size="small" @click="batchGen" :loading="batchLoading">
              <template #icon><n-icon><LayersOutline /></n-icon></template>
              批量生成 {{ Math.max(batchEnd - batchStart + 1, 0) }} 章
            </n-button>
          </div>
        </n-card>

        <!-- ══ 流式输出 ══ -->
        <n-card class="workspace-card" style="margin-top: 18px;">
          <template #header>
            <span class="card-title">📝 生成结果</span>
          </template>
          <StreamOutput
            ref="streamRef"
            :endpoint="streamEndpoint"
            :params="streamParams"
            :speed="streamSpeed"
            @done="onStreamDone"
            @save="onStreamSave"
            @error="onStreamError"
          />
        </n-card>

        <!-- ══ 章节列表 ══ -->
        <n-card class="workspace-card" style="margin-top: 18px;">
          <template #header>
            <span class="card-title">📑 章节列表</span>
          </template>
          <template #header-extra>
            <n-text depth="3" style="font-size: 12px">共 {{ chapters.length }} 章</n-text>
          </template>

          <template v-if="chapters.length">
            <div
              v-for="ch in chapters"
              :key="ch.id"
              class="chapter-row"
              @click="selectChapter(ch)"
            >
              <div class="chapter-no">{{ String(ch.chapter_number).padStart(2, '0') }}</div>
              <div class="chapter-body">
                <div class="chapter-title-line">
                  <span class="chapter-title">{{ ch.title || `第${ch.chapter_number}章` }}</span>
                  <n-tag size="tiny" :bordered="false" :type="chapterStatus(ch.status).type" round>
                    {{ chapterStatus(ch.status).label }}
                  </n-tag>
                  <span v-if="ch.word_count" class="chapter-words">{{ ch.word_count }} 字</span>
                </div>
                <div class="chapter-preview">
                  {{ (ch.content || '').slice(0, 90) || '（空章节）' }}<span v-if="(ch.content || '').length > 90">…</span>
                </div>
              </div>
              <div class="chapter-ops" @click.stop>
                <n-button size="tiny" quaternary @click="openChapter(ch)">阅读</n-button>
                <n-button size="tiny" quaternary type="warning" @click="continueWrite(ch)">续写</n-button>
                <n-button size="tiny" quaternary @click="polish(ch)">润色</n-button>
                <n-popconfirm @positive-click="deleteChapter(ch)">
                  <template #trigger>
                    <n-button size="tiny" quaternary type="error">删除</n-button>
                  </template>
                  确定删除第 {{ ch.chapter_number }} 章「{{ ch.title || '' }}」吗？
                </n-popconfirm>
              </div>
            </div>
          </template>
          <n-empty v-else description="暂无章节，输入提示后点击「流式生成」开始写作" />
        </n-card>
      </n-grid-item>

      <!-- ══ 侧栏 ══ -->
      <n-grid-item span="3 m:1">
        <n-card class="workspace-card">
          <template #header>
            <span class="card-title">📊 项目信息</span>
          </template>
          <n-descriptions :column="1" label-placement="left" size="small">
            <n-descriptions-item label="类型">{{ genreLabel(project?.genre) }}</n-descriptions-item>
            <n-descriptions-item label="状态">{{ statusMeta(project?.status).label }}</n-descriptions-item>
            <n-descriptions-item label="章节数">{{ chapters.length }}</n-descriptions-item>
            <n-descriptions-item label="总字数">{{ totalWords.toLocaleString() }}</n-descriptions-item>
            <n-descriptions-item label="创建于">{{ fmtDate(project?.created_at) }}</n-descriptions-item>
            <n-descriptions-item label="技能包">{{ project?.skill_packs || '未配置' }}</n-descriptions-item>
          </n-descriptions>
          <n-divider style="margin: 12px 0" />
          <n-text depth="3" style="font-size: 12px; line-height: 1.9; display: block;">
            💡 AI 会依据项目设定、大纲与知识库生成一致的内容。在「模块设定」中完善世界观与角色，可显著提升生成质量。
          </n-text>
        </n-card>

        <!-- 每小说模型设置 -->
        <n-card class="workspace-card" style="margin-top: 18px;">
          <template #header>
            <span class="card-title">🤖 模型设置</span>
          </template>
          <n-form size="small" label-placement="top">
            <n-form-item label="模型供应商">
              <n-select
                v-model:value="llmProviderId"
                :options="llmProviderOptions"
                clearable
                placeholder="默认（全局配置 / 环境变量）"
              />
            </n-form-item>
            <n-form-item label="模型覆盖（可选）">
              <n-input v-model:value="llmModel" placeholder="如 deepseek-chat，留空用供应商默认" />
            </n-form-item>
            <n-button type="primary" size="small" :loading="llmSaving" block @click="saveLlmConfig">
              保存模型设置
            </n-button>
            <n-text v-if="effectiveModel" depth="3" style="font-size: 12px; display: block; margin-top: 8px">
              本小说生效：{{ effectiveModel }}
            </n-text>
            <n-text depth="3" style="font-size: 12px; display: block; margin-top: 6px">
              在「全局设置」页可新增/编辑供应商配置；每部小说可独立选择模型。
            </n-text>
          </n-form>
        </n-card>

        <n-card class="workspace-card" style="margin-top: 18px;">
          <template #header>
            <span class="card-title">🗂️ 卷管理</span>
          </template>
          <div class="volume-list">
            <div v-for="v in volumes" :key="v.id" class="volume-row">
              <span class="volume-no">卷{{ v.volume_number }}</span>
              <span class="volume-name">{{ v.title }}</span>
            </div>
            <n-empty v-if="!volumes.length" description="暂无卷" size="small" style="padding: 6px 0" />
          </div>
          <n-divider style="margin: 10px 0" />
          <n-input v-model:value="newVolumeTitle" size="small" placeholder="新卷名，如：第一卷·初出茅庐" @keyup.enter="createVolume" />
          <n-button size="small" block style="margin-top: 8px" @click="createVolume" :loading="volumeCreating">
            <template #icon><n-icon><AddOutline /></n-icon></template>
            新建卷
          </n-button>
        </n-card>

        <n-card class="workspace-card" style="margin-top: 18px;">
          <template #header>
            <span class="card-title">🤖 AI 快捷指令</span>
          </template>
          <div class="cmd-list">
            <div v-for="cmd in quickCmds" :key="cmd" class="cmd-chip">{{ cmd }}</div>
          </div>
        </n-card>
      </n-grid-item>
    </n-grid>

    <!-- ══ 章节阅读/编辑抽屉 ══ -->
    <n-drawer v-model:show="showChapter" :width="720" placement="right" style="max-width: 100vw">
      <n-drawer-content :title="activeChapter ? `第${activeChapter.chapter_number}章 · ${activeChapter.title || ''}` : '章节'" closable>
        <n-spin :show="chapterLoading">
          <template v-if="activeChapter">
            <div class="chapter-meta">
              <n-tag size="small" :type="chapterStatus(activeChapter.status).type" round>{{ chapterStatus(activeChapter.status).label }}</n-tag>
              <n-text depth="3" style="font-size: 12px">{{ (activeChapter.content || '').length }} 字 · 更新于 {{ fmtDate(activeChapter.updated_at) }}</n-text>
            </div>
            <n-input
              v-model:value="editContent"
              type="textarea"
              :rows="22"
              class="chapter-editor"
              placeholder="章节正文..."
            />
          </template>
        </n-spin>
        <template #footer>
          <n-space justify="end">
            <n-button @click="showChapter = false">关闭</n-button>
            <n-button type="primary" :loading="saving" @click="saveChapterContent">
              <template #icon><n-icon><SaveOutline /></n-icon></template>
              保存修改
            </n-button>
          </n-space>
        </template>
      </n-drawer-content>
    </n-drawer>
  </n-spin>
</template>

<script setup>
/**
 * ProjectDetail.vue — 创作工作台
 * 适配后端: ProjectResponse(title/genre/synopsis/status/skill_packs/created_at)、
 * WritingService(chapter: title/chapter_number/content/word_count/status、volume: title/volume_number/summary/status)
 */
import { ref, computed, onMounted, onUnmounted, h } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { useMessage } from 'naive-ui'
import {
  SparklesOutline,
  StatsChartOutline,
  ListOutline,
  EllipsisHorizontalOutline,
  LayersOutline,
  AddOutline,
  SaveOutline,
} from '@vicons/ionicons5'
import { projectAPI, writingAPI, aiAPI, providerAPI } from '../api/index.js'
import StreamOutput from '../components/StreamOutput.vue'

const route = useRoute()
const router = useRouter()
const message = useMessage()

const pid = () => route.params.id
const loading = ref(true)
const project = ref({})
const chapters = ref([])
const volumes = ref([])

const chNum = ref(1)
const chTitle = ref('')
const volumeId = ref(null)
const targetWords = ref(2000)
const batchStart = ref(1)
const batchEnd = ref(10)
const batchLoading = ref(false)
const streaming = ref(false)

const newVolumeTitle = ref('')
const volumeCreating = ref(false)

const showChapter = ref(false)
const activeChapter = ref(null)
const editContent = ref('')
const chapterLoading = ref(false)
const saving = ref(false)

const streamRef = ref(null)
const streamSpeed = ref(25)

// ── 每小说模型设置 ──────────────────────────────────────────────
const llmProviderId = ref(null)
const llmModel = ref('')
const llmProviderOptions = ref([])
const llmProviderConfigs = ref([])
const llmGlobal = ref({ provider: '', model: '', source: 'env' })
const llmSaving = ref(false)

const effectiveModel = computed(() => {
  if (llmProviderId.value) {
    const cfg = llmProviderConfigs.value.find((c) => c.id === llmProviderId.value)
    const base = cfg ? `${cfg.name}（${cfg.provider}）` : '已选配置'
    return llmModel.value ? `${base} / ${llmModel.value}` : `${base} / ${cfg?.model || '默认模型'}`
  }
  return llmGlobal.value.source === 'db-default'
    ? `全局默认（${llmGlobal.value.provider} / ${llmGlobal.value.model || '默认模型'}）`
    : `全局默认（环境变量 ${llmGlobal.value.provider} / ${llmGlobal.value.model}）`
})

async function loadLlmOptions() {
  try {
    const res = await providerAPI.list()
    const configs = (res.data.configs || []).filter((c) => c.enabled)
    llmProviderConfigs.value = configs
    llmGlobal.value = res.data.current || llmGlobal.value
    llmProviderOptions.value = [
      ...configs.map((c) => ({
        label: `${c.name}（${c.provider}${c.model ? ' / ' + c.model : ''}）`,
        value: c.id,
      })),
    ]
  } catch {
    /* 忽略：默认模式仍可用 */
  }
}

async function saveLlmConfig() {
  llmSaving.value = true
  try {
    await projectAPI.updateProject(pid(), {
      llm_provider_id: llmProviderId.value || null,
      llm_model: llmModel.value?.trim() || '',
    })
    message.success('模型设置已保存')
    await load()
  } catch (e) {
    message.error('保存失败: ' + (e.message || '未知错误'))
  } finally {
    llmSaving.value = false
  }
}

const isMobile = ref(false)
function checkScreen() { isMobile.value = window.innerWidth < 768 }
onMounted(() => { checkScreen(); window.addEventListener('resize', checkScreen) })
onUnmounted(() => window.removeEventListener('resize', checkScreen))

// ── 展示映射 ────────────────────────────────────────────────────
const statusMeta = (s) => ({
  draft: { label: '草稿', type: 'default' },
  writing: { label: '创作中', type: 'warning' },
  completed: { label: '已完成', type: 'success' },
}[s] || { label: s || '草稿', type: 'default' })

const genreMap = {
  fantasy: '奇幻', xuanhuan: '玄幻', xiuxian: '修仙', romance: '言情',
  scifi: '科幻', mystery: '悬疑', urban: '都市', history: '历史', wuxia: '武侠', other: '其他',
}
function genreLabel(g) { return genreMap[g] || g || '奇幻' }

function chapterStatus(s) {
  return {
    draft: { label: '草稿', type: 'default' },
    done: { label: '已完成', type: 'success' },
    revising: { label: '修订中', type: 'warning' },
  }[s] || { label: s || '草稿', type: 'default' }
}

function fmtDate(ts) {
  return ts ? String(ts).slice(0, 10) : '—'
}

const totalWords = computed(() => chapters.value.reduce((s, c) => s + (c.word_count || 0), 0))
const wordCountText = computed(() => targetWords.value.toLocaleString())

const volumeOptions = computed(() =>
  volumes.value.map((v) => ({ label: `卷${v.volume_number} · ${v.title}`, value: v.id }))
)

const quickCmds = [
  '/mcp 生大纲',
  '/mcp 写第3章 2000字',
  '/mcp 审校',
  '/mcp 参考凡人修仙传',
]

// ── SSE 端点与参数 ──────────────────────────────────────────────
const streamEndpoint = computed(() => `/api/projects/${pid()}/writing/generate-stream`)

const streamParams = computed(() => ({
  prompt: chTitle.value
    ? `写第${chNum.value}章：${chTitle.value}`
    : `写第${chNum.value}章`,
  chapter_number: chNum.value,
  style: 'narrative',
  target_word_count: targetWords.value,
  volume_id: volumeId.value || null,
}))

// ── 更多操作 ────────────────────────────────────────────────────
const moreActions = [
  {
    label: '导出作品',
    key: 'export',
    icon: () => h('span', '⬇️'),
    children: [
      { label: 'Markdown (.md)', key: 'export-md' },
      { label: '纯文本 (.txt)', key: 'export-txt' },
      { label: '全量备份 (.json)', key: 'export-json' },
    ],
  },
  { type: 'divider' },
  {
    label: `打字速度: ${streamSpeed.value}ms`,
    key: 'speed',
    children: [
      { label: '即时 (1ms)', key: 'speed-1' },
      { label: '快速 (10ms)', key: 'speed-10' },
      { label: '正常 (25ms)', key: 'speed-25' },
      { label: '慢速 (60ms)', key: 'speed-60' },
    ],
  },
]

function handleMoreAction(key) {
  if (key?.startsWith('export-')) downloadExport(key.replace('export-', ''))
  else if (key?.startsWith('speed-')) {
    streamSpeed.value = parseInt(key.replace('speed-', ''))
    const speedItem = moreActions.find((a) => a.key === 'speed')
    if (speedItem) speedItem.label = `打字速度: ${streamSpeed.value}ms`
  }
}

async function downloadExport(format) {
  try {
    const blob = await projectAPI.exportProject(pid(), format)
    const url = URL.createObjectURL(blob)
    const a = document.createElement('a')
    a.href = url
    a.download = `${project.value.title || 'novel'}.${format}`
    document.body.appendChild(a)
    a.click()
    a.remove()
    URL.revokeObjectURL(url)
    message.success(`已导出 ${format.toUpperCase()} 文件`)
  } catch (e) {
    message.error(e.message || '导出失败')
  }
}

// ── 流式生成 ────────────────────────────────────────────────────
function streamGenerate() {
  if (!chTitle.value) {
    // 允许无标题直接生成，但给个提示
  }
  if (streamRef.value) {
    streaming.value = true
    streamRef.value.start()
  }
}

function onStreamDone({ content, tokens, result }) {
  streaming.value = false
  const tok = tokens || {}
  message.success(
    `生成完成！${(content || '').length} 字${tok.total ? ` · ${tok.total} tokens` : ''}`
  )
  load()
}

async function onStreamSave({ content }) {
  try {
    await writingAPI.createChapter(pid(), {
      title: chTitle.value || `第${chNum.value}章`,
      chapter_number: chNum.value,
      content,
      volume_id: volumeId.value || null,
    })
    message.success('章节已保存')
    await load()
  } catch (e) {
    message.error('保存失败: ' + (e.message || '未知错误'))
  }
}

function onStreamError(err) {
  streaming.value = false
  message.error('生成出错: ' + (err.message || '未知错误'))
}

// ── 续写 / 润色 / 删除 ──────────────────────────────────────────
async function continueWrite(ch) {
  try {
    await aiAPI.continueWriting(pid(), { chapter_id: ch.id, direction: '' })
    message.success(`第${ch.chapter_number}章续写完成`)
    await load()
  } catch (e) {
    message.error('续写失败: ' + (e.message || '未知错误'))
  }
}

async function polish(ch) {
  try {
    await aiAPI.polish(pid(), { chapter_id: ch.id, aspect: 'general' })
    message.success(`第${ch.chapter_number}章润色完成`)
    await load()
  } catch (e) {
    message.error('润色失败: ' + (e.message || '未知错误'))
  }
}

async function deleteChapter(ch) {
  try {
    await writingAPI.deleteChapter(pid(), ch.id)
    message.success('章节已删除')
    await load()
  } catch (e) {
    message.error('删除失败')
  }
}

// ── 章节阅读/编辑 ───────────────────────────────────────────────
function selectChapter(ch) {
  activeChapter.value = ch
  editContent.value = ch.content || ''
  showChapter.value = true
}

async function openChapter(ch) {
  chapterLoading.value = true
  try {
    const res = await writingAPI.getChapter(pid(), ch.id)
    activeChapter.value = res.data
    editContent.value = res.data.content || ''
    showChapter.value = true
  } catch (e) {
    message.error('加载章节失败')
  } finally {
    chapterLoading.value = false
  }
}

async function saveChapterContent() {
  if (!activeChapter.value) return
  saving.value = true
  try {
    await writingAPI.updateChapter(pid(), activeChapter.value.id, { content: editContent.value })
    message.success('章节内容已保存')
    showChapter.value = false
    await load()
  } catch (e) {
    message.error('保存失败: ' + (e.message || '未知错误'))
  } finally {
    saving.value = false
  }
}

// ── 批量生成 ────────────────────────────────────────────────────
async function batchGen() {
  if (batchEnd.value < batchStart.value) {
    message.warning('结束章节号需 ≥ 起始章节号')
    return
  }
  batchLoading.value = true
  try {
    const prompts = []
    for (let i = batchStart.value; i <= batchEnd.value; i++) {
      prompts.push(`写第${i}章`)
    }
    const res = await aiAPI.batchGenerate(pid(), {
      prompts,
      start_chapter_number: batchStart.value,
      style: 'narrative',
      target_word_count: targetWords.value,
      volume_id: volumeId.value || null,
    })
    const data = res.data
    message.success(`批量生成完成: ${data?.generated || 0} 章${data?.errors?.length ? `，${data.errors.length} 章失败` : ''}`)
    await load()
  } catch (e) {
    message.error('批量生成失败: ' + (e.message || '未知错误'))
  } finally {
    batchLoading.value = false
  }
}

// ── 卷管理 ──────────────────────────────────────────────────────
async function createVolume() {
  const title = newVolumeTitle.value.trim()
  if (!title) {
    message.warning('请输入卷名')
    return
  }
  volumeCreating.value = true
  try {
    await writingAPI.createVolume(pid(), {
      title,
      volume_number: volumes.value.length + 1,
      status: 'planned',
    })
    message.success('卷已创建')
    newVolumeTitle.value = ''
    await loadVolumes()
  } catch (e) {
    message.error('创建卷失败')
  } finally {
    volumeCreating.value = false
  }
}

// ── 数据加载 ────────────────────────────────────────────────────
async function loadVolumes() {
  try {
    const res = await writingAPI.getVolumes(pid())
    volumes.value = res.data || []
  } catch {
    volumes.value = []
  }
}

async function load() {
  loading.value = true
  try {
    const [pRes, cRes, vRes] = await Promise.all([
      projectAPI.getProject(pid()),
      writingAPI.getChapters(pid()).catch(() => ({ data: [] })),
      writingAPI.getVolumes(pid()).catch(() => ({ data: [] })),
    ])
    project.value = pRes.data?.data || pRes.data || {}
    chapters.value = cRes.data?.data || cRes.data || []
    volumes.value = vRes.data || []
    llmProviderId.value = project.value.llm_provider_id || null
    llmModel.value = project.value.llm_model || ''
    await loadLlmOptions()
  } catch {
    project.value = { id: pid(), title: '加载失败', genre: '', synopsis: '', status: '' }
    chapters.value = []
    volumes.value = []
  } finally {
    loading.value = false
  }
}

onMounted(load)
</script>

<style scoped>
.project-hero {
  display: flex;
  justify-content: space-between;
  align-items: center;
  gap: 16px;
  flex-wrap: wrap;
  margin-bottom: 20px;
  padding: 18px 22px;
  border-radius: 14px;
  background: linear-gradient(120deg, #ffffff 0%, #f8f6ff 100%);
  border: 1px solid rgba(108, 92, 231, 0.14);
  box-shadow: 0 2px 10px rgba(28, 24, 55, 0.04);
}

.hero-main {
  display: flex;
  align-items: center;
  gap: 14px;
  min-width: 0;
}

.hero-icon {
  width: 48px;
  height: 48px;
  border-radius: 14px;
  display: flex;
  align-items: center;
  justify-content: center;
  font-size: 24px;
  background: linear-gradient(135deg, rgba(108, 92, 231, 0.16), rgba(245, 158, 11, 0.12));
  flex-shrink: 0;
}

.hero-text {
  min-width: 0;
}

.hero-title-row {
  display: flex;
  align-items: center;
  gap: 8px;
  flex-wrap: wrap;
}

.hero-title-row h2 {
  margin: 0;
  font-size: 19px;
  font-weight: 700;
}

.hero-synopsis {
  display: block;
  font-size: 12px;
  margin-top: 4px;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
  max-width: 560px;
}

.hero-actions {
  display: flex;
  gap: 8px;
  flex-shrink: 0;
}

.workspace-card {
  border-radius: 14px;
}

.card-title {
  font-weight: 600;
  font-size: 15px;
}

.gen-row {
  display: flex;
  align-items: flex-end;
  gap: 12px;
  flex-wrap: wrap;
}

.gen-field {
  display: flex;
  flex-direction: column;
  gap: 4px;
}

.gen-field.grow {
  flex: 1;
  min-width: 180px;
}

.gen-label {
  font-size: 11px;
  color: #8a8f98;
}

.batch-row {
  display: flex;
  align-items: center;
  gap: 8px;
  flex-wrap: wrap;
}

.chapter-row {
  display: flex;
  align-items: flex-start;
  gap: 12px;
  padding: 10px 12px;
  border-radius: 10px;
  cursor: pointer;
  transition: background 0.15s;
}

.chapter-row:hover {
  background: #f8f7ff;
}

.chapter-no {
  width: 30px;
  height: 30px;
  border-radius: 8px;
  background: rgba(108, 92, 231, 0.10);
  color: #6c5ce7;
  font-weight: 700;
  font-size: 13px;
  display: flex;
  align-items: center;
  justify-content: center;
  flex-shrink: 0;
  font-variant-numeric: tabular-nums;
}

.chapter-body {
  flex: 1;
  min-width: 0;
}

.chapter-title-line {
  display: flex;
  align-items: center;
  gap: 8px;
  flex-wrap: wrap;
}

.chapter-title {
  font-weight: 600;
  font-size: 14px;
}

.chapter-words {
  font-size: 11px;
  color: #9ca3af;
}

.chapter-preview {
  font-size: 12px;
  color: #6b7280;
  margin-top: 3px;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.chapter-ops {
  display: flex;
  gap: 2px;
  flex-shrink: 0;
}

.volume-list {
  display: flex;
  flex-direction: column;
  gap: 4px;
}

.volume-row {
  display: flex;
  align-items: center;
  gap: 8px;
  padding: 5px 8px;
  border-radius: 8px;
  background: #faf9f6;
}

.volume-no {
  font-size: 11px;
  font-weight: 700;
  color: #6c5ce7;
  background: rgba(108, 92, 231, 0.10);
  padding: 1px 7px;
  border-radius: 999px;
}

.volume-name {
  font-size: 13px;
}

.cmd-list {
  display: flex;
  flex-direction: column;
  gap: 6px;
}

.cmd-chip {
  font-size: 12px;
  color: #6b7280;
  background: #f4f3ff;
  border: 1px solid rgba(108, 92, 231, 0.12);
  border-radius: 8px;
  padding: 5px 10px;
  font-family: ui-monospace, SFMono-Regular, Menlo, monospace;
}

.chapter-meta {
  display: flex;
  align-items: center;
  gap: 10px;
  margin-bottom: 12px;
}

.chapter-editor {
  font-family: ui-serif, Georgia, 'Songti SC', serif;
  font-size: 15px;
  line-height: 2;
}

@media (max-width: 768px) {
  .project-hero {
    flex-direction: column;
    align-items: flex-start;
  }
  .chapter-ops {
    display: none;
  }
}
</style>
