<template>
  <n-spin :show="loading">
    <n-page-header @back="$router.push('/projects')">
      <template #title>📖 {{ project?.title || '加载中...' }}</template>
      <template #extra>
        <n-button size="small" @click="$router.push(`/projects/${$route.params.id}/dashboard`)">📊 总览</n-button>
        <n-button size="small" @click="$router.push(`/projects/${$route.params.id}/outline`)">📜 大纲</n-button>
        <n-button size="small" @click="$router.push(`/projects/${$route.params.id}/world`)">🌍 世界观</n-button>
        <n-button size="small" @click="$router.push(`/projects/${$route.params.id}/characters`)">🎭 角色</n-button>
        <n-button size="small" @click="$router.push(`/projects/${$route.params.id}/factions`)">🏛️ 势力</n-button>
        <n-button size="small" @click="$router.push(`/projects/${$route.params.id}/settings`)">⚙️ 设定</n-button>
        <n-button size="small" style="margin-left:8px" @click="$router.push(`/projects/${$route.params.id}/review`)">🔍 审核</n-button>
      </template>
    </n-page-header>

    <n-grid :cols="3" :x-gap="16" style="margin-top:20px;">
      <n-grid-item span="2">
        <!-- 创作区 -->
        <n-card title="✍️ 创作" style="margin-bottom:16px;">
          <n-space vertical>
            <n-space>
              <n-input-number v-model:value="chNum" :min="1" style="width:80px" />
              <n-input v-model:value="chTitle" placeholder="章节标题(可选)" style="width:250px" />
              <n-button
                type="primary"
                @click="streamGenerate"
                :disabled="streamRef?.status === 'streaming' || streamRef?.status === 'connecting'"
              >
                <template #icon><n-icon><SparklesOutline /></n-icon></template>
                流式生成
              </n-button>
              <n-dropdown trigger="click" :options="moreActions" @select="handleMoreAction">
                <n-button>更多 ▾</n-button>
              </n-dropdown>
            </n-space>
            <n-space>
              <n-input-number v-model:value="batchStart" :min="1" style="width:80px" />
              <span>~</span>
              <n-input-number v-model:value="batchEnd" :min="1" style="width:80px" />
              <n-button @click="batchGen" :loading="batchLoading">批量生成</n-button>
            </n-space>
          </n-space>
        </n-card>

        <!-- 流式输出区 — 使用 StreamOutput 组件 -->
        <n-card title="📝 生成结果" style="margin-bottom:16px;">
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

        <!-- 章节列表 -->
        <n-card title="📑 章节列表">
          <template v-if="chapters.length">
            <n-thing
              v-for="ch in chapters"
              :key="ch.id"
              :title="`第${ch.chapter_number}章 ${ch.title || ''}`"
              style="margin-bottom:8px;"
            >
              <p style="color:#888;font-size:13px;">{{ ch.content?.slice(0, 80) }}...</p>
            </n-thing>
          </template>
          <n-empty v-else description="暂无章节，点击流式生成开始写作" />
        </n-card>
      </n-grid-item>

      <!-- 侧边信息 -->
      <n-grid-item>
        <n-card title="📊 项目信息">
          <n-descriptions :column="1" label-placement="left">
            <n-descriptions-item label="类型">{{ project?.genre }}</n-descriptions-item>
            <n-descriptions-item label="风格">{{ project?.style }}</n-descriptions-item>
            <n-descriptions-item label="状态">{{ project?.status || '创作中' }}</n-descriptions-item>
            <n-descriptions-item label="进度">{{ project?.progress || 0 }}%</n-descriptions-item>
            <n-descriptions-item label="章节数">{{ chapters.length }}</n-descriptions-item>
          </n-descriptions>
          <n-progress type="line" :percentage="project?.progress || 0" style="margin-top:12px;" />
        </n-card>

        <n-card title="🤖 MCP 快捷指令" style="margin-top:16px;">
          <p style="font-size:13px;color:#888;line-height:2;">
            <code>/mcp 生大纲</code><br/>
            <code>/mcp 写第3章 2000字</code><br/>
            <code>/mcp 审校</code><br/>
            <code>/mcp 参考凡人修仙传</code>
          </p>
        </n-card>
      </n-grid-item>
    </n-grid>
  </n-spin>
</template>

<script setup>
/**
 * ProjectDetail.vue — 创作工作台
 *
 * 集成 StreamOutput 组件，支持 SSE 流式生成 + 打字机展示。
 */
import { ref, computed, onMounted, h } from 'vue'
import { useRoute } from 'vue-router'
import { useMessage } from 'naive-ui'
import { SparklesOutline } from '@vicons/ionicons5'
import { projectAPI, writingAPI, aiAPI } from '../api/index.js'
import StreamOutput from '../components/StreamOutput.vue'

const route = useRoute()
const router = useRouter()
const message = useMessage()

const pid = () => route.params.id
const loading = ref(true)
const project = ref({})
const chapters = ref([])
const chNum = ref(1)
const chTitle = ref('')
const batchStart = ref(1)
const batchEnd = ref(10)
const batchLoading = ref(false)

// StreamOutput 组件引用
const streamRef = ref(null)

// 打字机速度
const streamSpeed = ref(25)

// ── SSE 端点与参数 ──────────────────────────────────────────────

const streamEndpoint = computed(() => {
  return `/api/projects/${pid()}/writing/generate-stream`
})

const streamParams = computed(() => ({
  prompt: chTitle.value
    ? `写第${chNum.value}章：${chTitle.value}，2000字`
    : `写第${chNum.value}章，2000字`,
  chapter_number: chNum.value,
  style: project.value?.style || 'narrative',
  target_word_count: 2000,
}))

// ── 更多操作 ────────────────────────────────────────────────────

const moreActions = [
  {
    label: '续写',
    key: 'continue',
    icon: () => h('span', '✏️'),
  },
  {
    label: '润色',
    key: 'polish',
    icon: () => h('span', '✨'),
  },
  {
    type: 'divider',
  },
  {
    label: `打字速度: ${streamSpeed.value}ms`,
    key: 'speed',
    children: [
      { label: '快速 (10ms)', key: 'speed-10' },
      { label: '正常 (25ms)', key: 'speed-25' },
      { label: '慢速 (60ms)', key: 'speed-60' },
      { label: '即时 (1ms)', key: 'speed-1' },
    ],
  },
]

function handleMoreAction(key) {
  if (key === 'continue') continueWrite()
  else if (key === 'polish') polish()
  else if (key?.startsWith('speed-')) {
    streamSpeed.value = parseInt(key.replace('speed-', ''))
    moreActions.find(a => a.key === 'speed').label = `打字速度: ${streamSpeed.value}ms`
  }
}

// ── 流式生成 ────────────────────────────────────────────────────

function streamGenerate() {
  if (streamRef.value) {
    streamRef.value.start()
  }
}

/** 流式生成完成回调 */
function onStreamDone({ content, tokens }) {
  message.success(`生成完成！${tokens.total} tokens 消耗`)
  // 刷新章节列表
  load()
}

/** 保存回调 */
async function onStreamSave({ content }) {
  try {
    await writingAPI.createChapter(pid(), {
      title: chTitle.value || `第${chNum.value}章`,
      chapter_number: chNum.value,
      content,
    })
    message.success('章节已保存')
    await load()
  } catch (e) {
    message.error('保存失败: ' + (e.message || '未知错误'))
  }
}

function onStreamError(err) {
  message.error('生成出错: ' + (err.message || '未知错误'))
}

// ── 传统操作 ────────────────────────────────────────────────────

async function continueWrite() {
  if (!chapters.value.length) { message.warning('暂无章节，请先生成章节') ; return }
  const lastChapter = chapters.value[chapters.value.length - 1]
  try {
    await aiAPI.continueWriting(pid(), { chapter_id: lastChapter.id, direction: '' })
    message.success('续写完成')
    await load()
  } catch (e) { message.error('续写失败: ' + (e.message || '未知错误')) }
}

async function polish() {
  if (!chapters.value.length) { message.warning('暂无章节，请先生成章节') ; return }
  const lastChapter = chapters.value[chapters.value.length - 1]
  try {
    await aiAPI.polish(pid(), { chapter_id: lastChapter.id, aspect: 'general' })
    message.success('润色完成')
    await load()
  } catch (e) { message.error('润色失败: ' + (e.message || '未知错误')) }
}

async function batchGen() {
  batchLoading.value = true
  try {
    const prompts = []
    for (let i = batchStart.value; i <= batchEnd.value; i++) {
      prompts.push(`写第${i}章，2000字`)
    }
    const res = await aiAPI.batchGenerate(pid(), {
      prompts,
      start_chapter_number: batchStart.value,
      style: project.value?.style || 'narrative',
      target_word_count: 2000,
    })
    message.success(`批量生成完成: ${res.data?.generated || 0} 章`)
    await load()
  } catch (e) {
    message.error('批量生成失败: ' + (e.message || '未知错误'))
  } finally {
    batchLoading.value = false
  }
}

// ── 数据加载 ────────────────────────────────────────────────────

async function load() {
  loading.value = true
  try {
    const [pRes, cRes] = await Promise.all([
      projectAPI.getProject(pid()),
      writingAPI.getChapters(pid()).catch(() => ({ data: [] })),
    ])
    project.value = pRes.data?.data || pRes.data || {}
    chapters.value = cRes.data?.data || cRes.data || []
  } catch {
    project.value = {
      id: pid(),
      title: '示例项目',
      genre: '玄幻',
      style: '爽文',
      progress: 15,
    }
    chapters.value = [
      {
        id: 1,
        chapter_number: 1,
        title: '初入仙途',
        content: '林玄站在宗门广场上...',
      },
    ]
  } finally {
    loading.value = false
  }
}

onMounted(load)
</script>
