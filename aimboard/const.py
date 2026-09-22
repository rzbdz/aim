"""Constants: the status vocabulary, the plan fields, the colour map and labels."""



DIVERGENCE = ("SEALED_DIVERGENT", "COMMIT", "SYNTHESIS")


STATUSES = ["backlog", "ready", "doing", "review", "done", "blocked", "dropped"]


TERMINAL = {"done", "dropped"}


PLAN_FIELDS = (
    "title", "owner", "status", "priority", "estimate", "start", "due",
    "blocked_by", "milestone", "tags", "accept", "visibility", "notes",
    "context_id", "created_by",
)


STATUS_COLOR = {
    "backlog": "#94a3b8", "ready": "#60a5fa", "doing": "#f59e0b",
    "review": "#a78bfa", "done": "#34d399", "blocked": "#ef4444",
    "dropped": "#9ca3af",
}


LABELS = {
    "en": {
        "overview": "Overview", "kanban": "Board", "gantt": "Timeline",
        "table": "Work items", "chat": "Chat", "barrier": "Barrier & audit",
        "reports": "Reports", "plan": "Plan & risk",
    },
    "zh": {
        "overview": "总览", "kanban": "看板", "gantt": "甘特图",
        "table": "工作项", "chat": "群聊", "barrier": "屏障与审计",
        "reports": "报表", "plan": "计划与风险",
    },
}
