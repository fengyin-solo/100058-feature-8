<template>
  <section class="page" data-module="signal">
    <header class="page-head">
      <div>
        <h2>信号机管理</h2>
        <p class="page-desc">维护信号机，围绕设备编号、设备类型、安装位置、显示制式做登记、筛选与状态流转；检修到期视图按下次检修日提示近期到期与超期设备。</p>
      </div>
      <div class="page-actions">
        <button class="btn primary" type="button" @click="openCreate">登记信号机</button>
        <button class="btn" type="button" @click="exportRows">导出信号机清单</button>
      </div>
    </header>

    <div class="stat-row">
      <article v-for="item in stats" :key="item.label" class="stat-card">
        <span class="stat-label">{{ item.label }}</span>
        <strong class="stat-value">{{ item.value }}</strong>
      </article>
    </div>

    <div class="view-tabs" role="tablist">
      <button
        v-for="tab in tabs"
        :key="tab.key"
        type="button"
        role="tab"
        class="tab"
        :class="{ active: viewStore.activeView === tab.key }"
        @click="switchView(tab.key)"
      >
        {{ tab.label }}
      </button>
    </div>

    <form v-if="viewStore.activeView === 'list'" class="filter-bar" @submit.prevent="() => reloadList()">
      <label v-for="field in filterFields" :key="field" class="filter-item">
        <span>{{ field }}</span>
        <input v-model="filters[field]" :placeholder="`按${field}检索`" />
      </label>
      <button class="btn" type="submit">查询</button>
      <button class="btn ghost" type="button" @click="resetFilters">重置条件</button>
    </form>

    <table v-if="viewStore.activeView === 'list'" ref="listTableEl" class="data-table">
      <thead>
        <tr>
          <th v-for="column in columns" :key="column">{{ column }}</th>
          <th>可执行动作</th>
        </tr>
      </thead>
      <tbody>
        <tr
          v-for="row in rows"
          :key="String(row.id)"
          :data-code="row[codeField]"
          class="selectable-row"
          :class="{ 'is-selected': isSelected(row) }"
          @click="selectRow(row)"
        >
          <td v-for="column in columns" :key="column">{{ row[column] ?? '—' }}</td>
          <td class="row-actions">
            <button
              v-for="action in actions"
              :key="action"
              class="link"
              type="button"
              @click.stop="runAction(action, row)"
            >
              {{ action }}
            </button>
          </td>
        </tr>
        <tr v-if="!rows.length">
          <td :colspan="columns.length + 1" class="empty-state">暂无信号机数据，可先登记信号机</td>
        </tr>
      </tbody>
    </table>

    <table v-else ref="dueTableEl" class="data-table">
      <thead>
        <tr>
          <th v-for="column in dueColumns" :key="column">{{ column }}</th>
          <th>可执行动作</th>
        </tr>
      </thead>
      <tbody v-for="section in dueSections" :key="section.key">
        <tr class="group-row" :class="`group-${section.key}`">
          <td :colspan="dueColumns.length + 1">{{ section.title }}</td>
        </tr>
        <tr v-if="!section.rows.length">
          <td :colspan="dueColumns.length + 1" class="empty-state">暂无{{ section.short }}信号机</td>
        </tr>
        <tr
          v-for="row in section.rows"
          :key="String(row.id)"
          :data-code="row[codeField]"
          class="selectable-row"
          :class="{
            'is-selected': isSelected(row),
            'is-overdue': section.key === 'overdue',
          }"
          @click="selectRow(row)"
        >
          <td>{{ row['设备编号'] ?? '—' }}</td>
          <td>{{ row['显示制式'] ?? '—' }}</td>
          <td>{{ row['所属区段'] ?? '—' }}</td>
          <td>{{ row['设备类型'] ?? '—' }}</td>
          <td>{{ row['安装位置'] ?? '—' }}</td>
          <td>{{ row['下次检修日'] || '—' }}</td>
          <td>
            <span v-if="section.key === 'overdue'" class="tag tag-danger">超期 {{ overdueDays(row) }} 天</span>
            <span v-else-if="section.key === 'upcoming'" class="tag" :class="dayOffset(row) === 0 ? 'tag-warning' : ''">
              {{ dayOffset(row) === 0 ? '今日到期' : `${dayOffset(row)} 天后` }}
            </span>
            <span v-else class="tag tag-muted">待补录</span>
          </td>
          <td>{{ row['设备状态'] ?? '—' }}</td>
          <td class="row-actions">
            <button
              v-for="action in dueActions"
              :key="action"
              class="link"
              type="button"
              @click.stop="runAction(action, row)"
            >
              {{ action }}
            </button>
          </td>
        </tr>
      </tbody>
    </table>

    <footer class="page-foot">
      <span v-if="viewStore.activeView === 'list'">共 {{ total }} 条信号机记录</span>
      <span v-else>
        共 {{ dueData.total }} 台在管信号机：超期 {{ dueData.overdue.length }} 台、
        近期到期 {{ dueData.upcoming.length }} 台、待补录 {{ dueData.missing.length }} 台
        （已更换设备不在视图内，统计基准日 {{ dueData.today }}）
      </span>
      <span v-if="errorMessage" class="error-text">{{ errorMessage }}</span>
    </footer>
  </section>
</template>

<script setup lang="ts">
import { computed, nextTick, onMounted, ref } from 'vue'

import { request } from '@/api/client'
import { useSignalViewStore, type SignalView } from '@/stores/signalView'

type Row = Record<string, string | number | null>

type DuePayload = {
  today: string
  within_days: number | null
  overdue: Row[]
  upcoming: Row[]
  missing: Row[]
  total: number
}

type DueSection = {
  key: 'overdue' | 'upcoming' | 'missing'
  title: string
  short: string
  rows: Row[]
}

const ENDPOINT = '/api/signal'
const codeField = '设备编号'
const columns = ["设备编号", "设备类型", "安装位置", "显示制式", "所属区段", "上次检修日", "下次检修日", "设备状态"]
const dueColumns = ["设备编号", "显示制式", "所属区段", "设备类型", "安装位置", "下次检修日", "到期情况", "设备状态"]
const actions = ["确认检修", "登记故障", "更换设备"]
// 到期视图只保留既有的确认检修与登记故障，更换设备仍在列表视图里
const dueActions = ["确认检修", "登记故障"]
const tabs: { key: SignalView; label: string }[] = [
  { key: 'list', label: '信号机列表' },
  { key: 'due', label: '检修到期' },
]
const stats = [{"label": "在运信号机", "value": 0}, {"label": "待检修信号机", "value": 0}, {"label": "故障停用台数", "value": 0}]

const viewStore = useSignalViewStore()

const rows = ref<Row[]>([])
const total = ref(0)
const errorMessage = ref('')
const filters = ref<Record<string, string>>({})
const filterFields = columns.slice(0, 3)

const emptyDue: DuePayload = { today: '', within_days: null, overdue: [], upcoming: [], missing: [], total: 0 }
const dueData = ref<DuePayload>(emptyDue)

const listTableEl = ref<HTMLTableElement | null>(null)
const dueTableEl = ref<HTMLTableElement | null>(null)
let listLoaded = false
let dueLoaded = false

const dueSections = computed<DueSection[]>(() => [
  { key: 'overdue', title: `超期未修（${dueData.value.overdue.length} 台）`, short: '超期', rows: dueData.value.overdue },
  { key: 'upcoming', title: `近期到期（${dueData.value.upcoming.length} 台）`, short: '近期到期', rows: dueData.value.upcoming },
  { key: 'missing', title: `待补录下次检修日（${dueData.value.missing.length} 台）`, short: '待补录', rows: dueData.value.missing },
])

function resetFilters() {
  filters.value = {}
  void reloadList()
}

function exportRows() {
  window.open(`${ENDPOINT}/export`, '_blank')
}

function openCreate() {
  errorMessage.value = '信号机登记入口尚未接入审批流'
}

function isSelected(row: Row) {
  const code = row[codeField]
  return code !== null && code !== undefined && String(code) === viewStore.selectedCode
}

function selectRow(row: Row) {
  // 两个视图都按设备编号定位同一条信号机，选中状态互相同步
  const code = row[codeField]
  viewStore.select(code === null || code === undefined ? '' : String(code))
}

function switchView(view: SignalView) {
  viewStore.setView(view)
  void loadActiveView()
}

async function loadActiveView() {
  if (viewStore.activeView === 'due') {
    await reloadDue()
  } else {
    await reloadList()
  }
}

async function runAction(action: string, row: Row) {
  errorMessage.value = ''
  try {
    const response = await request(`${ENDPOINT}/${row.id}/actions`, {
      method: 'POST',
      body: JSON.stringify({ action }),
    })
    if (!response.ok) {
      throw new Error('信号机动作未生效，请稍后重试')
    }
    // 当前视图必须刷新；另一个视图若已加载也一并刷新，避免分组与高亮错位
    await reloadActiveSilently()
    if (viewStore.activeView === 'due' && listLoaded) {
      await reloadList(true)
    } else if (viewStore.activeView === 'list' && dueLoaded) {
      await reloadDue(true)
    }
  } catch (error) {
    errorMessage.value = error instanceof Error ? error.message : '信号机操作失败'
  }
}

async function reloadActiveSilently() {
  if (viewStore.activeView === 'due') {
    await reloadDue()
  } else {
    await reloadList()
  }
}

async function reloadList(background = false) {
  listLoaded = true
  if (!background) {
    errorMessage.value = ''
  }
  const query = new URLSearchParams(filters.value as Record<string, string>).toString()
  try {
    const response = await request(`${ENDPOINT}?${query}`)
    if (!response.ok) {
      throw new Error('信号机列表读取失败')
    }
    const payload = await response.json()
    rows.value = payload.items ?? []
    total.value = payload.total ?? rows.value.length
    await nextTick()
    scrollToSelected(listTableEl.value)
  } catch (error) {
    errorMessage.value = error instanceof Error ? error.message : '信号机列表读取失败'
  }
}

async function reloadDue(background = false) {
  dueLoaded = true
  if (!background) {
    errorMessage.value = ''
  }
  try {
    const response = await request(`${ENDPOINT}/maintenance-due`)
    if (!response.ok) {
      throw new Error('检修到期数据读取失败')
    }
    dueData.value = (await response.json()) as DuePayload
    await nextTick()
    scrollToSelected(dueTableEl.value)
  } catch (error) {
    errorMessage.value = error instanceof Error ? error.message : '检修到期数据读取失败'
  }
}

function scrollToSelected(tableEl: HTMLTableElement | null) {
  // 重新进入页面后按设备编号找回原来的选中行并恢复位置
  if (!tableEl || !viewStore.selectedCode) {
    return
  }
  const target = Array.from(tableEl.querySelectorAll<HTMLElement>('tr[data-code]')).find(
    (tr) => tr.dataset.code === viewStore.selectedCode,
  )
  target?.scrollIntoView({ block: 'nearest' })
}

function parseDate(text: string | number | null): Date | null {
  if (text === null) {
    return null
  }
  const match = /^(\d{4})-(\d{2})-(\d{2})$/.exec(String(text))
  if (!match) {
    return null
  }
  const date = new Date(Number(match[1]), Number(match[2]) - 1, Number(match[3]))
  return Number.isNaN(date.getTime()) ? null : date
}

function dayOffset(row: Row): number | null {
  const due = parseDate(row['下次检修日'])
  const today = parseDate(dueData.value.today) ?? new Date()
  if (!due) {
    return null
  }
  const millisPerDay = 24 * 60 * 60 * 1000
  const dueDay = new Date(due.getFullYear(), due.getMonth(), due.getDate()).getTime()
  const todayDay = new Date(today.getFullYear(), today.getMonth(), today.getDate()).getTime()
  return Math.round((dueDay - todayDay) / millisPerDay)
}

function overdueDays(row: Row): number {
  return Math.max(0, -(dayOffset(row) ?? 0))
}

onMounted(loadActiveView)
</script>
