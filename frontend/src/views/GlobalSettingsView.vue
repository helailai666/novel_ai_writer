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
          <n-list v-if="bridgedTools.length">
            <n-list-item v-for="t in bridgedTools" :key="t.name">
              <n-text>{{ t.name }}</n-text>
            </n-list-item>
          </n-list>
          <n-empty v-else description="暂无已桥接的外部工具（配置 backend/config/mcp_servers.yaml 启用）" size="small" style="margin-top:12px" />
        </n-card>
      </n-grid-item>
    </n-grid>

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
import { providerAPI, mcpAPI, skillsAPI } from '../api/index.js'

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
</script>

<style scoped>
.settings-page { max-width: 1200px; margin: 0 auto; }
.page-header { display: flex; justify-content: space-between; align-items: flex-start; margin-bottom: 16px; }
.page-header h2 { margin: 0 0 4px 0; }
</style>
