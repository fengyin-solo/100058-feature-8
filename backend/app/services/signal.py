"""信号机业务规则：状态流转、字段校验与筛选口径都收在这里。"""
from __future__ import annotations

from datetime import date, datetime, timedelta
from typing import Any

from app.store import store

MODULE = "signal"
REQUIRED_FIELDS = ["设备编号", "设备类型", "安装位置"]
STATUS_ORDER = ["待检修", "运用正常", "故障停用", "已更换"]
ACTION_RULES = {"确认检修": "运用正常", "登记故障": "故障停用", "更换设备": "已更换"}
NEGATIVE_ACTIONS = []

DUE_DATE_FIELD = "下次检修日"
CODE_FIELD = "设备编号"


def parse_due_date(value: Any) -> date | None:
    """把下次检修日解析成日期；空值或非 YYYY-MM-DD 格式一律视为待补录。"""
    if value is None:
        return None
    text = str(value).strip()
    if not text:
        return None
    try:
        return datetime.strptime(text, "%Y-%m-%d").date()
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

    def maintenance_due(self, *, within_days: int | None = None) -> dict[str, Any]:
        """检修到期视图：已更换的设备不参与，按下次检修日分超期/到期/待补录三组。

        分组与排序口径固定：超期组按到期日最早在前（超期最久的最靠前），
        到期组按到期日升序、同日期按设备编号升序，待补录组按设备编号升序，
        保证重新进入页面后顺序不变。
        """
        today = date.today()
        horizon = today + timedelta(days=within_days) if within_days else None

        overdue: list[dict[str, Any]] = []
        upcoming: list[dict[str, Any]] = []
        missing: list[dict[str, Any]] = []
        for row in store.rows(MODULE):
            if row.get("status") == STATUS_ORDER[-1]:
                # 已更换的信号机不再出现在到期视图里
                continue
            due_date = parse_due_date(row.get(DUE_DATE_FIELD))
            if due_date is None:
                missing.append(row)
                continue
            if due_date < today:
                overdue.append((due_date, row))
            elif horizon is None or due_date <= horizon:
                upcoming.append((due_date, row))

        overdue.sort(key=lambda item: (item[0], str(item[1].get(CODE_FIELD, ""))))
        upcoming.sort(key=lambda item: (item[0], str(item[1].get(CODE_FIELD, ""))))
        missing.sort(key=lambda row: str(row.get(CODE_FIELD, "")))

        overdue_rows = [row for _, row in overdue]
        upcoming_rows = [row for _, row in upcoming]
        return {
            "today": today.isoformat(),
            "within_days": within_days,
            "overdue": overdue_rows,
            "upcoming": upcoming_rows,
            "missing": missing,
            "total": len(overdue_rows) + len(upcoming_rows) + len(missing),
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
