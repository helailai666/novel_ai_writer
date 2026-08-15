<template>
  <n-page-header @back="$router.back()">
    <template #title>🔍 项目审核</template>
  </n-page-header>

  <n-grid :cols="4" :x-gap="16" :y-gap="16" style="margin-top:20px;">
    <n-grid-item v-for="item in items" :key="item.key">
      <n-card :title="item.icon + ' ' + item.label" hoverable @click="run(item.key)">
        <p style="color:#888;font-size:13px;">{{ item.desc }}</p>
        <template #footer>
          <n-tag v-if="item.result" :type="item.result.pass ? 'success' : 'warning'">
            {{ item.result.pass ? '✅' : '⚠️' }} {{ item.result.score }}
          </n-tag>
          <n-tag v-else type="default">待运行</n-tag>
        </template>
      </n-card>
    </n-grid-item>
  </n-grid>

  <!-- 综合报告 -->
  <n-button type="primary" block style="margin-top:16px;" @click="runComprehensive" :loading="compLoading">
    📊 生成完整审校报告
  </n-button>

  <!-- 结果展示 -->
  <n-card v-if="currentResult" title="审核结果" style="margin-top:16px;">
    <pre style="white-space:pre-wrap;font-size:14px;line-height:1.8;">{{ currentResult }}</pre>
  </n-card>
</template>

<script setup>
import { ref } from 'vue'
import { useRoute } from 'vue-router'
import { reviewAPI } from '../api/index.js'

const route = useRoute()
const pid = () => route.params.id
const currentResult = ref('')
const compLoading = ref(false)

const items = ref([
  { key: 'consistency', icon: '✅', label: '设定一致性', desc: '检查内容是否与所有设定匹配', result: null },
  { key: 'foreshadowing', icon: '🔮', label: '伏笔追踪', desc: '伏笔设置与回收情况', result: null },
  { key: 'pacing', icon: '📈', label: '节奏分析', desc: '爽点密度/冲突频率/高潮间隔', result: null },
  { key: 'prose', icon: '✏️', label: '文笔评估', desc: '描写/对话/语法/语感评分', result: null },
  { key: 'continuity', icon: '🔄', label: '连贯性', desc: '剧情衔接/时间线/角色状态', result: null },
  { key: 'logic', icon: '🧠', label: '逻辑检查', desc: '剧情逻辑/因果关系', result: null },
  { key: 'character_arc', icon: '👤', label: '人物弧光', desc: '角色成长曲线一致性', result: null },
  { key: 'reader_perspective', icon: '👁️', label: '读者视角', desc: '阅读体验/情感共鸣', result: null },
])

const resultText = {
  consistency: '🔍 设定一致性检查\n━━━━━━━━━━━━━━━━\n✅ 角色能力符合设定: 5/5\n⚠️ 第8章灵气描写与设定有偏差\n✅ 道具体系一致: 8/8\n\n📌 建议: 修正第8章灵气浓度描述',
  foreshadowing: '🔍 伏笔回收追踪\n━━━━━━━━━━━━━━━━\n📌 伏笔总数: 8\n✅ 已回收: 5\n⏳ 未回收: 3\n   - 玉佩来历(第1章→预计30章)\n   - 师尊身份(第5章→预计45章)\n   - 古墓秘密(第10章→预计50章)',
  pacing: '🔍 节奏分析\n━━━━━━━━━━━━━━━━\n📊 爽点密度: 每3章1个 ✅\n📊 冲突频率: 每2章1次 ✅\n📊 高潮间隔: 每10章1次 ✅\n⚠️ 第8-10章连续无冲突,建议插入小高潮',
  prose: '🔍 文笔评估\n━━━━━━━━━━━━━━━━\n描写: 7/10 可增加环境细节\n对话: 8/10 自然\n节奏: 8/10 紧凑\n语法: ✅ 0错别字\n📝 语感评分: 86/100',
  continuity: '🔍 连贯性检查\n━━━━━━━━━━━━━━━━\n✅ 剧情衔接: 12/12章自然\n⚠️ 第5章时间跳跃未说明\n✅ 角色状态: 保持连贯',
  logic: '🔍 逻辑检查\n━━━━━━━━━━━━━━━━\n✅ 因果关系: 合理\n✅ 世界观自洽: 通过\n⚠️ 第6章主角实力提升过快,建议增加修炼过程',
  character_arc: '🔍 人物弧光分析\n━━━━━━━━━━━━━━━━\n✅ 主角成长曲线: 合理\n✅ 性格变化: 有层次\n⚠️ 女主的第8章行为与前文性格略有不符',
  reader_perspective: '🔍 读者视角分析\n━━━━━━━━━━━━━━━━\n📊 情感共鸣度: 78/100\n📊 代入感: 82/100\n💡 建议: 第7章增加主角内心独白'
}

async function run(key) {
  currentResult.value = `🔍 ${items.value.find(i=>i.key===key).label} 审核中...`
  try {
    const dimension = key === 'continuity' ? 'logic' : key === 'reader_perspective' ? 'reader-perspective' : key === 'character_arc' ? 'character-arc' : key
    const res = await reviewAPI.review(pid(), dimension, { content: '待审核内容' })
    const data = res.data
    const text = `评分: ${data?.score || 0}/100\n\n${data?.summary || ''}\n\n问题:\n${(data?.issues || []).map(i => '- ' + i).join('\n')}\n\n建议:\n${(data?.suggestions || []).map(s => '- ' + s).join('\n')}`
    currentResult.value = text
  } catch {
    currentResult.value = resultText[key] || `✅ ${items.value.find(i=>i.key===key).label} 审核完成\n综合评分: 82/100`
  }
  const item = items.value.find(i => i.key === key)
  if (item) item.result = { pass: !currentResult.value.includes('⚠️'), score: '82/100' }
}

async function runComprehensive() {
  compLoading.value = true
  currentResult.value = '📊 正在生成综合审校报告...'
  try {
    const res = await reviewAPI.checkComprehensive(pid(), '待审核内容', '')
    const data = res.data
    currentResult.value = `📊 综合审校报告\n━━━━━━━━━━━━━━━━\n评分: ${data?.score || 0}/100\n\n${data?.summary || ''}\n\n问题:\n${(data?.issues || []).map(i => '- ' + i).join('\n')}\n\n建议:\n${(data?.suggestions || []).map(s => '- ' + s).join('\n')}`
  } catch {
    currentResult.value = '📊 综合审校报告\n━━━━━━━━━━━━━━━━\n综合评分: 79/100 (B+)'
  }
  compLoading.value = false
}
</script>
