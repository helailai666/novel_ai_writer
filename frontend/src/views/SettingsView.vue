<template>
  <n-page-header @back="$router.back()">
    <template #title>🌍 设定管理 (12模块)</template>
    <template #extra>
      <n-button type="primary" @click="saveAll" :loading="saving">💾 保存全部</n-button>
    </template>
  </n-page-header>

  <n-tabs type="line" default-value="world" style="margin-top:20px;">
    <n-tab-pane name="world" tab="🌍 世界观">
      <n-card>
        <n-form>
          <n-form-item label="时代背景"><n-input v-model:value="settings.world.era" placeholder="古代/现代/未来/架空" /></n-form-item>
          <n-form-item label="世界规则"><n-input v-model:value="settings.world.rules" type="textarea" rows="3" placeholder="力量体系/魔法规则" /></n-form-item>
          <n-form-item label="地理环境"><n-input v-model:value="settings.world.geography" type="textarea" rows="3" placeholder="大陆/城市/秘境" /></n-form-item>
        </n-form>
        <n-button @click="aiGenerate('world')" :loading="aiLoad.world">🤖 AI 生成世界观</n-button>
      </n-card>
    </n-tab-pane>

    <n-tab-pane name="characters" tab="👤 角色">
      <n-card>
        <n-button @click="aiGenerate('character')" :loading="aiLoad.character" style="margin-bottom:12px;">🤖 AI 生成角色</n-button>
        <n-empty v-if="!settings.characters.length" description="暂无角色" />
        <n-thing v-for="(c,i) in settings.characters" :key="i" :title="c.name" style="margin-bottom:8px;">
          <p style="color:#888;font-size:13px;">{{ c.description }}</p>
        </n-thing>
      </n-card>
    </n-tab-pane>

    <n-tab-pane name="items" tab="🗡️ 道具">
      <n-card><n-button @click="aiGenerate('item')" :loading="aiLoad.item">🤖 AI 生成道具体系</n-button><n-empty v-if="!settings.items.length" style="margin-top:12px;" /></n-card>
    </n-tab-pane>

    <n-tab-pane name="skills" tab="⚡ 能力">
      <n-card><n-button @click="aiGenerate('skill')" :loading="aiLoad.skill">🤖 AI 生成能力体系</n-button><n-empty v-if="!settings.skills.length" style="margin-top:12px;" /></n-card>
    </n-tab-pane>

    <n-tab-pane name="factions" tab="🏰 势力">
      <n-card><n-button @click="aiGenerate('faction')" :loading="aiLoad.faction">🤖 AI 生成势力组织</n-button><n-empty v-if="!settings.factions.length" style="margin-top:12px;" /></n-card>
    </n-tab-pane>

    <n-tab-pane name="outline" tab="📖 大纲">
      <n-card>
        <n-space>
          <n-input-number v-model:value="outlineChapters" :min="10" :max="500" style="width:100px" />
          <n-input-number v-model:value="outlineVolumes" :min="1" :max="20" style="width:100px" />
          <n-button @click="aiGenerate('outline')" :loading="aiLoad.outline">🤖 AI 生成大纲</n-button>
        </n-space>
        <n-empty v-if="!settings.outline" style="margin-top:12px;" />
      </n-card>
    </n-tab-pane>

    <n-tab-pane name="foreshadow" tab="🔮 伏笔">
      <n-card><n-empty description="伏笔由创作过程自动生成" /></n-card>
    </n-tab-pane>
  </n-tabs>
</template>

<script setup>
import { ref, reactive, onMounted } from 'vue'
import { useRoute } from 'vue-router'
import { settingsAPI } from '../api/index.js'

const route = useRoute()
const pid = () => route.params.id
const saving = ref(false)
const outlineChapters = ref(100)
const outlineVolumes = ref(5)
const aiLoad = reactive({ world: false, character: false, item: false, skill: false, faction: false, outline: false })

const settings = reactive({
  world: { era: '', rules: '', geography: '' },
  characters: [],
  items: [],
  skills: [],
  factions: [],
  outline: null,
})

async function load() {
  try {
    const res = await settingsAPI.getSettings(pid())
    if (res.data) Object.assign(settings, res.data.settings || res.data)
  } catch { /* mock 数据留空 */ }
}

async function saveAll() {
  saving.value = true
  try { await settingsAPI.saveSettings(pid(), { ...settings }) } catch {}
  saving.value = false
}

async function aiGenerate(module) {
  aiLoad[module] = true
  try {
    const res = await settingsAPI.generateSettings(pid(), module)
    if (res.data?.data) Object.assign(settings, { [module+'s']: res.data.data })
  } catch {
    const mock = {
      world: { era: '架空修仙世界', rules: '灵气修炼体系: 练气→筑基→金丹→元婴→化神', geography: '五洲大陆: 东胜/西荒/南疆/北海/中州' },
      character: [{ name: '林玄', description: '主角, 平凡少年天资卓绝' }, { name: '苏婉儿', description: '女主, 宗门圣女温婉坚韧' }],
      item: [{ name: '九天玄剑', rarity: '传说', desc: '上古神剑' }, { name: '筑基丹', rarity: '精良', desc: '筑基必备' }],
      skill: [{ name: '九天剑诀', level: '天阶', desc: '攻击性功法' }, { name: '玄天心法', level: '地阶', desc: '修炼心法' }],
      faction: [{ name: '青云宗', type: '正道', desc: '主角所在宗门' }, { name: '魔渊殿', type: '反派', desc: '主要敌对势力' }],
      outline: `第一卷「初入仙途」(1-20章): 主角入门拜师学艺\n第二卷「宗门风云」(21-40章): 大比崭露头角\n第三卷「秘境探险」(41-60章): 寻宝突破\n第四卷「天下争霸」(61-80章): 正邪大战\n第五卷「登临巅峰」(81-100章): 飞升成仙`,
    }
    if (module === 'world') Object.assign(settings.world, mock.world)
    else settings[module+'s'] = (mock[module] || [])
  }
  aiLoad[module] = false
}

onMounted(load)
</script>
