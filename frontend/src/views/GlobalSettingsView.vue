<template>
  <div class="settings-page">
    <div class="page-header">
      <div class="page-title">
        <h2>⚙️ 全局设置</h2>
        <n-text depth="3">模型供应商 · 搜索模式 · 技能包 · MCP</n-text>
      </div>
    </div>

    <n-grid :cols="2" :x-gap="16" responsive="screen">
      <!-- 模型供应商 -->
      <n-grid-item span="2 m:1">
        <n-card title="🤖 模型供应商" size="small">
          <n-form label-placement="top">
            <n-form-item label="当前供应商">
              <n-select v-model:value="current.provider" :options="providerOptions" />
            </n-form-item>
            <n-form-item label="模型">
              <n-input v-model:value="current.model" placeholder="如 deepseek-chat / gpt-4o-mini" />
            </n-form-item>
            <n-form-item label="API Base">
              <n-input v-model:value="current.api_base" placeholder="OpenAI 兼容端点（可选）" />
            </n-form-item>
            <n-form-item label="API Key">
              <n-input v-model:value="current.api_key" type="password" show-password-on="click" placeholder="留空则使用环境变量" />
            </n-form-item>
            <n-space>
              <n-button type="primary" :loading="testing" @click="testProvider">测试连通</n-button>
            </n-space>
            <n-alert v-if="testResult" :type="testResult.ok ? 'success' : 'error'" style="margin-top:12px">
              {{ testResult.ok ? `✅ 连通成功（${testResult.is_mock ? 'Mock 模式' : '真实 API'}）：${testResult.reply.slice(0, 60)}` : `❌ ${testResult.error}` }}
            </n-alert>
          </n-form>
          <n-text depth="3" style="font-size:12px">提示：修改需写入后端 .env 后重启生效；此处用于验证连通性。可用供应商：{{ providerNames }}</n-text>
        </n-card>
      </n-grid-item>

      <!-- 搜索 + MCP -->
      <n-grid-item span="2 m:1">
        <n-card title="🌐 搜索模式" size="small" style="margin-bottom:16px">
          <n-space vertical>
            <n-select v-model:value="searchMode" :options="searchOptions" />
            <n-text depth="3" style="font-size:12px">auto = 按可用 Key 自动降级（Tavily → DuckDuckGo → Mock）</n-text>
          </n-space>
        </n-card>

        <n-card title="📦 外部 MCP 服务" size="small">
          <n-space align="center" justify="space-between">
            <n-text depth="2">已配置 {{ mcpServers.length }} 个外部 server</n-text>
            <n-button size="small" :loading="mcpLoading" @click="reloadMcp">重连桥接</n-button>
          </n-space>
          <n-list v-if="mcpServers.length">
            <n-list-item v-for="s in mcpServers" :key="s.name">
              <n-space vertical size="small" style="width:100%">
                <n-space align="center" justify="space-between">
                  <n-space align="center">
                    <b>{{ s.name }}</b>
                    <n-tag size="tiny" :type="s.enabled ? 'info' : 'default'">{{ s.transport }}</n-tag>
                  </n-space>
                  <n-tag v-if="s.status" size="tiny" :type="s.status.closed ? 'error' : s.status.sessions ? 'success' : 'default'">
                    {{ s.status.closed ? '已关闭' : s.status.sessions ? `会话 ${s.status.busy}/${s.status.sessions}` : '未连接' }}
                  </n-tag>
                </n-space>
                <n-text v-if="s.status" depth="3" style="font-size:12px">
                  池大小 {{ s.status.pool_size }} · 超时 {{ s.status.connect_timeout }}s · 重试 {{ s.status.max_retries }}
                  <span v-if="s.status.connected_at"> · {{ s.status.connected_at }}</span>
                </n-text>
                <n-text v-if="s.status && s.status.last_error" depth="3" style="font-size:12px;color:#ef4444">
                  最近错误：{{ s.status.last_error }}
                </n-text>
              </n-space>
            </n-list-item>
          </n-list>
          <n-empty v-else description="暂无已配置的外部 server（backend/config/mcp_servers.yaml）" size="small" style="margin-top:12px" />
          <n-divider style="margin:8px 0" />
          <n-text depth="3" style="font-size:12px">已桥接工具：{{ bridgedTools.map((t) => t.name).join('、') || '无' }}</n-text>
        </n-card>
      </n-grid-item>
    </n-grid>

    <!-- 运行时缓存 -->
    <n-card title="⚡ 运行时缓存" size="small" style="margin-top:16px">
      <n-space align="center" justify="space-between" style="margin-bottom:8px">
        <n-text depth="3" style="font-size:12px">意图分类 / 知识检索 命中统计（TTL 秒）</n-text>
        <n-button size="small" :loading="clearing" @click="clearCaches">清空缓存</n-button>
      </n-space>
      <n-grid :cols="2" :x-gap="12" responsive="screen">
        <n-grid-item v-for="(st, name) in cacheStats" :key="name">
          <n-card size="small" :bordered="false" class="cache-card">
            <n-text depth="2" style="font-size:12px;font-weight:600">{{ name === 'classify' ? '意图分类' : '知识检索' }}</n-text>
            <n-descriptions size="small" :column="2" label-placement="left">
              <n-descriptions-item label="命中">{{ st.hits }}</n-descriptions-item>
              <n-descriptions-item label="未命中">{{ st.misses }}</n-descriptions-item>
              <n-descriptions-item label="淘汰">{{ st.evictions }}</n-descriptions-item>
              <n-descriptions-item label="当前">{{ st.size }} 条</n-descriptions-item>
            </n-descriptions>
          </n-card>
        </n-grid-item>
      </n-grid>
    </n-card>

    <!-- 运行时配置 -->
    <n-card title="🔧 运行时配置" size="small" style="margin-top:16px">
      <n-descriptions size="small" :column="2" label-placement="left" bordered>
        <n-descriptions-item label="LLM">
          {{ cfg.llm.provider }} / {{ cfg.llm.model }}
          <n-tag v-if="cfg.llm.has_api_key" size="tiny" type="success" style="margin-left:6px">有 Key</n-tag>
        </n-descriptions-item>
        <n-descriptions-item label="搜索">{{ cfg.search.provider }}</n-descriptions-item>
        <n-descriptions-item label="向量后端">{{ cfg.vector_store.backend }}</n-descriptions-item>
        <n-descriptions-item label="Embedding">{{ cfg.embedding.provider }} / {{ cfg.embedding.model }}</n-descriptions-item>
        <n-descriptions-item label="意图分类">
          {{ cfg.agent.llm_supervisor ? 'LLM 优先' : '关键词' }} · 缓存 {{ cfg.agent.llm_supervisor_cache ? cfg.agent.llm_supervisor_cache_ttl + 's' : '关' }}
        </n-descriptions-item>
        <n-descriptions-item label="检索缓存">{{ cfg.agent.knowledge_cache ? cfg.agent.knowledge_cache_ttl + 's' : '关' }}</n-descriptions-item>
        <n-descriptions-item label="MCP 池默认">
          size={{ cfg.mcp.default_pool_size }} · timeout={{ cfg.mcp.default_connect_timeout }}s · retry={{ cfg.mcp.default_max_retries }}
        </n-descriptions-item>
        <n-descriptions-item label="技能目录">{{ (cfg.skills.dirs || []).join(', ') }}</n-descriptions-item>
      </n-descriptions>
    </n-card>

    <!-- 技能包 -->
    <n-card title="🎯 技能包" size="small" style="margin-top:16px">
      <n-grid :cols="3" :x-gap="12" :y-gap="12" responsive="screen" item-responsive>
        <n-grid-item v-for="s in skills" :key="s.name" span="3 s:3 m:1">
          <n-card size="small" hoverable>
            <template #header>
              <n-space align="center">
                <b>{{ s.name }}</b>
                <n-tag size="tiny" type="info">v{{ s.version }}</n-tag>
              </n-space>
            </template>
            <n-text depth="2" style="font-size:13px">{{ s.description }}</n-text>
            <template #footer>
              <n-tag v-if="s.tools.length" size="tiny" type="success">工具: {{ s.tools.join(', ') }}</n-tag>
            </template>
          </n-card>
        </n-grid-item>
      </n-grid>
    </n-card>
  </div>
</template>

<script setup>
import { ref, reactive, computed, onMounted } from 'vue'
import { useMessage } from 'naive-ui'
import { providerAPI, mcpAPI, skillsAPI, cacheAPI, runtimeAPI } from '../api/index.js'

const message = useMessage()
const current = reactive({ provider: 'openai', model: '', api_base: '', api_key: '' })
const providers = ref([])
const testing = ref(false)
const testResult = ref(null)
const searchMode = ref('auto')
const mcpServers = ref([])
const bridgedTools = ref([])
const mcpLoading = ref(false)
const skills = ref([])
const cacheStats = ref({})
const clearing = ref(false)
const cfg = ref({ llm: {}, search: {}, embedding: {}, vector_store: {}, mcp: {}, agent: {}, skills: {} })

const providerOptions = computed(() =>
  providers.value.map((p) => ({ label: p.name, value: p.name }))
)
const providerNames = computed(() => providers.value.map((p) => p.name).join(' / '))

const searchOptions = [
  { label: 'auto（自动降级）', value: 'auto' },
  { label: 'tavily', value: 'tavily' },
  { label: 'duckduckgo', value: 'duckduckgo' },
  { label: 'bing', value: 'bing' },
  { label: 'searxng', value: 'searxng' },
  { label: 'mock', value: 'mock' },
]

onMounted(async () => {
  try {
    const res = await providerAPI.list()
    providers.value = res.data.providers || []
    Object.assign(current, res.data.current || {})
  } catch (e) {
    message.error(e.message || '加载供应商失败')
  }
  loadMcp()
  loadSkills()
  loadCacheStats()
  loadRuntimeConfig()
})

async function testProvider() {
  testing.value = true
  testResult.value = null
  try {
    const res = await providerAPI.test({
      provider: current.provider,
      model: current.model || undefined,
      api_key: current.api_key || undefined,
      api_base: current.api_base || undefined,
    })
    testResult.value = res.data
  } catch (e) {
    testResult.value = { ok: false, error: e.message }
  } finally {
    testing.value = false
  }
}

async function loadMcp() {
  try {
    const res = await mcpAPI.servers()
    mcpServers.value = res.data.servers || []
    const t = await mcpAPI.tools()
    bridgedTools.value = t.data.tools || []
  } catch (e) {
    /* 忽略 */
  }
}

async function reloadMcp() {
  mcpLoading.value = true
  try {
    const res = await mcpAPI.reload()
    message.success('MCP 桥接完成')
    await loadMcp()
  } catch (e) {
    message.error(e.message || '桥接失败')
  } finally {
    mcpLoading.value = false
  }
}

async function loadSkills() {
  try {
    const res = await skillsAPI.list()
    skills.value = res.data.skills || []
  } catch (e) {
    /* 忽略 */
  }
}

async function loadCacheStats() {
  try {
    const res = await cacheAPI.stats()
    cacheStats.value = res.data || {}
  } catch (e) {
    /* 忽略 */
  }
}

async function clearCaches() {
  clearing.value = true
  try {
    await cacheAPI.clear()
    message.success('运行时缓存已清空')
    await loadCacheStats()
  } catch (e) {
    message.error(e.message || '清空失败')
  } finally {
    clearing.value = false
  }
}

async function loadRuntimeConfig() {
  try {
    const res = await runtimeAPI.config()
    cfg.value = res.data || cfg.value
  } catch (e) {
    /* 忽略 */
  }
}
</script>

<style scoped>
.settings-page { max-width: 1200px; margin: 0 auto; }
.page-header { display: flex; justify-content: space-between; align-items: flex-start; margin-bottom: 16px; }
.page-header h2 { margin: 0 0 4px 0; }
.cache-card { background: #fafafa; border: 1px solid #f0f0f0; }
</style>
