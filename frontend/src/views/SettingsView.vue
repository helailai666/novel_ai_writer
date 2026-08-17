<template>
  <n-page-header @back="$router.back()">
    <template #title>🌍 设定管理</template>
  </n-page-header>

  <!-- 项目级技能包 -->
  <n-card title="🎯 项目技能包（写作/设定生成时自动注入）" size="small" style="margin-top:16px">
    <n-space vertical>
      <n-checkbox-group v-model:value="projectSkills" @update:value="saveSkills">
        <n-space>
          <n-checkbox v-for="s in skillList" :key="s.name" :value="s.name" :label="`${s.name}（${s.description}）`" />
        </n-space>
      </n-checkbox-group>
      <n-text depth="3" style="font-size:12px">技能将注入生成时的 system prompt 并合并工具白名单；请求级 skills 字段优先。</n-text>
    </n-space>
  </n-card>

  <n-tabs type="line" default-value="world" style="margin-top:20px;">
    <n-tab-pane name="world" tab="🌍 世界观">
      <n-card>
        <n-space vertical>
          <n-button @click="aiGenerate('world')" :loading="aiLoad.world" type="primary">
            🤖 AI 生成世界观
          </n-button>
          <n-empty v-if="!worldSettings.length" description="暂无世界观条目" />
          <n-thing v-for="ws in worldSettings" :key="ws.id" :title="ws.name" style="margin-bottom:8px;">
            <p style="color:#888;font-size:13px;">{{ ws.content?.slice(0, 100) }}...</p>
          </n-thing>
        </n-space>
      </n-card>
    </n-tab-pane>

    <n-tab-pane name="characters" tab="👤 角色">
      <n-card>
        <n-space vertical>
          <n-button @click="aiGenerate('character')" :loading="aiLoad.character" type="primary">
            🤖 AI 生成角色
          </n-button>
          <n-empty v-if="!characters.length" description="暂无角色" />
          <n-thing v-for="c in characters" :key="c.id" :title="c.name" style="margin-bottom:8px;">
            <p style="color:#888;font-size:13px;">{{ c.background || c.personality }}</p>
          </n-thing>
        </n-space>
      </n-card>
    </n-tab-pane>

    <n-tab-pane name="items" tab="🗡️ 道具">
      <n-card>
        <n-space vertical>
          <n-button @click="aiGenerate('item')" :loading="aiLoad.item" type="primary">🤖 AI 生成道具</n-button>
          <n-empty v-if="!items.length" description="暂无道具" />
          <n-thing v-for="it in items" :key="it.id" :title="it.name" style="margin-bottom:8px;">
            <p style="color:#888;font-size:13px;">{{ it.description }}</p>
          </n-thing>
        </n-space>
      </n-card>
    </n-tab-pane>

    <n-tab-pane name="skills" tab="⚡ 技能">
      <n-card>
        <n-space vertical>
          <n-button @click="aiGenerate('skill')" :loading="aiLoad.skill" type="primary">🤖 AI 生成技能</n-button>
          <n-empty v-if="!skills.length" description="暂无技能" />
          <n-thing v-for="s in skills" :key="s.id" :title="s.name" style="margin-bottom:8px;">
            <p style="color:#888;font-size:13px;">{{ s.description }}</p>
          </n-thing>
        </n-space>
      </n-card>
    </n-tab-pane>

    <n-tab-pane name="factions" tab="🏰 势力">
      <n-card>
        <n-space vertical>
          <n-button @click="aiGenerate('faction')" :loading="aiLoad.faction" type="primary">🤖 AI 生成势力</n-button>
          <n-empty v-if="!factions.length" description="暂无势力" />
          <n-thing v-for="f in factions" :key="f.id" :title="f.name" style="margin-bottom:8px;">
            <p style="color:#888;font-size:13px;">{{ f.goal }}</p>
          </n-thing>
        </n-space>
      </n-card>
    </n-tab-pane>

    <n-tab-pane name="outline" tab="📖 大纲">
      <n-card>
        <n-space vertical>
          <n-button @click="aiGenerate('outline')" :loading="aiLoad.outline" type="primary">🤖 AI 生成大纲</n-button>
          <n-empty v-if="!outlines.length" description="暂无大纲" />
          <n-thing v-for="o in outlines" :key="o.id" :title="o.title" style="margin-bottom:8px;">
            <p style="color:#888;font-size:13px;">{{ o.summary }}</p>
          </n-thing>
        </n-space>
      </n-card>
    </n-tab-pane>

    <n-tab-pane name="foreshadow" tab="🔮 伏笔">
      <n-card>
        <n-empty v-if="!foreshadows.length" description="伏笔由创作过程自动生成" />
        <n-thing v-for="fs in foreshadows" :key="fs.id" :title="fs.description?.slice(0, 50)" style="margin-bottom:8px;">
          <p style="color:#888;font-size:13px;">状态: {{ fs.status }}</p>
        </n-thing>
      </n-card>
    </n-tab-pane>
  </n-tabs>
</template>

<script setup>
import { ref, reactive, onMounted } from 'vue'
import { useRoute } from 'vue-router'
import { useMessage } from 'naive-ui'
import { settingsAPI, aiGenerateAPI, projectAPI, skillsAPI } from '../api/index.js'

const route = useRoute()
const message = useMessage()
const pid = () => route.params.id

// ── 项目级技能 ────────────────────────────────────────────────
const skillList = ref([])
const projectSkills = ref([])

async function loadSkills() {
  try {
    const s = await skillsAPI.list()
    skillList.value = s.data.skills || []
    const p = await projectAPI.getProject(pid())
    projectSkills.value = (p.data.skill_packs || '').split(',').filter(Boolean)
  } catch { /* 忽略 */ }
}

async function saveSkills() {
  try {
    await projectAPI.updateProject(pid(), { skills: projectSkills.value.join(',') })
    message.success('项目技能已保存')
  } catch (e) {
    message.error(e.message || '保存失败')
  }
}
// ─────────────────────────────────────────────────────────────

const aiLoad = reactive({ world: false, character: false, item: false, skill: false, faction: false, outline: false })

const worldSettings = ref([])
const characters = ref([])
const items = ref([])
const skills = ref([])
const factions = ref([])
const outlines = ref([])
const foreshadows = ref([])

async function load() {
  try {
    const [world, chars, sk, it, fac, out, fs] = await Promise.all([
      settingsAPI.getWorldSettings(pid()).catch(() => ({ data: [] })),
      settingsAPI.getCharacters(pid()).catch(() => ({ data: [] })),
      settingsAPI.getSkills(pid()).catch(() => ({ data: [] })),
      settingsAPI.getItems(pid()).catch(() => ({ data: [] })),
      settingsAPI.getFactions(pid()).catch(() => ({ data: [] })),
      settingsAPI.getOutlines(pid()).catch(() => ({ data: [] })),
      settingsAPI.getForeshadows(pid()).catch(() => ({ data: [] })),
    ])
    worldSettings.value = world.data || []
    characters.value = chars.data || []
    skills.value = sk.data || []
    items.value = it.data || []
    factions.value = fac.data || []
    outlines.value = out.data || []
    foreshadows.value = fs.data || []
  } catch { /* 保持空数组 */ }
}

const generateMap = {
  world: { api: aiGenerateAPI.generateWorld, name: '世界观' },
  character: { api: aiGenerateAPI.generateCharacter, name: '角色' },
  item: { api: aiGenerateAPI.generateItem, name: '道具' },
  skill: { api: aiGenerateAPI.generateSkill, name: '技能' },
  faction: { api: aiGenerateAPI.generateFaction, name: '势力' },
  outline: { api: aiGenerateAPI.generateOutline, name: '大纲' },
}

async function aiGenerate(module) {
  const cfg = generateMap[module]
  if (!cfg) return
  aiLoad[module] = true
  try {
    await cfg.api(pid(), { name: `新${cfg.name}`, category: 'general', extra: '' })
    message.success(`${cfg.name} AI 生成完成！`)
    await load()
  } catch (e) {
    message.error(`AI 生成失败: ${e.message || '未知错误'}`)
  } finally {
    aiLoad[module] = false
  }
}

onMounted(() => {
  load()
  loadSkills()
})
</script>
