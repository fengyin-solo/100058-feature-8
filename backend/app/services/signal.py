"""信号机业务规则：状态流转、字段校验、筛选口径与检修到期分组都收在这里。"""
from __future__ import annotations

from datetime import date
from typing import Any

from app.store import store

MODULE = "signal"
REQUIRED_FIELDS = ["设备编号", "设备类型", "安装位置"]
STATUS_ORDER = ["待检修", "运用正常", "故障停用", "已更换"]
ACTION_RULES = {"确认检修": "运用正常", "登记故障": "故障停用", "更换设备": "已更换"}
NEGATIVE_ACTIONS = []
REPLACED_STATUS = STATUS_ORDER[-1]
NEXT_DATE_FIELD = "下次检修日"


def parse_iso_date(value: Any) -> date | None:
    """把「YYYY-MM-DD」文本解析成日期；占位文本、空值一律按缺日期处理。"""
    if not isinstance(value, str):
        return None
    text = value.strip()
    if len(text) != 10:
        return None
    try:
        return date.fromisoformat(text)
    except ValueError:
        return None


class SignalService:
    def list_entries(
        self,
        *,
        keyword: str | None = None,
        status: str | None = None,
        page: int = 1,
        size: int = 20,
    ) -> tuple[list[dict[str, Any]], int]:
        rows = store.rows(MODULE)
        if keyword:
            rows = [row for row in rows if keyword in str(row.get("设备编号", ""))]
        if status:
            rows = [row for row in rows if row.get("status") == status]
        total = len(rows)
        start = max(page - 1, 0) * size
        return rows[start:start + size], total

    def list_due_entries(
        self, *, window_days: int, today: date | None = None
    ) -> dict[str, Any]:
        """检修到期视图口径：

        - 已更换的信号机不再参与到期排程；
        - 下次检修日缺失或无法解析的归入「待补录」，不能被漏掉；
        - 有日期的按下次检修日升序，超期在前；同日按设备编号、id 稳定排序，
          保证重新进入页面顺序不变。
        """
        today = today or date.today()
        horizon = today.fromordinal(today.toordinal() + max(window_days, 0))
        due_rows: list[dict[str, Any]] = []
        missing_rows: list[dict[str, Any]] = []
        counts = {"overdue": 0, "upcoming": 0, "later": 0, "missing": 0}

        for row in store.rows(MODULE):
            if row.get("status") == REPLACED_STATUS:
                continue
            next_date = parse_iso_date(row.get(NEXT_DATE_FIELD))
            if next_date is None:
                entry = dict(row)
                entry["due_state"] = "missing"
                missing_rows.append(entry)
                counts["missing"] += 1
                continue
            if next_date < today:
                state = "overdue"
            elif next_date <= horizon:
                state = "upcoming"
            else:
                state = "later"
            counts[state] += 1
            entry = dict(row)
            entry["due_state"] = state
            entry["days_due"] = (next_date - today).days
            due_rows.append(entry)

        def due_key(row: dict[str, Any]) -> tuple[Any, ...]:
            parsed = parse_iso_date(row.get(NEXT_DATE_FIELD))
            return (parsed or date.max, str(row.get("设备编号", "")), int(row.get("id", 0)))

        def missing_key(row: dict[str, Any]) -> tuple[str, int]:
            return (str(row.get("设备编号", "")), int(row.get("id", 0)))

        due_rows.sort(key=due_key)
        missing_rows.sort(key=missing_key)
        return {
            "today": today.isoformat(),
            "window_days": max(window_days, 0),
            "overdue_count": counts["overdue"],
            "upcoming_count": counts["upcoming"],
            "later_count": counts["later"],
            "missing_count": counts["missing"],
            "items": due_rows,
            "missing_items": missing_rows,
            "total": len(due_rows) + len(missing_rows),
        }

    def get_entry(self, entry_id: int) -> dict[str, Any] | None:
        return store.find(MODULE, entry_id)

    def create_entry(self, values: dict[str, Any]) -> tuple[dict[str, Any] | None, list[str]]:
        missing = [field for field in REQUIRED_FIELDS if not str(values.get(field) or "").strip()]
        if missing:
            return None, missing
        rows = store.rows(MODULE)
        entry = {"id": max((int(row.get("id", 0)) for row in rows), default=0) + 1}
        entry.update({field: values.get(field) for field in REQUIRED_FIELDS})
        entry["status"] = STATUS_ORDER[0]
        entry["pending"] = True
        entry["abnormal"] = False
        rows.append(entry)
        return entry, []

    def run_action(self, entry_id: int, action: str) -> tuple[dict[str, Any] | None, str]:
        entry = store.find(MODULE, entry_id)
        if entry is None:
            return None, f"信号机 {entry_id} 不存在或已归档"
        if action not in ACTION_RULES:
            return None, f"动作「{action}」不属于信号机可执行范围"
        target = ACTION_RULES[action]
        if target not in STATUS_ORDER:
            return None, f"目标状态「{target}」不在允许的状态序列里"
        entry["status"] = target
        entry["pending"] = target != STATUS_ORDER[-1]
        entry["abnormal"] = action in NEGATIVE_ACTIONS
        return entry, f"信号机已{action}"
