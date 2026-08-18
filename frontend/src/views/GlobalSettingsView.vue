<template>
  <div class="settings-page">
    <div class="page-header">
      <div class="page-title">
        <div class="page-title-icon">⚙️</div>
        <div>
          <h2>全局设置</h2>
          <n-text depth="3">模型供应商 · 搜索模式 · 技能包 · MCP</n-text>
        </div>
      </div>
    </div>

    <n-grid :cols="2" :x-gap="16" responsive="screen">
      <!-- 模型供应商（前台配置，存数据库，无需改 .env） -->
      <n-grid-item span="2">
        <n-card title="🤖 模型供应商" size="small">
          <template #header-extra>
            <n-button size="small" type="primary" @click="openCreate">＋ 新增配置</n-button>
          </template>

          <n-alert type="info" :show-icon="true" style="margin-bottom:12px" closable>
            配置保存在数据库中，前台即时生效，无需修改后端 .env 或重启。
            解析优先级：请求级覆盖 → 项目级（每小说设置）→ 全局默认配置 → 环境变量。
          </n-alert>

          <!-- 当前生效的全局配置 -->
          <n-descriptions size="small" :column="2" label-placement="left" bordered style="margin-bottom:12px">
            <n-descriptions-item label="当前全局生效">
              <n-tag size="small" :type="current.source === 'db-default' ? 'success' : 'default'">
                {{ current.provider }} / {{ current.model || '（默认模型）' }}
              </n-tag>
              <n-tag v-if="current.has_api_key" size="tiny" type="success" style="margin-left:6px">有 Key</n-tag>
              <n-text depth="3" style="font-size:12px;margin-left:8px">
                {{ current.source === 'db-default' ? '来自前台默认配置' : '来自环境变量（未配置默认）' }}
              </n-text>
            </n-descriptions-item>
          </n-descriptions>

          <!-- 配置列表 -->
          <n-data-table
            v-if="configs.length"
            :columns="columns"
            :data="configs"
            :row-key="(row) => row.id"
            size="small"
            :pagination="false"
            :bordered="false"
          />
          <n-empty v-else description="暂无供应商配置 — 点击「新增配置」添加；未配置时回退环境变量" size="small" style="margin:16px 0" />

          <n-text depth="3" style="font-size:12px;display:block;margin-top:10px">
            可用供应商类型：{{ providerNames }}（均支持 OpenAI 兼容端点自定义）
          </n-text>
        </n-card>
      </n-grid-item>

      <!-- 搜索 + MCP -->
      <n-grid-item span="2">
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

    <!-- 供应商配置抽屉（新增/编辑） -->
    <n-drawer v-model:show="drawerShow" :width="440" placement="right">
      <n-drawer-content :title="editingId ? '编辑供应商配置' : '新增供应商配置'" closable>
        <n-form label-placement="top" size="small">
          <n-form-item label="配置名称">
            <n-input v-model:value="form.name" placeholder="如：DeepSeek 主力 / 本地 Ollama" />
          </n-form-item>
          <n-form-item label="供应商类型">
            <n-select v-model:value="form.provider" :options="providerOptions" />
          </n-form-item>
          <n-form-item label="模型">
            <n-input v-model:value="form.model" placeholder="如 deepseek-chat / gpt-4o-mini（留空用内置默认）" />
          </n-form-item>
          <n-form-item label="API Base">
            <n-input v-model:value="form.api_base" placeholder="OpenAI 兼容端点（可选），如 https://api.deepseek.com/v1" />
          </n-form-item>
          <n-form-item label="API Key">
            <n-input v-model:value="form.api_key" type="password" show-password-on="click" placeholder="留空则回退环境变量" />
          </n-form-item>
          <n-form-item label="Temperature">
            <n-input-number v-model:value="form.temperature" :min="0" :max="2" :step="0.1" style="width:100%" />
          </n-form-item>
          <n-space align="center">
            <n-switch v-model:value="form.enabled">
              <template #checked>启用</template>
              <template #unchecked>停用</template>
            </n-switch>
            <n-text depth="3" style="font-size:13px">设为全局默认（项目未指定时兜底）</n-text>
            <n-switch v-model:value="form.is_default" />
          </n-space>
        </n-form>
        <n-alert v-if="testResult" :type="testResult.ok ? 'success' : 'error'" style="margin:12px 0">
          {{ testResult.ok ? `✅ 连通成功（${testResult.is_mock ? 'Mock 模式' : '真实 API'}）：${testResult.reply.slice(0, 60)}` : `❌ ${testResult.error}` }}
        </n-alert>
        <template #footer>
          <n-space justify="space-between" style="width:100%">
            <n-button :loading="testing" @click="testCurrent">测试连通</n-button>
            <n-space>
              <n-button @click="drawerShow = false">取消</n-button>
              <n-button type="primary" :loading="saving" @click="saveConfig">
                {{ editingId ? '保存修改' : '创建配置' }}
              </n-button>
            </n-space>
          </n-space>
        </template>
      </n-drawer-content>
    </n-drawer>
  </div>
</template>

<script setup>
import { ref, reactive, computed, h, onMounted } from 'vue'
import { useMessage, useDialog, NButton, NSpace, NTag } from 'naive-ui'
import { providerAPI, mcpAPI, skillsAPI, cacheAPI, runtimeAPI } from '../api/index.js'

const message = useMessage()
const dialog = useDialog()

const providers = ref([])          // 注册表（供应商类型）
const configs = ref([])            // 已保存的 DB 配置
const current = reactive({ provider: '', model: '', api_base: '', has_api_key: false, source: 'env', provider_id: null })
const testing = ref(false)
const testResult = ref(null)
const saving = ref(false)
const searchMode = ref('auto')
const mcpServers = ref([])
const bridgedTools = ref([])
const mcpLoading = ref(false)
const skills = ref([])
const cacheStats = ref({})
const clearing = ref(false)
const cfg = ref({ llm: {}, search: {}, embedding: {}, vector_store: {}, mcp: {}, agent: {}, skills: {} })

// 抽屉表单
const drawerShow = ref(false)
const editingId = ref('')
const form = reactive({ name: '', provider: 'openai', model: '', api_base: '', api_key: '', temperature: 0.7, enabled: true, is_default: false })

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

// 配置列表列定义
const columns = [
  { title: '名称', key: 'name', width: 130, render: (row) => h('div', [
      h('b', { style: 'font-size:13px' }, row.name),
      row.is_default ? h(NTag, { size: 'tiny', type: 'success', style: 'margin-left:6px' }, () => '默认') : null,
    ]) },
  { title: '类型', key: 'provider', width: 90, render: (row) => h(NTag, { size: 'tiny', type: 'info' }, () => row.provider) },
  { title: '模型', key: 'model', render: (row) => row.model || h('span', { style: 'color:#999' }, '（内置默认）') },
  { title: 'API Key', key: 'api_key', width: 130, render: (row) => row.has_api_key ? h('span', { style: 'font-family:monospace' }, row.api_key) : h('span', { style: 'color:#999' }, '未配置（走环境变量）') },
  { title: '状态', key: 'enabled', width: 70, render: (row) => h(NTag, { size: 'tiny', type: row.enabled ? 'success' : 'default' }, () => row.enabled ? '启用' : '停用') },
  {
    title: '操作', key: 'actions', width: 200,
    render: (row) => h(NSpace, { size: 4, justify: 'center' }, () => [
      h(NButton, { size: 'tiny', quaternary: true, type: 'primary', onClick: () => testSaved(row) }, () => '测试'),
      h(NButton, { size: 'tiny', quaternary: true, onClick: () => openEdit(row) }, () => '编辑'),
      h(NButton, { size: 'tiny', quaternary: true, type: 'error', onClick: () => removeConfig(row) }, () => '删除'),
    ])
  },
]

onMounted(async () => {
  await loadProviders()
  loadMcp()
  loadSkills()
  loadCacheStats()
  loadRuntimeConfig()
})

async function loadProviders() {
  try {
    const res = await providerAPI.list()
    providers.value = res.data.providers || []
    configs.value = res.data.configs || []
    Object.assign(current, res.data.current || {})
  } catch (e) {
    message.error(e.message || '加载供应商失败')
  }
}

// ── 抽屉：新增 / 编辑 ──────────────────────────────────────────

function openCreate() {
  editingId.value = ''
  Object.assign(form, { name: '', provider: 'openai', model: '', api_base: '', api_key: '', temperature: 0.7, enabled: true, is_default: false })
  testResult.value = null
  drawerShow.value = true
}

function openEdit(row) {
  editingId.value = row.id
  Object.assign(form, {
    name: row.name, provider: row.provider, model: row.model,
    api_base: row.api_base || '', api_key: '', temperature: row.temperature,
    enabled: row.enabled, is_default: row.is_default,
  })
  testResult.value = null
  drawerShow.value = true
}

async function saveConfig() {
  if (!form.name.trim()) { message.warning('请填写配置名称'); return }
  saving.value = true
  try {
    const payload = { ...form }
    if (editingId.value) {
      // 编辑时不回填 Key：留空表示不修改
      if (!payload.api_key) delete payload.api_key
      await providerAPI.update(editingId.value, payload)
      message.success('配置已更新')
    } else {
      await providerAPI.create(payload)
      message.success('配置已创建')
    }
    drawerShow.value = false
    await loadProviders()
  } catch (e) {
    message.error(e.message || '保存失败')
  } finally {
    saving.value = false
  }
}

function removeConfig(row) {
  dialog.warning({
    title: '删除供应商配置',
    content: `确定删除「${row.name}」？引用它的项目将回退到全局默认/环境变量。`,
    positiveText: '删除',
    negativeText: '取消',
    onPositiveClick: async () => {
      try {
        await providerAPI.remove(row.id)
        message.success('已删除')
        await loadProviders()
      } catch (e) {
        message.error(e.message || '删除失败')
      }
    }
  })
}

// ── 连通性测试 ────────────────────────────────────────────────

function testSaved(row) {
  testing.value = true
  testResult.value = null
  providerAPI.test({ provider_id: row.id })
    .then((res) => { testResult.value = res.data; message[res.data.ok ? 'success' : 'error'](res.data.ok ? '连通成功' : '测试失败') })
    .catch((e) => { testResult.value = { ok: false, error: e.message } })
    .finally(() => { testing.value = false })
}

function testCurrent() {
  testing.value = true
  testResult.value = null
  providerAPI.test({
    provider: form.provider,
    model: form.model || undefined,
    api_key: form.api_key || undefined,
    api_base: form.api_base || undefined,
  })
    .then((res) => { testResult.value = res.data })
    .catch((e) => { testResult.value = { ok: false, error: e.message } })
    .finally(() => { testing.value = false })
}

// ── 其余（MCP / 技能 / 缓存 / 运行时配置）─────────────────────

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
.page-title { display: flex; align-items: center; gap: 12px; }
.page-header h2 { margin: 0 0 3px 0; }
.cache-card { background: #fafafa; border: 1px solid #f0f0f0; }
</style>
