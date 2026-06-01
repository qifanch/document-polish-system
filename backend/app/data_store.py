from __future__ import annotations

import json
import re
import zipfile
import xml.etree.ElementTree as ET
from concurrent.futures import ThreadPoolExecutor, as_completed
from difflib import SequenceMatcher
from copy import deepcopy
from datetime import datetime, timedelta
from pathlib import Path
from time import perf_counter, sleep
from typing import Any
from uuid import uuid4

from .database import (
    create_batch_activity_in_database,
    create_batch_document_in_database,
    create_polish_template_in_database,
    delete_batch_document_from_database,
    delete_polish_template_from_database,
    get_batch_document_from_database,
    get_polish_template_from_database,
    get_template_maps_from_database,
    load_batch_status_distribution_for_user,
    load_batch_processing_from_database,
    load_global_template_top5_from_records,
    load_processing_word_trend_since_user_registered,
    load_recent_active_users_trend,
    load_score_distribution_for_user,
    load_statistics_summary_since_user_registered,
    load_template_type_stats_for_user,
    load_tone_distribution_for_user,
    list_polish_templates_from_database,
    toggle_polish_template_enabled_in_database,
    update_batch_document_polish_state,
    update_polish_template_in_database,
)
from .file_importer import parse_imported_file
from .llm import LLMTemporaryError, run_deepseek_chat_completion


BASE_DIR = Path(__file__).resolve().parent.parent
UPLOAD_DIR = BASE_DIR / "storage" / "uploads"

STATISTICS_DEFAULT_START = "2025-04-24"
STATISTICS_DEFAULT_END = "2025-05-24"
STATISTICS_PROCESSING_VALUES = [
    362154,
    381620,
    395880,
    428265,
    462114,
    501228,
    548231,
    576804,
    612508,
    653220,
    693841,
    701526,
    712365,
    709876,
    688420,
    672315,
    641226,
    618442,
    592154,
    573288,
    581662,
    603518,
    628344,
    652902,
    674156,
    689225,
    705334,
    698244,
    684220,
    671854,
    659302,
]
STATISTICS_ACTIVE_USER_VALUES = [
    42,
    58,
    71,
    64,
    82,
    57,
    76,
    94,
    88,
    97,
    121,
    146,
    98,
    86,
    103,
    110,
    132,
    149,
    118,
    92,
    104,
    76,
    128,
    108,
    95,
    112,
    119,
    101,
    108,
    93,
    82,
]


def build_statistics_series(values: list[int]) -> list[dict[str, Any]]:
    start = datetime.strptime(STATISTICS_DEFAULT_START, "%Y-%m-%d")
    return [
        {
            "date": (start + timedelta(days=index)).strftime("%Y-%m-%d"),
            "value": value,
        }
        for index, value in enumerate(values)
    ]


DEFAULT_STATISTICS = {
    "defaultRange": {
        "start": STATISTICS_DEFAULT_START,
        "end": STATISTICS_DEFAULT_END,
    },
    "summary": [
        {
            "label": "总处理文档数",
            "value": 1248,
            "unit": "",
            "trendValue": "18.6%",
            "trendDirection": "up",
            "icon": "文",
            "iconTone": "tone-blue",
        },
        {
            "label": "总处理字数",
            "value": 2456732,
            "unit": "",
            "trendValue": "21.3%",
            "trendDirection": "up",
            "icon": "字",
            "iconTone": "tone-green",
        },
        {
            "label": "平均质量评分",
            "value": 92.4,
            "unit": "分",
            "trendValue": "2.7%",
            "trendDirection": "up",
            "icon": "分",
            "iconTone": "tone-purple",
        },
        {
            "label": "总润色次数",
            "value": 2183,
            "unit": "",
            "trendValue": "16.8%",
            "trendDirection": "up",
            "icon": "次",
            "iconTone": "tone-orange",
        },
        {
            "label": "用户总数",
            "value": 326,
            "unit": "",
            "trendValue": "8.9%",
            "trendDirection": "up",
            "icon": "人",
            "iconTone": "tone-cyan",
        },
        {
            "label": "模板使用次数",
            "value": 1562,
            "unit": "",
            "trendValue": "14.2%",
            "trendDirection": "up",
            "icon": "模",
            "iconTone": "tone-teal",
        },
    ],
    "processingSeries": build_statistics_series(STATISTICS_PROCESSING_VALUES),
    "activeUserSeries": build_statistics_series(STATISTICS_ACTIVE_USER_VALUES),
    "statusDistribution": {
        "total": 1248,
        "items": [
            {"label": "已完成", "count": 1064, "percent": "85.3%", "color": "#2f6df6"},
            {"label": "待确认", "count": 128, "percent": "10.3%", "color": "#f7a33f"},
            {"label": "未润色", "count": 36, "percent": "2.9%", "color": "#8b6ef6"},
            {"label": "失败", "count": 20, "percent": "1.5%", "color": "#f05a67"},
        ],
    },
    "templateTop5": [
        {"label": "学术论文润色", "count": 562, "color": "#2f6df6"},
        {"label": "商务报告优化", "count": 328, "color": "#35c28c"},
        {"label": "公文材料润色", "count": 256, "color": "#f6a341"},
        {"label": "简历优化", "count": 194, "color": "#8b6ef6"},
        {"label": "邮件润色", "count": 128, "color": "#54c6d4"},
    ],
    "scoreDistribution": {
        "averageScore": 92.4,
        "items": [
            {"label": "90分以上", "count": 826, "percent": "66.3%", "color": "#35c28c"},
            {"label": "80-90分", "count": 318, "percent": "25.5%", "color": "#5eb4ff"},
            {"label": "60-80分", "count": 82, "percent": "6.6%", "color": "#f5a54b"},
            {"label": "60分以下", "count": 22, "percent": "1.6%", "color": "#f05a67"},
        ],
    },
    "toneDistribution": {
        "total": 2183,
        "items": [
            {"label": "正式", "count": 1154, "percent": "52.8%", "color": "#2f6df6"},
            {"label": "专业", "count": 642, "percent": "29.4%", "color": "#35c28c"},
            {"label": "简洁", "count": 274, "percent": "12.5%", "color": "#f6a341"},
            {"label": "流畅", "count": 112, "percent": "5.1%", "color": "#8b6ef6"},
            {"label": "亲和", "count": 1, "percent": "0.0%", "color": "#f05a67"},
        ],
    },
    "templateTypeStats": [
        {
            "label": "学术论文",
            "processedCount": 568,
            "wordCount": 1245678,
            "averageScore": 93.2,
            "polishCount": 1002,
            "ratio": "45.6%",
            "color": "#2f6df6",
        },
        {
            "label": "产品文档",
            "processedCount": 238,
            "wordCount": 456732,
            "averageScore": 91.6,
            "polishCount": 412,
            "ratio": "18.7%",
            "color": "#35c28c",
        },
        {
            "label": "调研报告",
            "processedCount": 186,
            "wordCount": 321045,
            "averageScore": 90.8,
            "polishCount": 318,
            "ratio": "12.1%",
            "color": "#f6a341",
        },
        {
            "label": "公文材料",
            "processedCount": 142,
            "wordCount": 221654,
            "averageScore": 92.1,
            "polishCount": 221,
            "ratio": "8.1%",
            "color": "#8b6ef6",
        },
        {
            "label": "简历",
            "processedCount": 114,
            "wordCount": 211623,
            "averageScore": 91.4,
            "polishCount": 230,
            "ratio": "7.6%",
            "color": "#54c6d4",
        },
    ],
}

DEFAULT_SETTINGS = {
    "profile": {
        "username": "张同学",
        "email": "zhangtongxue@demo.com",
        "emailVerified": True,
        "role": "普通用户",
        "registeredAt": "2024-04-12 14:32:21",
        "lastLoginAt": "2025-05-24 10:15:33",
        "avatarText": "张",
    },
    "notifications": [
        {
            "key": "polish-completed",
            "title": "润色完成通知",
            "description": "文档润色完成时通知我",
            "icon": "文",
            "siteEnabled": True,
            "emailEnabled": False,
        },
        {
            "key": "batch-completed",
            "title": "批量任务完成通知",
            "description": "批量润色任务完成时通知我",
            "icon": "批",
            "siteEnabled": True,
            "emailEnabled": True,
        },
        {
            "key": "system-announcement",
            "title": "系统公告通知",
            "description": "系统公告、重要消息通知",
            "icon": "公",
            "siteEnabled": True,
            "emailEnabled": False,
        },
        {
            "key": "template-updated",
            "title": "模板更新通知",
            "description": "润色模板更新时通知我",
            "icon": "模",
            "siteEnabled": True,
            "emailEnabled": True,
        },
        {
            "key": "promotion",
            "title": "优惠活动通知",
            "description": "优惠活动、福利信息通知",
            "icon": "惠",
            "siteEnabled": False,
            "emailEnabled": True,
        },
    ],
    "accountActions": [
        {
            "key": "change-password",
            "title": "修改密码",
            "description": "定期修改密码，保障账号安全。",
            "icon": "密",
            "tone": "green",
        },
        {
            "key": "logout",
            "title": "退出登录",
            "description": "退出当前登录状态并返回登录页面。",
            "icon": "退",
            "tone": "green",
        },
        {
            "key": "deactivate-account",
            "title": "注销账号",
            "description": "永久注销账号，所有数据将被清除。",
            "icon": "号",
            "tone": "green",
        },
    ],
    "dataActions": [
        {
            "key": "clear-cache",
            "title": "清除缓存",
            "description": "清除系统缓存，提升页面与数据加载效率。",
            "icon": "清",
            "tone": "orange",
        },
        {
            "key": "export-data",
            "title": "导出我的数据",
            "description": "导出当前账号下的文档、记录及相关数据。",
            "icon": "导",
            "tone": "orange",
        },
        {
            "key": "import-data",
            "title": "导入数据",
            "description": "从本地文件导入历史数据与系统内容。",
            "icon": "入",
            "tone": "orange",
        },
        {
            "key": "reset-defaults",
            "title": "恢复默认设置",
            "description": "将当前系统配置恢复为默认状态。",
            "icon": "复",
            "tone": "orange",
        },
    ],
}

DEFAULT_DASHBOARD = {
    "summary": [
        {"label": "累计润色次数", "value": "128", "trend": "较昨日 +12%"},
        {"label": "累计处理字数", "value": "256,842", "trend": "较昨日 +8%"},
        {"label": "平均质量评分", "value": "92.4", "trend": "较昨日 +3.2%"},
        {"label": "累计导出次数", "value": "86", "trend": "较昨日 +15%"},
    ],
    "records": [
        {
            "title": "大语言模型在自然语言处理中的应用.docx",
            "meta": "学术论文润色 · 5321 字",
            "time": "2024-05-20 14:30",
            "score": "93 分",
        },
        {
            "title": "个人简历.txt",
            "meta": "简历优化 · 1268 字",
            "time": "2024-05-20 10:15",
            "score": "91 分",
        },
        {
            "title": "毕业设计开题报告.docx",
            "meta": "学术论文润色 · 4120 字",
            "time": "2024-05-19 16:45",
            "score": "92 分",
        },
        {
            "title": "项目汇报材料.pdf",
            "meta": "公文材料润色 · 2350 字",
            "time": "2024-05-19 09:30",
            "score": "90 分",
        },
    ],
    "notices": [],
}

DEFAULT_NOTIFICATIONS = [
    {
        "id": "notice-001",
        "title": "系统升级通知：智能润色页已完成联调",
        "summary": "现在可以在工作台和智能润色页之间完成完整的前后端演示流程。",
        "content": "智能润色页已接入正式后端。你可以输入原文、选择模板和润色设置，系统会返回结果、评分、优化建议和历史记录，用于完整演示前后端联调效果。",
        "createdAt": "2024-05-20 09:30:00",
        "isRead": False,
    },
    {
        "id": "notice-002",
        "title": "新增功能：支持摘要生成与文本导出",
        "summary": "润色结果现已支持一键复制、模拟导出和摘要生成。",
        "content": "润色完成后，你可以直接复制润色结果，导出为文本或模拟 Word 文件，并生成一段简短摘要，便于演示常见办公写作流程。",
        "createdAt": "2024-05-18 14:20:00",
        "isRead": False,
    },
    {
        "id": "notice-003",
        "title": "使用提示：先选模板再润色，效果更稳定",
        "summary": "建议先从首页快捷入口进入，再在智能润色页中微调风格和强度。",
        "content": "为了获得更接近真实业务的模拟效果，建议先选择合适的润色模板，再结合润色强度、语言风格和优化选项进行处理，这样结果会更稳定，也更贴近使用场景。",
        "createdAt": "2024-05-15 18:00:00",
        "isRead": True,
    },
]

DEFAULT_BATCH_PROCESSING = {
    "summary": [
        {
            "label": "全部文档",
            "count": 12,
            "wordCount": 97053,
            "icon": "总",
            "tone": "tone-blue",
        },
        {
            "label": "已完成",
            "count": 6,
            "wordCount": 63233,
            "icon": "成",
            "tone": "tone-green",
        },
        {
            "label": "待确认",
            "count": 3,
            "wordCount": 18398,
            "icon": "待",
            "tone": "tone-orange",
        },
        {
            "label": "未润色",
            "count": 3,
            "wordCount": 15422,
            "icon": "未",
            "tone": "tone-purple",
        },
    ],
    "distribution": {
        "total": 12,
        "items": [
            {"label": "学术论文", "count": 4, "percent": "33.3%", "color": "#2f6df6"},
            {"label": "产品文档", "count": 2, "percent": "16.7%", "color": "#35c28c"},
            {"label": "简历优化", "count": 2, "percent": "16.7%", "color": "#8b6ef6"},
            {"label": "调研报告", "count": 2, "percent": "16.7%", "color": "#5eb4ff"},
            {"label": "设计文档", "count": 1, "percent": "8.3%", "color": "#f5a54b"},
            {"label": "工作总结", "count": 1, "percent": "8.3%", "color": "#b4bccb"},
        ],
    },
    "templates": [
        "学术论文",
        "产品文档",
        "简历优化",
        "调研报告",
        "设计文档",
        "工作总结",
    ],
    "documents": [
        {
            "id": "batch-doc-001",
            "title": "深度学习在自然语言处理中的应用研究",
            "category": "学术论文",
            "fileType": "Word",
            "templateType": "学术论文",
            "wordCount": 12456,
            "status": "completed",
            "updatedAt": "2026-05-01 21:24",
            "hasResult": True,
            "sourceText": "本文围绕深度学习在自然语言处理中的应用场景展开论述，重点介绍了文本分类、机器翻译和问答系统中的典型做法，并总结了当前模型在训练效率与可解释性方面的挑战。",
            "resultText": "本文系统梳理了深度学习在自然语言处理中的核心应用场景，重点概述了文本分类、机器翻译与问答系统中的典型方法，并进一步总结了当前模型在训练效率、推理成本与可解释性方面面临的主要挑战。",
        },
        {
            "id": "batch-doc-002",
            "title": "产品需求文档 PRD v2.1",
            "category": "产品文档",
            "fileType": "PDF",
            "templateType": "产品文档",
            "wordCount": 8732,
            "status": "pending",
            "updatedAt": "2026-05-01 18:30",
            "hasResult": True,
            "sourceText": "本版本主要补充了用户分层、消息提醒和权限配置三个模块的需求说明，部分业务规则仍需和运营团队再次确认。",
            "resultText": "本版本重点补充了用户分层、消息提醒与权限配置三个模块的需求说明，同时明确标注了仍需与运营团队进一步确认的业务规则，以便后续评审和排期协同。",
        },
        {
            "id": "batch-doc-003",
            "title": "市场调研报告_2026Q2",
            "category": "调研报告",
            "fileType": "Word",
            "templateType": "调研报告",
            "wordCount": 15678,
            "status": "completed",
            "updatedAt": "2026-05-01 16:45",
            "hasResult": True,
            "sourceText": "本季度调研显示，核心用户仍集中在一线与新一线城市，但下沉市场用户的增长速度正在提升，价格敏感度和交付周期成为主要影响因素。",
            "resultText": "本季度调研结果表明，核心用户仍主要集中在一线及新一线城市，但下沉市场用户的增长速度正在持续提升；与此同时，价格敏感度与交付周期已成为影响购买决策的关键因素。",
        },
        {
            "id": "batch-doc-004",
            "title": "个人简历_张同学",
            "category": "简历优化",
            "fileType": "Word",
            "templateType": "简历优化",
            "wordCount": 2456,
            "status": "pending",
            "updatedAt": "2026-05-01 14:22",
            "hasResult": True,
            "sourceText": "负责校园项目的前端开发和页面维护，参与需求讨论，协助完成数据看板和活动页的上线。",
            "resultText": "主导校园项目的前端开发与页面迭代，积极参与需求讨论，并协同完成数据看板与活动专题页的高质量上线，突出执行力与协作能力。",
        },
        {
            "id": "batch-doc-005",
            "title": "项目总结报告",
            "category": "工作总结",
            "fileType": "Word",
            "templateType": "工作总结",
            "wordCount": 6789,
            "status": "unprocessed",
            "updatedAt": "2026-05-01 11:15",
            "hasResult": False,
            "sourceText": "本阶段主要完成了需求梳理、任务拆分和阶段复盘，后续仍需补充风险点分析和资源安排。",
            "resultText": "",
        },
        {
            "id": "batch-doc-006",
            "title": "用户体验设计规范",
            "category": "设计文档",
            "fileType": "PDF",
            "templateType": "设计文档",
            "wordCount": 9876,
            "status": "completed",
            "updatedAt": "2026-05-01 09:30",
            "hasResult": True,
            "sourceText": "规范中说明了表单、弹窗和按钮等基础组件的交互要求，但部分描述较为口语化，缺少统一术语。",
            "resultText": "该规范系统说明了表单、弹窗与按钮等基础组件的交互要求，同时将原先较为口语化的描述统一替换为标准术语，以提升文档的一致性与专业度。",
        },
        {
            "id": "batch-doc-007",
            "title": "开题报告",
            "category": "学术论文",
            "fileType": "Word",
            "templateType": "学术论文",
            "wordCount": 3945,
            "status": "unprocessed",
            "updatedAt": "2026-04-30 19:12",
            "hasResult": False,
            "sourceText": "本报告拟从研究背景、研究方法和预期成果三个方面对课题进行阐述。",
            "resultText": "",
        },
        {
            "id": "batch-doc-008",
            "title": "行业白皮书摘要版",
            "category": "调研报告",
            "fileType": "TXT",
            "templateType": "调研报告",
            "wordCount": 5824,
            "status": "completed",
            "updatedAt": "2026-04-30 17:20",
            "hasResult": True,
            "sourceText": "摘要版主要提炼行业规模、技术趋势和典型案例，适合作为对外汇报材料。",
            "resultText": "摘要版重点提炼了行业规模、技术趋势与典型案例，适合直接作为对外汇报和管理层同步材料使用。",
        },
        {
            "id": "batch-doc-009",
            "title": "应聘作品集文案",
            "category": "简历优化",
            "fileType": "Word",
            "templateType": "简历优化",
            "wordCount": 7210,
            "status": "pending",
            "updatedAt": "2026-04-30 15:18",
            "hasResult": True,
            "sourceText": "文案需要更突出项目价值和个人贡献，同时减少重复描述。",
            "resultText": "该版文案进一步突出项目价值与个人贡献，并通过合并重复表述强化整体节奏，使作品集更具说服力与专业呈现效果。",
        },
        {
            "id": "batch-doc-010",
            "title": "课程结题汇报材料",
            "category": "学术论文",
            "fileType": "Word",
            "templateType": "学术论文",
            "wordCount": 11034,
            "status": "completed",
            "updatedAt": "2026-04-30 12:05",
            "hasResult": True,
            "sourceText": "汇报材料介绍了课程研究过程、阶段成果与未来改进方向，需要进一步增强表达的学术规范性。",
            "resultText": "汇报材料系统介绍了课程研究过程、阶段性成果与后续改进方向，并进一步增强了整体表述的学术规范性与逻辑完整性。",
        },
        {
            "id": "batch-doc-011",
            "title": "技术方案说明书",
            "category": "产品文档",
            "fileType": "PDF",
            "templateType": "产品文档",
            "wordCount": 4688,
            "status": "unprocessed",
            "updatedAt": "2026-04-29 18:46",
            "hasResult": False,
            "sourceText": "方案说明书目前只完成了整体架构和关键模块描述，部署与风险章节仍待补充。",
            "resultText": "",
        },
        {
            "id": "batch-doc-012",
            "title": "阶段性研究成果汇编",
            "category": "学术论文",
            "fileType": "Word",
            "templateType": "学术论文",
            "wordCount": 8365,
            "status": "completed",
            "updatedAt": "2026-04-29 16:10",
            "hasResult": True,
            "sourceText": "该汇编整理了阶段性研究成果和核心结论，但章节衔接与摘要表述仍可进一步优化。",
            "resultText": "该汇编系统整理了阶段性研究成果与核心结论，并进一步优化了章节衔接与摘要表述，使整体结构更加清晰，便于读者快速把握重点。",
        },
    ],
    "recentActivities": [
        {
            "id": "activity-001",
            "type": "completed",
            "title": "完成润色：市场调研报告_2026Q2",
            "timeAgo": "1 小时前",
        },
        {
            "id": "activity-002",
            "type": "confirm",
            "title": "提交待确认：产品需求文档 PRD v2.1",
            "timeAgo": "2 小时前",
        },
        {
            "id": "activity-003",
            "type": "export",
            "title": "批量导出：共 5 个文档",
            "timeAgo": "3 小时前",
        },
        {
            "id": "activity-004",
            "type": "upload",
            "title": "批量上传：共 3 个文档",
            "timeAgo": "5 小时前",
        },
        {
            "id": "activity-005",
            "type": "completed",
            "title": "修改文档：用户体验设计规范",
            "timeAgo": "6 小时前",
        },
    ],
}

POLISH_TEMPLATES = [
    {
        "key": "general",
        "label": "通用润色",
        "description": "适用于常规文档、工作记录和说明性内容。",
        "icon": "文",
        "tone": "icon-blue",
    },
    {
        "key": "academic",
        "label": "学术论文润色",
        "description": "适用于论文、课程报告、研究综述等正式学术文本。",
        "icon": "学",
        "tone": "icon-blue",
    },
    {
        "key": "resume",
        "label": "简历优化",
        "description": "突出项目成果、量化指标和岗位匹配度。",
        "icon": "简",
        "tone": "icon-green",
    },
    {
        "key": "business",
        "label": "商务报告优化",
        "description": "适用于汇报、方案、复盘和经营分析等商务场景。",
        "icon": "商",
        "tone": "icon-purple",
    },
    {
        "key": "official",
        "label": "公文材料润色",
        "description": "适用于通知、公告、请示、报告等正式公文材料。",
        "icon": "公",
        "tone": "icon-orange",
    },
    {
        "key": "rewrite",
        "label": "改写降重",
        "description": "在保持原意的前提下改写表达，减少重复痕迹。",
        "icon": "改",
        "tone": "icon-green",
    },
    {
        "key": "summary",
        "label": "摘要优化",
        "description": "提炼重点信息，强化摘要结构和阅读效率。",
        "icon": "摘",
        "tone": "icon-blue",
    },
]

POLISH_STRENGTHS = [
    {"key": "light", "label": "轻度"},
    {"key": "medium", "label": "中度"},
    {"key": "deep", "label": "深度"},
]

POLISH_TONES = [
    {"key": "formal", "label": "正式"},
    {"key": "professional", "label": "专业"},
    {"key": "concise", "label": "简洁"},
    {"key": "fluent", "label": "流畅"},
    {"key": "friendly", "label": "亲和"},
]

POLISH_OPTIONS = [
    {"key": "wording", "label": "优化措辞与语法"},
    {"key": "clarity", "label": "提升表达清晰度"},
    {"key": "logic", "label": "增强逻辑连贯性"},
    {"key": "sentence", "label": "调整句式结构"},
]

TEMPLATE_LABELS = {item["key"]: item["label"] for item in POLISH_TEMPLATES}
STRENGTH_LABELS = {item["key"]: item["label"] for item in POLISH_STRENGTHS}
TONE_LABELS = {item["key"]: item["label"] for item in POLISH_TONES}
OPTION_LABELS = {item["key"]: item["label"] for item in POLISH_OPTIONS}
TEMPLATE_KEYS_BY_LABEL = {item["label"]: item["key"] for item in POLISH_TEMPLATES}
MAX_POLISH_PARAGRAPHS = 40
MAX_POLISH_CHARS = 10000
MIN_POLISH_PARAGRAPH_CHARS = 80
MAX_POLISH_SEGMENT_CHARS = 1200
POLISH_LLM_CONCURRENCY = 3
MAX_POLISH_LLM_CONCURRENCY = 3
POLISH_LLM_MAX_ATTEMPTS = 3
POLISH_LLM_RETRY_DELAYS = [0.8, 1.6]
BATCH_POLISH_OPTIONS = ["wording", "clarity", "logic", "sentence"]
BATCH_DOCX_LLM_CONCURRENCY = 3
MIN_DOCX_TEXT_NODE_CHARS = 12
DOCX_DOCUMENT_XML = "word/document.xml"
DOCX_WORD_NAMESPACE = "http://schemas.openxmlformats.org/wordprocessingml/2006/main"
DOCX_XML_NAMESPACES = {
    "w": DOCX_WORD_NAMESPACE,
    "r": "http://schemas.openxmlformats.org/officeDocument/2006/relationships",
    "wp": "http://schemas.openxmlformats.org/drawingml/2006/wordprocessingDrawing",
    "a": "http://schemas.openxmlformats.org/drawingml/2006/main",
    "pic": "http://schemas.openxmlformats.org/drawingml/2006/picture",
    "mc": "http://schemas.openxmlformats.org/markup-compatibility/2006",
    "w14": "http://schemas.microsoft.com/office/word/2010/wordml",
    "w15": "http://schemas.microsoft.com/office/word/2012/wordml",
}
for namespace_prefix, namespace_uri in DOCX_XML_NAMESPACES.items():
    ET.register_namespace(namespace_prefix, namespace_uri)
QUALITY_SCORE_DIMENSIONS = [
    {"key": "fluency", "label": "流畅度", "weight": 0.25},
    {"key": "accuracy", "label": "准确性", "weight": 0.35},
    {"key": "professionalism", "label": "专业性", "weight": 0.2},
    {"key": "readability", "label": "可读性", "weight": 0.2},
]
CATEGORY_BY_TEMPLATE = {
    "general": "通用文稿",
    "academic": "学术论文",
    "resume": "简历文稿",
    "business": "商务报告",
    "official": "公文材料",
    "rewrite": "改写文本",
    "summary": "摘要文稿",
}
DEFAULT_TEMPLATE_LIBRARY: list[dict[str, Any]] = []


def sanitize_template_key(raw_value: Any, fallback: str = "template") -> str:
    text = re.sub(r"[^a-z0-9]+", "-", str(raw_value or "").lower()).strip("-")
    if text:
        return text
    return f"{fallback}-{uuid4().hex[:6]}"


STANDARD_TEMPLATE_LIBRARY = [
    {
        "id": "tpl-general",
        "key": "general",
        "name": "通用润色",
        "label": "通用润色",
        "description": "适用于常规文档、工作记录和说明性内容，重点提升表达清晰度与整体可读性。",
        "icon": "通",
        "tone": "icon-blue",
        "enabled": True,
        "isDefault": True,
        "usageCount": 0,
        "averageScore": 0,
        "updatedAt": "2026-05-08",
        "systemPrompt": "在不改变原意和事实的前提下，优化语句流畅度、结构清晰度和书面表达。",
        "terminology": ["核心观点", "背景说明", "关键结论", "执行事项", "补充信息"],
        "forbiddenExpressions": ["差不多", "随便", "感觉还行", "大概如此"],
    },
    {
        "id": "tpl-academic",
        "key": "academic",
        "name": "学术论文润色",
        "label": "学术论文润色",
        "description": "适用于论文、课程报告、研究综述等正式学术文本，强调严谨、客观和术语一致。",
        "icon": "学",
        "tone": "icon-blue",
        "enabled": True,
        "isDefault": False,
        "usageCount": 0,
        "averageScore": 0,
        "updatedAt": "2026-05-08",
        "systemPrompt": "保持学术客观、术语规范和论证连贯，不新增原文未提供的事实或结论。",
        "terminology": ["摘要", "引言", "研究方法", "实验结果", "结论"],
        "forbiddenExpressions": ["我觉得", "其实", "特别好", "非常厉害"],
    },
    {
        "id": "tpl-business",
        "key": "business",
        "name": "商务报告优化",
        "label": "商务报告优化",
        "description": "适用于汇报、方案、复盘和经营分析，强调结论先行、信息层次和行动导向。",
        "icon": "商",
        "tone": "icon-green",
        "enabled": True,
        "isDefault": False,
        "usageCount": 0,
        "averageScore": 0,
        "updatedAt": "2026-05-08",
        "systemPrompt": "突出关键结论、风险和下一步动作，使用专业、简洁、便于决策的表达方式。",
        "terminology": ["核心结论", "项目进展", "关键指标", "行动计划", "风险控制"],
        "forbiddenExpressions": ["差不多", "随便", "感觉不错", "完美无缺"],
    },
    {
        "id": "tpl-official",
        "key": "official",
        "name": "公文材料润色",
        "label": "公文材料润色",
        "description": "适用于通知、通报、请示、总结等正式公文，强调规范、稳妥和条理。",
        "icon": "公",
        "tone": "icon-orange",
        "enabled": True,
        "isDefault": False,
        "usageCount": 0,
        "averageScore": 0,
        "updatedAt": "2026-05-08",
        "systemPrompt": "保持公文语气正式、措辞稳妥、层次分明，不扩写未经原文提供的信息。",
        "terminology": ["通知事项", "工作要求", "责任分工", "完成时限", "附件说明"],
        "forbiddenExpressions": ["麻烦大家", "赶紧弄一下", "应该没问题", "有空处理"],
    },
    {
        "id": "tpl-resume",
        "key": "resume",
        "name": "简历优化",
        "label": "简历优化",
        "description": "适用于简历、项目经历和求职材料，强调成果量化、职责聚焦和专业表达。",
        "icon": "简",
        "tone": "icon-purple",
        "enabled": True,
        "isDefault": False,
        "usageCount": 0,
        "averageScore": 0,
        "updatedAt": "2026-05-08",
        "systemPrompt": "突出个人贡献、量化成果和岗位匹配度，避免空泛、重复和口语化表达。",
        "terminology": ["项目经历", "核心职责", "量化成果", "业务指标", "岗位匹配"],
        "forbiddenExpressions": ["参与了一些", "负责一点", "比较熟悉", "非常努力"],
    },
    {
        "id": "tpl-email",
        "key": "email",
        "name": "邮件润色",
        "label": "邮件润色",
        "description": "适用于工作邮件和合作沟通，强调礼貌、清晰、目的明确和行动指向。",
        "icon": "邮",
        "tone": "icon-teal",
        "enabled": True,
        "isDefault": False,
        "usageCount": 0,
        "averageScore": 0,
        "updatedAt": "2026-05-08",
        "systemPrompt": "让邮件内容更清晰、礼貌、简洁，明确背景、诉求和下一步动作。",
        "terminology": ["邮件主题", "背景说明", "待确认事项", "后续动作", "回复时限"],
        "forbiddenExpressions": ["麻烦看下", "有空回我", "赶紧处理", "随便看看"],
    },
    {
        "id": "tpl-course",
        "key": "course",
        "name": "课程论文润色",
        "label": "课程论文润色",
        "description": "适用于课程论文、课堂报告和作业分析，强调结构完整、论述清晰和课堂语境适配。",
        "icon": "课",
        "tone": "icon-indigo",
        "enabled": True,
        "isDefault": False,
        "usageCount": 0,
        "averageScore": 0,
        "updatedAt": "2026-05-08",
        "systemPrompt": "在保持原始论点的前提下，优化课程作业的结构、表达和论证连贯性。",
        "terminology": ["课程主题", "研究问题", "分析过程", "阶段结论", "参考资料"],
        "forbiddenExpressions": ["我认为吧", "感觉是", "随便写写", "绝对证明"],
    },
    {
        "id": "tpl-rewrite",
        "key": "rewrite",
        "name": "改写优化",
        "label": "改写优化",
        "description": "适用于需要保留原意但重写表达方式的内容，强调句式变化和表述升级。",
        "icon": "改",
        "tone": "icon-amber",
        "enabled": True,
        "isDefault": False,
        "usageCount": 0,
        "averageScore": 0,
        "updatedAt": "2026-05-08",
        "systemPrompt": "保留原意与事实不变，优先重构句式和措辞，让表达更加自然、紧凑和书面化。",
        "terminology": ["原意保持", "句式调整", "措辞替换", "结构优化", "表达升级"],
        "forbiddenExpressions": ["完全照抄", "随便改改", "大概这个意思", "差不多就行"],
    },
    {
        "id": "tpl-summary",
        "key": "summary",
        "name": "摘要提炼",
        "label": "摘要提炼",
        "description": "适用于纪要、说明和长文压缩，强调抓取核心信息并浓缩表达。",
        "icon": "摘",
        "tone": "icon-cyan",
        "enabled": True,
        "isDefault": False,
        "usageCount": 0,
        "averageScore": 0,
        "updatedAt": "2026-05-08",
        "systemPrompt": "围绕核心信息提炼重点，压缩冗余表达，输出简洁、完整、便于快速理解的文本。",
        "terminology": ["核心信息", "关键背景", "主要结论", "后续事项", "约束条件"],
        "forbiddenExpressions": ["流水账", "什么都写", "特别啰嗦", "没有重点"],
    },
]

STANDARD_TEMPLATE_LABELS_BY_KEY = {
    str(item.get("key") or ""): str(item.get("label") or item.get("name") or "").strip()
    for item in STANDARD_TEMPLATE_LIBRARY
}
STANDARD_TEMPLATE_KEYS_BY_LABEL = {
    label: key for key, label in STANDARD_TEMPLATE_LABELS_BY_KEY.items() if label
}
LEGACY_TEMPLATE_LABEL_ALIASES = {
    "general": "通用润色",
    "academic": "学术论文润色",
    "resume": "简历优化",
    "business": "商务报告优化",
    "official": "公文材料润色",
    "rewrite": "改写降重",
    "summary": "摘要优化",
    "閫氱敤": "通用润色",
    "学术论文": "学术论文润色",
    "简历优化": "简历优化",
    "鍟嗗姟鎶ュ憡": "商务报告优化",
    "公文材料": "公文材料润色",
    "闄嶉噸鏀瑰啓": "改写降重",
    "摘要优化": "摘要优化",
    "通用文稿": "通用文稿",
    "简历文稿": "简历文稿",
    "鏀瑰啓鏂囨湰": "改写文本",
    "摘要文稿": "摘要文稿",
    "未选择": "未选择",
}


def normalize_template_label(value: Any, fallback: str = "未选择") -> str:
    text = str(value or "").strip()
    if not text:
        return fallback
    if text in STANDARD_TEMPLATE_LABELS_BY_KEY:
        return STANDARD_TEMPLATE_LABELS_BY_KEY[text]
    return LEGACY_TEMPLATE_LABEL_ALIASES.get(text, text)


def resolve_template_key(value: Any) -> str:
    text = str(value or "").strip()
    if not text:
        return ""
    if text in STANDARD_TEMPLATE_LABELS_BY_KEY:
        return text
    normalized_label = normalize_template_label(text, fallback="")
    if not normalized_label or normalized_label == "未选择":
        return ""
    return STANDARD_TEMPLATE_KEYS_BY_LABEL.get(normalized_label, TEMPLATE_KEYS_BY_LABEL.get(normalized_label, ""))


def build_default_polish_templates() -> list[dict[str, Any]]:
    return deepcopy(STANDARD_TEMPLATE_LIBRARY)


DEFAULT_TEMPLATE_TERMINOLOGY = {
    "general": ["核心观点", "关键背景", "主要结论"],
    "academic": ["摘要", "引言", "研究方法", "实验结果", "结论"],
    "business": ["项目目标", "核心结论", "行动计划", "资源投入", "风险控制"],
    "official": ["通知事项", "执行要求", "责任分工", "完成时限", "附件说明"],
    "resume": ["项目经历", "核心成果", "量化指标", "技能栈", "岗位匹配"],
    "email": ["邮件主题", "背景说明", "待确认事项", "后续动作", "回复时限"],
    "course": ["课程目标", "研究问题", "分析过程", "阶段结论", "参考资料"],
    "rewrite": ["原文语义", "句式调整", "措辞优化", "表达升级", "结构重组"],
    "summary": ["核心信息", "关键背景", "主要结论", "后续安排", "约束条件"],
}

DEFAULT_TEMPLATE_FORBIDDEN = {
    "general": ["特别好", "真的不错", "差不多", "感觉还行"],
    "academic": ["我觉得", "其实", "非常厉害", "特别好"],
    "business": ["差不多", "随便", "感觉不错", "应该还行"],
    "official": ["麻烦大家", "赶紧弄一下", "应该没问题", "有空处理"],
    "resume": ["参与了一些", "负责一点", "做过相关事情", "比较熟悉"],
    "email": ["麻烦看下", "有空回我", "大概这样", "随便看看"],
    "course": ["我认为", "感觉是", "非常厉害", "绝对证明"],
    "rewrite": ["直接照抄", "随便改改", "大概意思", "差不多就行"],
    "summary": ["流水账", "特别啰嗦", "什么都写", "没有重点"],
}


def normalize_template_strings(values: list[Any] | None) -> list[str]:
    normalized: list[str] = []
    for value in values or []:
        text = str(value).strip()
        if text:
            normalized.append(text)
    return normalized


def build_fallback_terminology(template_key: str, template: dict[str, Any]) -> list[str]:
    terminology = normalize_template_strings(template.get("terminology"))
    if terminology:
        return terminology

    scopes = normalize_template_strings(template.get("applicableScopes"))
    if scopes:
        return scopes[:6]

    return DEFAULT_TEMPLATE_TERMINOLOGY.get(template_key, DEFAULT_TEMPLATE_TERMINOLOGY["general"])


def build_fallback_forbidden_expressions(template_key: str, template: dict[str, Any]) -> list[str]:
    forbidden = normalize_template_strings(template.get("forbiddenExpressions"))
    if forbidden:
        return forbidden

    extracted: list[str] = []
    for rule in template.get("rules") or []:
        title = str(rule.get("title") or "").strip()
        if title.startswith("閬垮厤"):
            extracted.append(title.replace("閬垮厤", "", 1).strip() or title)

    if extracted:
        return extracted[:6]

    return DEFAULT_TEMPLATE_FORBIDDEN.get(template_key, DEFAULT_TEMPLATE_FORBIDDEN["general"])


def normalize_template_list(raw_templates: list[dict[str, Any]]) -> list[dict[str, Any]]:
    normalized: list[dict[str, Any]] = []
    used_ids: set[str] = set()
    used_keys: set[str] = set()

    for index, template in enumerate(raw_templates or []):
        name = str(template.get("name") or template.get("label") or "").strip() or f"润色模板 {index + 1}"
        base_key = sanitize_template_key(template.get("key") or template.get("id") or name)
        key = base_key
        suffix = 2
        while key in used_keys:
            key = f"{base_key}-{suffix}"
            suffix += 1

        template_id = str(template.get("id") or f"tpl-{key}").strip() or f"tpl-{key}"
        while template_id in used_ids:
            template_id = f"{template_id}-{suffix}"
            suffix += 1

        normalized.append(
            {
                "id": template_id,
                "key": key,
                "name": name,
                "label": template.get("label") or name,
                "description": str(template.get("description") or "").strip(),
                "icon": str(template.get("icon") or "模").strip() or "模",
                "tone": str(template.get("tone") or "icon-blue").strip() or "icon-blue",
                "enabled": bool(template.get("enabled", True)),
                "usageCount": int(template.get("usageCount") or 0),
                "averageScore": int(template.get("averageScore") or 0),
                "updatedAt": str(template.get("updatedAt") or now_string().split(" ")[0]),
                "systemPrompt": str(template.get("systemPrompt") or "").strip(),
                "terminology": build_fallback_terminology(key, template),
                "forbiddenExpressions": build_fallback_forbidden_expressions(key, template),
            }
        )

        used_ids.add(template_id)
        used_keys.add(key)

    return normalized

def get_template_maps(
    user_id: int | None = None,
    include_disabled: bool = True,
) -> tuple[dict[str, dict[str, Any]], dict[str, str]]:
    if user_id is None:
        return ({}, {})
    return get_template_maps_from_database(int(user_id), include_disabled=include_disabled)


def get_template_label(template_key: str, user_id: int | None = None) -> str:
    by_key, _ = get_template_maps(user_id)
    template = by_key.get(template_key)
    if template:
        return normalize_template_label(template.get("name"), fallback="通用润色")
    return normalize_template_label(TEMPLATE_LABELS.get(template_key), fallback="通用润色")


def get_template_category(template_key: str, user_id: int | None = None) -> str:
    by_key, _ = get_template_maps(user_id)
    template = by_key.get(template_key)
    if template:
        return normalize_template_label(template.get("name"), fallback="通用文稿")
    return normalize_template_label(
        CATEGORY_BY_TEMPLATE.get(template_key, TEMPLATE_LABELS.get(template_key)),
        fallback="通用文稿",
    )


def list_polish_templates(user_id: int) -> list[dict[str, Any]]:
    return list_polish_templates_from_database(int(user_id), include_disabled=True)


def get_polish_template_detail(user_id: int, template_id: str) -> dict[str, Any]:
    return get_polish_template_from_database(int(user_id), template_id)

def create_polish_template(user_id: int, payload: dict[str, Any]) -> dict[str, Any]:
    return create_polish_template_in_database(int(user_id), payload)


def update_polish_template(user_id: int, template_id: str, payload: dict[str, Any]) -> dict[str, Any]:
    return update_polish_template_in_database(int(user_id), template_id, payload)


def toggle_polish_template_enabled(user_id: int, template_id: str, enabled: bool) -> dict[str, Any]:
    return toggle_polish_template_enabled_in_database(int(user_id), template_id, enabled)


def delete_polish_template(user_id: int, template_id: str) -> None:
    delete_polish_template_from_database(int(user_id), template_id)

DEFAULT_RECORD_STATUS_FLOW = ["completed", "pending", "completed", "unprocessed"]

COMMON_REPLACEMENTS = [
    ("很重要", "至关重要"),
    ("很多", "诸多"),
    ("比较", "相对"),
    ("帮助", "助力"),
    ("提升", "进一步提升"),
    ("问题", "关键问题"),
]


def derive_record_status(record: dict[str, Any], index: int) -> str:
    status = record.get("status")
    if status in {"completed", "pending", "unprocessed"}:
        return status

    has_result = bool((record.get("resultText") or "").strip() or record.get("hasResult"))
    if not has_result:
        return "unprocessed"
    return DEFAULT_RECORD_STATUS_FLOW[index % len(DEFAULT_RECORD_STATUS_FLOW)]


def derive_record_category(record: dict[str, Any], template_key: str, template_label: str) -> str:
    return (
        record.get("category")
        or record.get("documentCategory")
        or get_template_category(template_key)
        or template_label
        or "通用文稿"
    )


def derive_record_file_type(record: dict[str, Any]) -> str:
    file_type = record.get("fileType")
    if file_type:
        return file_type

    title = str(record.get("title") or "").lower()
    if title.endswith(".pdf"):
        return "PDF"
    if title.endswith(".txt"):
        return "TXT"
    return "Word"


def build_default_polish_records() -> list[dict[str, Any]]:
    sample_records: list[dict[str, Any]] = []
    _, template_keys_by_label = get_template_maps()

    for index, document in enumerate(DEFAULT_BATCH_PROCESSING["documents"][:8]):
        template_label = normalize_template_label(document.get("templateType"), fallback="通用润色")
        template_key = template_keys_by_label.get(template_label) or resolve_template_key(template_label) or "general"
        status = document.get("status", "completed")
        has_result = bool(document.get("hasResult"))
        source_text = document.get("sourceText", "")
        result_text = document.get("resultText", "")
        source_count = count_characters(source_text)
        result_count = count_characters(result_text) if has_result else 0
        score = 90 + (index % 4) if has_result else None
        tone_key = "formal" if index % 2 == 0 else "professional"
        strength_key = "medium" if index % 3 else "deep"
        options = ["wording", "clarity", "logic", "sentence"]

        sample_records.append(
            {
                "id": f"seed-record-{index + 1:03d}",
                "documentId": document.get("id"),
                "title": document.get("title", f"示例润色记录 {index + 1}"),
                "description": "",
                "category": document.get("category") or template_label,
                "fileType": derive_record_file_type(document),
                "sourceText": source_text,
                "resultText": result_text,
                "template": template_key,
                "templateLabel": template_label,
                "strength": strength_key,
                "strengthLabel": STRENGTH_LABELS[strength_key],
                "tone": tone_key,
                "toneLabel": TONE_LABELS[tone_key],
                "options": options if has_result else [],
                "optionLabels": [OPTION_LABELS[item] for item in options] if has_result else [],
                "status": status,
                "hasResult": has_result,
                "score": score,
                "dimensions": (
                    [
                        {"label": "流畅度", "value": min(98, (score or 88) + 2)},
                        {"label": "准确性", "value": min(97, score or 88)},
                        {"label": "专业性", "value": min(99, (score or 88) + 1)},
                        {"label": "可读性", "value": min(97, (score or 88) + 1)},
                    ]
                    if has_result
                    else []
                ),
                "suggestions": (
                    [
                        {"label": "词汇优化", "count": 6},
                        {"label": "句式优化", "count": 4},
                        {"label": "语法修正", "count": 3},
                        {"label": "逻辑优化", "count": 2},
                    ]
                    if has_result
                    else []
                ),
"changes": (
    [
        "优化了句式结构，增强了表达的流畅性。",
        "统一了核心术语的使用，提升了整体专业度。",
        "调整了段落衔接，使信息表达更加清晰。",
    ]
    if has_result
    else []
),
"summary": build_summary_text(result_text) if has_result else "当前记录尚未生成润色结果。",
                "compareSections": build_compare_sections(source_text, result_text) if has_result else [],
                "revisionSegments": build_revision_segments(source_text, result_text) if has_result else [],
                "wordCount": {
                    "source": source_count,
                    "result": result_count,
                    "delta": result_count - source_count if has_result else 0,
                },
                "createdAt": f"{document.get('updatedAt', '2026-05-01 09:30')}:00",
            }
        )

    return sample_records

TEMPLATE_PREFIX = {
    "general": "从整体表达效果来看，",
    "academic": "从研究表述的规范性来看，",
    "resume": "从个人经历呈现的角度来看，",
    "business": "从商务沟通的清晰度来看，",
    "official": "从正式文本的规范性来看，",
    "rewrite": "在保持原意的基础上，",
    "summary": "围绕核心信息，",
}

TONE_SUFFIX = {
    "formal": "整体表述更加正式、稳健。",
    "professional": "专业术语与逻辑层次更加清晰。",
    "concise": "表达被压缩得更紧凑，重点更加突出。",
    "fluent": "句间衔接更加自然，阅读更顺畅。",
    "friendly": "语气更柔和，也更便于读者理解。",
}


def now_string() -> str:
    return datetime.now().strftime("%Y-%m-%d %H:%M:%S")



def normalize_batch_processing_template_fields(data: dict[str, Any]) -> dict[str, Any]:
    normalized = deepcopy(data or {})
    documents = []

    for document in normalized.get("documents") or []:
        next_document = dict(document)
        next_document["templateType"] = normalize_template_label(document.get("templateType"))
        documents.append(next_document)

    normalized["documents"] = documents
    normalized["templates"] = [
        normalize_template_label(item)
        for item in (normalized.get("templates") or [])
        if normalize_template_label(item, fallback="")
    ]

    distribution = dict(normalized.get("distribution") or {})
    distribution["items"] = [
        {
            **dict(item),
            "label": normalize_template_label((item or {}).get("label")),
        }
        for item in (distribution.get("items") or [])
    ]
    distribution["total"] = int(distribution.get("total") or len(documents))
    normalized["distribution"] = distribution
    return normalized


def load_batch_processing_data(user_id: int) -> dict[str, Any]:
    return load_batch_processing_from_database(int(user_id))


def save_batch_uploaded_file(user_id: int, filename: str, content: bytes) -> str:
    extension = Path(filename or "imported-file").suffix.lower()
    today = datetime.now().strftime("%Y%m%d")
    upload_dir = UPLOAD_DIR / "batch" / str(int(user_id)) / today
    upload_dir.mkdir(parents=True, exist_ok=True)
    stored_name = f"{uuid4().hex}{extension}"
    target = upload_dir / stored_name
    target.write_bytes(content)
    return str(target.relative_to(BASE_DIR)).replace("\\", "/")


def format_batch_import_activity_title(imported_count: int, failed_count: int) -> str:
    if imported_count and failed_count:
        return f"批量导入：成功 {imported_count} 个，失败 {failed_count} 个"
    if imported_count:
        return f"批量导入：共 {imported_count} 个文件"
    return f"批量导入失败：{failed_count} 个文件"


def import_batch_processing_files(user_id: int, files: list[dict[str, Any]]) -> dict[str, Any]:
    imported: list[dict[str, Any]] = []
    failed: list[dict[str, str]] = []

    for file_item in files:
        filename = str(file_item.get("filename") or "imported-file")
        content = file_item.get("content") or b""
        try:
            parsed = parse_imported_file(filename, content)
            storage_path = save_batch_uploaded_file(int(user_id), filename, content)
            document = create_batch_document_in_database(
                int(user_id),
                {
                    "title": parsed["filename"],
                    "filename": parsed["filename"],
                    "fileType": parsed["fileType"],
                    "templateType": "未选择",
                    "wordCount": parsed["charCount"],
                    "status": "unprocessed",
                    "storagePath": storage_path,
                    "hasResult": False,
                },
            )
            imported.append(document)
        except Exception as exc:
            failed.append(
                {
                    "filename": filename,
                    "error": str(exc),
                }
            )

    create_batch_activity_in_database(
        int(user_id),
        "upload",
        format_batch_import_activity_title(len(imported), len(failed)),
        json.dumps(
            {
                "imported": len(imported),
                "failed": len(failed),
                "filenames": [str(item.get("filename") or "") for item in files],
                "errors": failed,
            },
            ensure_ascii=False,
        ),
    )
    data = load_batch_processing_data(int(user_id))
    return {
        "imported": len(imported),
        "failed": len(failed),
        "errors": failed,
        "data": data,
    }


def resolve_batch_storage_path(storage_path: str) -> Path:
    normalized = str(storage_path or "").strip()
    if not normalized:
        raise ValueError("批量文档缺少原始文件路径。")

    resolved = (BASE_DIR / normalized).resolve()
    if not is_within_directory(resolved, BASE_DIR.resolve()):
        raise ValueError("批量文档路径不在系统存储目录内。")
    if not resolved.exists():
        raise ValueError("批量文档原始文件不存在，请重新导入。")
    return resolved


def batch_user_upload_dir(user_id: int) -> Path:
    return (UPLOAD_DIR / "batch" / str(int(user_id))).resolve()


def resolve_batch_deletable_path(user_id: int, storage_path: str) -> Path:
    normalized = str(storage_path or "").strip()
    if not normalized:
        raise ValueError("批量文档删除路径无效。")

    resolved = (BASE_DIR / normalized).resolve()
    allowed_root = batch_user_upload_dir(int(user_id))
    if not is_within_directory(resolved, allowed_root):
        raise ValueError("批量文档删除路径无效。")
    return resolved


def batch_result_sidecar_path(source_path: Path) -> Path:
    return source_path.with_name(f"{source_path.stem}.polished.json")


def batch_docx_result_path(source_path: Path) -> Path:
    return source_path.with_name(f"{source_path.stem}.polished.docx")


def batch_txt_result_path(source_path: Path) -> Path:
    return source_path.with_name(f"{source_path.stem}.polished.txt")


def to_storage_relative_path(path: Path) -> str:
    return str(path.resolve().relative_to(BASE_DIR.resolve())).replace("\\", "/")


def is_within_directory(target: Path, root: Path) -> bool:
    try:
        target.resolve().relative_to(root.resolve())
        return True
    except ValueError:
        return False


def write_batch_result_sidecar(source_path: Path, payload: dict[str, Any]) -> Path:
    sidecar_path = batch_result_sidecar_path(source_path)
    sidecar_path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    return sidecar_path


def read_batch_result_sidecar(source_path: Path) -> dict[str, Any] | None:
    sidecar_path = batch_result_sidecar_path(source_path)
    if not sidecar_path.exists():
        return None
    try:
        payload = json.loads(sidecar_path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        raise ValueError("批量润色结果文件已损坏，请重新润色。") from exc
    if not isinstance(payload, dict):
        raise ValueError("批量润色结果格式无效，请重新润色。")
    return payload


def load_docx_document_xml(docx_path: Path) -> bytes:
    try:
        with zipfile.ZipFile(docx_path, "r") as archive:
            return archive.read(DOCX_DOCUMENT_XML)
    except KeyError as exc:
        raise ValueError("docx 文件缺少 word/document.xml，无法保留结构润色。") from exc
    except zipfile.BadZipFile as exc:
        raise ValueError("docx 文件结构损坏，请重新导入。") from exc


def parse_docx_document_xml(document_xml: bytes) -> tuple[ET.Element, list[ET.Element]]:
    try:
        root = ET.fromstring(document_xml)
    except ET.ParseError as exc:
        raise ValueError("docx 正文 XML 解析失败，请重新导入。") from exc
    text_nodes = list(root.iter(f"{{{DOCX_WORD_NAMESPACE}}}t"))
    if not text_nodes:
        raise ValueError("docx 文件未找到可润色文本。")
    return root, text_nodes


def extract_docx_plain_text(docx_path: Path) -> str:
    _, text_nodes = parse_docx_document_xml(load_docx_document_xml(docx_path))
    return "".join(str(node.text or "") for node in text_nodes).strip()


def write_polished_docx(source_path: Path, document_xml: bytes) -> Path:
    target_path = batch_docx_result_path(source_path)
    try:
        with zipfile.ZipFile(source_path, "r") as source_archive:
            with zipfile.ZipFile(target_path, "w") as target_archive:
                for info in source_archive.infolist():
                    if info.filename == DOCX_DOCUMENT_XML:
                        target_archive.writestr(info, document_xml)
                    else:
                        target_archive.writestr(info, source_archive.read(info.filename))
    except zipfile.BadZipFile as exc:
        raise ValueError("docx 文件结构损坏，请重新导入。") from exc
    return target_path


def write_polished_txt(source_path: Path, result_text: str) -> Path:
    target_path = batch_txt_result_path(source_path)
    target_path.write_text(str(result_text or ""), encoding="utf-8")
    return target_path


def resolve_existing_batch_result_path(user_id: int, document: dict[str, Any], source_path: Path) -> Path:
    result_file_path = str(document.get("resultFilePath") or "").strip()
    if result_file_path:
        candidate = resolve_batch_storage_path(result_file_path)
        if not candidate.exists() or not is_within_directory(candidate, batch_user_upload_dir(int(user_id))):
            raise ValueError("批量润色结果路径无效，请重新润色。")
        return candidate

    file_type = str(document.get("fileType") or "").upper()
    fallback_path: Path | None = None
    if file_type == "TXT":
        fallback_path = batch_txt_result_path(source_path)
    elif file_type == "WORD":
        fallback_path = batch_docx_result_path(source_path)

    if fallback_path is None:
        raise ValueError("当前文档缺少可下载的润色结果文件。")
    return fallback_path.resolve()


def sanitize_batch_download_name(value: str) -> str:
    cleaned = re.sub(r'[\\/:*?"<>|]+', "_", str(value or "").strip())
    cleaned = re.sub(r"\s+", " ", cleaned).strip(" ._")
    return cleaned or "batch-document"


def build_batch_result_download_filename(document: dict[str, Any], source_path: Path, result_path: Path) -> str:
    preferred_name = str(document.get("title") or "").strip()
    original_filename = str(document.get("originalFilename") or "").strip()
    base_name = (
        Path(preferred_name).stem
        if preferred_name
        else Path(original_filename).stem or source_path.stem or result_path.stem
    )
    extension = result_path.suffix or source_path.suffix or ".txt"
    return f"{sanitize_batch_download_name(base_name)}_polished{extension}"


def resolve_batch_processing_download(user_id: int, document_id: str) -> dict[str, Any]:
    document = get_batch_document_from_database(int(user_id), document_id)

    status = str(document.get("status") or "")
    if status not in {"pending", "completed"}:
        raise ValueError("当前文档状态不支持下载润色结果。")
    if not document.get("hasResult"):
        raise ValueError("当前文档暂无可下载的润色结果。")

    source_path = resolve_batch_storage_path(str(document.get("filePath") or ""))
    result_path = resolve_existing_batch_result_path(int(user_id), document, source_path)

    media_type = "application/octet-stream"
    if result_path.suffix.lower() == ".txt":
        media_type = "text/plain; charset=utf-8"
    elif result_path.suffix.lower() == ".docx":
        media_type = "application/vnd.openxmlformats-officedocument.wordprocessingml.document"

    return {
        "document": document,
        "path": result_path,
        "filename": build_batch_result_download_filename(document, source_path, result_path),
        "mediaType": media_type,
    }


def build_batch_result_payload(
    document: dict[str, Any],
    *,
    template_key: str,
    template_label: str,
    source_text: str,
    result_text: str,
    template_detail: dict[str, Any] | None,
    full_summary: str,
    result_file_path: str = "",
) -> dict[str, Any]:
    quality_score = run_llm_quality_score(
        source_text,
        result_text,
        template_detail=template_detail,
        strength="medium",
        tone="formal",
        options=BATCH_POLISH_OPTIONS,
    )
    source_count = count_characters(source_text)
    result_count = count_characters(result_text)
    return {
        "documentId": document["id"],
        "title": document.get("title", ""),
        "fileType": document.get("fileType", ""),
        "templateKey": template_key,
        "templateLabel": template_label,
        "sourceText": source_text,
        "resultText": result_text,
        "score": quality_score["score"],
        "dimensions": quality_score["dimensions"],
        "suggestions": quality_score["suggestions"],
        "summary": build_summary_text(result_text),
        "fullSummary": full_summary,
        "wordCount": {
            "source": source_count,
            "result": result_count,
            "delta": result_count - source_count,
        },
        "resultFilePath": result_file_path,
        "scoringModel": quality_score["model"],
        "scoringLatencyMs": quality_score["latencyMs"],
        "createdAt": now_string(),
    }


def polish_batch_txt_document(
    source_path: Path,
    document: dict[str, Any],
    *,
    template_key: str,
    template_label: str,
    template_detail: dict[str, Any] | None,
) -> dict[str, Any]:
    parsed = parse_imported_file(document.get("originalFilename") or source_path.name, source_path.read_bytes())
    source_text = str(parsed.get("text") or "").strip()
    polish_result = run_segmented_llm_polish(
        source_text,
        template_detail=template_detail,
        strength="medium",
        tone="formal",
        options=BATCH_POLISH_OPTIONS,
    )
    result_path = write_polished_txt(source_path, polish_result["resultText"])
    return build_batch_result_payload(
        document,
        template_key=template_key,
        template_label=template_label,
        source_text=source_text,
        result_text=polish_result["resultText"],
        template_detail=template_detail,
        full_summary=polish_result["fullSummary"],
        result_file_path=to_storage_relative_path(result_path),
    )


def polish_batch_docx_document(
    source_path: Path,
    document: dict[str, Any],
    *,
    template_key: str,
    template_label: str,
    template_detail: dict[str, Any] | None,
) -> dict[str, Any]:
    root, text_nodes = parse_docx_document_xml(load_docx_document_xml(source_path))
    source_text = "".join(str(node.text or "") for node in text_nodes).strip()
    if not source_text:
        raise ValueError("docx 文件未找到可润色文本。")

    summary_response = run_deepseek_chat_completion(build_summary_messages(source_text), max_tokens=220, temperature=0.1)
    full_summary = clean_llm_polish_text(summary_response["content"])
    if not full_summary:
        raise ValueError("大模型未返回有效全文摘要。")

    eligible_nodes = [
        (index, node, str(node.text or ""))
        for index, node in enumerate(text_nodes)
        if count_characters(str(node.text or "")) >= MIN_DOCX_TEXT_NODE_CHARS
    ]

    polished_by_index: dict[int, str] = {}
    if eligible_nodes:
        concurrency = min(BATCH_DOCX_LLM_CONCURRENCY, len(eligible_nodes))
        with ThreadPoolExecutor(max_workers=concurrency) as executor:
            futures = [
                executor.submit(
                    run_segment_polish_with_retry,
                    index,
                    text,
                    full_summary=full_summary,
                    template_detail=template_detail,
                    strength="medium",
                    tone="formal",
                    options=BATCH_POLISH_OPTIONS,
                )
                for index, _, text in eligible_nodes
            ]
            for future in as_completed(futures):
                item = future.result()
                polished_by_index[int(item["index"])] = str(item["result"])

    for index, node, _ in eligible_nodes:
        if index in polished_by_index:
            node.text = polished_by_index[index]

    result_text = "".join(str(node.text or "") for node in text_nodes).strip()
    document_xml = ET.tostring(root, encoding="utf-8", xml_declaration=True)
    result_path = write_polished_docx(source_path, document_xml)
    return build_batch_result_payload(
        document,
        template_key=template_key,
        template_label=template_label,
        source_text=source_text,
        result_text=result_text,
        template_detail=template_detail,
        full_summary=full_summary,
        result_file_path=to_storage_relative_path(result_path),
    )


def resolve_batch_template(
    user_id: int,
    template_key: str,
    template_label: str,
) -> tuple[str, str, dict[str, Any]]:
    template_by_key, template_keys_by_label = get_template_maps(int(user_id), include_disabled=False)
    normalized_key = str(template_key or "").strip()
    normalized_label = normalize_template_label(template_label, fallback="")
    if not normalized_key and normalized_label:
        normalized_key = template_keys_by_label.get(normalized_label, "") or resolve_template_key(normalized_label)
    template_detail = template_by_key.get(normalized_key) if normalized_key else None
    if template_detail is None and normalized_label:
        matched_key = template_keys_by_label.get(normalized_label, "")
        if matched_key:
            normalized_key = matched_key
            template_detail = template_by_key.get(matched_key)
    if template_detail is None:
        raise ValueError("润色模板不存在或已停用。")
    normalized_key = str(template_detail.get("key") or normalized_key).strip()
    normalized_label = normalize_template_label(
        template_detail.get("name") or template_detail.get("label"),
        fallback="通用润色",
    )
    return normalized_key, normalized_label, template_detail


def polish_single_batch_document(user_id: int, payload: dict[str, Any]) -> dict[str, Any]:
    document_id = str(payload.get("documentId") or "")
    if not document_id:
        raise ValueError("缺少批量文档 ID。")

    document = get_batch_document_from_database(int(user_id), document_id)
    source_path = resolve_batch_storage_path(str(document.get("filePath") or ""))
    original_filename = str(document.get("originalFilename") or source_path.name)
    file_type = str(document.get("fileType") or "").upper()
    if not file_type:
        suffix = Path(original_filename).suffix.lower()
        if suffix == ".txt":
            file_type = "TXT"
        elif suffix == ".docx":
            file_type = "WORD"
        elif suffix == ".pdf":
            file_type = "PDF"
    if file_type == "PDF":
        raise ValueError("PDF 文件不支持智能润色或批量处理。")

    template_key, template_label, template_detail = resolve_batch_template(
        int(user_id),
        str(payload.get("templateKey") or ""),
        str(payload.get("templateLabel") or document.get("templateType") or ""),
    )

    if file_type == "TXT":
        detail = polish_batch_txt_document(
            source_path,
            document,
            template_key=template_key,
            template_label=template_label,
            template_detail=template_detail,
        )
    elif file_type == "WORD":
        detail = polish_batch_docx_document(
            source_path,
            document,
            template_key=template_key,
            template_label=template_label,
            template_detail=template_detail,
        )
    else:
        raise ValueError("仅支持 txt 和 docx 文件批量润色。")

    sidecar_path = write_batch_result_sidecar(source_path, detail)
    word_count_payload = detail.get("wordCount") if isinstance(detail.get("wordCount"), dict) else {}
    return update_batch_document_polish_state(
        int(user_id),
        document_id,
        template_type=template_label,
        status="pending",
        has_result=True,
        result_text="",
        result_file_path=str(detail.get("resultFilePath") or ""),
        result_detail_path=to_storage_relative_path(sidecar_path),
        processed_at=str(detail.get("createdAt") or ""),
        processed_word_count=int(word_count_payload.get("result") or 0),
        score=detail.get("score"),
        confirmed_at="",
    )


def format_batch_polish_activity_title(processed_count: int, failed_count: int) -> str:
    if processed_count and failed_count:
        return f"批量润色：成功 {processed_count} 个，失败 {failed_count} 个"
    if processed_count:
        return f"批量润色：共 {processed_count} 个文件"
    return f"批量润色失败：{failed_count} 个文件"


def format_batch_confirm_activity_title(confirmed_count: int, failed_count: int) -> str:
    if confirmed_count and failed_count:
        return f"批量确认：成功 {confirmed_count} 个，失败 {failed_count} 个"
    if confirmed_count:
        return f"批量确认：共 {confirmed_count} 个文件"
    return f"批量确认失败：{failed_count} 个文件"


def format_batch_export_activity_title(documents: list[dict[str, Any]]) -> str:
    valid_documents = [item for item in documents if isinstance(item, dict)]
    if not valid_documents:
        return "批量下载"

    if len(valid_documents) == 1:
        title = str(valid_documents[0].get("title") or "未命名文档")
        return f"下载结果：{title}"

    return f"批量下载：共 {len(valid_documents)} 个文件"


def format_batch_template_activity_title(documents: list[dict[str, Any]], template_label: str) -> str:
    valid_documents = [item for item in documents if isinstance(item, dict)]
    normalized_label = normalize_template_label(template_label)
    if not valid_documents:
        return f"选择模板：{normalized_label}"

    if len(valid_documents) == 1:
        title = str(valid_documents[0].get("title") or "未命名文档")
        return f"选择模板：{title} -> {normalized_label}"

    return f"批量选择模板：{normalized_label}，共 {len(valid_documents)} 个文件"


def format_batch_delete_activity_title(deleted_documents: list[dict[str, Any]]) -> str:
    valid_documents = [item for item in deleted_documents if isinstance(item, dict)]
    if not valid_documents:
        return "批量删除"

    if len(valid_documents) == 1:
        title = str(valid_documents[0].get("title") or "未命名文档")
        return f"删除文档：{title}"

    return f"批量删除：共 {len(valid_documents)} 个文件"


def format_batch_delete_activity_title(deleted_documents: list[dict[str, Any]]) -> str:
    valid_documents = [item for item in deleted_documents if isinstance(item, dict)]
    if not valid_documents:
        return "批量删除"

    if len(valid_documents) == 1:
        title = str(valid_documents[0].get("title") or "未命名文档")
        return f"删除文档：{title}"

    return f"批量删除：共 {len(valid_documents)} 个文件"


def collect_batch_document_cleanup_paths(user_id: int, document: dict[str, Any]) -> list[Path]:
    candidates = [
        str(document.get("filePath") or "").strip(),
        str(document.get("resultFilePath") or "").strip(),
        str(document.get("resultDetailPath") or "").strip(),
    ]
    unique_paths: list[Path] = []
    seen: set[Path] = set()

    for storage_path in candidates:
        if not storage_path:
            continue
        resolved = resolve_batch_deletable_path(int(user_id), storage_path)
        if resolved in seen:
            continue
        seen.add(resolved)
        unique_paths.append(resolved)

    return unique_paths


def delete_batch_processing_documents(user_id: int, documents: list[dict[str, Any]]) -> dict[str, Any]:
    if not documents:
        raise ValueError("请选择需要删除的批量文档。")

    deleted = 0
    failed: list[dict[str, str]] = []
    deleted_documents: list[dict[str, str]] = []

    for item in documents:
        document_id = str(item.get("documentId") or "").strip()
        if not document_id:
            failed.append({"documentId": "", "error": "缺少批量文档 ID。"})
            continue

        try:
            document = get_batch_document_from_database(int(user_id), document_id)
            if str(document.get("status") or "") == "polishing":
                raise ValueError("文档正在润色中，暂时不能删除。")

            cleanup_paths = collect_batch_document_cleanup_paths(int(user_id), document)
            for path in cleanup_paths:
                if not path.exists():
                    continue
                try:
                    path.unlink()
                except FileNotFoundError:
                    continue
                except OSError as exc:
                    raise ValueError(f"删除后端文件失败：{path.name}") from exc

            deleted_documents.append(
                {
                    "documentId": document_id,
                    "title": str(document.get("title") or "未命名文档"),
                    "filename": str(document.get("originalFilename") or document.get("title") or "batch-document"),
                }
            )
            delete_batch_document_from_database(int(user_id), document_id)
            deleted += 1
        except Exception as exc:
            failed.append(
                {
                    "documentId": document_id,
                    "error": str(exc),
                }
            )

    if deleted_documents:
        create_batch_activity_in_database(
            int(user_id),
            "delete",
            format_batch_delete_activity_title(deleted_documents),
            json.dumps(
                {
                    "count": len(deleted_documents),
                    "documents": deleted_documents,
                    "filenames": [item["filename"] for item in deleted_documents],
                    "failed": len(failed),
                    "errors": failed,
                },
                ensure_ascii=False,
            ),
        )

    return {
        "deleted": deleted,
        "failed": len(failed),
        "errors": failed,
        "data": load_batch_processing_data(int(user_id)),
    }


def polish_batch_processing_documents(user_id: int, documents: list[dict[str, Any]]) -> dict[str, Any]:
    if not documents:
        raise ValueError("请选择需要批量润色的文件。")

    processed: list[dict[str, Any]] = []
    failed: list[dict[str, str]] = []
    queued_documents: list[dict[str, Any]] = []
    for item in documents:
        document_id = str(item.get("documentId") or "")
        try:
            document = get_batch_document_from_database(int(user_id), document_id)
            if document.get("status") == "completed":
                raise ValueError("已确认的文档不可重复润色，请选择待确认或未润色文档。")
            _, template_label, _ = resolve_batch_template(
                int(user_id),
                str(item.get("templateKey") or ""),
                str(item.get("templateLabel") or document.get("templateType") or ""),
            )
            update_batch_document_polish_state(
                int(user_id),
                document_id,
                template_type=template_label,
                status="polishing",
                has_result=False,
                result_text="",
                result_file_path="",
                result_detail_path="",
                confirmed_at="",
            )
            queued_documents.append(
                {
                    "documentId": document_id,
                    "templateKey": str(item.get("templateKey") or ""),
                    "templateLabel": template_label,
                }
            )
        except Exception as exc:
            failed.append(
                {
                    "documentId": document_id,
                    "error": str(exc),
                }
            )

    for item in queued_documents:
        document_id = str(item.get("documentId") or "")
        try:
            processed.append(polish_single_batch_document(int(user_id), item))
        except Exception as exc:
            try:
                update_batch_document_polish_state(
                    int(user_id),
                    document_id,
                    template_type=normalize_template_label(item.get("templateLabel")),
                    status="unprocessed",
                    has_result=False,
                    result_text="",
                    result_file_path="",
                    result_detail_path="",
                    confirmed_at="",
                )
            except Exception:
                pass
            failed.append(
                {
                    "documentId": document_id,
                    "error": str(exc),
                }
            )

    create_batch_activity_in_database(
        int(user_id),
        "polish",
        format_batch_polish_activity_title(len(processed), len(failed)),
        json.dumps(
            {
                "processed": len(processed),
                "failed": len(failed),
                "documents": documents,
                "filenames": [
                    str(item.get("originalFilename") or item.get("title") or "batch-document")
                    for item in processed
                ],
                "errors": failed,
            },
            ensure_ascii=False,
        ),
    )
    return {
        "processed": len(processed),
        "failed": len(failed),
        "errors": failed,
        "data": load_batch_processing_data(int(user_id)),
    }


def confirm_batch_processing_documents(user_id: int, documents: list[dict[str, Any]]) -> dict[str, Any]:
    if not documents:
        raise ValueError("请选择需要确认的文档。")

    confirmed: list[dict[str, Any]] = []
    failed: list[dict[str, str]] = []
    confirmed_at = now_string()

    for item in documents:
        document_id = str(item.get("documentId") or "")
        try:
            document = get_batch_document_from_database(int(user_id), document_id)
            if document.get("status") != "pending":
                raise ValueError("只有待确认的文档可以执行确认。")
            if not document.get("hasResult"):
                raise ValueError("当前文档尚未生成润色结果，无法确认。")
            confirmed.append(
                update_batch_document_polish_state(
                    int(user_id),
                    document_id,
                    template_type=str(document.get("templateType") or ""),
                    status="completed",
                    has_result=True,
                    result_text=str(document.get("resultText") or ""),
                    confirmed_at=confirmed_at,
                )
            )
        except Exception as exc:
            failed.append(
                {
                    "documentId": document_id,
                    "error": str(exc),
                }
            )

    create_batch_activity_in_database(
        int(user_id),
        "confirm",
        format_batch_confirm_activity_title(len(confirmed), len(failed)),
        json.dumps(
            {
                "confirmed": len(confirmed),
                "failed": len(failed),
                "documents": documents,
                "filenames": [
                    str(item.get("originalFilename") or item.get("title") or "batch-document")
                    for item in confirmed
                ],
                "errors": failed,
            },
            ensure_ascii=False,
        ),
    )
    return {
        "processed": len(confirmed),
        "failed": len(failed),
        "errors": failed,
        "data": load_batch_processing_data(int(user_id)),
    }


def record_batch_processing_export(user_id: int, documents: list[dict[str, Any]]) -> dict[str, Any]:
    if not documents:
        raise ValueError("请选择需要导出的批量文档。")

    exported_documents: list[dict[str, Any]] = []
    invalid_documents: list[dict[str, str]] = []

    for item in documents:
        document_id = str(item.get("documentId") or "").strip()
        if not document_id:
            invalid_documents.append({"documentId": "", "error": "缺少文档标识。"})
            continue

        try:
            document = get_batch_document_from_database(int(user_id), document_id)
        except KeyError:
            invalid_documents.append({"documentId": document_id, "error": "文档不存在。"})
            continue

        exported_documents.append(
            {
                "documentId": document_id,
                "title": str(document.get("title") or "未命名文档"),
                "filename": str(item.get("filename") or "").strip()
                or str(document.get("originalFilename") or document.get("title") or "batch-result"),
            }
        )

    if not exported_documents:
        raise ValueError("没有可导出的批量文档。")

    activity = create_batch_activity_in_database(
        int(user_id),
        "export",
        format_batch_export_activity_title(exported_documents),
        json.dumps(
            {
                "count": len(exported_documents),
                "documents": exported_documents,
                "filenames": [item["filename"] for item in exported_documents],
                "invalidDocuments": invalid_documents,
            },
            ensure_ascii=False,
        ),
    )
    return {
        "processed": len(exported_documents),
        "failed": len(invalid_documents),
        "errors": invalid_documents,
        "activity": activity,
        "recentActivities": load_batch_processing_data(int(user_id)).get("recentActivities", []),
    }


def record_batch_processing_template_event(
    user_id: int,
    documents: list[dict[str, Any]],
    template_key: str,
    template_label: str,
) -> dict[str, Any]:
    if not documents:
        raise ValueError("请选择至少一个文件。")

    normalized_label = str(template_label or "").strip()
    if not normalized_label:
        raise ValueError("缺少模板名称。")

    affected_documents: list[dict[str, str]] = []
    invalid_documents: list[dict[str, str]] = []

    for item in documents:
        document_id = str(item.get("documentId") or "").strip()
        if not document_id:
            invalid_documents.append({"documentId": "", "error": "缺少文档标识。"})
            continue

        try:
            document = get_batch_document_from_database(int(user_id), document_id)
        except KeyError:
            invalid_documents.append({"documentId": document_id, "error": "文档不存在。"})
            continue

        affected_documents.append(
            {
                "documentId": document_id,
                "title": str(document.get("title") or "未命名文档"),
                "filename": str(document.get("originalFilename") or document.get("title") or "batch-document"),
            }
        )

    if not affected_documents:
        raise ValueError("没有可记录的模板选择。")

    activity = create_batch_activity_in_database(
        int(user_id),
        "template",
        format_batch_template_activity_title(affected_documents, normalized_label),
        json.dumps(
            {
                "count": len(affected_documents),
                "templateKey": str(template_key or "").strip(),
                "templateLabel": normalized_label,
                "documents": affected_documents,
                "filenames": [item["filename"] for item in affected_documents],
                "failed": len(invalid_documents),
                "errors": invalid_documents,
            },
            ensure_ascii=False,
        ),
    )

    return {
        "processed": len(affected_documents),
        "failed": len(invalid_documents),
        "errors": invalid_documents,
        "activity": activity,
        "recentActivities": load_batch_processing_data(int(user_id)).get("recentActivities", []),
    }

def parse_batch_source_text_for_result(document: dict[str, Any], source_path: Path) -> str:
    file_type = str(document.get("fileType") or "").upper()
    if file_type == "TXT":
        parsed = parse_imported_file(document.get("originalFilename") or source_path.name, source_path.read_bytes())
        return str(parsed.get("text") or "")
    if file_type == "WORD":
        return extract_docx_plain_text(source_path)
    raise ValueError("PDF 文件暂不支持读取原文内容。")


def get_batch_processing_result(user_id: int, document_id: str) -> dict[str, Any]:
    document = get_batch_document_from_database(int(user_id), document_id)
    if not document.get("hasResult"):
        raise KeyError(document_id)

    source_path = resolve_batch_storage_path(str(document.get("filePath") or ""))
    sidecar = read_batch_result_sidecar(source_path)
    if sidecar:
        return {
            **document,
            **sidecar,
        }

    result_text = str(document.get("resultText") or "")
    if not result_text:
        raise KeyError(document_id)

    source_text = parse_batch_source_text_for_result(document, source_path)
    source_count = count_characters(source_text)
    result_count = count_characters(result_text)
    return {
        **document,
        "sourceText": source_text,
        "resultText": result_text,
        "score": None,
        "dimensions": [],
        "suggestions": [],
        "templateLabel": document.get("templateType") or "",
        "wordCount": {
            "source": source_count,
            "result": result_count,
            "delta": result_count - source_count,
        },
    }


def parse_statistics_date(value: str | None, fallback: str) -> datetime:
    target = value or fallback
    return datetime.strptime(target, "%Y-%m-%d")


def filter_statistics_series(
    points: list[dict[str, Any]],
    range_start: datetime,
    range_end: datetime,
) -> list[dict[str, Any]]:
    filtered = []
    for point in points:
        point_date = datetime.strptime(point["date"], "%Y-%m-%d")
        if range_start <= point_date <= range_end:
            filtered.append({"date": point_date, "value": int(point["value"])})

    if filtered:
        return filtered

    return [
        {"date": datetime.strptime(point["date"], "%Y-%m-%d"), "value": int(point["value"])}
        for point in points
    ]


def aggregate_filtered_statistics_series(
    filtered: list[dict[str, Any]],
    granularity: str,
) -> dict[str, list[Any]]:
    if not filtered:
        return {"labels": [], "values": []}

    if granularity == "day":
        return {
            "labels": [item["date"].strftime("%m-%d") for item in filtered],
            "values": [item["value"] for item in filtered],
        }

    if granularity == "month":
        grouped: dict[str, list[int]] = {}
        for item in filtered:
            key = item["date"].strftime("%Y-%m")
            grouped.setdefault(key, []).append(item["value"])
        return {
            "labels": [datetime.strptime(key, "%Y-%m").strftime("%Y-%m") for key in grouped],
            "values": [sum(values) for values in grouped.values()],
        }

    labels: list[str] = []
    values: list[int] = []
    for index in range(0, len(filtered), 7):
        chunk = filtered[index:index + 7]
        labels.append(f"{chunk[0]['date'].strftime('%m-%d')} ~ {chunk[-1]['date'].strftime('%m-%d')}")
        values.append(sum(item["value"] for item in chunk))
    return {"labels": labels, "values": values}


def aggregate_statistics_series(
    points: list[dict[str, Any]],
    range_start: datetime,
    range_end: datetime,
    granularity: str,
) -> dict[str, list[Any]]:
    filtered = filter_statistics_series(points, range_start, range_end)
    return aggregate_filtered_statistics_series(filtered, granularity)


def load_statistics_data(
    range_start: str | None = None,
    range_end: str | None = None,
    granularity: str = "week",
    user_id: int = 0,
) -> dict[str, Any]:
    granularity = granularity if granularity in {"day", "week", "month"} else "week"
    parsed_start = parse_statistics_date(range_start, STATISTICS_DEFAULT_START)
    parsed_end = parse_statistics_date(range_end, STATISTICS_DEFAULT_END)

    if parsed_start > parsed_end:
        parsed_start, parsed_end = parsed_end, parsed_start

    summary = load_statistics_summary_since_user_registered(int(user_id))
    status_distribution = load_batch_status_distribution_for_user(int(user_id))
    processing_trend_payload = load_processing_word_trend_since_user_registered(int(user_id), granularity, 30)
    score_distribution = load_score_distribution_for_user(int(user_id))
    tone_distribution = load_tone_distribution_for_user(int(user_id))
    active_user_trend_payload = load_recent_active_users_trend(30)

    template_top = load_global_template_top5_from_records(5)
    max_count = max((int(item.get("count", 0)) for item in template_top), default=1)
    template_top = [
        {
            **item,
            "barWidth": f"{max(12, round((int(item.get('count', 0)) / max_count) * 100))}%",
        }
        for item in template_top
    ]

    return {
        "defaultRange": {
            "start": STATISTICS_DEFAULT_START,
            "end": STATISTICS_DEFAULT_END,
        },
        "selectedRange": {
            "start": parsed_start.strftime("%Y-%m-%d"),
            "end": parsed_end.strftime("%Y-%m-%d"),
        },
        "granularity": granularity,
        "summary": summary,
        "processingTrend": processing_trend_payload.get("trend", {"labels": [], "values": []}),
        "activeUsersTrend": active_user_trend_payload.get("trend", {"labels": [], "values": []}),
        "processingSeries": processing_trend_payload.get("series", []),
        "activeUserSeries": active_user_trend_payload.get("series", []),
        "statusDistribution": status_distribution,
        "templateTop5": template_top,
        "scoreDistribution": score_distribution,
        "toneDistribution": tone_distribution,
        "templateTypeStats": load_template_type_stats_for_user(int(user_id)),
    }


def build_auto_title(content: str) -> str:
    plain = re.sub(r"\s+", "", content)
    if not plain:
        return "未命名文档"
    return f"{plain[:12]}{'...' if len(plain) > 12 else ''}"


def count_characters(text: str) -> int:
    return len(re.sub(r"\s+", "", text))


def load_polish_config(user_id: int) -> dict[str, Any]:
    templates = list_polish_templates_from_database(int(user_id), include_disabled=False)
    preferred_default = next((item for item in templates if item["key"] == "general"), templates[0] if templates else None)
    return {
        "defaultTemplate": preferred_default["key"] if preferred_default else "",
        "defaultStrength": "medium",
        "defaultTone": "formal",
        "templates": [
            {
                "key": item["key"],
                "label": item["name"],
                "description": item["description"],
                "icon": item["icon"],
                "tone": item["tone"],
            }
            for item in templates
        ],
        "strengths": POLISH_STRENGTHS,
        "tones": POLISH_TONES,
        "options": POLISH_OPTIONS,
    }


def normalize_text(text: str) -> str:
    lines = [line.strip() for line in text.replace("\r", "").split("\n")]
    return "\n".join([line for line in lines if line])


def apply_common_replacements(text: str, level: str) -> str:
    result = text
    replacements = COMMON_REPLACEMENTS[:]
    if level == "light":
        replacements = replacements[:2]
    elif level == "medium":
        replacements = replacements[:4]

    for source, target in replacements:
        result = result.replace(source, target)
    return result


def split_sentences(text: str) -> list[str]:
    normalized = normalize_text(text)
    parts = re.split(r"(?<=[。！？；.!?;])", normalized)
    return [part.strip() for part in parts if part.strip()]


def join_sentences(sentences: list[str]) -> str:
    joined = "".join(sentences).strip()
    return joined or "暂无润色结果。"


def polish_sentences(
    content: str,
    template: str,
    strength: str,
    tone: str,
    options: list[str],
) -> tuple[str, list[str]]:
    sentences = split_sentences(content)
    if not sentences:
        return "", []

    polished: list[str] = []
    changes: list[str] = []
    prefix = TEMPLATE_PREFIX.get(template, TEMPLATE_PREFIX["general"])
    suffix = TONE_SUFFIX.get(tone, TONE_SUFFIX["formal"])

    for index, sentence in enumerate(sentences):
        current = apply_common_replacements(sentence, strength)
        if index == 0 and not current.startswith(prefix):
            current = prefix + current

        if "clarity" in options and "因此" not in current and len(current) > 18:
            current = current.replace("。", "，从而使重点表达更清晰。")
        if "logic" in options and index > 0 and not current.startswith(("同时", "此外", "另外", "因此")):
            current = "同时，" + current
        if "sentence" in options and "并且" in current:
            current = current.replace("并且", "并进一步")
        if template == "academic":
            current = current.replace("认为", "指出").replace("使用", "采用")
        elif template == "resume":
            current = current.replace("负责", "主导").replace("参与", "参与并推动")
        elif template == "business":
            current = current.replace("沟通", "协同沟通").replace("推进", "高效推进")
        elif template == "official":
            current = current.replace("需要", "应当").replace("加强", "进一步加强")
        elif template == "rewrite":
            current = current.replace("但是", "然而").replace("所以", "因此")
        elif template == "summary":
            current = current.replace("研究", "核心研究").replace("重点", "关键信息")

        if strength == "deep" and index == len(sentences) - 1 and suffix not in current:
            if current.endswith("。"):
                current = current[:-1] + "，" + suffix
            else:
                current = current + "，" + suffix
        elif strength == "medium" and index == len(sentences) - 1 and tone in {"formal", "professional"}:
            if current.endswith("。"):
                current = current[:-1] + "，整体表达更加清晰。"

        polished.append(current)

    changes.append("优化了句式结构，增强了表达的流畅性。")
    if "wording" in options:
        changes.append("使用更精准的词汇，提升了语言的专业性。")
    if "logic" in options:
        changes.append("增强了逻辑衔接，使文章结构更加清晰。")
    if strength == "deep":
        changes.append("在保留原意的基础上，提升了整体表达质量。")
    else:
        changes.append("在尽量保留原意的前提下，完成了表达优化。")

    return join_sentences(polished), changes


def build_summary_text(text: str) -> str:
    sentences = split_sentences(text)
    if not sentences:
        return "暂无可提炼的摘要内容。"
    summary = "".join(sentences[:2]).strip()
    if len(summary) > 110:
        summary = summary[:110] + "..."
    if not summary.endswith(("。", "！", "？")):
        summary += "。"
    return summary


def build_score_bundle(content: str, strength: str, tone: str, options: list[str]) -> tuple[int, list[dict[str, Any]], list[dict[str, Any]]]:
    base = 84 + min(10, count_characters(content) // 60)
    strength_boost = {"light": 1, "medium": 3, "deep": 5}.get(strength, 3)
    tone_boost = {"formal": 1, "professional": 2, "concise": 1, "fluent": 2, "friendly": 1}.get(tone, 1)
    option_boost = min(4, len(options))
    total_score = min(98, base + strength_boost + tone_boost + option_boost)

    dimensions = [
        {"label": "流畅度", "value": min(98, total_score + 2)},
        {"label": "准确性", "value": min(97, total_score - 1)},
        {"label": "专业性", "value": min(99, total_score + (2 if tone == "professional" else 0))},
        {"label": "可读性", "value": min(97, total_score + (1 if "clarity" in options else 0))},
    ]

    suggestions = [
        {"label": "词汇优化", "count": 8 if "wording" in options else 5},
        {"label": "句式优化", "count": 6 if strength == "deep" else 4},
        {"label": "语法修正", "count": 4 if "sentence" in options else 2},
        {"label": "逻辑优化", "count": 5 if "logic" in options else 2},
    ]
    return total_score, dimensions, suggestions


def extract_json_object(text: str) -> dict[str, Any]:
    cleaned = str(text or "").strip()
    cleaned = re.sub(r"^```(?:json)?\s*", "", cleaned, flags=re.IGNORECASE)
    cleaned = re.sub(r"\s*```$", "", cleaned).strip()
    start = cleaned.find("{")
    end = cleaned.rfind("}")
    if start >= 0 and end >= start:
        cleaned = cleaned[start : end + 1]
    try:
        parsed = json.loads(cleaned)
    except json.JSONDecodeError as exc:
        raise ValueError("大模型评分未返回有效 JSON。") from exc
    if not isinstance(parsed, dict):
        raise ValueError("大模型评分 JSON 必须是对象。")
    return parsed


def normalize_quality_score_value(value: Any, label: str) -> float:
    try:
        score = float(value)
    except (TypeError, ValueError) as exc:
        raise ValueError(f"{label}评分必须是数字。") from exc
    if score < 0 or score > 100:
        raise ValueError(f"{label}评分必须在 0 到 100 之间。")
    return round(score, 1)


def normalize_quality_score_reason(value: Any, label: str) -> str:
    reason = re.sub(r"\s+", " ", str(value or "")).strip()
    if not reason:
        raise ValueError(f"{label}评分必须给出简短理由。")
    return reason[:160]
    return reason[:160]


def build_quality_score_messages(
    source_text: str,
    result_text: str,
    requirement_text: str,
) -> list[dict[str, str]]:
    scoring_standard = "\n".join(
        [
            "1. 流畅度：评价润色结果是否通顺、自然、没有语病，满分100分。",
            "2. 准确性：评价润色结果是否保持原文核心含义，是否存在误改、漏改、添加原文没有的信息，满分100分。准确性必须重点参考原文。",
            "3. 专业性：评价润色结果是否符合文本场景，用词是否规范，术语是否准确，风格是否正式，满分100分。",
            "4. 可读性：评价润色结果结构是否清晰、逻辑是否顺畅、是否容易理解，满分100分。",
            "不要因为文字更华丽就给高分；如果改变原意，应降低准确性分数。",
            "总分 = 流畅度 × 25% + 准确性 × 35% + 专业性 × 20% + 可读性 × 20%。",
        ]
    )
    return [
        {
            "role": "system",
            "content": (
                "你是严格的中文文档润色质量评审。请对润色结果进行客观评分。"
                "只返回 JSON，不要输出 Markdown、解释文字或代码块。"
            ),
        },
        {
            "role": "user",
            "content": (
                "请根据原文、润色结果、润色要求和评分标准进行评分。\n\n"
                f"【原文】\n{source_text}\n\n"
                f"【润色结果】\n{result_text}\n\n"
                f"【润色要求】\n{requirement_text}\n\n"
                f"【评分标准】\n{scoring_standard}\n\n"
                "请严格返回如下 JSON 结构：\n"
                "{\"score\": 0, \"dimensions\": ["
                "{\"key\":\"fluency\",\"label\":\"流畅度\",\"value\":0,\"reason\":\"一句简短理由\"},"
                "{\"key\":\"accuracy\",\"label\":\"准确性\",\"value\":0,\"reason\":\"一句简短理由\"},"
                "{\"key\":\"professionalism\",\"label\":\"专业性\",\"value\":0,\"reason\":\"一句简短理由\"},"
                "{\"key\":\"readability\",\"label\":\"可读性\",\"value\":0,\"reason\":\"一句简短理由\"}"
                "]}"
            ),
        },
    ]


def normalize_quality_score_response(raw_score: dict[str, Any]) -> dict[str, Any]:
    raw_dimensions = raw_score.get("dimensions")
    if not isinstance(raw_dimensions, list):
        raise ValueError("大模型评分 JSON 缺少 dimensions 数组。")

    raw_by_key = {
        str(item.get("key") or "").strip(): item
        for item in raw_dimensions
        if isinstance(item, dict)
    }
    raw_by_label = {
        str(item.get("label") or "").strip(): item
        for item in raw_dimensions
        if isinstance(item, dict)
    }

    dimensions: list[dict[str, Any]] = []
    weighted_score = 0.0
    for meta in QUALITY_SCORE_DIMENSIONS:
        item = raw_by_key.get(meta["key"]) or raw_by_label.get(meta["label"])
        if not item:
            raise ValueError(f"大模型评分缺少 {meta['label']} 维度。")
        value = normalize_quality_score_value(item.get("value"), meta["label"])
        reason = normalize_quality_score_reason(item.get("reason"), meta["label"])
        weighted_score += value * float(meta["weight"])
        dimensions.append(
            {
                "key": meta["key"],
                "label": meta["label"],
                "value": value,
                "reason": reason,
            }
        )

    score = round(weighted_score, 1)
    if score.is_integer():
        score = int(score)
    return {
        "score": score,
        "dimensions": dimensions,
        "suggestions": [],
    }


def run_llm_quality_score(
    source_text: str,
    result_text: str,
    *,
    template_detail: dict[str, Any] | None,
    strength: str,
    tone: str,
    options: list[str],
) -> dict[str, Any]:
    started_at = perf_counter()
    requirement_text = (
        build_template_requirement_text(template_detail)
        if template_detail
        else build_option_requirement_text(strength, tone, options)
    )
    response = run_deepseek_chat_completion(
        build_quality_score_messages(source_text, result_text, requirement_text),
        max_tokens=1400,
        temperature=0,
        thinking_type="enabled",
    )
    latency_ms = int((perf_counter() - started_at) * 1000)
    score_data = normalize_quality_score_response(extract_json_object(response["content"]))
    return {
        **score_data,
        "model": response["model"],
        "latencyMs": latency_ms,
        "scoringJson": {
            "score": score_data["score"],
            "dimensions": score_data["dimensions"],
        },
    }


def build_compare_sections(source_text: str, result_text: str) -> list[dict[str, str]]:
    source_sentences = split_sentences(source_text)
    result_sentences = split_sentences(result_text)
    pairs = []
    for index, source in enumerate(source_sentences[:3]):
        pairs.append(
            {
                "label": f"片段 {index + 1}",
                "source": source,
                "result": result_sentences[index] if index < len(result_sentences) else result_text,
            }
        )
    return pairs


def merge_revision_segments(segments: list[dict[str, str]]) -> list[dict[str, str]]:
    merged: list[dict[str, str]] = []
    for segment in segments:
        text = segment.get("text", "")
        segment_type = segment.get("type", "unchanged")
        if not text:
            continue
        if merged and merged[-1]["type"] == segment_type:
            merged[-1]["text"] += text
        else:
            merged.append({"type": segment_type, "text": text})
    return merged


def build_revision_segments(source_text: str, result_text: str) -> list[dict[str, str]]:
    matcher = SequenceMatcher(None, source_text or "", result_text or "")
    segments: list[dict[str, str]] = []

    for tag, source_start, source_end, result_start, result_end in matcher.get_opcodes():
        if tag == "equal":
            segments.append(
                {
                    "type": "unchanged",
                    "text": result_text[result_start:result_end],
                }
            )
        elif tag == "delete":
            segments.append(
                {
                    "type": "deleted",
                    "text": source_text[source_start:source_end],
                }
            )
        elif tag == "insert":
            segments.append(
                {
                    "type": "added",
                    "text": result_text[result_start:result_end],
                }
            )
        elif tag == "replace":
            removed = source_text[source_start:source_end]
            added = result_text[result_start:result_end]
            if removed:
                segments.append({"type": "deleted", "text": removed})
            if added:
                segments.append({"type": "added", "text": added})

    return merge_revision_segments(segments)


def clean_llm_polish_text(text: str) -> str:
    cleaned = str(text or "").strip()
    cleaned = re.sub(r"^```(?:text|markdown)?\s*", "", cleaned, flags=re.IGNORECASE)
    cleaned = re.sub(r"\s*```$", "", cleaned)
    cleaned = re.sub(r"^(润色结果|修改后文本|优化后文本)[:：]\s*", "", cleaned).strip()
    return cleaned


def build_option_requirement_text(strength: str, tone: str, options: list[str]) -> str:
    option_labels = [OPTION_LABELS[item] for item in options if item in OPTION_LABELS]
    option_text = "、".join(option_labels) if option_labels else "保持原意并提升表达质量"
    return "\n".join(
        [
            f"润色强度：{STRENGTH_LABELS.get(strength, strength)}",
            f"语言风格：{TONE_LABELS.get(tone, tone)}",
            f"优化选项：{option_text}",
        ]
    )


def build_template_requirement_text(template_detail: dict[str, Any]) -> str:
    lines = [
        f"模板名称：{template_detail.get('name') or template_detail.get('label') or ''}",
    ]
    system_prompt = str(template_detail.get("systemPrompt") or "").strip()
    terminology = [item for item in template_detail.get("terminology") or [] if str(item).strip()]
    forbidden = [item for item in template_detail.get("forbiddenExpressions") or [] if str(item).strip()]
    if system_prompt:
        lines.append(f"模板提示词：\n{system_prompt}")
    if terminology:
        lines.append("术语要求：" + "、".join(str(item).strip() for item in terminology))
    if forbidden:
        lines.append("禁用写法：" + "、".join(str(item).strip() for item in forbidden))
    return "\n".join(lines)


def build_llm_polish_messages(
    content: str,
    *,
    template_detail: dict[str, Any] | None,
    strength: str,
    tone: str,
    options: list[str],
) -> list[dict[str, str]]:
    base_instruction = (
        "你是专业中文文档润色助手。请在保持原意、事实、数据和结构不被篡改的前提下润色文本。"
        "只输出润色后的正文，不要输出解释、标题、Markdown 代码块或修改说明。"
    )
    if template_detail:
        requirement_text = build_template_requirement_text(template_detail)
    else:
        requirement_text = build_option_requirement_text(strength, tone, options)

    return [
        {"role": "system", "content": base_instruction},
        {
            "role": "user",
            "content": f"请根据以下要求润色原文。\n\n【润色要求】\n{requirement_text}\n\n【原文】\n{content}",
        },
    ]


def run_llm_polish(
    content: str,
    *,
    template_detail: dict[str, Any] | None,
    strength: str,
    tone: str,
    options: list[str],
) -> tuple[str, str, int]:
    started_at = perf_counter()
    response = run_deepseek_chat_completion(
        build_llm_polish_messages(
            content,
            template_detail=template_detail,
            strength=strength,
            tone=tone,
            options=options,
        )
    )
    latency_ms = int((perf_counter() - started_at) * 1000)
    result_text = clean_llm_polish_text(response["content"])
    if not result_text:
        raise ValueError("大模型未返回有效润色结果。")
    return result_text, response["model"], latency_ms


def build_change_summaries(revision_segments: list[dict[str, str]]) -> list[str]:
    added_count = sum(1 for item in revision_segments if item.get("type") == "added")
    deleted_count = sum(1 for item in revision_segments if item.get("type") == "deleted")
    changed_count = added_count + deleted_count
    if changed_count == 0:
        return ["大模型保留了原文主体表达，未检测到明显文本差异。"]
    summaries = [f"检测到 {changed_count} 处文本调整。"]
    if added_count:
        summaries.append(f"新增或改写了 {added_count} 处表达。")
    if deleted_count:
        summaries.append(f"删除或替换了 {deleted_count} 处原文表达。")
    return summaries
    return summaries


def split_polish_paragraphs(content: str) -> list[str]:
    raw_paragraphs = [part.strip() for part in re.split(r"\n\s*\n+", content.strip()) if part.strip()]
    if len(raw_paragraphs) == 1 and len([line for line in content.splitlines() if line.strip()]) > 1:
        raw_paragraphs = [line.strip() for line in content.splitlines() if line.strip()]
    if not raw_paragraphs:
        return []

    merged: list[str] = []
    buffer: list[str] = []
    for paragraph in raw_paragraphs:
        buffer.append(paragraph)
        if count_characters("\n".join(buffer)) >= MIN_POLISH_PARAGRAPH_CHARS:
            merged.append("\n".join(buffer))
            buffer = []

    if buffer:
        if merged and count_characters("\n".join(buffer)) < MIN_POLISH_PARAGRAPH_CHARS:
            merged[-1] = merged[-1] + "\n" + "\n".join(buffer)
        else:
            merged.append("\n".join(buffer))

    segments: list[str] = []
    for paragraph in merged:
        segments.extend(split_long_polish_segment(paragraph))

    return segments


def split_sentences_for_polish_segment(text: str) -> list[str]:
    return [part.strip() for part in re.findall(r"[^。！？；.!?;]+[。！？；.!?;]?|[。！？；.!?;]+", text) if part.strip()]


def split_long_polish_segment(segment: str) -> list[str]:
    if count_characters(segment) <= MAX_POLISH_SEGMENT_CHARS:
        return [segment]

    sentences = split_sentences_for_polish_segment(segment)
    if len(sentences) <= 1:
        return [segment]

    chunks: list[str] = []
    buffer: list[str] = []
    for sentence in sentences:
        if count_characters(sentence) > MAX_POLISH_SEGMENT_CHARS:
            if buffer:
                chunks.append("".join(buffer).strip())
                buffer = []
            chunks.append(sentence)
            continue

        candidate = "".join([*buffer, sentence])
        if buffer and count_characters(candidate) > MAX_POLISH_SEGMENT_CHARS:
            chunks.append("".join(buffer).strip())
            buffer = [sentence]
        else:
            buffer.append(sentence)

    if buffer:
        chunks.append("".join(buffer).strip())

    return [chunk for chunk in chunks if chunk]


def validate_polish_paragraphs(content: str, paragraphs: list[str]) -> None:
    if count_characters(content) > MAX_POLISH_CHARS:
        raise ValueError(f"原文超过 {MAX_POLISH_CHARS} 字上限，请缩短后再润色。")
    if not paragraphs:
        raise ValueError("原文内容不能为空。")
    if len(paragraphs) > MAX_POLISH_PARAGRAPHS:
        raise ValueError(f"分段数量超过 {MAX_POLISH_PARAGRAPHS} 段，请减少空行或前往批量处理。")


def build_summary_messages(content: str) -> list[dict[str, str]]:
    return [
        {
            "role": "system",
            "content": "你是中文文档摘要助手。请提炼全文核心主题、对象、结论和关键约束。",
        },
        {
            "role": "user",
            "content": f"请用不超过 20 字概括以下全文。只输出摘要正文。\n\n【全文】\n{content}",
        },
    ]


def build_segment_polish_messages(
    paragraph: str,
    *,
    full_summary: str,
    template_detail: dict[str, Any] | None,
    strength: str,
    tone: str,
    options: list[str],
) -> list[dict[str, str]]:
    if template_detail:
        requirement_text = build_template_requirement_text(template_detail)
    else:
        requirement_text = build_option_requirement_text(strength, tone, options)

    return [
        {
            "role": "system",
            "content": (
                "你是专业中文文档润色助手。请只润色用户提供的当前段落，保持段落原意、事实、数据和叙述对象不变。"
                "不要改写其他段落，不要输出标题、解释、Markdown 代码块或修改说明。"
            ),
        },
        {
            "role": "user",
            "content": (
                f"请根据全文摘要和润色要求，只润色当前段落。\n\n"
                f"【全文摘要】\n{full_summary}\n\n"
                f"【润色要求】\n{requirement_text}\n\n"
                f"【当前段落】\n{paragraph}"
            ),
        },
    ]


def should_retry_llm_error(error: Exception) -> bool:
    return bool(getattr(error, "retryable", False))


def run_summary_with_retry(content: str) -> dict[str, Any]:
    last_error: Exception | None = None
    messages = build_summary_messages(content)
    for attempt in range(1, POLISH_LLM_MAX_ATTEMPTS + 1):
        try:
            response = run_deepseek_chat_completion(messages, max_tokens=220, temperature=0.1)
            full_summary = clean_llm_polish_text(response["content"])
            if not full_summary:
                raise LLMTemporaryError("DeepSeek returned an empty summary response.")
            return {
                "content": full_summary,
                "model": response["model"],
                "attempts": attempt,
                "retries": attempt - 1,
            }
        except Exception as exc:
            last_error = exc
            if attempt >= POLISH_LLM_MAX_ATTEMPTS or not should_retry_llm_error(exc):
                break
            sleep(POLISH_LLM_RETRY_DELAYS[min(attempt - 1, len(POLISH_LLM_RETRY_DELAYS) - 1)])
    raise RuntimeError(f"全文摘要生成失败：{last_error}") from last_error


def get_polish_llm_concurrency() -> int:
    try:
        configured = int(POLISH_LLM_CONCURRENCY)
    except (TypeError, ValueError):
        configured = MAX_POLISH_LLM_CONCURRENCY
    return min(max(1, configured), MAX_POLISH_LLM_CONCURRENCY)


def run_segment_polish_with_retry(
    index: int,
    paragraph: str,
    *,
    full_summary: str,
    template_detail: dict[str, Any] | None,
    strength: str,
    tone: str,
    options: list[str],
) -> dict[str, Any]:
    messages = build_segment_polish_messages(
        paragraph,
        full_summary=full_summary,
        template_detail=template_detail,
        strength=strength,
        tone=tone,
        options=options,
    )
    last_error: Exception | None = None
    for attempt in range(1, POLISH_LLM_MAX_ATTEMPTS + 1):
        try:
            response = run_deepseek_chat_completion(messages, max_tokens=2000, temperature=0.2)
            result_text = clean_llm_polish_text(response["content"])
            if not result_text:
                raise LLMTemporaryError("DeepSeek returned an empty paragraph polish response.")
            return {
                "index": index,
                "source": paragraph,
                "result": result_text,
                "model": response["model"],
                "attempts": attempt,
                "retries": attempt - 1,
            }
        except Exception as exc:
            last_error = exc
            if attempt >= POLISH_LLM_MAX_ATTEMPTS or not should_retry_llm_error(exc):
                break
            sleep(POLISH_LLM_RETRY_DELAYS[min(attempt - 1, len(POLISH_LLM_RETRY_DELAYS) - 1)])

    paragraph_number = index + 1
    raise RuntimeError(f"第 {paragraph_number} 段润色失败：{last_error}") from last_error


def build_segment_revision_segments(pairs: list[dict[str, Any]]) -> list[dict[str, str]]:
    segments: list[dict[str, str]] = []
    for index, pair in enumerate(pairs):
        if index:
            segments.append({"type": "unchanged", "text": "\n\n"})
        segments.extend(build_revision_segments(pair["source"], pair["result"]))
    return merge_revision_segments(segments)


def build_segment_change_summaries(revision_segments: list[dict[str, str]], pairs: list[dict[str, Any]]) -> list[str]:
    changed_paragraphs = 0
    for pair in pairs:
        paragraph_segments = build_revision_segments(pair["source"], pair["result"])
        if any(item.get("type") in {"added", "deleted"} for item in paragraph_segments):
            changed_paragraphs += 1

    summaries = build_change_summaries(revision_segments)
    summaries.insert(0, f"按 {len(pairs)} 个段落分别润色，{changed_paragraphs} 个段落检测到文本调整。")
    return summaries
    return summaries


def run_segmented_llm_polish(
    content: str,
    *,
    template_detail: dict[str, Any] | None,
    strength: str,
    tone: str,
    options: list[str],
) -> dict[str, Any]:
    started_at = perf_counter()
    paragraphs = split_polish_paragraphs(content)
    validate_polish_paragraphs(content, paragraphs)

    summary_response = run_summary_with_retry(content)
    full_summary = summary_response["content"]

    results: list[dict[str, Any] | None] = [None] * len(paragraphs)
    concurrency = get_polish_llm_concurrency()
    with ThreadPoolExecutor(max_workers=concurrency) as executor:
        futures = [
            executor.submit(
                run_segment_polish_with_retry,
                index,
                paragraph,
                full_summary=full_summary,
                template_detail=template_detail,
                strength=strength,
                tone=tone,
                options=options,
            )
            for index, paragraph in enumerate(paragraphs)
        ]
        for future in as_completed(futures):
            item = future.result()
            results[item["index"]] = item

    pairs = [item for item in results if item is not None]
    result_text = "\n\n".join(item["result"] for item in pairs)
    revision_segments = build_segment_revision_segments(pairs)
    retry_count = sum(int(item.get("retries") or 0) for item in pairs)
    model_name = next((str(item.get("model") or "") for item in pairs if item.get("model")), summary_response["model"])
    latency_ms = int((perf_counter() - started_at) * 1000)

    return {
        "resultText": result_text,
        "revisionSegments": revision_segments,
        "changes": build_segment_change_summaries(revision_segments, pairs),
        "model": model_name,
        "latencyMs": latency_ms,
        "fullSummary": full_summary,
        "paragraphCount": len(pairs),
        "concurrency": concurrency,
        "retryCount": retry_count,
        "failedParagraphInfo": "",
    }


def create_polish_record(payload: dict[str, Any], user_id: int | None = None) -> dict[str, Any]:
    content = (payload.get("content") or "").strip()
    if not content:
        raise ValueError("原文内容不能为空。")

    template = str(payload.get("template") or "").strip()
    strength = payload.get("strength") or "medium"
    tone = payload.get("tone") or "formal"
    options = [item for item in (payload.get("options") or []) if item in OPTION_LABELS]
    document_id = payload.get("documentId")
    title = (payload.get("title") or "").strip() or build_auto_title(content)
    description = (payload.get("description") or "").strip()

    template_by_key, _ = get_template_maps(user_id, include_disabled=False)
    template_detail = template_by_key.get(template) if template else None
    if template and template_detail is None:
        raise ValueError("润色模板不存在。")
    if strength not in STRENGTH_LABELS:
        raise ValueError("润色强度不存在。")
    if tone not in TONE_LABELS:
        raise ValueError("语言风格不存在。")

    polish_result = run_segmented_llm_polish(
        content,
        template_detail=template_detail,
        strength=strength,
        tone=tone,
        options=options,
    )
    result_text = polish_result["resultText"]
    revision_segments = polish_result["revisionSegments"]
    changes = polish_result["changes"]
    summary = build_summary_text(result_text)
    quality_score = run_llm_quality_score(
        content,
        result_text,
        template_detail=template_detail,
        strength=strength,
        tone=tone,
        options=options,
    )
    timestamp = now_string()

    record = {
        "id": f"record-{uuid4().hex[:10]}",
        "documentId": document_id,
        "title": title,
        "description": description,
        "category": get_template_category(template, user_id) if template else "通用润色",
        "fileType": "Word",
        "sourceText": content,
        "resultText": result_text,
        "template": template,
        "templateLabel": template_detail["name"] if template_detail else "未选择模板",
        "strength": strength,
        "strengthLabel": STRENGTH_LABELS[strength],
        "tone": tone,
        "toneLabel": TONE_LABELS[tone],
        "options": options,
        "optionLabels": [OPTION_LABELS[item] for item in options if item in OPTION_LABELS],
        "status": "completed",
        "hasResult": True,
        "score": quality_score["score"],
        "dimensions": quality_score["dimensions"],
        "suggestions": quality_score["suggestions"],
        "changes": changes,
        "summary": summary,
        "compareSections": build_compare_sections(content, result_text),
        "revisionSegments": revision_segments,
        "llmModel": polish_result["model"],
        "scoringModel": quality_score["model"],
        "scoringLatencyMs": quality_score["latencyMs"],
        "scoringJson": quality_score["scoringJson"],
        "usedTemplate": bool(template_detail),
        "llmLatencyMs": polish_result["latencyMs"],
        "fullSummary": polish_result["fullSummary"],
        "paragraphCount": polish_result["paragraphCount"],
        "llmConcurrency": polish_result["concurrency"],
        "llmRetryCount": polish_result["retryCount"],
        "failedParagraphInfo": polish_result["failedParagraphInfo"],
        "wordCount": {
            "source": count_characters(content),
            "result": count_characters(result_text),
            "delta": count_characters(result_text) - count_characters(content),
        },
        "createdAt": timestamp,
    }
    return record


def generate_summary(payload: dict[str, Any]) -> dict[str, str]:
    text = (payload.get("text") or "").strip()
    if not text:
        raise ValueError("摘要内容不能为空。")
    return {"summary": build_summary_text(text)}
