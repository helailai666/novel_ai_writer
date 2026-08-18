<template>
  <div class="chat-page">
    <div class="page-header">
      <div class="page-title">
        <h2>💬 AI 对话</h2>
        <n-text depth="3">自由文本 → LLM 意图路由（设定 / 写作 / 审核 / 知识问答）· 流式输出（K 轮）</n-text>
      </div>
      <n-space>
        <n-button size="small" quaternary @click="clearChat">清空对话</n-button>
      </n-space>
    </div>

    <n-card class="chat-card" :bordered="false">
      <div ref="scrollRef" class="msg-list">
        <div v-for="(m, i) in messages" :key="i" class="msg" :class="m.role">
          <div class="avatar">{{ m.role === 'user' ? '🧑' : '🤖' }}</div>
          <div class="bubble">
            <div v-if="m.role === 'assistant' && m.route" class="meta-line">
              <n-tag size="tiny" :type="routeType(m.route.intent)">{{ routeLabel(m.route.intent) }}</n-tag>
              <n-tag size="tiny" type="default">{{ m.route.method === 'llm' ? 'LLM 分类' : '关键词' }}</n-tag>
              <n-tag v-if="m.saved" size="tiny" type="success">已保存</n-tag>
              <n-text v-if="m.retrieve !== undefined" depth="3" style="font-size:12px">检索到 {{ m.retrieve }} 条资料</n-text>
            </div>
            <div class="text" v-html="renderText(m.content)" />
            <div v-if="m.tools.length" class="tool-chips">
              <n-tag v-for="(t, j) in m.tools" :key="j" size="tiny" type="warning">🔧 {{ t }}</n-tag>
            </div>
            <div v-if="m.sources.length" class="sources">
              <n-collapse>
                <n-collapse-item title="📎 参考来源" name="src">
                  <div v-for="(s, j) in m.sources" :key="j" class="source-item">
                    <n-tag size="tiny" :type="sourceType(s.type)">{{ s.type }}</n-tag>
                    <b>{{ s.title }}</b>
                    <span>{{ s.content }}</span>
                    <a v-if="s.url" :href="s.url" target="_blank" rel="noreferrer">🔗</a>
                  </div>
                </n-collapse-item>
              </n-collapse>
            </div>
            <div v-if="m.error" class="error">❌ {{ m.error }}</div>
          </div>
        </div>
        <n-empty v-if="!messages.length" description="输入问题开始对话，如：这个世界的修仙境界怎么划分？" style="margin-top:60px" />
      </div>

      <div class="input-row">
        <n-input
          v-model:value="draft"
          type="textarea"
          :rows="2"
          :disabled="running"
          placeholder="问设定、写章节、审内容、查知识…（Enter 发送，Shift+Enter 换行）"
          @keydown="onKey"
        />
        <n-button type="primary" :loading="running" @click="send" class="send-btn">
          <template #icon><n-icon><SendOutline /></n-icon></template>
          发送
        </n-button>
      </div>
    </n-card>
  </div>
</template>

<script setup>
/**
 * ChatView.vue — AI 对话面板（K 轮）
 * 消费 /api/agents/chat SSE：路由徽标 + 流式打字机 + 工具 chips + 来源折叠 + localStorage 持久化
 */
import { ref, computed, onMounted, nextTick } from 'vue'
import { useRoute } from 'vue-router'
import { useMessage, NIcon } from 'naive-ui'
import { SendOutline } from '@vicons/ionicons5'
import { agentsAPI } from '../api/index.js'

const route = useRoute()
const message = useMessage()
const projectId = computed(() => route.params.id)

const storageKey = computed(() => `dsh.chat.${projectId.value}`)

const messages = ref([])
const draft = ref('')
const running = ref(false)
const scrollRef = ref(null)

const ROUTE_META = {
  setting: { label: '设定', type: 'info' },
  chapter: { label: '写作', type: 'primary' },
  review: { label: '审核', type: 'warning' },
  qa: { label: '问答', type: 'success' },
}
function routeType(intent) { return (ROUTE_META[intent] || {}).type || 'default' }
function routeLabel(intent) { return (ROUTE_META[intent] || {}).label || intent }
function sourceType(t) { return { doc: 'info', meme: 'warning', web: 'success' }[t] || 'default' }

// ── 渲染（换行 → <br>，避免 XSS：仅转义后的文本）─────────────────
function renderText(content) {
  return String(content || '')
    .replace(/&/g, '&amp;').replace(/</g, '&lt;').replace(/>/g, '&gt;')
    .replace(/\n/g, '<br/>')
}

// ── 持久化 ───────────────────────────────────────────────────────
function save() {
  try {
    localStorage.setItem(storageKey.value, JSON.stringify(messages.value))
  } catch (e) { /* 忽略配额错误 */ }
}

function clearChat() {
  messages.value = []
  try { localStorage.removeItem(storageKey.value) } catch (e) { /* 忽略 */ }
}

onMounted(() => {
  try {
    const raw = localStorage.getItem(storageKey.value)
    if (raw) messages.value = JSON.parse(raw) || []
  } catch (e) { /* 忽略 */ }
})

// ── 发送 / SSE 消费 ──────────────────────────────────────────────
async function send() {
  const task = draft.value.trim()
  if (!task || running.value) return
  draft.value = ''
  running.value = true
  messages.value.push({ role: 'user', content: task, tools: [], sources: [], error: '' })
  const m = { role: 'assistant', content: '', route: null, tools: [], sources: [], error: '', saved: false, retrieve: undefined }
  messages.value.push(m)
  scrollToBottom()
  save()

  try {
    const res = await agentsAPI.chat({ graph: 'chat', project_id: projectId.value, task })
    if (!res.ok || !res.body) throw new Error(`请求失败（${res.status}）`)
    const reader = res.body.getReader()
    const decoder = new TextDecoder()
    let buf = ''
    for (;;) {
      const { done, value } = await reader.read()
      if (done) break
      buf += decoder.decode(value, { stream: true })
      let idx
      while ((idx = buf.indexOf('\n\n')) >= 0) {
        const frame = buf.slice(0, idx)
        buf = buf.slice(idx + 2)
        for (const line of frame.split('\n')) {
          if (!line.startsWith('data: ')) continue
          let ev
          try { ev = JSON.parse(line.slice(6)) } catch { continue }
          handleEvent(m, ev)
        }
      }
    }
    if (buf.trim()) {
      for (const line of buf.split('\n')) {
        if (!line.startsWith('data: ')) continue
        try { handleEvent(m, JSON.parse(line.slice(6))) } catch { /* 忽略 */ }
      }
    }
  } catch (e) {
    m.error = e.message || '对话请求失败'
  } finally {
    running.value = false
    save()
    scrollToBottom()
  }
}

function handleEvent(m, ev) {
  switch (ev.type) {
    case 'route':
      m.route = { intent: ev.intent, method: ev.method }
      save()
      break
    case 'token':
      m.content += ev.content || ''
      break
    case 'tool_call':
      if (ev.tool && !m.tools.includes(ev.tool)) m.tools.push(ev.tool)
      break
    case 'retrieve':
      m.retrieve = ev.hits
      break
    case 'done': {
      const r = ev.result || {}
      m.saved = r.saved === true
      if (r.sources) m.sources = r.sources
      if (r.error) m.error = r.error
      break
    }
    case 'error':
      m.error = ev.message || '图执行出错'
      break
    default:
      break
  }
  scrollToBottom()
}

function onKey(e) {
  if (e.key === 'Enter' && !e.shiftKey && !e.isComposing) {
    e.preventDefault()
    send()
  }
}

async function scrollToBottom() {
  await nextTick()
  if (scrollRef.value) scrollRef.value.scrollTop = scrollRef.value.scrollHeight
}
</script>

<style scoped>
.chat-page { max-width: 1000px; margin: 0 auto; }
.page-header { display: flex; justify-content: space-between; align-items: flex-start; margin-bottom: 16px; }
.page-title h2 { margin: 0 0 4px; }
.chat-card { background: #fff; }
.msg-list { height: calc(100vh - 320px); min-height: 360px; overflow-y: auto; padding: 4px 8px; }
.msg { display: flex; gap: 10px; margin-bottom: 14px; }
.msg.user { flex-direction: row-reverse; }
.avatar { width: 34px; height: 34px; border-radius: 50%; background: #f3f4f6; display: flex; align-items: center; justify-content: center; font-size: 18px; flex-shrink: 0; }
.bubble {
  max-width: 78%; padding: 10px 14px; border-radius: 12px; background: #f6f8fa; font-size: 14px; line-height: 1.7;
}
.msg.user .bubble { background: #e94560; color: #fff; }
.meta-line { display: flex; flex-wrap: wrap; gap: 6px; align-items: center; margin-bottom: 6px; }
.text { white-space: normal; word-break: break-word; }
.tool-chips { display: flex; flex-wrap: wrap; gap: 4px; margin-top: 6px; }
.sources { margin-top: 8px; font-size: 12px; }
.source-item { display: flex; align-items: flex-start; gap: 6px; padding: 3px 0; }
.source-item span { color: #6b7280; flex: 1; }
.error { margin-top: 6px; color: #ef4444; font-size: 13px; }
.input-row { display: flex; gap: 10px; margin-top: 12px; align-items: flex-end; }
.send-btn { height: 64px; }
</style>
