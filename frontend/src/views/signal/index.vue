<template>
  <section class="page" data-module="signal">
    <header class="page-head">
      <div>
        <h2>信号机管理</h2>
        <p class="page-desc">维护信号机，围绕设备编号、设备类型、安装位置、显示制式做登记、筛选与状态流转；检修到期视图按下次检修日排列近期到期设备并高亮超期项。</p>
      </div>
      <div class="page-actions">
        <button class="btn primary" type="button" @click="openCreate">登记信号机</button>
        <button class="btn" type="button" @click="exportRows">导出信号机清单</button>
      </div>
    </header>

    <div class="view-tabs" role="tablist">
      <button
        type="button"
        role="tab"
        :class="{ active: view === 'list' }"
        @click="switchView('list')"
      >
        信号机列表
      </button>
      <button
        type="button"
        role="tab"
        :class="{ active: view === 'due' }"
        @click="switchView('due')"
      >
        检修到期
      </button>
    </div>

    <div class="stat-row">
      <article v-for="item in stats" :key="item.label" class="stat-card" :class="item.tone ? `tone-${item.tone}` : ''">
        <span class="stat-label">{{ item.label }}</span>
        <strong class="stat-value">{{ item.value }}</strong>
      </article>
    </div>

    <template v-if="view === 'list'">
      <form class="filter-bar" @submit.prevent="reloadList()">
        <label v-for="field in filterFields" :key="field" class="filter-item">
          <span>{{ field }}</span>
          <input v-model="filters[field]" :placeholder="`按${field}检索`" />
        </label>
        <button class="btn" type="submit">查询</button>
        <button class="btn ghost" type="button" @click="resetFilters">重置条件</button>
      </form>

      <div class="table-wrap">
        <table class="data-table">
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
              :data-code="codeOf(row)"
              :class="{ 'row-selected': isSelected(row) }"
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
      </div>

      <footer class="page-foot">
        <span>共 {{ total }} 条信号机记录<span v-if="selectedCode"> · 当前选中：{{ selectedCode }}</span></span>
        <span v-if="errorMessage" class="error-text">{{ errorMessage }}</span>
      </footer>
    </template>

    <template v-else>
      <div class="due-toolbar">
        <div class="window-switch" role="group" aria-label="近期到期窗口">
          <span class="window-label">近期窗口：</span>
          <button
            v-for="option in windowOptions"
            :key="option"
            type="button"
            class="btn"
            :class="{ primary: option === dueWindow }"
            @click="changeWindow(option)"
          >
            {{ option }} 天
          </button>
        </div>
        <span class="window-hint">统计基准日：{{ dueData.today }} · 已更换信号机不参与到期排程</span>
      </div>

      <h3 class="section-title">
        按下次检修日排列
        <span class="title-count">超期 {{ dueData.overdue_count }} · 窗口内 {{ dueData.upcoming_count }} · 窗口外 {{ dueData.later_count }}</span>
      </h3>
      <div class="table-wrap">
        <table class="data-table due-table">
          <thead>
            <tr>
              <th v-for="column in dueColumns" :key="column">{{ column }}</th>
              <th>到期状态</th>
              <th>可执行动作</th>
            </tr>
          </thead>
          <tbody>
            <tr
              v-for="row in dueData.items"
              :key="`due-${row.id}`"
              :data-code="codeOf(row)"
              :class="{
                'row-selected': isSelected(row),
                'row-overdue': row.due_state === 'overdue',
                'row-today': (row.days_due ?? 0) === 0,
              }"
              @click="selectRow(row)"
            >
              <td v-for="column in dueColumns" :key="column">{{ row[column] ?? '—' }}</td>
              <td>
                <span class="due-badge" :class="`badge-${row.due_state}`">{{ dueLabel(row) }}</span>
              </td>
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
            <tr v-if="!dueData.items.length">
              <td :colspan="dueColumns.length + 2" class="empty-state">近期暂无已排定检修日的信号机</td>
            </tr>
          </tbody>
        </table>
      </div>

      <h3 class="section-title">
        待补录（缺少下次检修日）
        <span class="title-count">{{ dueData.missing_count }} 台</span>
      </h3>
      <div class="table-wrap">
        <table class="data-table due-table">
          <thead>
            <tr>
              <th v-for="column in missingColumns" :key="column">{{ column }}</th>
              <th>可执行动作</th>
            </tr>
          </thead>
          <tbody>
            <tr
              v-for="row in dueData.missing_items"
              :key="`missing-${row.id}`"
              :data-code="codeOf(row)"
              :class="{ 'row-selected': isSelected(row) }"
              @click="selectRow(row)"
            >
              <td v-for="column in missingColumns" :key="column">{{ row[column] ?? '—' }}</td>
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
            <tr v-if="!dueData.missing_items.length">
              <td :colspan="missingColumns.length + 1" class="empty-state">没有待补录下次检修日的信号机</td>
            </tr>
          </tbody>
        </table>
      </div>

      <footer class="page-foot">
        <span>共 {{ dueData.total }} 台在排信号机<span v-if="selectedCode"> · 当前选中：{{ selectedCode }}</span></span>
        <span v-if="errorMessage" class="error-text">{{ errorMessage }}</span>
      </footer>
    </template>
  </section>
</template>

<script setup lang="ts">
import { computed, nextTick, onMounted, ref } from 'vue'

import { request } from '@/api/client'
import { useSignalViewStore, type SignalView } from '@/stores/signalView'

type DueState = 'overdue' | 'upcoming' | 'later' | 'missing'

interface SignalRow {
  id: number
  due_state?: DueState
  days_due?: number
  [field: string]: string | number | null | undefined
}

interface DuePayload {
  today: string
  window_days: number
  overdue_count: number
  upcoming_count: number
  later_count: number
  missing_count: number
  items: SignalRow[]
  missing_items: SignalRow[]
  total: number
}

interface StatCard {
  label: string
  value: number
  tone?: 'danger' | 'warn'
}

const ENDPOINT = '/api/signal'
const columns = ["设备编号", "设备类型", "安装位置", "显示制式", "所属区段", "上次检修日", "下次检修日", "设备状态"]
const dueColumns = ["设备编号", "显示制式", "所属区段", "设备类型", "下次检修日", "设备状态"]
const missingColumns = ["设备编号", "设备类型", "显示制式", "所属区段", "上次检修日", "设备状态"]
const actions = ["确认检修", "登记故障", "更换设备"]
const dueActions = ["确认检修", "登记故障"]
const windowOptions = [7, 30, 90]

const viewStore = useSignalViewStore()

const rows = ref<SignalRow[]>([])
const total = ref(0)
const errorMessage = ref('')
const filters = ref<Record<string, string>>({})
const filterFields = columns.slice(0, 3)

const dueWindow = ref(30)
const dueData = ref<DuePayload>({
  today: '',
  window_days: 30,
  overdue_count: 0,
  upcoming_count: 0,
  later_count: 0,
  missing_count: 0,
  items: [],
  missing_items: [],
  total: 0,
})

const view = computed<SignalView>(() => viewStore.view)
const selectedCode = computed(() => viewStore.selectedCode)

const allDueRows = computed<SignalRow[]>(() => [...dueData.value.items, ...dueData.value.missing_items])

const stats = computed<StatCard[]>(() => {
  if (view.value === 'due') {
    return [
      { label: '超期信号机', value: dueData.value.overdue_count, tone: 'danger' },
      { label: `近期到期（${dueWindow.value} 天内）`, value: dueData.value.upcoming_count, tone: 'warn' },
      { label: '窗口外排定', value: dueData.value.later_count },
      { label: '待补录检修日', value: dueData.value.missing_count },
    ]
  }
  const inUse = allDueRows.value.length
  const pending = allDueRows.value.filter((row) => row.status === '待检修').length
  const fault = allDueRows.value.filter((row) => row.status === '故障停用').length
  return [
    { label: '在运信号机', value: inUse },
    { label: '待检修信号机', value: pending },
    { label: '故障停用台数', value: fault },
  ]
})

function codeOf(row: SignalRow): string {
  return String(row['设备编号'] ?? '')
}

function isSelected(row: SignalRow): boolean {
  const code = codeOf(row)
  return code.length > 0 && code === selectedCode.value
}

function dueLabel(row: SignalRow): string {
  const days = row.days_due ?? 0
  if (row.due_state === 'overdue') {
    return `超期 ${Math.abs(days)} 天`
  }
  if (days === 0) {
    return '今日到期'
  }
  return `${days} 天后到期`
}

function selectRow(row: SignalRow) {
  viewStore.select(codeOf(row))
  void locateSelectedRow(false)
}

async function switchView(next: SignalView) {
  if (next === view.value) {
    return
  }
  viewStore.setView(next)
  await nextTick()
  await locateSelectedRow(true)
}

async function changeWindow(days: number) {
  if (days === dueWindow.value) {
    return
  }
  dueWindow.value = days
  await reloadDue()
}

function resetFilters() {
  filters.value = {}
  viewStore.setListKeyword('')
  void reloadList()
}

function exportRows() {
  window.open(`${ENDPOINT}/export`, '_blank')
}

function openCreate() {
  errorMessage.value = '信号机登记入口尚未接入审批流'
}

async function runAction(action: string, row: SignalRow) {
  errorMessage.value = ''
  viewStore.select(codeOf(row))
  try {
    const response = await request(`${ENDPOINT}/${row.id}/actions`, {
      method: 'POST',
      body: JSON.stringify({ action }),
    })
    if (!response.ok) {
      throw new Error('信号机动作未生效，请稍后重试')
    }
    // 确认检修、登记故障等老动作照旧：动作后两个视图都刷新，选中按设备编号保留
    await Promise.all([reloadList(true), reloadDue(true)])
    await locateSelectedRow(true)
  } catch (error) {
    errorMessage.value = error instanceof Error ? error.message : '信号机操作失败'
  }
}

async function reloadList(silent = false) {
  if (!silent) {
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
    // 列表检索词记下来：切走再回来时仍按设备编号定位到原记录
    viewStore.setListKeyword(filters.value['设备编号'] ?? '')
  } catch (error) {
    errorMessage.value = error instanceof Error ? error.message : '信号机列表读取失败'
  }
}

async function reloadDue(silent = false) {
  if (!silent) {
    errorMessage.value = ''
  }
  try {
    const response = await request(`${ENDPOINT}/due?window_days=${dueWindow.value}`)
    if (!response.ok) {
      throw new Error('检修到期数据读取失败')
    }
    dueData.value = await response.json()
  } catch (error) {
    errorMessage.value = error instanceof Error ? error.message : '检修到期数据读取失败'
  }
}

/** 在当前视图里把选中行滚动到可视区中部；两个视图的高亮都按设备编号匹配。 */
async function locateSelectedRow(scroll: boolean) {
  const code = selectedCode.value
  if (!code) {
    return
  }
  if (view.value === 'list' && !rows.value.some((row) => codeOf(row) === code)) {
    // 当前分页/过滤条件下看不到选中项：按设备编号重新定位
    filters.value['设备编号'] = code
    await reloadList(true)
  }
  if (!scroll) {
    return
  }
  await nextTick()
  const root = document.querySelector<HTMLElement>('section[data-module="signal"]')
  if (!root) {
    return
  }
  const candidates = root.querySelectorAll<HTMLElement>('tr[data-code]')
  for (const element of candidates) {
    if (element.dataset.code === code) {
      element.scrollIntoView({ behavior: 'smooth', block: 'center' })
      return
    }
  }
}

onMounted(async () => {
  // 回到本页时恢复上次的检索口径与选中项
  if (viewStore.listKeyword) {
    filters.value['设备编号'] = viewStore.listKeyword
  }
  await Promise.all([reloadList(true), reloadDue(true)])
  await nextTick()
  await locateSelectedRow(true)
})
</script>
