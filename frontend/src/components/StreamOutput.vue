<template>
  <div class="stream-output">
    <!-- 工具栏 -->
    <div class="stream-toolbar">
      <n-space align="center">
        <n-tag :type="statusTagType" size="small">
          {{ statusLabel }}
        </n-tag>

        <n-button-group size="tiny">
          <n-button
            v-if="status === 'idle' || status === 'done' || status === 'error'"
            type="primary"
            @click="start"
            :loading="status === 'connecting'"
          >
            <template #icon><n-icon><PlayOutline /></n-icon></template>
            开始生成
          </n-button>

          <n-button
            v-if="status === 'streaming'"
            @click="pause"
          >
            <template #icon><n-icon><PauseOutline /></n-icon></template>
            暂停
          </n-button>

          <n-button
            v-if="status === 'paused'"
            type="warning"
            @click="resume"
          >
            <template #icon><n-icon><PlayOutline /></n-icon></template>
            继续
          </n-button>

          <n-button
            v-if="status !== 'idle'"
            @click="reset"
          >
            <template #icon><n-icon><RefreshOutline /></n-icon></template>
            重置
          </n-button>
        </n-button-group>

        <n-divider vertical />

        <!-- Token 统计 -->
        <n-popover trigger="hover" placement="bottom">
          <template #trigger>
            <n-tag type="info" size="small" round>
              🪙 {{ tokenStats.total }} tokens
            </n-tag>
          </template>
          <n-descriptions :column="1" size="small" label-placement="left">
            <n-descriptions-item label="输入 Token">{{ tokenStats.input }}</n-descriptions-item>
            <n-descriptions-item label="输出 Token">{{ tokenStats.output }}</n-descriptions-item>
            <n-descriptions-item label="总计">{{ tokenStats.total }}</n-descriptions-item>
          </n-descriptions>
        </n-popover>

        <n-tag size="small" v-if="wordCount > 0">
          📝 {{ wordCount }} 字
        </n-tag>

        <n-tag size="small" v-if="elapsedSeconds > 0" type="default">
          ⏱ {{ formatTime(elapsedSeconds) }}
        </n-tag>
      </n-space>

      <!-- 进度条 -->
      <n-progress
        v-if="status === 'streaming' || status === 'paused'"
        type="line"
        :percentage="progressPercent"
        :color="progressColor"
        :height="3"
        :border-radius="2"
        style="margin-top: 8px"
      />
    </div>

    <!-- 输出内容区 -->
    <div
      class="stream-content"
      :class="{ 'is-empty': !displayText && status === 'idle' }"
      ref="contentRef"
    >
      <!-- 打字机文本 -->
      <div class="stream-text" v-if="displayText">
        <span
          v-for="(char, idx) in displayChars"
          :key="idx"
          :style="{ animationDelay: `${idx * 15}ms` }"
          class="char-fade-in"
        >{{ char }}</span>
        <span v-if="status === 'streaming'" class="cursor-blink">▌</span>
      </div>

      <!-- 空状态 -->
      <n-empty
        v-else-if="status === 'idle'"
        description="点击「开始生成」启动 AI 创作"
        size="large"
      />

      <!-- 错误 -->
      <n-result
        v-if="status === 'error'"
        status="error"
        :title="errorMessage"
        description="请检查后端服务是否正常运行"
        size="small"
      >
        <template #footer>
          <n-button @click="start" type="primary">重试</n-button>
        </template>
      </n-result>

      <!-- 完成标记 -->
      <div v-if="status === 'done'" class="done-marker">
        <n-divider>
          <n-tag type="success" round>✨ 生成完成 · {{ wordCount }} 字</n-tag>
        </n-divider>
      </div>
    </div>

    <!-- 底部操作 -->
    <div class="stream-footer" v-if="displayText">
      <n-space justify="end">
        <n-button size="small" text @click="copyContent">
          <template #icon><n-icon><CopyOutline /></n-icon></template>
          复制
        </n-button>
        <n-button size="small" text @click="saveContent" v-if="status === 'done'">
          <template #icon><n-icon><SaveOutline /></n-icon></template>
          保存到章节
        </n-button>
      </n-space>
    </div>
  </div>
</template>

<script setup>
/**
 * StreamOutput.vue — SSE 流式内容展示组件
 *
 * 功能：
 * - 逐字打字机效果展示 AI 生成内容
 * - 暂停 / 继续 控制
 * - Token 消耗统计
 * - 字数 / 耗时实时统计
 *
 * Props:
 *   endpoint  — SSE 端点 URL
 *   params    — POST 请求体参数
 *   speed     — 打字速度（毫秒/字符），默认 25
 */
import { ref, computed, watch, onUnmounted, nextTick } from 'vue'
import {
  PlayOutline,
  PauseOutline,
  RefreshOutline,
  CopyOutline,
  SaveOutline,
} from '@vicons/ionicons5'
import { useMessage, useClipboard } from 'naive-ui'

const props = defineProps({
  endpoint: { type: String, required: true },
  params: { type: Object, default: () => ({}) },
  speed: { type: Number, default: 25 },
})

const emit = defineEmits(['done', 'save', 'error'])

const message = useMessage()
const { copy } = useClipboard()

// ── 状态 ────────────────────────────────────────────────────────
const status = ref('idle')            // idle | connecting | streaming | paused | done | error
const fullText = ref('')              // 完整接收到的文本
const displayText = ref('')           // 打字机展示的文本
const errorMessage = ref('')
const contentRef = ref(null)

// Token 统计
const tokenStats = ref({ input: 0, output: 0, total: 0 })

// 计时
const startTime = ref(0)
const elapsedSeconds = ref(0)
let timerInterval = null

// 进度估算
const progressPercent = ref(0)

// 中止控制器
let abortController = null

// ── 计算属性 ────────────────────────────────────────────────────

/** 逐字拆分（用于打字机动画） */
const displayChars = computed(() => {
  return [...displayText.value]
})

/** 字数统计 */
const wordCount = computed(() => {
  // 中文字符 + 英文单词
  const chineseChars = (fullText.value.match(/[\u4e00-\u9fff]/g) || []).length
  const englishWords = (fullText.value.match(/[a-zA-Z]+/g) || []).length
  return chineseChars + englishWords
})

/** 状态标签 */
const statusLabel = computed(() => {
  const map = {
    idle: '⏳ 就绪',
    connecting: '🔗 连接中...',
    streaming: '⚡ 生成中',
    paused: '⏸️ 已暂停',
    done: '✅ 完成',
    error: '❌ 错误',
  }
  return map[status.value] || status.value
})

const statusTagType = computed(() => {
  const map = {
    idle: 'default',
    connecting: 'info',
    streaming: 'primary',
    paused: 'warning',
    done: 'success',
    error: 'error',
  }
  return map[status.value] || 'default'
})

const progressColor = computed(() => {
  if (status.value === 'paused') return '#f0a020'
  return '#7C3AED'
})

// ── 方法 ────────────────────────────────────────────────────────

/** 启动 SSE 流式请求 */
async function start() {
  if (status.value === 'streaming' || status.value === 'connecting') return

  // 重置状态
  fullText.value = ''
  displayText.value = ''
  errorMessage.value = ''
  progressPercent.value = 0
  tokenStats.value = { input: 0, output: 0, total: 0 }
  status.value = 'connecting'
  startTime.value = Date.now()
  startTimer()

  abortController = new AbortController()

  try {
    const response = await fetch(props.endpoint, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(props.params),
      signal: abortController.signal,
    })

    if (!response.ok) {
      throw new Error(`HTTP ${response.status}: ${response.statusText}`)
    }

    status.value = 'streaming'

    const reader = response.body.getReader()
    const decoder = new TextDecoder()
    let buffer = ''

    while (true) {
      const { done, value } = await reader.read()
      if (done) break

      buffer += decoder.decode(value, { stream: true })

      // 解析 SSE 事件
      const lines = buffer.split('\n')
      buffer = lines.pop() || ''  // 保留不完整的行

      for (const line of lines) {
        if (line.startsWith('data: ')) {
          const jsonStr = line.slice(6).trim()
          if (!jsonStr) continue

          try {
            const data = JSON.parse(jsonStr)
            handleSSEData(data)
          } catch {
            // 非 JSON 数据，直接当文本追加
            fullText.value += jsonStr
            updateDisplay()
          }
        }
      }
    }

    // 流结束
    stopTimer()
    if (status.value === 'streaming') {
      status.value = 'done'
      progressPercent.value = 100
      // 确保所有文本显示完毕
      displayText.value = fullText.value
      emit('done', { content: fullText.value, tokens: tokenStats.value })
    }
  } catch (err) {
    if (err.name === 'AbortError') {
      // 用户主动中止，不报错
      if (status.value !== 'paused') {
        status.value = 'idle'
      }
    } else {
      stopTimer()
      status.value = 'error'
      errorMessage.value = err.message || '未知错误'
      emit('error', err)
    }
  }
}

/** 处理单条 SSE 数据 */
function handleSSEData(data) {
  if (data.done) {
    // 生成完成信号
    stopTimer()
    status.value = 'done'
    progressPercent.value = 100
    displayText.value = fullText.value
    emit('done', { content: fullText.value, tokens: tokenStats.value })
    return
  }

  if (data.error) {
    throw new Error(data.error)
  }

  if (data.chunk) {
    fullText.value += data.chunk
    updateDisplay()
  }

  // Token 统计
  if (data.token_input !== undefined || data.token_output !== undefined) {
    tokenStats.value.input = data.token_input || tokenStats.value.input
    tokenStats.value.output = data.token_output || tokenStats.value.output
    tokenStats.value.total = tokenStats.value.input + tokenStats.value.output
  }

  // 估算进度（按字数）
  if (data.total_length) {
    progressPercent.value = Math.min(
      100,
      Math.round((fullText.value.length / data.total_length) * 100)
    )
  } else {
    // 粗略估计：假设目标 2000 字
    progressPercent.value = Math.min(99, Math.round((wordCount.value / 2000) * 100))
  }
}

/** 更新打字机展示 */
let typewriterTimer = null
function updateDisplay() {
  // 暂停状态下不更新展示
  if (status.value === 'paused') return

  // 清除之前的打字机定时器
  if (typewriterTimer) clearTimeout(typewriterTimer)

  const typeNext = () => {
    if (displayText.value.length < fullText.value.length && status.value !== 'paused') {
      // 每次追加 1-3 个字符，模拟打字效果
      const nextLen = Math.min(
        displayText.value.length + Math.floor(Math.random() * 3) + 1,
        fullText.value.length
      )
      displayText.value = fullText.value.slice(0, nextLen)

      // 自动滚动到底部
      nextTick(() => {
        if (contentRef.value) {
          contentRef.value.scrollTop = contentRef.value.scrollHeight
        }
      })

      typewriterTimer = setTimeout(typeNext, props.speed)
    }
  }
  typeNext()
}

/** 暂停 */
function pause() {
  if (status.value !== 'streaming') return
  status.value = 'paused'
  stopTimer()
  // 不 abort 连接，只是暂停展示
}

/** 继续 */
function resume() {
  if (status.value !== 'paused') return
  status.value = 'streaming'
  startTime.value = Date.now() - elapsedSeconds.value * 1000
  startTimer()
  // 继续打字机效果
  updateDisplay()
}

/** 重置 */
function reset() {
  if (abortController) {
    abortController.abort()
    abortController = null
  }
  stopTimer()
  if (typewriterTimer) clearTimeout(typewriterTimer)
  status.value = 'idle'
  fullText.value = ''
  displayText.value = ''
  progressPercent.value = 0
  tokenStats.value = { input: 0, output: 0, total: 0 }
  elapsedSeconds.value = 0
}

/** 复制内容 */
function copyContent() {
  copy(fullText.value).then(() => {
    message.success('已复制到剪贴板')
  }).catch(() => {
    message.error('复制失败，请手动复制')
  })
}

/** 保存到章节 */
function saveContent() {
  emit('save', { content: fullText.value, tokens: tokenStats.value })
  message.success('已提交保存')
}

// ── 计时器 ──────────────────────────────────────────────────────
function startTimer() {
  stopTimer()
  timerInterval = setInterval(() => {
    elapsedSeconds.value = Math.floor((Date.now() - startTime.value) / 1000)
  }, 1000)
}

function stopTimer() {
  if (timerInterval) {
    clearInterval(timerInterval)
    timerInterval = null
  }
}

function formatTime(seconds) {
  const m = Math.floor(seconds / 60)
  const s = seconds % 60
  return `${m}:${s.toString().padStart(2, '0')}`
}

// ── 清理 ────────────────────────────────────────────────────────
onUnmounted(() => {
  if (abortController) abortController.abort()
  stopTimer()
  if (typewriterTimer) clearTimeout(typewriterTimer)
})
</script>

<style scoped>
.stream-output {
  border: 1px solid var(--n-border-color, #e0e0e0);
  border-radius: 8px;
  overflow: hidden;
  background: var(--n-color, #fff);
}

.stream-toolbar {
  padding: 12px 16px;
  border-bottom: 1px solid var(--n-border-color, #e0e0e0);
  background: var(--n-color-embedded, #fafafa);
}

.stream-content {
  min-height: 200px;
  max-height: 500px;
  overflow-y: auto;
  padding: 20px 24px;
  font-size: 15px;
  line-height: 2;
  color: var(--n-text-color, #333);
  background: #fff;
}

.stream-content.is-empty {
  display: flex;
  align-items: center;
  justify-content: center;
}

.stream-text {
  white-space: pre-wrap;
  word-break: break-word;
}

.char-fade-in {
  animation: fadeIn 0.15s ease-out;
}

@keyframes fadeIn {
  from { opacity: 0; transform: translateY(2px); }
  to   { opacity: 1; transform: translateY(0); }
}

.cursor-blink {
  animation: blink 1s step-end infinite;
  color: #7C3AED;
  font-weight: bold;
}

@keyframes blink {
  0%, 100% { opacity: 1; }
  50%      { opacity: 0; }
}

.done-marker {
  margin-top: 16px;
}

.stream-footer {
  padding: 8px 16px;
  border-top: 1px solid var(--n-border-color, #e0e0e0);
  background: var(--n-color-embedded, #fafafa);
}
</style>
