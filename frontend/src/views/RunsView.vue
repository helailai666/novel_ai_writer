<template>
  <n-spin :show="loading">
    <div class="page-header">
      <div class="page-title">
        <div class="page-title-icon">⚡</div>
        <div>
          <h2>运行记录</h2>
          <n-text depth="3">LangGraph 各图运行审计 · 事件时间线可视化</n-text>
        </div>
      </div>
      <div class="page-actions">
        <n-select v-model:value="graphFilter" :options="graphOptions" placeholder="全部图" clearable style="width:130px" @update:value="loadRuns" />
        <n-select v-model:value="statusFilter" :options="statusOptions" placeholder="全部状态" clearable style="width:130px" @update:value="loadRuns" />
        <n-space align="center" class="auto-refresh">
          <n-switch v-model:value="autoRefresh" size="small" />
          <n-text depth="3" style="font-size:12px">自动刷新{{ pollHint }}</n-text>
        </n-space>
        <n-button @click="loadRuns">
          <template #icon><n-icon><RefreshOutline /></n-icon></template>
          刷新
        </n-button>
        <n-button type="error" ghost @click="clearAllRuns">
          <template #icon><n-icon><TrashOutline /></n-icon></template>
          清空记录
        </n-button>
      </div>
    </div>

    <n-card size="small" :bordered="false">
      <n-data-table
        :columns="columns"
        :data="runs"
        :loading="loading"
        :row-key="(r) => r.id"
        :pagination="{ pageSize: 15 }"
      />
      <n-empty v-if="!runs.length && !loading" description="暂无运行记录。在创作工作台发起一次生成/审核后即可看到" style="margin-top:40px" />
    </n-card>

    <!-- 详情抽屉 -->
    <n-drawer v-model:show="showDetail" :width="680" placement="right" style="max-width: 100vw">
      <n-drawer-content :title="detailTitle" closable>
        <n-spin :show="detailLoading">
          <template v-if="detail.id">
            <!-- 统计条 -->
            <n-space class="stats-bar" :wrap="true">
              <n-tag :type="statusType(detail.status)" size="small">{{ statusText(detail.status) }}</n-tag>
              <n-tag size="small" type="info">{{ detail.graph_name }}</n-tag>
              <n-tag size="small">总 token: {{ detail.total_tokens }}</n-tag>
              <n-tag size="small">耗时: {{ detail.duration_seconds }}s</n-tag>
              <n-tag size="small">{{ fmtTime(detail.created_at) }}</n-tag>
            </n-space>

            <n-tabs type="line" size="small" style="margin-top:12px">
              <n-tab-pane name="events" tab="事件时间线">
                <!-- 节点耗时 -->
                <div class="block-title">节点耗时</div>
                <n-space v-if="nodeSpans.length" :wrap="true" style="margin-bottom:8px">
                  <n-tag v-for="s in nodeSpans" :key="s.node" size="small" :bordered="false" round>
                    {{ s.node }} · {{ s.duration.toFixed(1) }}s
                  </n-tag>
                </n-space>
                <n-space v-if="Object.keys(detail.token_counts || {}).length" :wrap="true" style="margin-bottom:8px">
                  <n-tag v-for="(v, k) in detail.token_counts" :key="k" size="small" type="warning" :bordered="false">
                    {{ k }}: {{ v }} tok
                  </n-tag>
                </n-space>

                <!-- 事件流 -->
                <div class="block-title">事件流</div>
                <div v-if="detail.events.length" class="timeline">
                  <div v-for="(ev, i) in detail.events" :key="i" class="timeline-item">
                    <span class="tl-dot" :class="dotClass(ev.type)" />
                    <span class="tl-icon">{{ iconFor(ev.type) }}</span>
                    <div class="tl-body">
                      <span class="tl-type" :class="dotClass(ev.type)">{{ ev.type }}</span>
                      <span v-if="ev.node" class="tl-node">{{ ev.node }}</span>
                      <span v-if="ev.tool" class="tl-tool">{{ ev.tool }}</span>
                      <span v-if="ev.dimension" class="tl-score">{{ ev.dimension }}: {{ ev.score }}</span>
                      <span v-if="ev.round !== undefined" class="tl-round">round {{ ev.round }} · {{ ev.status }}</span>
                      <span v-if="ev.intent" class="tl-intent">→ {{ ev.intent }} ({{ ev.method }})</span>
                      <span v-if="ev.summary" class="tl-summary">{{ ev.summary }}</span>
                      <pre v-if="ev.type === 'tool_call' && ev.args" class="tl-args">{{ pretty(ev.args) }}</pre>
                      <span v-if="ev.message" class="tl-error">{{ ev.message }}</span>
                      <span v-if="ev.ts" class="tl-ts">{{ fmtTime(ev.ts) }}</span>
                    </div>
                  </div>
                </div>
                <n-empty v-else description="该运行未产生结构化事件" size="small" />
              </n-tab-pane>

              <n-tab-pane name="input" tab="输入">
                <pre class="json-block">{{ pretty(detail.input_data) }}</pre>
              </n-tab-pane>

              <n-tab-pane name="output" tab="输出">
                <pre class="json-block">{{ pretty(detail.output_data) }}</pre>
              </n-tab-pane>
            </n-tabs>
          </template>
        </n-spin>
      </n-drawer-content>
    </n-drawer>
  </n-spin>
</template>

<script setup>
/**
 * RunsView.vue — 运行记录（G4）
 * 列表 + 过滤 + 详情抽屉（节点耗时 / token 统计 / 事件时间线 / 输入输出）
 */
import { ref, computed, h, onMounted, onUnmounted, watch } from 'vue'
import { useRoute } from 'vue-router'
import { useMessage, NTag, NButton, NIcon, NSwitch } from 'naive-ui'
import { RefreshOutline, EyeOutline, TrashOutline } from '@vicons/ionicons5'
import { agentsAPI } from '../api/index.js'

const route = useRoute()
const message = useMessage()
const projectId = computed(() => route.params.id)

const loading = ref(false)
const runs = ref([])
const graphFilter = ref(null)
const statusFilter = ref(null)

// ── H2 自动刷新：有 running 运行时每 5s 轮询（列表 + 打开中的详情）──
const POLL_MS = 5000
const autoRefresh = ref(true)
let pollTimer = null

const hasRunning = computed(() => runs.value.some((r) => r.status === 'running'))
const pollHint = computed(() => {
  if (!autoRefresh.value) return '（关）'
  if (hasRunning.value) return ` · ${POLL_MS / 1000}s`
  return '（无运行中）'
})

function shouldPoll() {
  return autoRefresh.value && (hasRunning.value || (showDetail.value && detail.value.status === 'running'))
}

function stopPolling() {
  if (pollTimer) {
    clearInterval(pollTimer)
    pollTimer = null
  }
}

function startPolling() {
  stopPolling()
  pollTimer = setInterval(async () => {
    await loadRuns(true)
    if (showDetail.value && detail.value.status === 'running') {
      await openDetail({ id: detail.value.id, graph_name: detail.value.graph_name }, true)
    }
  }, POLL_MS)
}

const showDetail = ref(false)
const detailLoading = ref(false)
const detail = ref({})

// 依赖 showDetail/detail —— 必须在声明之后注册 watch
watch([autoRefresh, hasRunning, showDetail], () => {
  if (shouldPoll()) startPolling()
  else stopPolling()
})
onUnmounted(stopPolling)

const graphOptions = [
  { label: 'chat 对话', value: 'chat' },
  { label: 'setting 设定', value: 'setting' },
  { label: 'chapter 写作', value: 'chapter' },
  { label: 'review 审核', value: 'review' },
]
const statusOptions = [
  { label: '运行中', value: 'running' },
  { label: '完成', value: 'completed' },
  { label: '失败', value: 'failed' },
]

const detailTitle = computed(() =>
  detail.value.id ? `运行 #${detail.value.id.slice(0, 8)} · ${detail.value.graph_name}` : '运行详情'
)

function statusType(s) {
  return s === 'completed' ? 'success' : s === 'failed' ? 'error' : 'warning'
}
function statusText(s) {
  return s === 'completed' ? '完成' : s === 'failed' ? '失败' : '运行中'
}

function fmtTime(ts) {
  if (!ts) return ''
  if (typeof ts === 'number') return new Date(ts * 1000).toLocaleTimeString()
  return String(ts).slice(0, 19).replace('T', ' ')
}

function pretty(obj) {
  if (typeof obj === 'string') {
    try {
      return JSON.stringify(JSON.parse(obj), null, 2)
    } catch {
      return obj
    }
  }
  return JSON.stringify(obj, null, 2)
}

// ── 节点耗时（由 node_start/node_end 配对）──────────────────────
const nodeSpans = computed(() => {
  const spans = []
  const stack = []
  for (const ev of detail.value.events || []) {
    if (ev.type === 'node_start') stack.push({ node: ev.node, ts: ev.ts })
    else if (ev.type === 'node_end' && stack.length) {
      const s = stack.pop()
      const dur = ev.ts && s.ts ? ev.ts - s.ts : 0
      spans.push({ node: s.node, duration: dur })
    }
  }
  return spans
})

// ── 事件样式 ────────────────────────────────────────────────────
function dotClass(type) {
  return {
    node_start: 'is-node',
    node_end: 'is-node',
    tool_call: 'is-tool',
    tool_result: 'is-tool',
    review: 'is-review',
    checkpoint: 'is-check',
    route: 'is-route',
    error: 'is-error',
    done: 'is-done',
  }[type] || ''
}

function iconFor(type) {
  return {
    node_start: '▶', node_end: '⏹', tool_call: '🔧', tool_result: '✅',
    review: '⭐', checkpoint: '🔁', route: '🔀', error: '❌', done: '🏁',
  }[type] || '•'
}

// ── 表格列 ──────────────────────────────────────────────────────
const columns = [
  {
    title: '时间', key: 'created_at', width: 160,
    render: (r) => h('span', { style: 'font-size:12px;color:#888' }, fmtTime(r.created_at)),
  },
  {
    title: '图', key: 'graph_name', width: 100,
    render: (r) => h(NTag, { size: 'small', type: 'info' }, { default: () => r.graph_name }),
  },
  {
    title: '状态', key: 'status', width: 90,
    render: (r) => h(NTag, { size: 'small', type: statusType(r.status) }, { default: () => statusText(r.status) }),
  },
  {
    title: '摘要', key: 'summary',
    render: (r) => h('span', { style: 'font-size:12px' }, r.summary || '—'),
  },
  {
    title: '耗时', key: 'duration_seconds', width: 90,
    render: (r) => h('span', { style: 'font-size:12px;color:#888' }, `${r.duration_seconds}s`),
  },
  {
    title: '操作', key: 'actions', width: 190,
    render: (r) => h('span', [
      h(NButton, { size: 'tiny', quaternary: true, onClick: () => openDetail(r) }, {
        default: () => h('span', [h(NIcon, { size: 14 }, { default: () => h(EyeOutline) }), ' 查看']),
      }),
      h(NButton, { size: 'tiny', quaternary: true, type: 'warning', onClick: () => retryRun(r) }, {
        default: () => h('span', [h(NIcon, { size: 14 }, { default: () => h(RefreshOutline) }), ' 重试']),
      }),
      h(NButton, { size: 'tiny', quaternary: true, type: 'error', onClick: () => removeRun(r) }, {
        default: () => h('span', [h(NIcon, { size: 14 }, { default: () => h(TrashOutline) }), ' 删除']),
      }),
    ]),
  },
]

onMounted(loadRuns)

async function loadRuns(silent = false) {
  if (!silent) loading.value = true
  try {
    const params = { project_id: projectId.value, limit: 100 }
    if (graphFilter.value) params.graph = graphFilter.value
    if (statusFilter.value) params.status = statusFilter.value
    const res = await agentsAPI.listRuns(params)
    runs.value = res.data
  } catch (e) {
    message.error(e.message || '加载失败')
  } finally {
    loading.value = false
  }
}

async function openDetail(r, silent = false) {
  showDetail.value = true
  if (!silent) detailLoading.value = true
  try {
    const res = await agentsAPI.getRun(r.id)
    detail.value = res.data
  } catch (e) {
    message.error(e.message || '加载详情失败')
  } finally {
    detailLoading.value = false
  }
}

async function removeRun(r) {
  const ok = await window.confirm(`确认删除运行 #${r.id.slice(0, 8)}（${r.graph_name}）？`)
  if (!ok) return
  try {
    await agentsAPI.deleteRun(r.id)
    message.success('已删除')
    if (detail.value.id === r.id) showDetail.value = false
    await loadRuns()
  } catch (e) {
    message.error(e.message || '删除失败')
  }
}

async function retryRun(r) {
  try {
    const res = await agentsAPI.retryRun(r.id)
    const data = res.data || {}
    if (data.retried) {
      message.success(`已重试（${data.graph}），生成新运行记录`)
      await loadRuns()
    } else {
      message.error(data.error || '重试失败')
    }
  } catch (e) {
    message.error(e.message || '重试失败')
  }
}

async function clearAllRuns() {
  const ok = await window.confirm('确认清空本项目的全部运行记录？此操作不可恢复。')
  if (!ok) return
  try {
    const res = await agentsAPI.clearRuns({ project_id: projectId.value })
    message.success(`已清空 ${res.data.deleted} 条运行记录`)
    showDetail.value = false
    await loadRuns()
  } catch (e) {
    message.error(e.message || '清空失败')
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
.page-title h2 {
  margin: 0 0 3px;
}
.stats-bar {
  margin-bottom: 4px;
}
.block-title {
  font-size: 12px;
  color: #888;
  margin: 12px 0 6px;
}
.auto-refresh {
  white-space: nowrap;
}
.timeline {
  border-left: 2px solid #e5e7eb;
  margin-left: 6px;
  padding-left: 14px;
}
.timeline-item {
  display: flex;
  align-items: flex-start;
  gap: 8px;
  padding: 3px 0;
  font-size: 13px;
}
.tl-dot {
  width: 8px;
  height: 8px;
  border-radius: 50%;
  margin-top: 5px;
  flex-shrink: 0;
  background: #9ca3af;
}
.tl-dot.is-node { background: #409eff; }
.tl-dot.is-tool { background: #f59e0b; }
.tl-dot.is-review { background: #e94560; }
.tl-dot.is-check { background: #8b5cf6; }
.tl-dot.is-route { background: #10b981; }
.tl-dot.is-error { background: #ef4444; }
.tl-dot.is-done { background: #22c55e; }
.tl-icon { width: 18px; text-align: center; flex-shrink: 0; }
.tl-body {
  display: flex;
  flex-wrap: wrap;
  align-items: baseline;
  gap: 6px;
  min-width: 0;
}
.tl-type {
  font-weight: 600;
  font-size: 12px;
  color: #6b7280;
  text-transform: uppercase;
}
.tl-type.is-node { color: #409eff; }
.tl-type.is-tool { color: #b45309; }
.tl-type.is-review { color: #e94560; }
.tl-type.is-check { color: #7c3aed; }
.tl-type.is-route { color: #059669; }
.tl-type.is-error { color: #ef4444; }
.tl-type.is-done { color: #16a34a; }
.tl-node, .tl-tool {
  font-size: 12px;
  background: #f3f4f6;
  border-radius: 4px;
  padding: 0 6px;
  color: #374151;
}
.tl-score {
  font-size: 12px;
  color: #e94560;
  font-weight: 600;
}
.tl-round, .tl-intent {
  font-size: 12px;
  color: #7c3aed;
}
.tl-summary {
  font-size: 12px;
  color: #4b5563;
  max-width: 480px;
}
.tl-error {
  font-size: 12px;
  color: #ef4444;
}
.tl-ts {
  font-size: 11px;
  color: #bbb;
  margin-left: auto;
}
.tl-args {
  width: 100%;
  margin: 2px 0 0;
  font-size: 11px;
  background: #f9fafb;
  padding: 4px 6px;
  border-radius: 4px;
  white-space: pre-wrap;
  word-break: break-all;
}
.json-block {
  font-size: 12px;
  background: #f9fafb;
  border-radius: 6px;
  padding: 12px;
  max-height: 60vh;
  overflow: auto;
  white-space: pre-wrap;
  word-break: break-all;
}
</style>
