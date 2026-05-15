from __future__ import annotations

import base64
import hashlib
import hmac
import json
import os
import re
import secrets
from difflib import SequenceMatcher
from datetime import datetime, timedelta
from pathlib import Path
from typing import Any
from uuid import uuid4

from .config import MySQLSettings, get_mysql_settings

SEED_USAGE_WORD_COUNTS = [1240, 1680, 945, 1530, 2110, 890, 1765, 1420, 1988, 1324, 1860, 1980]
AUTH_TOKEN_TTL_SECONDS = 7 * 24 * 60 * 60
POLISH_RECORD_STRENGTH_LABELS = {"light": "轻度", "medium": "中度", "deep": "深度"}
POLISH_RECORD_TONE_LABELS = {
    "formal": "正式",
    "professional": "专业",
    "concise": "简洁",
    "fluent": "流畅",
    "friendly": "亲和",
}
POLISH_RECORD_OPTION_LABELS = {
    "wording": "优化措辞与语法",
    "clarity": "提升表达清晰度",
    "logic": "增强逻辑连贯性",
    "sentence": "调整句式结构",
}
POLISH_RECORD_CATEGORY_BY_TEMPLATE = {
    "general": "通用文稿",
    "academic": "学术论文",
    "resume": "简历文稿",
    "business": "商务报告",
    "official": "公文材料",
    "rewrite": "改写文本",
    "summary": "摘要文稿",
}
SEED_NOTIFICATIONS = [
    {
        "id": "notice-db-001",
        "title": "系统升级通知：顶部栏消息已接入数据库",
        "summary": "消息列表、未读状态和详情内容现在都由 MySQL 统一提供。",
        "content": "顶部栏消息通知已完成数据库联调。刷新页面后，消息数量、未读角标和详情内容都会从后端数据库读取，适合继续演示真实持久化流程。",
        "isRead": False,
    },
    {
        "id": "notice-db-002",
        "title": "润色任务提醒：今日已有多次处理记录",
        "summary": "侧边栏今日使用情况已根据数据库统计实时更新。",
        "content": "系统会记录每次成功润色后的处理字数，并在侧边栏同步今日次数和本周处理字数，帮助你观察当前账号的使用情况。",
        "isRead": False,
    },
    {
        "id": "notice-db-003",
        "title": "模板建议：学术论文润色模板适合长文档",
        "summary": "当原文偏正式或研究型内容较多时，建议优先选择学术论文润色。",
        "content": "学术论文润色模板会更强调表述规范、逻辑层次和术语一致性，适合论文、课题报告、研究综述等文档。",
        "isRead": False,
    },
    {
        "id": "notice-db-004",
        "title": "批量处理提示：上传后可按状态筛选",
        "summary": "文档管理页支持按处理状态查看批量任务。",
        "content": "批量处理列表中可以区分已完成、待确认和未润色文档，方便快速定位需要继续处理的材料。",
        "isRead": False,
    },
    {
        "id": "notice-db-005",
        "title": "功能提示：润色记录支持查看详情",
        "summary": "历史记录中可查看原文、润色结果、评分和修改片段。",
        "content": "打开润色记录详情后，可以对比原文与润色结果，查看系统给出的评分维度、优化建议和修订片段。",
        "isRead": False,
    },
    {
        "id": "notice-db-006",
        "title": "账号提醒：建议完善个人资料",
        "summary": "设置中心可维护用户名、邮箱和消息偏好。",
        "content": "完善个人资料后，后续可以更自然地扩展账号体系、消息订阅和个性化推荐能力。",
        "isRead": True,
    },
    {
        "id": "notice-db-007",
        "title": "数据统计更新：图表支持时间范围筛选",
        "summary": "统计页可按日期和粒度查看处理趋势。",
        "content": "你可以在数据统计页调整时间范围和统计粒度，查看文档处理量、活跃用户趋势和模板使用情况。",
        "isRead": True,
    },
    {
        "id": "notice-db-008",
        "title": "演示数据已准备：通知数量超过十条",
        "summary": "数据库初始化会自动补齐消息通知，便于抽屉列表展示。",
        "content": "当 notifications 表不足十二条时，系统会补充演示通知；已有通知不会被覆盖，已读状态也会保留。",
        "isRead": True,
    },
    {
        "id": "notice-db-009",
        "title": "使用建议：先创建文档再发起润色",
        "summary": "带文档 ID 的润色记录更便于后续追踪。",
        "content": "在智能润色页中先保存文档，再基于文档发起润色，可以让历史记录和文档管理之间的关联更完整。",
        "isRead": False,
    },
    {
        "id": "notice-db-010",
        "title": "系统公告：后端健康检查包含数据库状态",
        "summary": "访问健康检查接口可以确认 MySQL 是否连接正常。",
        "content": "健康检查接口会返回数据库名称、连接状态和错误信息，便于排查本地环境配置问题。",
        "isRead": True,
    },
    {
        "id": "notice-db-011",
        "title": "流程提醒：未读消息打开详情后自动标记已读",
        "summary": "顶部栏角标会跟随数据库未读状态变化。",
        "content": "当你打开未读消息详情时，前端会调用标记已读 API，后端更新数据库后返回最新通知对象。",
        "isRead": False,
    },
    {
        "id": "notice-db-012",
        "title": "开发提示：通知 API 路径保持不变",
        "summary": "前端无需调整调用路径，即可切换到数据库数据源。",
        "content": "GET /api/notifications 和 PATCH /api/notifications/{id}/read 已保持原有接口形状，降低前端联调成本。",
        "isRead": True,
    },
]

BASE_DIR = Path(__file__).resolve().parent.parent
STORAGE_DIR = BASE_DIR / "storage"
UPLOADS_DIR = STORAGE_DIR / "uploads"
BATCH_UPLOADS_DIR = UPLOADS_DIR / "batch"
DEMO_ACCOUNT_PASSWORD = "Demo@2026"
DEMO_ACCOUNT_SPECS = [
    {
        "username": "demo_presenter",
        "password": DEMO_ACCOUNT_PASSWORD,
        "displayName": "演示专员",
        "email": "demo.presenter@example.com",
        "avatarText": "演",
        "profile": "企业演示",
        "polishSeedCount": 24,
        "batchSeedCount": 14,
        "topicPrefix": "演示方案",
    },
    {
        "username": "demo_editor_01",
        "password": DEMO_ACCOUNT_PASSWORD,
        "displayName": "内容编辑林岚",
        "email": "demo.editor@example.com",
        "avatarText": "林",
        "profile": "内容编辑",
        "polishSeedCount": 18,
        "batchSeedCount": 0,
        "topicPrefix": "内容稿件",
    },
    {
        "username": "demo_product_01",
        "password": DEMO_ACCOUNT_PASSWORD,
        "displayName": "产品经理周衡",
        "email": "demo.product@example.com",
        "avatarText": "周",
        "profile": "产品方案",
        "polishSeedCount": 16,
        "batchSeedCount": 9,
        "topicPrefix": "产品文档",
    },
    {
        "username": "demo_research_01",
        "password": DEMO_ACCOUNT_PASSWORD,
        "displayName": "研究助理顾遥",
        "email": "demo.research@example.com",
        "avatarText": "顾",
        "profile": "研究分析",
        "polishSeedCount": 17,
        "batchSeedCount": 8,
        "topicPrefix": "研究材料",
    },
]
DEMO_STRENGTH_SEQUENCE = ["light", "medium", "deep"]
DEMO_TONE_SEQUENCE = ["formal", "professional", "concise", "fluent", "friendly"]
DEMO_OPTION_SEQUENCE = [
    ["wording", "clarity"],
    ["clarity", "logic"],
    ["wording", "sentence"],
    ["logic", "sentence"],
]
DEMO_POLISH_CATEGORIES = [
    "周报汇总",
    "项目方案",
    "会议纪要",
    "课程论文",
    "商务邮件",
    "岗位材料",
]
DEMO_BATCH_CATEGORIES = [
    "项目资料",
    "汇报材料",
    "周度纪要",
    "研究摘要",
    "通知文稿",
]
DEMO_BATCH_ACTIVITY_LABELS = {
    "upload": "批量导入",
    "template": "选择模板",
    "completed": "完成润色",
    "confirm": "批量确认",
    "export": "导出结果",
}
DEFAULT_NOTIFICATION_SETTING_TYPES = [
    {
        "key": "polish-completed",
        "title": "润色完成通知",
        "description": "文档润色完成时通知我",
        "icon": "✓",
        "emailEnabled": False,
    },
    {
        "key": "batch-completed",
        "title": "批量任务完成通知",
        "description": "批量润色任务完成时通知我",
        "icon": "≋",
        "emailEnabled": True,
    },
    {
        "key": "system-announcement",
        "title": "系统公告通知",
        "description": "系统公告、重要消息通知",
        "icon": "!",
        "emailEnabled": False,
    },
    {
        "key": "template-updated",
        "title": "模板更新通知",
        "description": "润色模板更新时通知我",
        "icon": "◇",
        "emailEnabled": True,
    },
    {
        "key": "promotion",
        "title": "优惠活动通知",
        "description": "优惠活动、福利信息通知",
        "icon": "□",
        "emailEnabled": True,
    },
]


def mask_database_error(error: Exception) -> str:
    message = str(error)
    try:
        settings = get_mysql_settings()
    except Exception:
        return message
    if settings.password:
        message = message.replace(settings.password, "******")
    return message


def load_notification_setting_seed_rows() -> list[dict[str, Any]]:
    return [
        {
            **item,
            "sortOrder": index,
        }
        for index, item in enumerate(DEFAULT_NOTIFICATION_SETTING_TYPES)
    ]


def quote_identifier(identifier: str) -> str:
    return f"`{identifier.replace('`', '``')}`"


def get_server_connection_kwargs(settings: MySQLSettings) -> dict[str, Any]:
    return {
        "host": settings.host,
        "port": settings.port,
        "user": settings.user,
        "password": settings.password,
        "charset": "utf8mb4",
        "connect_timeout": 3,
        "read_timeout": 3,
        "write_timeout": 3,
        "autocommit": True,
    }


def get_database_connection_kwargs(settings: MySQLSettings) -> dict[str, Any]:
    return {
        **get_server_connection_kwargs(settings),
        "database": settings.database,
    }


def ensure_mysql_database(settings: MySQLSettings | None = None) -> None:
    settings = settings or get_mysql_settings()

    import pymysql

    connection = pymysql.connect(**get_server_connection_kwargs(settings))
    try:
        with connection.cursor() as cursor:
            cursor.execute(
                f"CREATE DATABASE IF NOT EXISTS {quote_identifier(settings.database)} "
                "CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci"
            )
    finally:
        connection.close()


def load_table_indexes(cursor: Any, table_name: str) -> dict[str, list[str]]:
    cursor.execute(f"SHOW INDEX FROM {quote_identifier(table_name)}")
    indexes: dict[str, list[tuple[int, str]]] = {}
    for row in cursor.fetchall():
        key_name = str(row[2] or "")
        sequence = int(row[3] or 0)
        column_name = str(row[4] or "")
        indexes.setdefault(key_name, []).append((sequence, column_name))
    return {
        key_name: [column_name for _, column_name in sorted(columns, key=lambda item: item[0])]
        for key_name, columns in indexes.items()
    }


def add_index_if_missing(cursor: Any, table_name: str, index_name: str, alter_sql: str) -> dict[str, list[str]]:
    indexes = load_table_indexes(cursor, table_name)
    if index_name in indexes:
        return indexes

    try:
        cursor.execute(alter_sql)
    except Exception as exc:
        if getattr(exc, "args", [None])[0] != 1061:
            raise
        indexes = load_table_indexes(cursor, table_name)
        if index_name not in indexes:
            raise
        return indexes

    return load_table_indexes(cursor, table_name)


def drop_index_if_exists(cursor: Any, table_name: str, index_name: str) -> dict[str, list[str]]:
    indexes = load_table_indexes(cursor, table_name)
    if index_name not in indexes:
        return indexes

    try:
        cursor.execute(f"ALTER TABLE {quote_identifier(table_name)} DROP INDEX {quote_identifier(index_name)}")
    except Exception as exc:
        if getattr(exc, "args", [None])[0] != 1091:
            raise
    return load_table_indexes(cursor, table_name)


def load_index_rows(cursor: Any, table_name: str, index_name: str) -> list[tuple[Any, ...]]:
    cursor.execute(
        f"SHOW INDEX FROM {quote_identifier(table_name)} WHERE Key_name = %s",
        (index_name,),
    )
    return list(cursor.fetchall())


def ensure_mysql_schema(settings: MySQLSettings | None = None) -> None:
    settings = settings or get_mysql_settings()

    import pymysql

    ensure_mysql_database(settings)
    connection = pymysql.connect(**get_database_connection_kwargs(settings))
    try:
        with connection.cursor() as cursor:
            cursor.execute(
                """
                CREATE TABLE IF NOT EXISTS usage_events (
                    id BIGINT UNSIGNED NOT NULL AUTO_INCREMENT,
                    user_id BIGINT UNSIGNED NULL,
                    event_type VARCHAR(32) NOT NULL DEFAULT 'polish',
                    word_count INT UNSIGNED NOT NULL DEFAULT 0,
                    score DECIMAL(5,2) NULL,
                    event_source VARCHAR(64) NULL,
                    created_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
                    PRIMARY KEY (id),
                    KEY idx_usage_events_created_at (created_at),
                    KEY idx_usage_events_type_created_at (event_type, created_at),
                    KEY idx_usage_events_user_type_created_at (user_id, event_type, created_at)
                ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci
                """
            )
            cursor.execute("SHOW COLUMNS FROM usage_events LIKE 'user_id'")
            if cursor.fetchone() is None:
                cursor.execute("ALTER TABLE usage_events ADD COLUMN user_id BIGINT UNSIGNED NULL AFTER id")
            cursor.execute("SHOW COLUMNS FROM usage_events LIKE 'score'")
            if cursor.fetchone() is None:
                cursor.execute("ALTER TABLE usage_events ADD COLUMN score DECIMAL(5,2) NULL AFTER word_count")
            cursor.execute("SHOW COLUMNS FROM usage_events LIKE 'event_source'")
            if cursor.fetchone() is None:
                cursor.execute("ALTER TABLE usage_events ADD COLUMN event_source VARCHAR(64) NULL AFTER score")
            cursor.execute("SHOW INDEX FROM usage_events WHERE Key_name = 'idx_usage_events_user_type_created_at'")
            if cursor.fetchone() is None:
                cursor.execute(
                    "ALTER TABLE usage_events ADD KEY idx_usage_events_user_type_created_at "
                    "(user_id, event_type, created_at)"
                )
            cursor.execute(
                """
                CREATE TABLE IF NOT EXISTS notifications (
                    id VARCHAR(64) NOT NULL,
                    title VARCHAR(255) NOT NULL,
                    summary VARCHAR(512) NOT NULL DEFAULT '',
                    content TEXT NOT NULL,
                    is_read TINYINT(1) NOT NULL DEFAULT 0,
                    created_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
                    updated_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
                    PRIMARY KEY (id),
                    KEY idx_notifications_read_created_at (is_read, created_at)
                ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci
                """
            )
            cursor.execute(
                """
                CREATE TABLE IF NOT EXISTS users (
                    id BIGINT UNSIGNED NOT NULL AUTO_INCREMENT,
                    username VARCHAR(80) NOT NULL,
                    email VARCHAR(120) NULL,
                    password_hash VARCHAR(128) NOT NULL,
                    password_salt VARCHAR(64) NOT NULL,
                    display_name VARCHAR(80) NOT NULL,
                    avatar_text VARCHAR(8) NOT NULL DEFAULT '',
                    created_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
                    last_login_at DATETIME NULL,
                    updated_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
                    PRIMARY KEY (id),
                    UNIQUE KEY idx_users_username (username),
                    KEY idx_users_email (email)
                ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci
                """
            )
            cursor.execute("SHOW COLUMNS FROM users LIKE 'email'")
            if cursor.fetchone() is None:
                cursor.execute("ALTER TABLE users ADD COLUMN email VARCHAR(120) NULL AFTER username")
            cursor.execute("SHOW COLUMNS FROM users LIKE 'last_login_at'")
            if cursor.fetchone() is None:
                cursor.execute("ALTER TABLE users ADD COLUMN last_login_at DATETIME NULL AFTER created_at")
            email_index_rows = load_index_rows(cursor, "users", "idx_users_email")
            email_index_is_unique = any(int(row[1] or 0) == 0 for row in email_index_rows)
            if email_index_is_unique:
                drop_index_if_exists(cursor, "users", "idx_users_email")
                add_index_if_missing(
                    cursor,
                    "users",
                    "idx_users_email",
                    "ALTER TABLE users ADD KEY idx_users_email (email)",
                )
            elif not email_index_rows:
                add_index_if_missing(
                    cursor,
                    "users",
                    "idx_users_email",
                    "ALTER TABLE users ADD KEY idx_users_email (email)",
                )
            cursor.execute(
                """
                CREATE TABLE IF NOT EXISTS polish_templates (
                    id BIGINT UNSIGNED NOT NULL AUTO_INCREMENT,
                    user_id BIGINT UNSIGNED NULL,
                    template_id VARCHAR(64) NOT NULL,
                    template_key VARCHAR(80) NOT NULL,
                    name VARCHAR(120) NOT NULL,
                    description VARCHAR(512) NOT NULL DEFAULT '',
                    icon VARCHAR(16) NOT NULL DEFAULT '',
                    tone VARCHAR(64) NOT NULL DEFAULT 'icon-blue',
                    enabled TINYINT(1) NOT NULL DEFAULT 1,
                    is_deleted TINYINT(1) NOT NULL DEFAULT 0,
                    user_modified TINYINT(1) NOT NULL DEFAULT 0,
                    usage_count INT UNSIGNED NOT NULL DEFAULT 0,
                    average_score DECIMAL(5,2) NOT NULL DEFAULT 0,
                    updated_at DATE NULL,
                    system_prompt TEXT NULL,
                    terminology_json TEXT NULL,
                    forbidden_expressions_json TEXT NULL,
                    PRIMARY KEY (id),
                    UNIQUE KEY idx_polish_templates_user_template_id (user_id, template_id),
                    UNIQUE KEY idx_polish_templates_user_template_key (user_id, template_key),
                    KEY idx_polish_templates_common (user_id, is_deleted, enabled, usage_count, updated_at),
                    CONSTRAINT fk_polish_templates_user
                        FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE
                ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci
                """
            )
            cursor.execute("SHOW COLUMNS FROM polish_templates LIKE 'user_id'")
            if cursor.fetchone() is None:
                cursor.execute("ALTER TABLE polish_templates ADD COLUMN user_id BIGINT UNSIGNED NULL AFTER id")
            cursor.execute("SHOW COLUMNS FROM polish_templates LIKE 'system_prompt'")
            if cursor.fetchone() is None:
                cursor.execute("ALTER TABLE polish_templates ADD COLUMN system_prompt TEXT NULL AFTER updated_at")
            cursor.execute("SHOW COLUMNS FROM polish_templates LIKE 'terminology_json'")
            if cursor.fetchone() is None:
                cursor.execute("ALTER TABLE polish_templates ADD COLUMN terminology_json TEXT NULL AFTER system_prompt")
            cursor.execute("SHOW COLUMNS FROM polish_templates LIKE 'forbidden_expressions_json'")
            if cursor.fetchone() is None:
                cursor.execute(
                    "ALTER TABLE polish_templates ADD COLUMN forbidden_expressions_json TEXT NULL AFTER terminology_json"
                )
            cursor.execute("SHOW COLUMNS FROM polish_templates LIKE 'user_modified'")
            if cursor.fetchone() is None:
                cursor.execute(
                    "ALTER TABLE polish_templates ADD COLUMN user_modified TINYINT(1) NOT NULL DEFAULT 0 AFTER enabled"
                )
            cursor.execute("SHOW COLUMNS FROM polish_templates LIKE 'is_deleted'")
            if cursor.fetchone() is None:
                cursor.execute(
                    "ALTER TABLE polish_templates ADD COLUMN is_deleted TINYINT(1) NOT NULL DEFAULT 0 AFTER enabled"
                )
            polish_template_indexes = load_table_indexes(cursor, "polish_templates")
            if "idx_polish_templates_template_id" in polish_template_indexes:
                polish_template_indexes = drop_index_if_exists(
                    cursor,
                    "polish_templates",
                    "idx_polish_templates_template_id",
                )
            if "idx_polish_templates_template_key" in polish_template_indexes:
                polish_template_indexes = drop_index_if_exists(
                    cursor,
                    "polish_templates",
                    "idx_polish_templates_template_key",
                )
            expected_common_index = ["user_id", "is_deleted", "enabled", "usage_count", "updated_at"]
            if (
                "idx_polish_templates_common" in polish_template_indexes
                and polish_template_indexes["idx_polish_templates_common"] != expected_common_index
            ):
                polish_template_indexes = drop_index_if_exists(
                    cursor,
                    "polish_templates",
                    "idx_polish_templates_common",
                )
            polish_template_indexes = add_index_if_missing(
                cursor,
                "polish_templates",
                "idx_polish_templates_user_template_id",
                "ALTER TABLE polish_templates ADD UNIQUE KEY idx_polish_templates_user_template_id "
                "(user_id, template_id)",
            )
            polish_template_indexes = add_index_if_missing(
                cursor,
                "polish_templates",
                "idx_polish_templates_user_template_key",
                "ALTER TABLE polish_templates ADD UNIQUE KEY idx_polish_templates_user_template_key "
                "(user_id, template_key)",
            )
            if "idx_polish_templates_common" not in polish_template_indexes:
                polish_template_indexes = add_index_if_missing(
                    cursor,
                    "polish_templates",
                    "idx_polish_templates_common",
                    "ALTER TABLE polish_templates ADD KEY idx_polish_templates_common "
                    "(user_id, is_deleted, enabled, usage_count, updated_at)",
                )
            cursor.execute(
                """
                SELECT 1
                FROM information_schema.TABLE_CONSTRAINTS
                WHERE CONSTRAINT_SCHEMA = DATABASE()
                  AND TABLE_NAME = 'polish_templates'
                  AND CONSTRAINT_NAME = 'fk_polish_templates_user'
                LIMIT 1
                """
            )
            if cursor.fetchone() is None:
                cursor.execute(
                    "ALTER TABLE polish_templates ADD CONSTRAINT fk_polish_templates_user "
                    "FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE"
                )
            cursor.execute(
                """
                CREATE TABLE IF NOT EXISTS polish_records (
                    id BIGINT UNSIGNED NOT NULL AUTO_INCREMENT,
                    user_id BIGINT UNSIGNED NOT NULL,
                    record_id VARCHAR(64) NOT NULL,
                    document_id VARCHAR(64) NOT NULL DEFAULT '',
                    title VARCHAR(255) NOT NULL DEFAULT '',
                    source_text TEXT NOT NULL,
                    result_text TEXT NOT NULL,
                    template_label VARCHAR(120) NOT NULL DEFAULT '',
                    score DECIMAL(5,2) NULL,
                    word_count INT UNSIGNED NOT NULL DEFAULT 0,
                    created_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
                    template_key VARCHAR(80) NOT NULL DEFAULT '',
                    strength_key VARCHAR(32) NOT NULL DEFAULT '',
                    tone_key VARCHAR(32) NOT NULL DEFAULT '',
                    options_json TEXT NULL,
                    model_name VARCHAR(120) NOT NULL DEFAULT '',
                    used_template TINYINT(1) NOT NULL DEFAULT 0,
                    llm_latency_ms INT UNSIGNED NOT NULL DEFAULT 0,
                    revision_segments_json MEDIUMTEXT NULL,
                    changes_json TEXT NULL,
                    full_summary TEXT NULL,
                    paragraph_count INT UNSIGNED NOT NULL DEFAULT 0,
                    llm_concurrency INT UNSIGNED NOT NULL DEFAULT 0,
                    llm_retry_count INT UNSIGNED NOT NULL DEFAULT 0,
                    failed_paragraph_info TEXT NULL,
                    total_latency_ms INT UNSIGNED NOT NULL DEFAULT 0,
                    scoring_json MEDIUMTEXT NULL,
                    scoring_model_name VARCHAR(120) NOT NULL DEFAULT '',
                    scoring_latency_ms INT UNSIGNED NOT NULL DEFAULT 0,
                    PRIMARY KEY (id),
                    UNIQUE KEY idx_polish_records_user_record (user_id, record_id),
                    KEY idx_polish_records_user_created_at (user_id, created_at),
                    CONSTRAINT fk_polish_records_user
                        FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE
                ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci
                """
            )
            polish_record_columns = {
                "document_id": "ALTER TABLE polish_records ADD COLUMN document_id VARCHAR(64) NOT NULL DEFAULT '' AFTER record_id",
                "title": "ALTER TABLE polish_records ADD COLUMN title VARCHAR(255) NOT NULL DEFAULT '' AFTER document_id",
                "template_key": "ALTER TABLE polish_records ADD COLUMN template_key VARCHAR(80) NOT NULL DEFAULT '' AFTER created_at",
                "strength_key": "ALTER TABLE polish_records ADD COLUMN strength_key VARCHAR(32) NOT NULL DEFAULT '' AFTER template_key",
                "tone_key": "ALTER TABLE polish_records ADD COLUMN tone_key VARCHAR(32) NOT NULL DEFAULT '' AFTER strength_key",
                "options_json": "ALTER TABLE polish_records ADD COLUMN options_json TEXT NULL AFTER tone_key",
                "model_name": "ALTER TABLE polish_records ADD COLUMN model_name VARCHAR(120) NOT NULL DEFAULT '' AFTER options_json",
                "used_template": "ALTER TABLE polish_records ADD COLUMN used_template TINYINT(1) NOT NULL DEFAULT 0 AFTER model_name",
                "llm_latency_ms": "ALTER TABLE polish_records ADD COLUMN llm_latency_ms INT UNSIGNED NOT NULL DEFAULT 0 AFTER used_template",
                "revision_segments_json": "ALTER TABLE polish_records ADD COLUMN revision_segments_json MEDIUMTEXT NULL AFTER llm_latency_ms",
                "changes_json": "ALTER TABLE polish_records ADD COLUMN changes_json TEXT NULL AFTER revision_segments_json",
                "full_summary": "ALTER TABLE polish_records ADD COLUMN full_summary TEXT NULL AFTER changes_json",
                "paragraph_count": "ALTER TABLE polish_records ADD COLUMN paragraph_count INT UNSIGNED NOT NULL DEFAULT 0 AFTER full_summary",
                "llm_concurrency": "ALTER TABLE polish_records ADD COLUMN llm_concurrency INT UNSIGNED NOT NULL DEFAULT 0 AFTER paragraph_count",
                "llm_retry_count": "ALTER TABLE polish_records ADD COLUMN llm_retry_count INT UNSIGNED NOT NULL DEFAULT 0 AFTER llm_concurrency",
                "failed_paragraph_info": "ALTER TABLE polish_records ADD COLUMN failed_paragraph_info TEXT NULL AFTER llm_retry_count",
                "total_latency_ms": "ALTER TABLE polish_records ADD COLUMN total_latency_ms INT UNSIGNED NOT NULL DEFAULT 0 AFTER failed_paragraph_info",
                "scoring_json": "ALTER TABLE polish_records ADD COLUMN scoring_json MEDIUMTEXT NULL AFTER total_latency_ms",
                "scoring_model_name": "ALTER TABLE polish_records ADD COLUMN scoring_model_name VARCHAR(120) NOT NULL DEFAULT '' AFTER scoring_json",
                "scoring_latency_ms": "ALTER TABLE polish_records ADD COLUMN scoring_latency_ms INT UNSIGNED NOT NULL DEFAULT 0 AFTER scoring_model_name",
            }
            for column_name, alter_sql in polish_record_columns.items():
                cursor.execute(f"SHOW COLUMNS FROM polish_records LIKE '{column_name}'")
                if cursor.fetchone() is None:
                    cursor.execute(alter_sql)
            add_index_if_missing(
                cursor,
                "polish_records",
                "idx_polish_records_user_template_doc",
                "ALTER TABLE polish_records ADD KEY idx_polish_records_user_template_doc "
                "(user_id, template_key, document_id)",
            )
            cursor.execute(
                """
                CREATE TABLE IF NOT EXISTS batch_documents (
                    id BIGINT UNSIGNED NOT NULL AUTO_INCREMENT,
                    user_id BIGINT UNSIGNED NOT NULL,
                    document_id VARCHAR(64) NOT NULL,
                    title VARCHAR(255) NOT NULL DEFAULT '',
                    category VARCHAR(120) NOT NULL DEFAULT '',
                    file_type VARCHAR(32) NOT NULL DEFAULT '',
                    template_type VARCHAR(120) NOT NULL DEFAULT '',
                    word_count INT UNSIGNED NOT NULL DEFAULT 0,
                    processed_word_count INT UNSIGNED NOT NULL DEFAULT 0,
                    score DECIMAL(5,2) NULL,
                    status VARCHAR(32) NOT NULL DEFAULT 'unprocessed',
                    original_filename VARCHAR(255) NOT NULL DEFAULT '',
                    storage_path VARCHAR(500) NOT NULL DEFAULT '',
                    result_file_path VARCHAR(500) NOT NULL DEFAULT '',
                    result_detail_path VARCHAR(500) NOT NULL DEFAULT '',
                    result_text MEDIUMTEXT NULL,
                    has_result TINYINT(1) NOT NULL DEFAULT 0,
                    processed_at DATETIME NULL,
                    confirmed_at DATETIME NULL,
                    created_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
                    updated_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
                    PRIMARY KEY (id),
                    UNIQUE KEY idx_batch_documents_user_document (user_id, document_id),
                    KEY idx_batch_documents_user_updated_at (user_id, updated_at),
                    KEY idx_batch_documents_user_processed_at (user_id, processed_at),
                    KEY idx_batch_documents_user_status (user_id, status),
                    CONSTRAINT fk_batch_documents_user
                        FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE
                ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci
                """
            )
            batch_document_columns = {
                "result_file_path": (
                    "ALTER TABLE batch_documents "
                    "ADD COLUMN result_file_path VARCHAR(500) NOT NULL DEFAULT '' AFTER storage_path"
                ),
                "result_detail_path": (
                    "ALTER TABLE batch_documents "
                    "ADD COLUMN result_detail_path VARCHAR(500) NOT NULL DEFAULT '' AFTER result_file_path"
                ),
                "processed_word_count": (
                    "ALTER TABLE batch_documents "
                    "ADD COLUMN processed_word_count INT UNSIGNED NOT NULL DEFAULT 0 AFTER word_count"
                ),
                "confirmed_at": (
                    "ALTER TABLE batch_documents "
                    "ADD COLUMN confirmed_at DATETIME NULL AFTER has_result"
                ),
                "processed_at": (
                    "ALTER TABLE batch_documents "
                    "ADD COLUMN processed_at DATETIME NULL AFTER has_result"
                ),
                "score": (
                    "ALTER TABLE batch_documents "
                    "ADD COLUMN score DECIMAL(5,2) NULL AFTER processed_word_count"
                ),
            }
            for column_name, alter_sql in batch_document_columns.items():
                cursor.execute(f"SHOW COLUMNS FROM batch_documents LIKE '{column_name}'")
                if cursor.fetchone() is None:
                    cursor.execute(alter_sql)
            add_index_if_missing(
                cursor,
                "batch_documents",
                "idx_batch_documents_user_processed_at",
                "ALTER TABLE batch_documents ADD KEY idx_batch_documents_user_processed_at (user_id, processed_at)",
            )
            cursor.execute(
                """
                CREATE TABLE IF NOT EXISTS batch_activities (
                    id BIGINT UNSIGNED NOT NULL AUTO_INCREMENT,
                    user_id BIGINT UNSIGNED NOT NULL,
                    activity_id VARCHAR(64) NOT NULL,
                    type VARCHAR(32) NOT NULL DEFAULT '',
                    title VARCHAR(255) NOT NULL DEFAULT '',
                    detail TEXT NULL,
                    created_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
                    PRIMARY KEY (id),
                    UNIQUE KEY idx_batch_activities_user_activity (user_id, activity_id),
                    KEY idx_batch_activities_user_created_at (user_id, created_at),
                    CONSTRAINT fk_batch_activities_user
                        FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE
                ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci
                """
            )
            cursor.execute(
                """
                CREATE TABLE IF NOT EXISTS user_notification_reads (
                    id BIGINT UNSIGNED NOT NULL AUTO_INCREMENT,
                    user_id BIGINT UNSIGNED NOT NULL,
                    notification_id VARCHAR(64) NOT NULL,
                    read_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
                    PRIMARY KEY (id),
                    UNIQUE KEY idx_user_notification_reads_user_notification (user_id, notification_id),
                    KEY idx_user_notification_reads_notification (notification_id),
                    CONSTRAINT fk_user_notification_reads_user
                        FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE,
                    CONSTRAINT fk_user_notification_reads_notification
                        FOREIGN KEY (notification_id) REFERENCES notifications(id) ON DELETE CASCADE
                ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci
                """
            )
            cursor.execute(
                """
                CREATE TABLE IF NOT EXISTS notification_setting_types (
                    `key` VARCHAR(64) NOT NULL,
                    title VARCHAR(255) NOT NULL,
                    description VARCHAR(512) NOT NULL DEFAULT '',
                    icon VARCHAR(32) NOT NULL DEFAULT '',
                    sort_order INT NOT NULL DEFAULT 0,
                    is_active TINYINT(1) NOT NULL DEFAULT 1,
                    created_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
                    updated_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
                    PRIMARY KEY (`key`),
                    KEY idx_notification_setting_types_sort_order (sort_order, is_active)
                ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci
                """
            )
            cursor.execute(
                """
                CREATE TABLE IF NOT EXISTS user_notification_email_settings (
                    id BIGINT UNSIGNED NOT NULL AUTO_INCREMENT,
                    user_id BIGINT UNSIGNED NOT NULL,
                    notification_key VARCHAR(64) NOT NULL,
                    email_enabled TINYINT(1) NOT NULL DEFAULT 0,
                    created_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
                    updated_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
                    PRIMARY KEY (id),
                    UNIQUE KEY idx_user_notification_email_settings_user_notification (user_id, notification_key),
                    KEY idx_user_notification_email_settings_notification_key (notification_key),
                    CONSTRAINT fk_user_notification_email_settings_user
                        FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE,
                    CONSTRAINT fk_user_notification_email_settings_type
                        FOREIGN KEY (notification_key) REFERENCES notification_setting_types(`key`) ON DELETE CASCADE
                ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci
                """
            )
            normalize_template_values_in_database(cursor)
        connection.commit()
    finally:
        connection.close()


def seed_usage_events_if_empty(settings: MySQLSettings | None = None) -> None:
    settings = settings or get_mysql_settings()

    import pymysql

    connection = pymysql.connect(**get_database_connection_kwargs(settings))
    try:
        with connection.cursor() as cursor:
            cursor.execute("SELECT COUNT(*) FROM usage_events")
            count = int(cursor.fetchone()[0])
            if count:
                return

            seed_start = datetime.now().replace(hour=0, minute=0, second=0, microsecond=0)
            seed_rows = []
            for word_count in SEED_USAGE_WORD_COUNTS:
                created_at = seed_start
                seed_rows.append(("polish", word_count, created_at.strftime("%Y-%m-%d %H:%M:%S")))

            cursor.executemany(
                "INSERT INTO usage_events (event_type, word_count, created_at) VALUES (%s, %s, %s)",
                seed_rows,
            )
    finally:
        connection.close()


def seed_polish_templates_if_empty(settings: MySQLSettings | None = None) -> None:
    settings = settings or get_mysql_settings()

    import pymysql

    connection = pymysql.connect(**get_database_connection_kwargs(settings))
    try:
        with connection.cursor() as cursor:
            sync_standard_polish_templates(cursor)
    finally:
        connection.close()


def sanitize_template_key(raw_value: Any, fallback: str = "template") -> str:
    text = re.sub(r"[^a-z0-9]+", "-", str(raw_value or "").lower()).strip("-")
    return text or f"{fallback}-{uuid4().hex[:6]}"


def normalize_template_strings(values: list[Any] | None) -> list[str]:
    normalized: list[str] = []
    for value in values or []:
        text = str(value).strip()
        if text:
            normalized.append(text)
    return normalized


def encode_template_strings(values: list[Any] | None) -> str:
    return json.dumps(normalize_template_strings(values), ensure_ascii=False)


def decode_template_strings(raw_value: Any) -> list[str]:
    if not raw_value:
        return []
    try:
        parsed = json.loads(str(raw_value))
    except json.JSONDecodeError:
        return []
    if not isinstance(parsed, list):
        return []
    return normalize_template_strings(parsed)


def format_template_date(value: Any) -> str:
    if hasattr(value, "strftime"):
        return value.strftime("%Y-%m-%d")
    text = str(value or "").strip()
    return text[:10] if text else datetime.now().strftime("%Y-%m-%d")


def format_polish_template_row(
    row: tuple[Any, ...],
    metrics_by_key: dict[str, dict[str, Any]] | None = None,
) -> dict[str, Any]:
    (
        template_id,
        template_key,
        name,
        description,
        icon,
        tone,
        enabled,
        user_modified,
        usage_count,
        average_score,
        updated_at,
        system_prompt,
        terminology_json,
        forbidden_expressions_json,
    ) = row
    template_key_text = str(template_key or "")
    standard_by_key, _ = get_standard_template_maps()
    standard_template = standard_by_key.get(template_key_text)
    is_user_modified = bool(user_modified)
    normalized_name = normalize_template_label_value(name, fallback=template_key_text)
    normalized_description = str(description or "")
    normalized_icon = str(icon or "M")
    normalized_tone = str(tone or "icon-blue")
    normalized_system_prompt = str(system_prompt or "")
    normalized_terminology = decode_template_strings(terminology_json)
    normalized_forbidden = decode_template_strings(forbidden_expressions_json)

    if standard_template and not is_user_modified:
        normalized_name = str(standard_template.get("name") or standard_template.get("label") or normalized_name)
        normalized_description = str(standard_template.get("description") or normalized_description)
        normalized_icon = str(standard_template.get("icon") or normalized_icon)
        normalized_tone = str(standard_template.get("tone") or normalized_tone)
        normalized_system_prompt = str(standard_template.get("systemPrompt") or normalized_system_prompt)
        normalized_terminology = normalize_template_strings(standard_template.get("terminology"))
        normalized_forbidden = normalize_template_strings(standard_template.get("forbiddenExpressions"))

    metric = (metrics_by_key or {}).get(template_key_text, {})
    usage_count_value = int(metric.get("usageCount", usage_count or 0) or 0)
    average_score_value = metric.get("averageScore", average_score or 0) or 0
    average_score_value = round(float(average_score_value), 1)
    if average_score_value.is_integer():
        average_score_value = int(average_score_value)

    return {
        "id": str(template_id or ""),
        "key": template_key_text,
        "name": normalized_name,
        "label": normalized_name,
        "description": normalized_description,
        "icon": normalized_icon,
        "tone": normalized_tone,
        "enabled": bool(enabled),
        "userModified": is_user_modified,
        "usageCount": usage_count_value,
        "averageScore": average_score_value,
        "updatedAt": format_template_date(updated_at),
        "systemPrompt": normalized_system_prompt,
        "terminology": normalized_terminology,
        "forbiddenExpressions": normalized_forbidden,
    }


POLISH_TEMPLATE_SELECT_COLUMNS = """
    template_id,
    template_key,
    name,
    description,
    icon,
    tone,
    enabled,
    user_modified,
    usage_count,
    average_score,
    updated_at,
    system_prompt,
    terminology_json,
    forbidden_expressions_json
"""


def get_standard_polish_templates() -> list[dict[str, Any]]:
    from .data_store import build_default_polish_templates, normalize_template_list

    return normalize_template_list(build_default_polish_templates())


LEGACY_TEMPLATE_LABEL_ALIASES = {
    "general": "通用润色",
    "academic": "学术论文润色",
    "resume": "简历优化",
    "business": "商务报告优化",
    "official": "公文材料润色",
    "rewrite": "改写优化",
    "summary": "摘要总结",
    "通用润色": "通用润色",
    "学术论文润色": "学术论文润色",
    "简历优化": "简历优化",
    "商务报告优化": "商务报告优化",
    "公文材料润色": "公文材料润色",
    "改写优化": "改写优化",
    "摘要总结": "摘要总结",
    "邮件润色": "邮件润色",
}


def get_standard_template_maps() -> tuple[dict[str, dict[str, Any]], dict[str, str]]:
    templates = get_standard_polish_templates()
    by_key = {str(item.get("key") or ""): item for item in templates}
    by_label = {
        str(item.get("name") or item.get("label") or "").strip(): str(item.get("key") or "")
        for item in templates
        if str(item.get("name") or item.get("label") or "").strip()
    }
    return by_key, by_label


def is_standard_template_key(template_key: Any) -> bool:
    standard_by_key, _ = get_standard_template_maps()
    return str(template_key or "").strip() in standard_by_key


def normalize_template_label_value(value: Any, *, fallback: str = "未选择") -> str:
    text = str(value or "").strip()
    if not text:
        return fallback

    standard_by_key, standard_key_by_label = get_standard_template_maps()
    if text in standard_by_key:
        template = standard_by_key[text]
        return str(template.get("name") or template.get("label") or fallback).strip() or fallback
    if text in standard_key_by_label:
        return text
    return LEGACY_TEMPLATE_LABEL_ALIASES.get(text, text)


def normalize_batch_template_type(value: Any) -> str:
    return normalize_template_label_value(value, fallback="未选择")


def get_polish_template_metadata(cursor: Any, user_id: int, template_id: str) -> dict[str, Any] | None:
    cursor.execute(
        """
        SELECT template_key, is_deleted
        FROM polish_templates
        WHERE user_id = %s
          AND template_id = %s
        LIMIT 1
        """,
        (int(user_id), template_id),
    )
    row = cursor.fetchone()
    if row is None:
        return None
    return {
        "template_key": str(row[0] or ""),
        "is_deleted": bool(row[1]),
    }


def normalize_template_values_in_database(cursor: Any) -> None:
    standard_templates = get_standard_polish_templates()

    for legacy_value, normalized_value in LEGACY_TEMPLATE_LABEL_ALIASES.items():
        if not legacy_value or legacy_value == normalized_value:
            continue
        cursor.execute(
            "UPDATE batch_documents SET template_type = %s WHERE template_type = %s",
            (normalized_value, legacy_value),
        )

    for template in standard_templates:
        template_key = str(template.get("key") or "")
        template_name = str(template.get("name") or template.get("label") or "").strip()
        if not template_key or not template_name:
            continue

        cursor.execute(
            """
            UPDATE polish_templates
            SET name = %s,
                description = %s,
                icon = %s,
                tone = %s,
                enabled = %s,
                updated_at = %s,
                system_prompt = %s,
                terminology_json = %s,
                forbidden_expressions_json = %s
            WHERE user_id IS NULL
              AND template_key = %s
            """,
            (
                template_name,
                str(template.get("description") or ""),
                str(template.get("icon") or ""),
                str(template.get("tone") or "icon-blue"),
                1 if template.get("enabled", True) else 0,
                str(template.get("updatedAt") or datetime.now().strftime("%Y-%m-%d")),
                str(template.get("systemPrompt") or "").strip(),
                encode_template_strings(template.get("terminology")),
                encode_template_strings(template.get("forbiddenExpressions")),
                template_key,
            ),
        )
        cursor.execute(
            """
            UPDATE polish_templates
            SET name = %s,
                description = %s,
                icon = %s,
                tone = %s,
                enabled = %s,
                updated_at = %s,
                system_prompt = %s,
                terminology_json = %s,
                forbidden_expressions_json = %s
            WHERE user_id IS NOT NULL
              AND template_key = %s
              AND is_deleted = 0
              AND user_modified = 0
            """,
            (
                template_name,
                str(template.get("description") or ""),
                str(template.get("icon") or ""),
                str(template.get("tone") or "icon-blue"),
                1 if template.get("enabled", True) else 0,
                str(template.get("updatedAt") or datetime.now().strftime("%Y-%m-%d")),
                str(template.get("systemPrompt") or "").strip(),
                encode_template_strings(template.get("terminology")),
                encode_template_strings(template.get("forbiddenExpressions")),
                template_key,
            ),
        )


def sync_standard_polish_templates(cursor: Any) -> None:
    for template in get_standard_polish_templates():
        values = (
            str(template.get("id") or ""),
            str(template.get("key") or ""),
            str(template.get("name") or ""),
            str(template.get("description") or ""),
            str(template.get("icon") or ""),
            str(template.get("tone") or "icon-blue"),
            1 if template.get("enabled", True) else 0,
            0,
            max(0, int(template.get("usageCount") or 0)),
            max(0, min(100, float(template.get("averageScore") or 0))),
            str(template.get("updatedAt") or datetime.now().strftime("%Y-%m-%d")),
            str(template.get("systemPrompt") or "").strip(),
            encode_template_strings(template.get("terminology")),
            encode_template_strings(template.get("forbiddenExpressions")),
        )
        cursor.execute(
            "SELECT id FROM polish_templates WHERE user_id IS NULL AND template_key = %s ORDER BY id ASC LIMIT 1",
            (values[1],),
        )
        row = cursor.fetchone()
        if row is None:
            cursor.execute(
                """
                INSERT INTO polish_templates (
                    template_id,
                    template_key,
                    name,
                    description,
                    icon,
                    tone,
                    enabled,
                    user_modified,
                    usage_count,
                    average_score,
                    updated_at,
                    system_prompt,
                    terminology_json,
                    forbidden_expressions_json
                )
                VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
                """,
                values,
            )
            continue

        cursor.execute(
            """
            UPDATE polish_templates
            SET template_id = %s,
                template_key = %s,
                name = %s,
                description = %s,
                icon = %s,
                tone = %s,
                enabled = %s,
                user_modified = %s,
                usage_count = %s,
                average_score = %s,
                updated_at = %s,
                system_prompt = %s,
                terminology_json = %s,
                forbidden_expressions_json = %s
            WHERE id = %s
            """,
            (*values, int(row[0])),
        )


def load_default_template_seed_rows(cursor: Any) -> list[dict[str, Any]]:
    return get_standard_polish_templates()


def seed_user_polish_templates_if_missing(cursor: Any, user_id: int) -> None:
    seed_templates = load_default_template_seed_rows(cursor)
    if not seed_templates:
        return

    cursor.execute(
        "SELECT template_key, user_modified, is_deleted FROM polish_templates WHERE user_id = %s",
        (int(user_id),),
    )
    existing_by_key = {
        str(row[0] or ""): {
            "user_modified": bool(row[1]),
            "is_deleted": bool(row[2]),
        }
        for row in cursor.fetchall()
    }

    for template in seed_templates:
        template_key = str(template.get("key") or "")
        values = (
            str(template.get("id") or ""),
            template_key,
            str(template.get("name") or ""),
            str(template.get("description") or ""),
            str(template.get("icon") or ""),
            str(template.get("tone") or "icon-blue"),
            1 if template.get("enabled", True) else 0,
            str(template.get("updatedAt") or datetime.now().strftime("%Y-%m-%d")),
            str(template.get("systemPrompt") or "").strip(),
            encode_template_strings(template.get("terminology")),
            encode_template_strings(template.get("forbiddenExpressions")),
        )

        if template_key not in existing_by_key:
            cursor.execute(
                """
                INSERT INTO polish_templates (
                    user_id,
                    template_id,
                    template_key,
                    name,
                    description,
                    icon,
                    tone,
                    enabled,
                    user_modified,
                    usage_count,
                    average_score,
                    updated_at,
                    system_prompt,
                    terminology_json,
                    forbidden_expressions_json
                )
                VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
                """,
                (int(user_id), *values[:7], 0, 0, 0, *values[7:]),
            )
            continue

        existing = existing_by_key[template_key]
        if existing["is_deleted"]:
            continue

        if existing["user_modified"]:
            continue

        cursor.execute(
            """
            UPDATE polish_templates
            SET template_id = %s,
                name = %s,
                description = %s,
                icon = %s,
                tone = %s,
                enabled = %s,
                updated_at = %s,
                system_prompt = %s,
                terminology_json = %s,
                forbidden_expressions_json = %s,
                user_modified = 0
            WHERE user_id = %s
              AND template_key = %s
            """,
            (
                values[0],
                values[2],
                values[3],
                values[4],
                values[5],
                values[6],
                values[7],
                values[8],
                values[9],
                values[10],
                int(user_id),
                template_key,
            ),
        )


def ensure_user_polish_templates(user_id: int, settings: MySQLSettings | None = None) -> None:
    settings = settings or get_mysql_settings()

    import pymysql

    connection = pymysql.connect(**get_database_connection_kwargs(settings))
    try:
        with connection.cursor() as cursor:
            seed_user_polish_templates_if_missing(cursor, int(user_id))
    finally:
        connection.close()


def seed_user_polish_templates_for_existing_users(settings: MySQLSettings | None = None) -> None:
    settings = settings or get_mysql_settings()

    import pymysql

    connection = pymysql.connect(**get_database_connection_kwargs(settings))
    try:
        with connection.cursor() as cursor:
            cursor.execute("SELECT id FROM users")
            for row in cursor.fetchall():
                seed_user_polish_templates_if_missing(cursor, int(row[0]))
    finally:
        connection.close()


def list_polish_templates_from_database(user_id: int, *, include_disabled: bool = True) -> list[dict[str, Any]]:
    settings = get_mysql_settings()

    import pymysql

    ensure_mysql_schema(settings)
    ensure_user_polish_templates(int(user_id), settings)
    connection = pymysql.connect(**get_database_connection_kwargs(settings))
    try:
        with connection.cursor() as cursor:
            where_clause = (
                "WHERE user_id = %s AND is_deleted = 0"
                if include_disabled
                else "WHERE user_id = %s AND is_deleted = 0 AND enabled = 1"
            )
            cursor.execute(
                f"""
                SELECT {POLISH_TEMPLATE_SELECT_COLUMNS}
                FROM polish_templates
                {where_clause}
                ORDER BY LOWER(COALESCE(NULLIF(name, ''), NULLIF(template_key, ''), '')) ASC,
                         updated_at DESC,
                         id DESC
                """,
                (int(user_id),),
            )
            rows = cursor.fetchall()
    finally:
        connection.close()

    metrics_by_key = load_template_metrics_by_user(int(user_id))
    return [format_polish_template_row(row, metrics_by_key) for row in rows]


def get_polish_template_from_database(user_id: int, template_id: str) -> dict[str, Any]:
    settings = get_mysql_settings()

    import pymysql

    ensure_mysql_schema(settings)
    ensure_user_polish_templates(int(user_id), settings)
    connection = pymysql.connect(**get_database_connection_kwargs(settings))
    try:
        with connection.cursor() as cursor:
            cursor.execute(
                f"""
                SELECT {POLISH_TEMPLATE_SELECT_COLUMNS}
                FROM polish_templates
                WHERE user_id = %s
                  AND is_deleted = 0
                  AND template_id = %s
                """,
                (int(user_id), template_id),
            )
            row = cursor.fetchone()
    finally:
        connection.close()

    if row is None:
        raise KeyError(template_id)
    metrics_by_key = load_template_metrics_by_user(int(user_id))
    return format_polish_template_row(row, metrics_by_key)


def build_unique_template_key(cursor: Any, user_id: int, raw_key: Any, name: str) -> str:
    base_key = sanitize_template_key(raw_key or name)
    key = base_key
    suffix = 2
    while True:
        cursor.execute(
            "SELECT 1 FROM polish_templates WHERE user_id = %s AND template_key = %s LIMIT 1",
            (int(user_id), key),
        )
        if cursor.fetchone() is None:
            return key
        key = f"{base_key}-{suffix}"
        suffix += 1


def create_polish_template_in_database(user_id: int, payload: dict[str, Any]) -> dict[str, Any]:
    name = (payload.get("name") or payload.get("label") or "").strip()
    if not name:
        raise ValueError("模板名称不能为空。")

    settings = get_mysql_settings()

    import pymysql

    ensure_mysql_schema(settings)
    ensure_user_polish_templates(int(user_id), settings)
    template_id = f"tpl-{uuid4().hex[:8]}"
    updated_at = datetime.now().strftime("%Y-%m-%d")
    connection = pymysql.connect(**get_database_connection_kwargs(settings))
    try:
        with connection.cursor() as cursor:
            template_key = build_unique_template_key(cursor, int(user_id), payload.get("key"), name)
            cursor.execute(
                """
                INSERT INTO polish_templates (
                    user_id,
                    template_id,
                    template_key,
                    name,
                    description,
                    icon,
                    tone,
                    enabled,
                    user_modified,
                    usage_count,
                    average_score,
                    updated_at,
                    system_prompt,
                    terminology_json,
                    forbidden_expressions_json
                )
                VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
                """,
                (
                    int(user_id),
                    template_id,
                    template_key,
                    name,
                    str(payload.get("description") or "").strip(),
                    str(payload.get("icon") or "M").strip() or "M",
                    str(payload.get("tone") or "icon-blue").strip() or "icon-blue",
                    1 if payload.get("enabled", True) else 0,
                    1,
                    max(0, int(payload.get("usageCount") or 0)),
                    max(0, min(100, float(payload.get("averageScore") or 0))),
                    updated_at,
                    str(payload.get("systemPrompt") or "").strip(),
                    encode_template_strings(payload.get("terminology")),
                    encode_template_strings(payload.get("forbiddenExpressions")),
                ),
            )
    finally:
        connection.close()

    return get_polish_template_from_database(int(user_id), template_id)


def update_polish_template_in_database(user_id: int, template_id: str, payload: dict[str, Any]) -> dict[str, Any]:
    name = (payload.get("name") or payload.get("label") or "").strip()
    if not name:
        raise ValueError("模板名称不能为空。")

    settings = get_mysql_settings()

    import pymysql

    ensure_mysql_schema(settings)
    ensure_user_polish_templates(int(user_id), settings)
    updated_at = datetime.now().strftime("%Y-%m-%d")
    connection = pymysql.connect(**get_database_connection_kwargs(settings))
    try:
        with connection.cursor() as cursor:
            cursor.execute(
                "SELECT 1 FROM polish_templates WHERE user_id = %s AND template_id = %s AND is_deleted = 0 LIMIT 1",
                (int(user_id), template_id),
            )
            if cursor.fetchone() is None:
                raise KeyError(template_id)
            cursor.execute(
                """
                UPDATE polish_templates
                SET name = %s,
                    description = %s,
                    icon = %s,
                    tone = %s,
                    enabled = %s,
                    usage_count = %s,
                    average_score = %s,
                    updated_at = %s,
                    system_prompt = %s,
                    terminology_json = %s,
                    forbidden_expressions_json = %s,
                    user_modified = 1
                WHERE user_id = %s
                  AND is_deleted = 0
                  AND template_id = %s
                """,
                (
                    name,
                    str(payload.get("description") or "").strip(),
                    str(payload.get("icon") or "M").strip() or "M",
                    str(payload.get("tone") or "icon-blue").strip() or "icon-blue",
                    1 if payload.get("enabled", True) else 0,
                    max(0, int(payload.get("usageCount") or 0)),
                    max(0, min(100, float(payload.get("averageScore") or 0))),
                    updated_at,
                    str(payload.get("systemPrompt") or "").strip(),
                    encode_template_strings(payload.get("terminology")),
                    encode_template_strings(payload.get("forbiddenExpressions")),
                    int(user_id),
                    template_id,
                ),
            )
    finally:
        connection.close()

    return get_polish_template_from_database(int(user_id), template_id)


def toggle_polish_template_enabled_in_database(user_id: int, template_id: str, enabled: bool) -> dict[str, Any]:
    settings = get_mysql_settings()

    import pymysql

    ensure_mysql_schema(settings)
    ensure_user_polish_templates(int(user_id), settings)
    connection = pymysql.connect(**get_database_connection_kwargs(settings))
    try:
        with connection.cursor() as cursor:
            cursor.execute(
                "SELECT 1 FROM polish_templates WHERE user_id = %s AND template_id = %s AND is_deleted = 0 LIMIT 1",
                (int(user_id), template_id),
            )
            if cursor.fetchone() is None:
                raise KeyError(template_id)
            cursor.execute(
                """
                UPDATE polish_templates
                SET enabled = %s,
                    updated_at = %s,
                    user_modified = 1
                WHERE user_id = %s
                  AND is_deleted = 0
                  AND template_id = %s
                """,
                (1 if enabled else 0, datetime.now().strftime("%Y-%m-%d"), int(user_id), template_id),
            )
        connection.commit()
    finally:
        connection.close()

    return get_polish_template_from_database(int(user_id), template_id)


def delete_polish_template_from_database(user_id: int, template_id: str) -> None:
    settings = get_mysql_settings()

    import pymysql

    ensure_mysql_schema(settings)
    ensure_user_polish_templates(int(user_id), settings)
    connection = pymysql.connect(**get_database_connection_kwargs(settings))
    try:
        with connection.cursor() as cursor:
            metadata = get_polish_template_metadata(cursor, int(user_id), template_id)
            if metadata is None or metadata["is_deleted"]:
                raise KeyError(template_id)
            if is_standard_template_key(metadata["template_key"]):
                cursor.execute(
                    """
                    UPDATE polish_templates
                    SET is_deleted = 1,
                        user_modified = 1,
                        updated_at = %s
                    WHERE user_id = %s
                      AND template_id = %s
                      AND is_deleted = 0
                    """,
                    (datetime.now().strftime("%Y-%m-%d"), int(user_id), template_id),
                )
            else:
                cursor.execute(
                    "DELETE FROM polish_templates WHERE user_id = %s AND template_id = %s",
                    (int(user_id), template_id),
                )
            if cursor.rowcount == 0:
                raise KeyError(template_id)
        connection.commit()
    finally:
        connection.close()


def get_template_maps_from_database(
    user_id: int,
    include_disabled: bool = True,
) -> tuple[dict[str, dict[str, Any]], dict[str, str]]:
    templates = list_polish_templates_from_database(int(user_id), include_disabled=include_disabled)
    return (
        {item["key"]: item for item in templates},
        {item["name"]: item["key"] for item in templates},
    )


def _resolve_template_metric_key(
    raw_key: Any,
    raw_label: Any,
    *,
    active_templates: dict[str, str],
    template_key_by_name: dict[str, str],
    deleted_template_keys: set[str],
) -> str:
    standard_by_key, standard_key_by_label = get_standard_template_maps()
    normalized_key = str(raw_key or "").strip()
    normalized_label = normalize_template_label_value(raw_label, fallback="")
    raw_label_text = str(raw_label or "").strip()
    unselected_labels = {"", "未选择", "未选择模板", "自定义设置", "鑷畾涔夎缃?"}

    if normalized_key in deleted_template_keys:
        return ""
    if normalized_key in active_templates:
        return normalized_key

    label_candidates = [normalized_label, raw_label_text]
    for label in label_candidates:
        if label in unselected_labels:
            continue
        mapped_key = str(template_key_by_name.get(label) or "").strip()
        if mapped_key in active_templates:
            return mapped_key
        standard_key = str(standard_key_by_label.get(label) or "").strip()
        if standard_key in active_templates:
            return standard_key
        if label in standard_by_key and label in active_templates:
            return label

    if normalized_key in standard_by_key and normalized_key in active_templates:
        return normalized_key
    return ""


def load_template_metrics_by_user(user_id: int) -> dict[str, dict[str, Any]]:
    settings = get_mysql_settings()

    import pymysql

    ensure_mysql_schema(settings)
    ensure_user_polish_templates(int(user_id), settings)
    connection = pymysql.connect(**get_database_connection_kwargs(settings))
    try:
        with connection.cursor() as cursor:
            cursor.execute(
                """
                SELECT template_key, name, is_deleted
                FROM polish_templates
                WHERE user_id = %s
                """,
                (int(user_id),),
            )
            template_rows = cursor.fetchall()
            cursor.execute(
                """
                SELECT template_key, template_label, score
                FROM polish_records
                WHERE user_id = %s
                """,
                (int(user_id),),
            )
            polish_rows = cursor.fetchall()
            cursor.execute(
                """
                SELECT template_type, score
                FROM batch_documents
                WHERE user_id = %s
                  AND has_result = 1
                """,
                (int(user_id),),
            )
            batch_rows = cursor.fetchall()
    finally:
        connection.close()

    active_templates: dict[str, str] = {}
    template_key_by_name: dict[str, str] = {}
    deleted_template_keys: set[str] = set()
    for template_key, template_name, is_deleted in template_rows:
        normalized_key = str(template_key or "").strip()
        if not normalized_key:
            continue
        normalized_name = str(template_name or "").strip()
        if bool(is_deleted):
            deleted_template_keys.add(normalized_key)
            continue
        active_templates[normalized_key] = normalized_name or normalized_key
        if normalized_name:
            template_key_by_name[normalized_name] = normalized_key

    metrics_by_key: dict[str, dict[str, Any]] = {}

    def add_metric(template_key: str, score: Any) -> None:
        if not template_key:
            return
        bucket = metrics_by_key.setdefault(
            template_key,
            {
                "usageCount": 0,
                "scoreTotal": 0.0,
                "scoreCount": 0,
            },
        )
        bucket["usageCount"] += 1
        if score is not None:
            bucket["scoreTotal"] += float(score)
            bucket["scoreCount"] += 1

    for template_key, template_label, score in polish_rows:
        resolved_key = _resolve_template_metric_key(
            template_key,
            template_label,
            active_templates=active_templates,
            template_key_by_name=template_key_by_name,
            deleted_template_keys=deleted_template_keys,
        )
        add_metric(resolved_key, score)

    for template_type, score in batch_rows:
        resolved_key = _resolve_template_metric_key(
            "",
            template_type,
            active_templates=active_templates,
            template_key_by_name=template_key_by_name,
            deleted_template_keys=deleted_template_keys,
        )
        add_metric(resolved_key, score)

    return {
        template_key: {
            "usageCount": int(metric.get("usageCount") or 0),
            "averageScore": (
                round(float(metric["scoreTotal"]) / int(metric["scoreCount"]), 1)
                if int(metric.get("scoreCount") or 0) > 0
                else 0
            ),
        }
        for template_key, metric in metrics_by_key.items()
    }


STATUS_LABELS = {
    "completed": "已完成",
    "polishing": "润色中",
    "pending": "待确认",
    "unprocessed": "未润色",
}

STATUS_CARD_META = [
    ("all", "全部文档", "文", "tone-blue"),
    ("completed", "已完成", "✓", "tone-green"),
    ("pending", "待确认", "●", "tone-orange"),
    ("unprocessed", "未润色", "○", "tone-purple"),
]


def normalize_batch_file_type(file_type: Any) -> str:
    text = str(file_type or "").strip().lower()
    if text == "pdf":
        return "PDF"
    if text in {"txt", "text"}:
        return "TXT"
    if text in {"docx", "word"}:
        return "Word"
    return "Word"


def format_batch_datetime(value: Any) -> str:
    if hasattr(value, "strftime"):
        return value.strftime("%Y-%m-%d %H:%M")
    return str(value or "")[:16]


def format_batch_datetime_seconds(value: Any) -> str:
    if hasattr(value, "strftime"):
        return value.strftime("%Y-%m-%d %H:%M:%S")
    return str(value or "")[:19]


def normalize_datetime_string(value: Any) -> str:
    if isinstance(value, datetime):
        return value.replace(microsecond=0).strftime("%Y-%m-%d %H:%M:%S")

    text = str(value or "").strip().replace("T", " ")
    if not text:
        return ""
    if text.endswith("Z"):
        text = f"{text[:-1]}+00:00"

    candidates = [text]
    if len(text) == 16:
        candidates.insert(0, f"{text}:00")
    if len(text) > 19:
        candidates.append(text[:19])

    seen: set[str] = set()
    for candidate in candidates:
        if not candidate or candidate in seen:
            continue
        seen.add(candidate)
        try:
            parsed = datetime.fromisoformat(candidate)
        except ValueError:
            continue
        return parsed.replace(tzinfo=None, microsecond=0).strftime("%Y-%m-%d %H:%M:%S")
    return ""


def format_batch_document_row(row: tuple[Any, ...]) -> dict[str, Any]:
    (
        document_id,
        title,
        category,
        file_type,
        template_type,
        word_count,
        processed_word_count,
        score,
        status,
        original_filename,
        storage_path,
        result_file_path,
        result_detail_path,
        result_text,
        has_result,
        processed_at,
        confirmed_at,
        updated_at,
    ) = row
    status_text = str(status or "unprocessed")
    result = str(result_text or "") if has_result else ""
    storage_path_text = str(storage_path or "")
    next_result_file_path = str(result_file_path or "")
    next_result_detail_path = str(result_detail_path or "")
    if storage_path_text and not next_result_detail_path and has_result:
        storage_path_obj = Path(storage_path_text.replace("\\", "/"))
        next_result_detail_path = str(storage_path_obj.with_name(f"{storage_path_obj.stem}.polished.json"))
    if storage_path_text and not next_result_file_path and has_result:
        storage_path_obj = Path(storage_path_text.replace("\\", "/"))
        suffix = storage_path_obj.suffix.lower()
        if suffix in {".txt", ".text"}:
            next_result_file_path = str(storage_path_obj.with_name(f"{storage_path_obj.stem}.polished.txt"))
        elif suffix == ".docx":
            next_result_file_path = str(storage_path_obj.with_name(f"{storage_path_obj.stem}.polished.docx"))
    return {
        "id": str(document_id or ""),
        "title": str(title or original_filename or "未命名文档"),
        "category": str(category or "批量导入"),
        "fileType": normalize_batch_file_type(file_type),
        "templateType": normalize_batch_template_type(template_type),
        "wordCount": int(word_count or 0),
        "processedWordCount": int(processed_word_count or 0),
        "score": _normalize_batch_score_value(score),
        "status": status_text if status_text in STATUS_LABELS else "unprocessed",
        "updatedAt": format_batch_datetime(updated_at),
        "processedAt": format_batch_datetime_seconds(processed_at) if processed_at else None,
        "hasResult": bool(has_result),
        "sourceText": "",
        "resultText": result,
        "originalFilename": str(original_filename or ""),
        "filePath": storage_path_text,
        "resultFilePath": next_result_file_path,
        "resultDetailPath": next_result_detail_path,
        "confirmedAt": format_batch_datetime(confirmed_at) if confirmed_at else None,
    }


BATCH_DOCUMENT_SELECT_COLUMNS = """
    document_id,
    title,
    category,
    file_type,
    template_type,
    word_count,
    processed_word_count,
    score,
    status,
    original_filename,
    storage_path,
    result_file_path,
    result_detail_path,
    result_text,
    has_result,
    processed_at,
    confirmed_at,
    updated_at
"""


def list_batch_documents_from_database(user_id: int) -> list[dict[str, Any]]:
    settings = get_mysql_settings()

    import pymysql

    ensure_mysql_schema(settings)
    connection = pymysql.connect(**get_database_connection_kwargs(settings))
    try:
        with connection.cursor() as cursor:
            cursor.execute(
                f"""
                SELECT {BATCH_DOCUMENT_SELECT_COLUMNS}
                FROM batch_documents
                WHERE user_id = %s
                ORDER BY updated_at ASC, id ASC
                """,
                (int(user_id),),
            )
            rows = cursor.fetchall()
    finally:
        connection.close()

    return [format_batch_document_row(row) for row in rows]


def get_batch_document_from_database(user_id: int, document_id: str) -> dict[str, Any]:
    settings = get_mysql_settings()

    import pymysql

    ensure_mysql_schema(settings)
    connection = pymysql.connect(**get_database_connection_kwargs(settings))
    try:
        with connection.cursor() as cursor:
            cursor.execute(
                f"""
                SELECT {BATCH_DOCUMENT_SELECT_COLUMNS}
                FROM batch_documents
                WHERE user_id = %s
                  AND document_id = %s
                LIMIT 1
                """,
                (int(user_id), str(document_id or "")),
            )
            row = cursor.fetchone()
    finally:
        connection.close()

    if not row:
        raise KeyError(document_id)
    return format_batch_document_row(row)


def update_batch_document_polish_state(
    user_id: int,
    document_id: str,
    *,
    template_type: str,
    status: str,
    has_result: bool,
    result_text: str = "",
    result_file_path: str | None = None,
    result_detail_path: str | None = None,
    processed_at: str | None = None,
    processed_word_count: int | None = None,
    score: float | int | None = None,
    confirmed_at: str | None = None,
) -> dict[str, Any]:
    settings = get_mysql_settings()

    import pymysql

    ensure_mysql_schema(settings)
    current_document = get_batch_document_from_database(int(user_id), str(document_id or ""))
    now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    next_result_file_path = (
        current_document.get("resultFilePath", "") if result_file_path is None else str(result_file_path or "")
    )
    next_result_detail_path = (
        current_document.get("resultDetailPath", "") if result_detail_path is None else str(result_detail_path or "")
    )
    next_processed_at = (
        current_document.get("processedAt", "") if processed_at is None else normalize_datetime_string(processed_at)
    )
    next_processed_word_count = (
        int(current_document.get("processedWordCount") or 0)
        if processed_word_count is None
        else max(0, int(processed_word_count or 0))
    )
    next_score = (
        current_document.get("score")
        if score is None and has_result
        else (_normalize_batch_score_value(score) if has_result else None)
    )
    next_confirmed_at = current_document.get("confirmedAt") if confirmed_at is None else str(confirmed_at or "")
    connection = pymysql.connect(**get_database_connection_kwargs(settings))
    try:
        with connection.cursor() as cursor:
            cursor.execute(
                """
                UPDATE batch_documents
                SET template_type = %s,
                    status = %s,
                    result_text = %s,
                    has_result = %s,
                    result_file_path = %s,
                    result_detail_path = %s,
                    processed_at = NULLIF(%s, ''),
                    processed_word_count = %s,
                    score = %s,
                    confirmed_at = NULLIF(%s, ''),
                    updated_at = %s
                WHERE user_id = %s
                  AND document_id = %s
                """,
                (
                    normalize_batch_template_type(template_type)[:120],
                    str(status or "unprocessed")[:32],
                    str(result_text or ""),
                    1 if has_result else 0,
                    next_result_file_path[:500],
                    next_result_detail_path[:500],
                    next_processed_at,
                    next_processed_word_count,
                    next_score,
                    next_confirmed_at,
                    now,
                    int(user_id),
                    str(document_id or ""),
                ),
            )
            if cursor.rowcount == 0:
                cursor.execute(
                    "SELECT id FROM batch_documents WHERE user_id = %s AND document_id = %s LIMIT 1",
                    (int(user_id), str(document_id or "")),
                )
                if not cursor.fetchone():
                    raise KeyError(document_id)
    finally:
        connection.close()

    return get_batch_document_from_database(int(user_id), str(document_id or ""))


def delete_batch_document_from_database(user_id: int, document_id: str) -> None:
    settings = get_mysql_settings()

    import pymysql

    ensure_mysql_schema(settings)
    connection = pymysql.connect(**get_database_connection_kwargs(settings))
    try:
        with connection.cursor() as cursor:
            cursor.execute(
                """
                DELETE FROM batch_documents
                WHERE user_id = %s
                  AND document_id = %s
                """,
                (int(user_id), str(document_id or "")),
            )
            if cursor.rowcount == 0:
                raise KeyError(document_id)
    finally:
        connection.close()


def build_batch_summary(documents: list[dict[str, Any]]) -> list[dict[str, Any]]:
    summary = []
    for status_key, label, icon, tone in STATUS_CARD_META:
        if status_key == "all":
            items = documents
        else:
            items = [item for item in documents if item.get("status") == status_key]
        summary.append(
            {
                "label": label,
                "count": len(items),
                "wordCount": sum(int(item.get("wordCount") or 0) for item in items),
                "icon": icon,
                "tone": tone,
            }
        )
    return summary


def build_batch_distribution(documents: list[dict[str, Any]]) -> dict[str, Any]:
    colors = ["#2f6df6", "#35c28c", "#8b6ef6", "#5eb4ff", "#f5a54b", "#b4bccb"]
    counts: dict[str, int] = {}
    for item in documents:
        key = str(item.get("templateType") or "未选择")
        counts[key] = counts.get(key, 0) + 1

    total = len(documents)
    items = []
    for index, (label, count) in enumerate(sorted(counts.items(), key=lambda pair: pair[1], reverse=True)):
        percent = f"{(count / total * 100):.1f}%" if total else "0%"
        items.append(
            {
                "label": label,
                "count": count,
                "percent": percent,
                "color": colors[index % len(colors)],
            }
        )
    return {"total": total, "items": items}


def load_batch_status_distribution_for_user(user_id: int) -> dict[str, Any]:
    settings = get_mysql_settings()

    import pymysql

    ensure_mysql_schema(settings)
    status_meta = [
        ("completed", "已完成", "#35c28c"),
        ("polishing", "润色中", "#2f6df6"),
        ("pending", "待确认", "#f5a54b"),
        ("unprocessed", "未润色", "#8b6ef6"),
    ]
    counts = {key: 0 for key, _, _ in status_meta}

    connection = pymysql.connect(**get_database_connection_kwargs(settings))
    try:
        with connection.cursor() as cursor:
            cursor.execute(
                """
                SELECT status, COUNT(*)
                FROM batch_documents
                WHERE user_id = %s
                GROUP BY status
                """,
                (int(user_id),),
            )
            rows = cursor.fetchall()
    finally:
        connection.close()

    for status, count in rows:
        status_key = str(status or "unprocessed")
        if status_key not in counts:
            status_key = "unprocessed"
        counts[status_key] += int(count or 0)

    total = sum(counts.values())
    items = [
        {
            "label": label,
            "count": counts[key],
            "percent": f"{(counts[key] / total * 100):.1f}%" if total else "0%",
            "color": color,
        }
        for key, label, color in status_meta
    ]
    return {"total": total, "items": items}


def load_global_template_top5_from_records(limit: int = 5) -> list[dict[str, Any]]:
    settings = get_mysql_settings()

    import pymysql

    ensure_mysql_schema(settings)
    connection = pymysql.connect(**get_database_connection_kwargs(settings))
    try:
        with connection.cursor() as cursor:
            cursor.execute(
                """
                SELECT template_key, template_label, COUNT(*) AS usage_count
                FROM polish_records
                WHERE used_template = 1
                   OR (
                        COALESCE(NULLIF(template_key, ''), NULLIF(template_label, '')) IS NOT NULL
                    AND COALESCE(template_label, '') <> '未选择'
                   )
                GROUP BY template_key, template_label
                """
            )
            rows = cursor.fetchall()
    finally:
        connection.close()

    standard_by_key, standard_key_by_label = get_standard_template_maps()
    aggregated: dict[str, dict[str, Any]] = {}

    for template_key, template_label, usage_count in rows:
        raw_key = str(template_key or "").strip()
        normalized_label = normalize_template_label_value(template_label, fallback="")
        if normalized_label == "未选择":
            continue

        normalized_key = raw_key
        if normalized_key in standard_by_key:
            normalized_label = str(
                standard_by_key[normalized_key].get("name")
                or standard_by_key[normalized_key].get("label")
                or normalized_label
            )
        elif normalized_label and normalized_label in standard_key_by_label:
            normalized_key = standard_key_by_label[normalized_label]
            normalized_label = str(
                standard_by_key[normalized_key].get("name")
                or standard_by_key[normalized_key].get("label")
                or normalized_label
            )
        elif normalized_key:
            normalized_key = sanitize_template_key(normalized_key, fallback="template")
        elif normalized_label:
            normalized_key = sanitize_template_key(normalized_label, fallback="template")
        else:
            continue

        display_label = normalized_label or normalize_template_label_value(raw_key, fallback="通用润色")
        bucket = aggregated.setdefault(
            normalized_key,
            {
                "key": normalized_key,
                "label": display_label,
                "count": 0,
            },
        )
        bucket["count"] += int(usage_count or 0)

    palette = ["#2f6df6", "#35c28c", "#f6a341", "#8b6ef6", "#54c6d4"]
    ranked = sorted(
        aggregated.values(),
        key=lambda item: (-int(item["count"]), str(item["label"]).lower(), str(item["key"])),
    )[: max(1, int(limit))]

    return [
        {
            "label": str(item["label"]),
            "count": int(item["count"]),
            "color": palette[index % len(palette)],
        }
        for index, item in enumerate(ranked)
    ]


def load_template_type_stats_for_user(user_id: int) -> list[dict[str, Any]]:
    settings = get_mysql_settings()

    import pymysql

    ensure_mysql_schema(settings)
    ensure_user_polish_templates(int(user_id), settings)
    connection = pymysql.connect(**get_database_connection_kwargs(settings))
    try:
        with connection.cursor() as cursor:
            cursor.execute(
                """
                SELECT template_key, name, is_deleted
                FROM polish_templates
                WHERE user_id = %s
                """,
                (int(user_id),),
            )
            template_rows = cursor.fetchall()
            cursor.execute(
                """
                SELECT record_id, document_id, template_key, template_label, word_count, score
                FROM polish_records
                WHERE user_id = %s
                """,
                (int(user_id),),
            )
            rows = cursor.fetchall()
    finally:
        connection.close()

    palette = ["#2f6df6", "#35c28c", "#f6a341", "#8b6ef6", "#54c6d4", "#f05a67"]
    aggregated: dict[str, dict[str, Any]] = {}
    active_templates: dict[str, str] = {}
    deleted_template_keys: set[str] = set()
    unselected_labels = {"未选择", "未选择模板", "自定义设置", "鑷畾涔夎缃?"}

    for template_key, template_name, is_deleted in template_rows:
        normalized_key = str(template_key or "").strip()
        if not normalized_key:
            continue
        if bool(is_deleted):
            deleted_template_keys.add(normalized_key)
            continue
        active_templates[normalized_key] = str(template_name or "").strip() or normalized_key

    for record_id, document_id, template_key, template_label, word_count, score in rows:
        raw_key = str(template_key or "").strip()
        raw_label = str(template_label or "").strip()
        normalized_label = normalize_template_label_value(template_label, fallback="")
        if normalized_label in unselected_labels or raw_label in unselected_labels:
            normalized_label = ""

        if raw_key in deleted_template_keys:
            continue
        if raw_key in active_templates:
            normalized_key = raw_key
            display_label = active_templates[normalized_key] or "通用润色"
        else:
            normalized_key = "unselected"
            display_label = "未选择模板"

        document_identity = str(document_id or "").strip() or str(record_id or "").strip()
        if not document_identity:
            continue

        bucket = aggregated.setdefault(
            normalized_key,
            {
                "key": normalized_key,
                "label": display_label or "通用润色",
                "wordCount": 0,
                "polishCount": 0,
                "scoreTotal": 0.0,
                "scoreCount": 0,
                "documentKeys": set(),
            },
        )
        bucket["documentKeys"].add(document_identity)
        bucket["wordCount"] += int(word_count or 0)
        bucket["polishCount"] += 1
        if score is not None:
            bucket["scoreTotal"] += float(score)
            bucket["scoreCount"] += 1

    ranked = sorted(
        aggregated.values(),
        key=lambda item: (
            -len(item["documentKeys"]),
            -int(item["polishCount"]),
            str(item["label"]).lower(),
            str(item["key"]),
        ),
    )
    total_processed_count = sum(len(item["documentKeys"]) for item in ranked)

    return [
        {
            "label": str(item["label"]),
            "processedCount": len(item["documentKeys"]),
            "wordCount": int(item["wordCount"]),
            "averageScore": (
                round(float(item["scoreTotal"]) / int(item["scoreCount"]), 1)
                if int(item["scoreCount"]) > 0
                else 0
            ),
            "polishCount": int(item["polishCount"]),
            "ratio": (
                f"{(len(item['documentKeys']) / total_processed_count * 100):.1f}%"
                if total_processed_count
                else "0%"
            ),
            "color": palette[index % len(palette)],
        }
        for index, item in enumerate(ranked)
    ]


def load_score_distribution_for_user(user_id: int) -> dict[str, Any]:
    settings = get_mysql_settings()

    import pymysql

    ensure_mysql_schema(settings)
    bucket_meta = [
        ("90分以上", "#35c28c"),
        ("80-90分", "#5eb4ff"),
        ("60-80分", "#f5a54b"),
        ("60分以下", "#f05a67"),
    ]
    connection = pymysql.connect(**get_database_connection_kwargs(settings))
    try:
        with connection.cursor() as cursor:
            cursor.execute(
                """
                SELECT
                    AVG(score) AS average_score,
                    SUM(CASE WHEN score >= 90 THEN 1 ELSE 0 END) AS bucket_90_plus,
                    SUM(CASE WHEN score >= 80 AND score < 90 THEN 1 ELSE 0 END) AS bucket_80_90,
                    SUM(CASE WHEN score >= 60 AND score < 80 THEN 1 ELSE 0 END) AS bucket_60_80,
                    SUM(CASE WHEN score < 60 THEN 1 ELSE 0 END) AS bucket_below_60
                FROM polish_records
                WHERE user_id = %s
                  AND score IS NOT NULL
                """,
                (int(user_id),),
            )
            row = cursor.fetchone()
    finally:
        connection.close()

    average_score, bucket_90_plus, bucket_80_90, bucket_60_80, bucket_below_60 = row or (
        None,
        0,
        0,
        0,
        0,
    )
    counts = [
        int(bucket_90_plus or 0),
        int(bucket_80_90 or 0),
        int(bucket_60_80 or 0),
        int(bucket_below_60 or 0),
    ]
    total = sum(counts)
    items = [
        {
            "label": label,
            "count": count,
            "percent": f"{(count / total * 100):.1f}%" if total else "0%",
            "color": color,
        }
        for (label, color), count in zip(bucket_meta, counts)
    ]
    return {
        "averageScore": 0 if average_score is None else round(float(average_score), 1),
        "items": items,
    }


def load_tone_distribution_for_user(user_id: int) -> dict[str, Any]:
    settings = get_mysql_settings()

    import pymysql

    ensure_mysql_schema(settings)
    tone_meta = [
        ("formal", "正式", "#2f6df6"),
        ("professional", "专业", "#35c28c"),
        ("concise", "简洁", "#f6a341"),
        ("fluent", "流畅", "#8b6ef6"),
        ("friendly", "亲和", "#f05a67"),
    ]
    counts = {key: 0 for key, _, _ in tone_meta}

    connection = pymysql.connect(**get_database_connection_kwargs(settings))
    try:
        with connection.cursor() as cursor:
            cursor.execute(
                """
                SELECT COALESCE(NULLIF(tone_key, ''), 'formal') AS normalized_tone_key, COUNT(*)
                FROM polish_records
                WHERE user_id = %s
                  AND used_template = 0
                GROUP BY normalized_tone_key
                """,
                (int(user_id),),
            )
            rows = cursor.fetchall()
    finally:
        connection.close()

    for tone_key, count in rows:
        normalized_key = str(tone_key or "formal").strip() or "formal"
        if normalized_key not in counts:
            continue
        counts[normalized_key] += int(count or 0)

    total = sum(counts.values())
    items = [
        {
            "label": label,
            "count": counts[key],
            "percent": f"{(counts[key] / total * 100):.1f}%" if total else "0%",
            "color": color,
        }
        for key, label, color in tone_meta
    ]
    return {"total": total, "items": items}


def build_batch_recent_activities(documents: list[dict[str, Any]]) -> list[dict[str, str]]:
    activity_groups: list[dict[str, Any]] = []
    ordered_documents = sorted(
        documents,
        key=lambda item: (str(item.get("updatedAt") or ""), str(item.get("id") or "")),
        reverse=True,
    )
    for item in ordered_documents:
        status = str(item.get("status") or "unprocessed")
        if status == "completed":
            action = "完成润色"
            activity_type = "completed"
        elif status == "polishing":
            action = "润色中"
            activity_type = "confirm"
        elif status == "pending":
            action = "提交待确认"
            activity_type = "confirm"
        else:
            action = "批量导入"
            activity_type = "upload"
        updated_at = str(item.get("updatedAt") or "")
        group_key = (activity_type, updated_at)
        if activity_groups and activity_groups[-1]["key"] == group_key:
            activity_groups[-1]["count"] += 1
            continue
        activity_groups.append(
            {
                "key": group_key,
                "id": f"activity-{item.get('id')}",
                "type": activity_type,
                "action": action,
                "title": str(item.get("title") or "未命名文档"),
                "timeAgo": updated_at,
                "count": 1,
            }
        )
        if len(activity_groups) >= 8:
            break

    activities = []
    for group in activity_groups:
        if group["count"] > 1:
            title = f"{group['action']}：共 {group['count']} 个文件"
        else:
            title = f"{group['action']}：{group['title']}"
        activities.append(
            {
                "id": group["id"],
                "type": group["type"],
                "title": title,
                "timeAgo": group["timeAgo"],
            }
        )
    return activities


def format_batch_activity_row(row: tuple[Any, ...]) -> dict[str, str]:
    activity_id, activity_type, title, detail, created_at = row
    return {
        "id": str(activity_id or ""),
        "type": str(activity_type or "upload"),
        "title": str(title or ""),
        "detail": str(detail or ""),
        "timeAgo": format_batch_datetime(created_at),
    }


def list_batch_activities_from_database(user_id: int, limit: int = 8) -> list[dict[str, str]]:
    settings = get_mysql_settings()

    import pymysql

    ensure_mysql_schema(settings)
    connection = pymysql.connect(**get_database_connection_kwargs(settings))
    try:
        with connection.cursor() as cursor:
            cursor.execute(
                """
                SELECT activity_id, type, title, detail, created_at
                FROM batch_activities
                WHERE user_id = %s
                ORDER BY created_at DESC, id DESC
                LIMIT %s
                """,
                (int(user_id), max(1, int(limit))),
            )
            rows = cursor.fetchall()
    finally:
        connection.close()

    return [format_batch_activity_row(row) for row in rows]


def create_batch_activity_in_database(
    user_id: int,
    activity_type: str,
    title: str,
    detail: str = "",
) -> dict[str, str]:
    settings = get_mysql_settings()

    import pymysql

    ensure_mysql_schema(settings)
    activity_id = f"batch-activity-{uuid4().hex[:12]}"
    now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    connection = pymysql.connect(**get_database_connection_kwargs(settings))
    try:
        with connection.cursor() as cursor:
            cursor.execute(
                """
                INSERT INTO batch_activities (
                    user_id,
                    activity_id,
                    type,
                    title,
                    detail,
                    created_at
                )
                VALUES (%s, %s, %s, %s, %s, %s)
                """,
                (
                    int(user_id),
                    activity_id,
                    str(activity_type or "upload")[:32],
                    str(title or "")[:255],
                    str(detail or ""),
                    now,
                ),
            )
        connection.commit()
    finally:
        connection.close()

    return {
        "id": activity_id,
        "type": str(activity_type or "upload")[:32],
        "title": str(title or "")[:255],
        "detail": str(detail or ""),
        "timeAgo": format_batch_datetime(now),
    }


def load_batch_processing_from_database(user_id: int) -> dict[str, Any]:
    documents = list_batch_documents_from_database(int(user_id))
    templates = sorted({str(item.get("templateType") or "") for item in documents if item.get("templateType")})
    activities = list_batch_activities_from_database(int(user_id))
    if not activities:
        activities = build_batch_recent_activities(documents)
    return {
        "summary": build_batch_summary(documents),
        "distribution": build_batch_distribution(documents),
        "templates": templates,
        "documents": documents,
        "recentActivities": activities,
    }


def create_batch_document_in_database(user_id: int, payload: dict[str, Any]) -> dict[str, Any]:
    settings = get_mysql_settings()

    import pymysql

    ensure_mysql_schema(settings)
    document_id = str(payload.get("id") or f"batch-doc-{uuid4().hex[:10]}")
    now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    connection = pymysql.connect(**get_database_connection_kwargs(settings))
    try:
        with connection.cursor() as cursor:
            cursor.execute(
                """
                INSERT INTO batch_documents (
                    user_id,
                    document_id,
                    title,
                    category,
                    file_type,
                    template_type,
                    word_count,
                    status,
                    original_filename,
                    storage_path,
                    result_text,
                    has_result,
                    created_at,
                    updated_at
                )
                VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
                """,
                (
                    int(user_id),
                    document_id,
                    str(payload.get("title") or payload.get("filename") or "未命名文档")[:255],
                    str(payload.get("category") or "批量导入")[:120],
                    normalize_batch_file_type(payload.get("fileType")),
                    normalize_batch_template_type(payload.get("templateType"))[:120],
                    max(0, int(payload.get("wordCount") or 0)),
                    str(payload.get("status") or "unprocessed"),
                    str(payload.get("filename") or "")[:255],
                    str(payload.get("storagePath") or "")[:500],
                    str(payload.get("resultText") or ""),
                    1 if payload.get("hasResult") else 0,
                    now,
                    now,
                ),
            )
    finally:
        connection.close()

    return next(
        item for item in list_batch_documents_from_database(int(user_id)) if item["id"] == document_id
    )


def _format_demo_datetime(value: datetime) -> str:
    return value.replace(microsecond=0).strftime("%Y-%m-%d %H:%M:%S")


def _normalize_demo_text(value: str) -> str:
    return "".join(str(value or "").split())


def _count_demo_words(value: str) -> int:
    return len(_normalize_demo_text(value))


def _build_demo_dimensions(score: int) -> list[dict[str, Any]]:
    base = max(78, min(98, int(score)))
    return [
        {"label": "表达清晰度", "value": base},
        {"label": "逻辑完整性", "value": max(72, base - 2)},
        {"label": "风格一致性", "value": max(70, base - 1)},
        {"label": "专业准确性", "value": max(74, base - 3)},
    ]


def _build_demo_suggestions(score: int, template_label: str) -> list[dict[str, Any]]:
    if score >= 92:
        return [
            {"label": f"{template_label}表达已优化", "count": 4},
            {"label": "长句已压缩", "count": 3},
            {"label": "关键结论已前置", "count": 2},
        ]
    return [
        {"label": "长句拆分", "count": 4},
        {"label": "逻辑衔接增强", "count": 3},
        {"label": f"{template_label}语气校准", "count": 2},
    ]


def _relative_storage_text(path: Path) -> str:
    return path.resolve().relative_to(BASE_DIR).as_posix()


def _write_demo_text_file(path: Path, content: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    normalized = str(content or "").replace("\r\n", "\n")
    if path.exists():
        try:
            if path.read_text(encoding="utf-8") == normalized:
                return
        except OSError:
            pass
    with path.open("w", encoding="utf-8", newline="\n") as handle:
        handle.write(normalized)


def _write_demo_json_file(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    normalized = json.dumps(payload, ensure_ascii=False, indent=2)
    if path.exists():
        try:
            if path.read_text(encoding="utf-8") == normalized:
                return
        except OSError:
            pass
    with path.open("w", encoding="utf-8", newline="\n") as handle:
        handle.write(normalized)


def _build_demo_source_text(
    profile: str,
    template_name: str,
    topic_prefix: str,
    topic_label: str,
    day_index: int,
    item_index: int,
) -> str:
    return (
        f"{profile}场景下的《{topic_prefix}{topic_label}》原稿需要整理给团队评审，"
        f"当前版本第 {day_index + 1} 天第 {item_index + 1} 轮，整体信息完整，但表达略显口语化，"
        f"部分结论放在段末，阅读者需要花较多时间才能抓到重点。\n\n"
        f"本次希望按“{template_name}”的风格统一整理，保留既有事实、结论与行动项，"
        f"重点优化逻辑衔接、措辞准确度和版式层次，让内容更适合用于正式汇报、跨部门同步或对外展示。\n\n"
        f"需要保留的核心信息包括：阶段目标、当前进度、关键风险、资源安排以及下一步计划。"
        f"如果是面向管理层的文本，要让摘要先给结论，再补背景说明。"
    )


def _build_demo_result_text(
    profile: str,
    template_name: str,
    topic_prefix: str,
    topic_label: str,
    score: int,
) -> str:
    return (
        f"《{topic_prefix}{topic_label}》已按{template_name}风格完成整理，现将核心内容归纳如下：\n"
        f"一是围绕{profile}场景先行呈现阶段结论，明确当前工作已形成可执行方案，整体表述更适合正式评审与汇报。\n"
        f"二是补齐背景说明、关键节点与风险提示，确保阅读者在短时间内能够理解事项来龙去脉，并快速识别需要决策的重点。\n"
        f"三是将后续动作、责任分工与时间安排单独列示，使文本逻辑更清晰、信息密度更均衡，最终稿整体质量评分稳定在 {score} 分左右。"
    )


def _build_demo_polish_record(
    account_spec: dict[str, Any],
    template: dict[str, Any],
    created_at: datetime,
    index: int,
) -> dict[str, Any]:
    template_key = str(template.get("key") or "general")
    template_name = str(template.get("name") or template.get("label") or "通用润色")
    topic_prefix = str(account_spec.get("topicPrefix") or "演示文稿")
    topic_label = f"{DEMO_POLISH_CATEGORIES[index % len(DEMO_POLISH_CATEGORIES)]}{index + 1:02d}"
    source_text = _build_demo_source_text(
        str(account_spec.get("profile") or "通用"),
        template_name,
        topic_prefix,
        topic_label,
        created_at.day % 30,
        index,
    )
    score = 84 + ((index + len(template_key)) % 14)
    result_text = _build_demo_result_text(
        str(account_spec.get("profile") or "通用"),
        template_name,
        topic_prefix,
        topic_label,
        score,
    )
    source_count = _count_demo_words(source_text)
    result_count = _count_demo_words(result_text)
    full_summary = (
        f"本次将《{topic_prefix}{topic_label}》中的背景说明、核心结论、风险提示与下一步动作重新编排，"
        f"确保内容适合在{account_spec.get('profile')}场景下直接汇报或复用。"
    )
    return {
        "id": f"demo-polish-{account_spec['username']}-{created_at.strftime('%Y%m%d')}-{index + 1:02d}",
        "documentId": f"demo-doc-{account_spec['username']}-{index + 1:03d}",
        "title": f"{account_spec['displayName']}_{topic_label}.docx",
        "sourceText": source_text,
        "resultText": result_text,
        "templateLabel": template_name,
        "template": template_key,
        "score": score,
        "wordCount": {
            "source": source_count,
            "result": result_count,
            "delta": result_count - source_count,
        },
        "createdAt": _format_demo_datetime(created_at),
        "strength": DEMO_STRENGTH_SEQUENCE[index % len(DEMO_STRENGTH_SEQUENCE)],
        "tone": DEMO_TONE_SEQUENCE[index % len(DEMO_TONE_SEQUENCE)],
        "options": DEMO_OPTION_SEQUENCE[index % len(DEMO_OPTION_SEQUENCE)],
        "usedTemplate": True,
        "revisionSegments": _build_polish_record_revision_segments(source_text, result_text),
        "changes": [],
        "fullSummary": full_summary,
        "paragraphCount": max(1, result_text.count("\n") + 1),
        "llmConcurrency": 2,
        "llmRetryCount": 0,
        "failedParagraphInfo": "",
        "llmLatencyMs": 820 + (index % 5) * 70,
        "llmModel": "deepseek-v4-flash",
        "scoringJson": {"dimensions": _build_demo_dimensions(score)},
        "scoringModel": "deepseek-v4-flash",
        "scoringLatencyMs": 240 + (index % 4) * 20,
    }


def _build_demo_batch_result_payload(
    *,
    source_text: str,
    result_text: str,
    template_label: str,
    created_at: str,
    score: int,
) -> dict[str, Any]:
    source_count = _count_demo_words(source_text)
    result_count = _count_demo_words(result_text)
    return {
        "sourceText": source_text,
        "resultText": result_text,
        "templateLabel": template_label,
        "templateType": template_label,
        "score": score,
        "dimensions": _build_demo_dimensions(score),
        "suggestions": _build_demo_suggestions(score, template_label),
        "summary": _build_polish_record_summary_text(result_text, ""),
        "fullSummary": (
            f"本次批量结果已完成结构压缩、措辞统一和要点前置，整体更适合集中汇报、资料归档和跨部门共享。"
        ),
        "wordCount": {
            "source": source_count,
            "result": result_count,
            "delta": result_count - source_count,
        },
        "createdAt": created_at,
        "changes": [],
        "compareSections": _build_polish_record_compare_sections(source_text, result_text),
    }


def _build_demo_batch_activity_detail(documents: list[dict[str, str]], extra: dict[str, Any] | None = None) -> str:
    payload: dict[str, Any] = {
        "filenames": [str(item.get("filename") or "") for item in documents if item.get("filename")],
        "documents": documents,
    }
    if extra:
        payload.update(extra)
    return json.dumps(payload, ensure_ascii=False)


def _ensure_demo_user(cursor: Any, account_spec: dict[str, Any], now: datetime) -> int:
    cursor.execute("SELECT id FROM users WHERE username = %s LIMIT 1", (str(account_spec["username"]),))
    row = cursor.fetchone()
    if row is not None:
        return int(row[0])

    password_hash, password_salt = hash_password(str(account_spec.get("password") or DEMO_ACCOUNT_PASSWORD))
    created_at = _format_demo_datetime(now - timedelta(days=35))
    last_login_at = _format_demo_datetime(now - timedelta(days=1, hours=2))
    cursor.execute(
        """
        INSERT INTO users (
            username,
            email,
            password_hash,
            password_salt,
            display_name,
            avatar_text,
            created_at,
            last_login_at
        )
        VALUES (%s, %s, %s, %s, %s, %s, %s, %s)
        """,
        (
            str(account_spec["username"]),
            str(account_spec.get("email") or ""),
            password_hash,
            password_salt,
            str(account_spec.get("displayName") or account_spec["username"]),
            str(account_spec.get("avatarText") or str(account_spec["username"])[0])[:8],
            created_at,
            last_login_at,
        ),
    )
    return int(cursor.lastrowid)


def _seed_demo_usage_event_if_missing(cursor: Any, user_id: int, source: str, word_count: int, score: int, created_at: str) -> None:
    cursor.execute("SELECT 1 FROM usage_events WHERE event_source = %s LIMIT 1", (source,))
    if cursor.fetchone() is not None:
        return
    cursor.execute(
        """
        INSERT INTO usage_events (user_id, event_type, word_count, score, event_source, created_at)
        VALUES (%s, 'polish', %s, %s, %s, %s)
        """,
        (int(user_id), max(0, int(word_count)), max(0, min(100, float(score))), source[:64], created_at),
    )


def _seed_demo_polish_records(cursor: Any, user_id: int, account_spec: dict[str, Any], template_map: dict[str, dict[str, Any]], now: datetime) -> None:
    template_list = [template_map[key] for key in template_map]
    seed_count = max(0, int(account_spec.get("polishSeedCount") or 0))
    user_shift = sum(ord(char) for char in str(account_spec.get("username") or "")) % max(1, len(template_list))

    for index in range(seed_count):
        created_at = now - timedelta(days=(index + user_shift) % 30, hours=8 + (index % 6))
        template = template_list[(index + user_shift) % len(template_list)]
        record = _build_demo_polish_record(account_spec, template, created_at, index)
        save_polish_record(int(user_id), record)
        event_source = f"demo-seed:polish:{account_spec['username']}:{created_at.strftime('%Y%m%d')}:{index + 1:02d}"
        word_count = int((record.get("wordCount") or {}).get("result") or 0)
        score = int(record.get("score") or 0)
        _seed_demo_usage_event_if_missing(
            cursor,
            int(user_id),
            event_source,
            word_count,
            score,
            str(record.get("createdAt") or _format_demo_datetime(created_at)),
        )


def _seed_demo_batch_documents(cursor: Any, user_id: int, account_spec: dict[str, Any], template_map: dict[str, dict[str, Any]], now: datetime) -> None:
    seed_count = max(0, int(account_spec.get("batchSeedCount") or 0))
    if not seed_count:
        return

    template_list = [template_map[key] for key in template_map]
    user_root = (BATCH_UPLOADS_DIR / str(int(user_id))).resolve()
    user_root.mkdir(parents=True, exist_ok=True)
    user_shift = sum(ord(char) for char in str(account_spec.get("username") or "")) % max(1, len(template_list))

    seeded_documents: list[dict[str, Any]] = []

    for index in range(seed_count):
        created_at = now - timedelta(days=(index + user_shift) % 18, hours=2 + (index % 5))
        status = "completed" if index < max(3, seed_count // 2) else ("pending" if index < seed_count - 2 else "unprocessed")
        template = template_list[(index + user_shift) % len(template_list)]
        template_label = str(template.get("name") or template.get("label") or "通用润色")
        topic_label = f"{DEMO_BATCH_CATEGORIES[index % len(DEMO_BATCH_CATEGORIES)]}{index + 1:02d}"
        source_text = _build_demo_source_text(
            str(account_spec.get("profile") or "通用"),
            template_label,
            str(account_spec.get("topicPrefix") or "演示材料"),
            topic_label,
            created_at.day % 30,
            index,
        )
        score = 85 + ((index + user_shift) % 11)
        result_text = (
            _build_demo_result_text(
                str(account_spec.get("profile") or "通用"),
                template_label,
                str(account_spec.get("topicPrefix") or "演示材料"),
                topic_label,
                score,
            )
            if status != "unprocessed"
            else ""
        )

        document_id = f"demo-batch-{account_spec['username']}-{index + 1:03d}"
        filename = f"{account_spec['username']}_{index + 1:02d}_batch-{(index % len(DEMO_BATCH_CATEGORIES)) + 1:02d}.txt"
        source_path = (user_root / filename).resolve()
        result_path = source_path.with_name(f"{source_path.stem}.polished.txt")
        sidecar_path = source_path.with_name(f"{source_path.stem}.polished.json")
        storage_path_text = _relative_storage_text(source_path)
        result_path_text = _relative_storage_text(result_path) if status != "unprocessed" else ""
        sidecar_path_text = _relative_storage_text(sidecar_path) if status != "unprocessed" else ""
        processed_at = created_at + timedelta(hours=2, minutes=index * 3)
        confirmed_at = processed_at + timedelta(hours=4) if status == "completed" else None
        updated_at = confirmed_at or processed_at if status != "unprocessed" else created_at
        source_count = _count_demo_words(source_text)
        processed_count = _count_demo_words(result_text) if result_text else 0

        _write_demo_text_file(source_path, source_text)
        if status != "unprocessed":
            _write_demo_text_file(result_path, result_text)
            _write_demo_json_file(
                sidecar_path,
                _build_demo_batch_result_payload(
                    source_text=source_text,
                    result_text=result_text,
                    template_label=template_label,
                    created_at=_format_demo_datetime(processed_at),
                    score=score,
                ),
            )

        cursor.execute(
            """
            INSERT INTO batch_documents (
                user_id,
                document_id,
                title,
                category,
                file_type,
                template_type,
                word_count,
                processed_word_count,
                score,
                status,
                original_filename,
                storage_path,
                result_file_path,
                result_detail_path,
                result_text,
                has_result,
                processed_at,
                confirmed_at,
                created_at,
                updated_at
            )
            VALUES (%s, %s, %s, %s, 'TXT', %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
            ON DUPLICATE KEY UPDATE
                title = VALUES(title),
                category = VALUES(category),
                file_type = VALUES(file_type),
                template_type = VALUES(template_type),
                word_count = VALUES(word_count),
                processed_word_count = VALUES(processed_word_count),
                score = VALUES(score),
                status = VALUES(status),
                original_filename = VALUES(original_filename),
                storage_path = VALUES(storage_path),
                result_file_path = VALUES(result_file_path),
                result_detail_path = VALUES(result_detail_path),
                result_text = VALUES(result_text),
                has_result = VALUES(has_result),
                processed_at = VALUES(processed_at),
                confirmed_at = VALUES(confirmed_at),
                created_at = VALUES(created_at),
                updated_at = VALUES(updated_at)
            """,
            (
                int(user_id),
                document_id,
                f"{account_spec['topicPrefix']}{topic_label}",
                DEMO_BATCH_CATEGORIES[index % len(DEMO_BATCH_CATEGORIES)],
                template_label[:120],
                source_count,
                processed_count,
                score if status != "unprocessed" else None,
                status,
                filename,
                storage_path_text,
                result_path_text,
                sidecar_path_text,
                result_text,
                0 if status == "unprocessed" else 1,
                _format_demo_datetime(processed_at) if status != "unprocessed" else None,
                _format_demo_datetime(confirmed_at) if confirmed_at else None,
                _format_demo_datetime(created_at),
                _format_demo_datetime(updated_at),
            ),
        )

        seeded_documents.append(
            {
                "documentId": document_id,
                "title": f"{account_spec['topicPrefix']}{topic_label}",
                "filename": filename,
                "templateLabel": template_label,
                "status": status,
                "createdAt": _format_demo_datetime(created_at),
                "processedAt": _format_demo_datetime(processed_at),
                "confirmedAt": _format_demo_datetime(confirmed_at) if confirmed_at else "",
            }
        )

    uploaded_documents = seeded_documents[: min(6, len(seeded_documents))]
    completed_documents = [item for item in seeded_documents if item["status"] == "completed"][: min(5, len(seeded_documents))]
    pending_documents = [item for item in seeded_documents if item["status"] == "pending"][: min(4, len(seeded_documents))]
    export_documents = completed_documents[: min(3, len(completed_documents))]

    activity_specs = [
        {
            "activityId": f"demo-activity-{account_spec['username']}-upload",
            "type": "upload",
            "title": f"{DEMO_BATCH_ACTIVITY_LABELS['upload']}：共 {len(uploaded_documents)} 个文件",
            "detail": _build_demo_batch_activity_detail(uploaded_documents, {"count": len(uploaded_documents)}),
            "createdAt": _format_demo_datetime(now - timedelta(hours=3)),
        },
        {
            "activityId": f"demo-activity-{account_spec['username']}-template",
            "type": "template",
            "title": f"{DEMO_BATCH_ACTIVITY_LABELS['template']}：已批量应用模板",
            "detail": _build_demo_batch_activity_detail(
                uploaded_documents,
                {
                    "count": len(uploaded_documents),
                    "templateLabel": uploaded_documents[0]["templateLabel"] if uploaded_documents else "通用润色",
                },
            ),
            "createdAt": _format_demo_datetime(now - timedelta(hours=2, minutes=40)),
        },
        {
            "activityId": f"demo-activity-{account_spec['username']}-completed",
            "type": "completed",
            "title": f"{DEMO_BATCH_ACTIVITY_LABELS['completed']}：共 {len(completed_documents)} 个文件",
            "detail": _build_demo_batch_activity_detail(completed_documents, {"count": len(completed_documents)}),
            "createdAt": _format_demo_datetime(now - timedelta(hours=2)),
        },
        {
            "activityId": f"demo-activity-{account_spec['username']}-confirm",
            "type": "confirm",
            "title": f"{DEMO_BATCH_ACTIVITY_LABELS['confirm']}：共 {len(pending_documents)} 个文件待确认",
            "detail": _build_demo_batch_activity_detail(pending_documents, {"count": len(pending_documents)}),
            "createdAt": _format_demo_datetime(now - timedelta(hours=1, minutes=20)),
        },
        {
            "activityId": f"demo-activity-{account_spec['username']}-export",
            "type": "export",
            "title": f"{DEMO_BATCH_ACTIVITY_LABELS['export']}：共 {len(export_documents)} 个文件",
            "detail": _build_demo_batch_activity_detail(export_documents, {"count": len(export_documents)}),
            "createdAt": _format_demo_datetime(now - timedelta(minutes=40)),
        },
    ]

    for activity in activity_specs:
        if not json.loads(activity["detail"]).get("documents"):
            continue
        cursor.execute(
            """
            INSERT INTO batch_activities (
                user_id,
                activity_id,
                type,
                title,
                detail,
                created_at
            )
            VALUES (%s, %s, %s, %s, %s, %s)
            ON DUPLICATE KEY UPDATE
                type = VALUES(type),
                title = VALUES(title),
                detail = VALUES(detail),
                created_at = VALUES(created_at)
            """,
            (
                int(user_id),
                str(activity["activityId"]),
                str(activity["type"]),
                str(activity["title"]),
                str(activity["detail"]),
                str(activity["createdAt"]),
            ),
        )


def seed_demo_accounts_with_activity(settings: MySQLSettings | None = None) -> None:
    settings = settings or get_mysql_settings()

    import pymysql

    ensure_mysql_schema(settings)
    standard_templates = [template for template in get_standard_polish_templates() if template.get("enabled", True)]
    if not standard_templates:
        return
    template_map = {str(template.get("key") or ""): template for template in standard_templates if template.get("key")}
    now = datetime.now().replace(minute=0, second=0, microsecond=0)

    connection = pymysql.connect(**get_database_connection_kwargs(settings))
    try:
        with connection.cursor() as cursor:
            seed_notification_setting_types_if_missing(cursor)
            for account_spec in DEMO_ACCOUNT_SPECS:
                user_id = _ensure_demo_user(cursor, account_spec, now)
                seed_user_polish_templates_if_missing(cursor, int(user_id))
                seed_user_notification_email_settings_if_missing(cursor, int(user_id))
                _seed_demo_polish_records(cursor, int(user_id), account_spec, template_map, now)
                _seed_demo_batch_documents(cursor, int(user_id), account_spec, template_map, now)
    finally:
        connection.close()


def initialize_usage_database() -> None:
    settings = get_mysql_settings()
    ensure_mysql_schema(settings)
    seed_usage_events_if_empty(settings)
    seed_notifications_if_needed(settings)
    seed_notification_setting_types(settings)
    seed_polish_templates_if_empty(settings)
    seed_user_polish_templates_for_existing_users(settings)
    seed_user_notification_email_settings_for_existing_users(settings)
    backfill_batch_processed_metrics_from_sidecars(settings)
    seed_demo_accounts_with_activity(settings)


def seed_notifications_if_needed(settings: MySQLSettings | None = None) -> None:
    settings = settings or get_mysql_settings()

    import pymysql

    connection = pymysql.connect(**get_database_connection_kwargs(settings))
    try:
        with connection.cursor() as cursor:
            cursor.execute("SELECT COUNT(*) FROM notifications")
            count = int(cursor.fetchone()[0] or 0)
            missing_count = max(0, len(SEED_NOTIFICATIONS) - count)
            if not missing_count:
                return

            cursor.execute("SELECT id FROM notifications")
            existing_ids = {row[0] for row in cursor.fetchall()}
            now = datetime.now().replace(microsecond=0)
            seed_rows = []
            for index, notification in enumerate(SEED_NOTIFICATIONS):
                if len(seed_rows) >= missing_count:
                    break
                if notification["id"] in existing_ids:
                    continue
                created_at = now - timedelta(hours=index * 3)
                seed_rows.append(
                    (
                        notification["id"],
                        notification["title"],
                        notification["summary"],
                        notification["content"],
                        1 if notification["isRead"] else 0,
                        created_at.strftime("%Y-%m-%d %H:%M:%S"),
                        created_at.strftime("%Y-%m-%d %H:%M:%S"),
                    )
                )

            if seed_rows:
                cursor.executemany(
                    """
                    INSERT INTO notifications
                        (id, title, summary, content, is_read, created_at, updated_at)
                    VALUES (%s, %s, %s, %s, %s, %s, %s)
                    """,
                    seed_rows,
                )
    finally:
        connection.close()


def seed_notification_setting_types_if_missing(cursor: Any) -> None:
    seed_rows = load_notification_setting_seed_rows()
    if not seed_rows:
        return

    now = datetime.now().replace(microsecond=0).strftime("%Y-%m-%d %H:%M:%S")
    cursor.executemany(
        """
        INSERT INTO notification_setting_types
            (`key`, title, description, icon, sort_order, is_active, created_at, updated_at)
        VALUES (%s, %s, %s, %s, %s, %s, %s, %s)
        ON DUPLICATE KEY UPDATE
            title = VALUES(title),
            description = VALUES(description),
            icon = VALUES(icon),
            sort_order = VALUES(sort_order),
            is_active = VALUES(is_active),
            updated_at = VALUES(updated_at)
        """,
        [
            (
                str(item.get("key") or ""),
                str(item.get("title") or ""),
                str(item.get("description") or ""),
                str(item.get("icon") or ""),
                int(item.get("sortOrder") or 0),
                1,
                now,
                now,
            )
            for item in seed_rows
        ],
    )


def seed_notification_setting_types(settings: MySQLSettings | None = None) -> None:
    settings = settings or get_mysql_settings()

    import pymysql

    ensure_mysql_schema(settings)
    connection = pymysql.connect(**get_database_connection_kwargs(settings))
    try:
        with connection.cursor() as cursor:
            seed_notification_setting_types_if_missing(cursor)
        connection.commit()
    finally:
        connection.close()


def seed_user_notification_email_settings_if_missing(cursor: Any, user_id: int) -> None:
    seed_rows = load_notification_setting_seed_rows()
    if not seed_rows:
        return

    seed_notification_setting_types_if_missing(cursor)
    cursor.execute(
        "SELECT notification_key FROM user_notification_email_settings WHERE user_id = %s",
        (int(user_id),),
    )
    existing_keys = {str(row[0] or "") for row in cursor.fetchall()}
    pending_rows = []
    now = datetime.now().replace(microsecond=0).strftime("%Y-%m-%d %H:%M:%S")
    for item in seed_rows:
        notification_key = str(item.get("key") or "")
        if not notification_key or notification_key in existing_keys:
            continue
        pending_rows.append(
            (
                int(user_id),
                notification_key,
                1 if bool(item.get("emailEnabled", False)) else 0,
                now,
                now,
            )
        )

    if pending_rows:
        cursor.executemany(
            """
            INSERT INTO user_notification_email_settings
                (user_id, notification_key, email_enabled, created_at, updated_at)
            VALUES (%s, %s, %s, %s, %s)
            """,
            pending_rows,
        )


def ensure_user_notification_email_settings(user_id: int, settings: MySQLSettings | None = None) -> None:
    settings = settings or get_mysql_settings()

    import pymysql

    ensure_mysql_schema(settings)
    connection = pymysql.connect(**get_database_connection_kwargs(settings))
    try:
        with connection.cursor() as cursor:
            seed_user_notification_email_settings_if_missing(cursor, int(user_id))
        connection.commit()
    finally:
        connection.close()


def seed_user_notification_email_settings_for_existing_users(settings: MySQLSettings | None = None) -> None:
    settings = settings or get_mysql_settings()

    import pymysql

    ensure_mysql_schema(settings)
    connection = pymysql.connect(**get_database_connection_kwargs(settings))
    try:
        with connection.cursor() as cursor:
            seed_notification_setting_types_if_missing(cursor)
            cursor.execute("SELECT id FROM users")
            for row in cursor.fetchall():
                seed_user_notification_email_settings_if_missing(cursor, int(row[0]))
        connection.commit()
    finally:
        connection.close()


def format_datetime(value: Any) -> str:
    if isinstance(value, datetime):
        return value.strftime("%Y-%m-%d %H:%M:%S")
    return str(value or "")


def build_notification(row: tuple[Any, ...]) -> dict[str, Any]:
    return {
        "id": row[0],
        "title": row[1],
        "summary": row[2],
        "content": row[3],
        "isRead": bool(row[4]),
        "createdAt": format_datetime(row[5]),
    }


def hash_password(password: str, salt: str | None = None) -> tuple[str, str]:
    salt = salt or secrets.token_hex(16)
    digest = hashlib.pbkdf2_hmac("sha256", password.encode("utf-8"), salt.encode("utf-8"), 120_000)
    return digest.hex(), salt


def verify_password(password: str, password_hash: str, salt: str) -> bool:
    candidate_hash, _ = hash_password(password, salt)
    return hmac.compare_digest(candidate_hash, password_hash)


def is_within_directory(target: Path, root: Path) -> bool:
    try:
        target.resolve().relative_to(root.resolve())
        return True
    except ValueError:
        return False


def resolve_user_batch_cleanup_path(user_id: int, path_text: Any) -> Path | None:
    normalized = str(path_text or "").strip().replace("\\", "/")
    if not normalized:
        return None

    resolved = (BASE_DIR / normalized).resolve()
    user_root = (BATCH_UPLOADS_DIR / str(int(user_id))).resolve()
    if not is_within_directory(resolved, user_root):
        raise ValueError("账号数据文件路径无效，无法注销账号。")
    return resolved


def collect_user_account_cleanup_paths(user_id: int, rows: list[tuple[Any, ...]]) -> list[Path]:
    cleanup_paths: list[Path] = []
    seen_paths: set[Path] = set()

    for row in rows:
        for path_text in row:
            resolved = resolve_user_batch_cleanup_path(int(user_id), path_text)
            if resolved is None or resolved in seen_paths:
                continue
            seen_paths.add(resolved)
            cleanup_paths.append(resolved)

    return cleanup_paths


def remove_empty_user_upload_dirs(user_id: int) -> None:
    user_root = (BATCH_UPLOADS_DIR / str(int(user_id))).resolve()
    if not user_root.exists():
        return

    for directory in sorted((path for path in user_root.rglob("*") if path.is_dir()), key=lambda item: len(item.parts), reverse=True):
        try:
            directory.rmdir()
        except OSError:
            continue

    try:
        user_root.rmdir()
    except OSError:
        pass


def is_valid_email(email: str) -> bool:
    return bool(email) and "@" in email and "." in email.split("@")[-1]


def build_user(row: tuple[Any, ...]) -> dict[str, Any]:
    return {
        "id": int(row[0]),
        "username": row[1],
        "displayName": row[2],
        "avatarText": row[3],
    }


def build_settings_profile(row: tuple[Any, ...]) -> dict[str, Any]:
    username = str(row[0] or "")
    avatar_text = str(row[4] or "") or username[:1]
    return {
        "username": username,
        "email": str(row[1] or ""),
        "emailVerified": True,
        "role": "普通用户",
        "registeredAt": format_datetime(row[2]),
        "lastLoginAt": format_datetime(row[3]),
        "avatarText": avatar_text,
    }


def get_auth_secret() -> bytes:
    secret = os.getenv("AUTH_TOKEN_SECRET", "document-polish-system-dev-secret")
    return secret.encode("utf-8")


def encode_token_part(payload: bytes) -> str:
    return base64.urlsafe_b64encode(payload).decode("utf-8").rstrip("=")


def decode_token_part(payload: str) -> bytes:
    padding = "=" * (-len(payload) % 4)
    return base64.urlsafe_b64decode(payload + padding)


def issue_auth_token(user: dict[str, Any]) -> str:
    payload = {
        "sub": int(user["id"]),
        "username": user["username"],
        "exp": int((datetime.now() + timedelta(seconds=AUTH_TOKEN_TTL_SECONDS)).timestamp()),
    }
    encoded_payload = encode_token_part(json.dumps(payload, ensure_ascii=False, separators=(",", ":")).encode("utf-8"))
    signature = hmac.new(get_auth_secret(), encoded_payload.encode("utf-8"), hashlib.sha256).digest()
    return f"{encoded_payload}.{encode_token_part(signature)}"


def parse_auth_token(token: str) -> dict[str, Any]:
    try:
        encoded_payload, encoded_signature = token.split(".", 1)
    except ValueError as exc:
        raise ValueError("Invalid token") from exc

    expected_signature = hmac.new(get_auth_secret(), encoded_payload.encode("utf-8"), hashlib.sha256).digest()
    try:
        provided_signature = decode_token_part(encoded_signature)
    except Exception as exc:
        raise ValueError("Invalid token") from exc
    if not hmac.compare_digest(expected_signature, provided_signature):
        raise ValueError("Invalid token")

    try:
        payload = json.loads(decode_token_part(encoded_payload).decode("utf-8"))
    except Exception as exc:
        raise ValueError("Invalid token") from exc
    if int(payload.get("exp") or 0) < int(datetime.now().timestamp()):
        raise ValueError("Token expired")
    return payload


def get_user_by_id(user_id: int) -> dict[str, Any]:
    settings = get_mysql_settings()

    import pymysql

    ensure_mysql_schema(settings)
    connection = pymysql.connect(**get_database_connection_kwargs(settings))
    try:
        with connection.cursor() as cursor:
            cursor.execute(
                "SELECT id, username, display_name, avatar_text FROM users WHERE id = %s",
                (user_id,),
            )
            row = cursor.fetchone()
            if row is None:
                raise KeyError(user_id)
            return build_user(row)
    finally:
        connection.close()


def get_user_from_token(token: str) -> dict[str, Any]:
    payload = parse_auth_token(token)
    return get_user_by_id(int(payload["sub"]))


def load_settings_profile_from_database(user_id: int) -> dict[str, Any]:
    settings = get_mysql_settings()

    import pymysql

    ensure_mysql_schema(settings)
    connection = pymysql.connect(**get_database_connection_kwargs(settings))
    try:
        with connection.cursor() as cursor:
            cursor.execute(
                """
                SELECT username, email, created_at, last_login_at, avatar_text
                FROM users
                WHERE id = %s
                """,
                (int(user_id),),
            )
            row = cursor.fetchone()
            if row is None:
                raise KeyError(user_id)
            return build_settings_profile(row)
    finally:
        connection.close()


def update_settings_profile_in_database(user_id: int, payload: dict[str, Any]) -> dict[str, Any]:
    settings = get_mysql_settings()

    import pymysql

    username = str(payload.get("username", "")).strip()
    email = str(payload.get("email", "")).strip().lower()
    if not username:
        raise ValueError("用户名不能为空。")
    if not is_valid_email(email):
        raise ValueError("邮箱格式不正确。")

    ensure_mysql_schema(settings)
    connection = pymysql.connect(**get_database_connection_kwargs(settings))
    try:
        with connection.cursor() as cursor:
            cursor.execute(
                "SELECT id FROM users WHERE username = %s AND id <> %s",
                (username, int(user_id)),
            )
            if cursor.fetchone() is not None:
                raise ValueError("用户名已存在。")
            cursor.execute(
                """
                UPDATE users
                SET username = %s,
                    email = %s,
                    display_name = %s,
                    avatar_text = %s,
                    updated_at = CURRENT_TIMESTAMP
                WHERE id = %s
                """,
                (username, email, username, username[:1], int(user_id)),
            )
        connection.commit()
    finally:
        connection.close()

    return load_settings_profile_from_database(int(user_id))


def load_settings_notifications_from_database(user_id: int) -> list[dict[str, Any]]:
    settings = get_mysql_settings()

    import pymysql

    ensure_mysql_schema(settings)
    ensure_user_notification_email_settings(int(user_id), settings)
    connection = pymysql.connect(**get_database_connection_kwargs(settings))
    try:
        with connection.cursor() as cursor:
            cursor.execute(
                """
                SELECT
                    t.`key`,
                    COALESCE(s.email_enabled, 0) AS email_enabled
                FROM notification_setting_types t
                LEFT JOIN user_notification_email_settings s
                  ON s.notification_key = t.`key`
                 AND s.user_id = %s
                WHERE t.is_active = 1
                ORDER BY t.sort_order ASC, t.`key` ASC
                """,
                (int(user_id),),
            )
            return [
                {
                    "key": str(row[0] or ""),
                    "emailEnabled": bool(row[1]),
                }
                for row in cursor.fetchall()
            ]
    finally:
        connection.close()


def update_settings_notifications_in_database(user_id: int, payload: dict[str, Any]) -> list[dict[str, Any]]:
    settings = get_mysql_settings()

    import pymysql

    updates = payload.get("notifications", payload)
    if not isinstance(updates, list):
        raise ValueError("通知设置格式不正确。")

    ensure_mysql_schema(settings)
    connection = pymysql.connect(**{**get_database_connection_kwargs(settings), "autocommit": False})
    try:
        with connection.cursor() as cursor:
            seed_notification_setting_types_if_missing(cursor)
            seed_user_notification_email_settings_if_missing(cursor, int(user_id))
            cursor.execute(
                "SELECT `key` FROM notification_setting_types WHERE is_active = 1"
            )
            valid_keys = {str(row[0] or "") for row in cursor.fetchall()}
            update_rows = [
                (
                    int(user_id),
                    key,
                    1 if bool(item.get("emailEnabled", False)) else 0,
                )
                for item in updates
                if isinstance(item, dict)
                for key in [str(item.get("key") or "").strip()]
                if key in valid_keys
            ]
            if update_rows:
                cursor.executemany(
                    """
                    INSERT INTO user_notification_email_settings
                        (user_id, notification_key, email_enabled)
                    VALUES (%s, %s, %s)
                    ON DUPLICATE KEY UPDATE email_enabled = VALUES(email_enabled)
                    """,
                    update_rows,
                )
        connection.commit()
    finally:
        connection.close()

    return load_settings_notifications_from_database(int(user_id))


def change_user_password(user_id: int, current_password: str, new_password: str) -> None:
    settings = get_mysql_settings()

    import pymysql

    if not current_password:
        raise ValueError("请输入当前密码。")
    if not new_password:
        raise ValueError("请输入新密码。")

    ensure_mysql_schema(settings)
    connection = pymysql.connect(**{**get_database_connection_kwargs(settings), "autocommit": False})
    try:
        with connection.cursor() as cursor:
            cursor.execute(
                """
                SELECT password_hash, password_salt
                FROM users
                WHERE id = %s
                LIMIT 1
                """,
                (int(user_id),),
            )
            row = cursor.fetchone()
            if row is None:
                raise KeyError(user_id)
            if not verify_password(current_password, str(row[0] or ""), str(row[1] or "")):
                raise ValueError("当前密码错误。")

            password_hash, password_salt = hash_password(new_password)
            cursor.execute(
                """
                UPDATE users
                SET password_hash = %s,
                    password_salt = %s,
                    updated_at = CURRENT_TIMESTAMP
                WHERE id = %s
                """,
                (password_hash, password_salt, int(user_id)),
            )
        connection.commit()
    finally:
        connection.close()


def delete_user_account(user_id: int, current_password: str) -> None:
    settings = get_mysql_settings()

    import pymysql

    if not current_password:
        raise ValueError("请输入当前密码。")

    ensure_mysql_schema(settings)
    connection = pymysql.connect(**{**get_database_connection_kwargs(settings), "autocommit": False})
    try:
        with connection.cursor() as cursor:
            cursor.execute(
                """
                SELECT password_hash, password_salt
                FROM users
                WHERE id = %s
                LIMIT 1
                """,
                (int(user_id),),
            )
            user_row = cursor.fetchone()
            if user_row is None:
                raise KeyError(user_id)
            if not verify_password(current_password, str(user_row[0] or ""), str(user_row[1] or "")):
                raise ValueError("当前密码错误。")

            cursor.execute(
                """
                SELECT storage_path, result_file_path, result_detail_path
                FROM batch_documents
                WHERE user_id = %s
                """,
                (int(user_id),),
            )
            cleanup_paths = collect_user_account_cleanup_paths(int(user_id), list(cursor.fetchall()))

        for path in cleanup_paths:
            if not path.exists():
                continue
            try:
                path.unlink()
            except FileNotFoundError:
                continue
            except OSError as exc:
                raise ValueError(f"删除账号关联文件失败：{path.name}") from exc

        with connection.cursor() as cursor:
            cursor.execute("DELETE FROM users WHERE id = %s", (int(user_id),))
            if cursor.rowcount == 0:
                raise KeyError(user_id)

        connection.commit()
    except Exception:
        connection.rollback()
        raise
    finally:
        connection.close()

    remove_empty_user_upload_dirs(int(user_id))


def authenticate_user(username: str, password: str) -> dict[str, Any]:
    settings = get_mysql_settings()

    import pymysql

    ensure_mysql_schema(settings)
    connection = pymysql.connect(**get_database_connection_kwargs(settings))
    try:
        with connection.cursor() as cursor:
            cursor.execute(
                """
                SELECT id, username, display_name, avatar_text, password_hash, password_salt
                FROM users
                WHERE username = %s
                """,
                (username,),
            )
            row = cursor.fetchone()
            if row is None:
                raise ValueError("用户名或密码错误。")
            if not verify_password(password, row[4], row[5]):
                raise ValueError("用户名或密码错误。")
            cursor.execute(
                "UPDATE users SET last_login_at = CURRENT_TIMESTAMP WHERE id = %s",
                (int(row[0]),),
            )
            connection.commit()
            return build_user(row[:4])
    finally:
        connection.close()


def create_user(username: str, password: str, display_name: str | None = None) -> dict[str, Any]:
    settings = get_mysql_settings()

    import pymysql

    username = username.strip()
    display_name = (display_name or username).strip()
    avatar_text = display_name[:1] or username[:1]
    password_hash, password_salt = hash_password(password)

    ensure_mysql_schema(settings)
    connection = pymysql.connect(**get_database_connection_kwargs(settings))
    try:
        with connection.cursor() as cursor:
            cursor.execute(
                """
                INSERT INTO users (username, password_hash, password_salt, display_name, avatar_text)
                VALUES (%s, %s, %s, %s, %s)
                """,
                (username, password_hash, password_salt, display_name, avatar_text),
            )
            user_id = int(cursor.lastrowid)
            seed_user_polish_templates_if_missing(cursor, user_id)
            seed_user_notification_email_settings_if_missing(cursor, user_id)
            return get_user_by_id(user_id)
    finally:
        connection.close()


def register_user(username: str, email: str, password: str) -> dict[str, Any]:
    settings = get_mysql_settings()

    import pymysql

    username = username.strip()
    email = email.strip().lower()
    if not username or not email or not password:
        raise ValueError("用户名、邮箱和密码不能为空。")
    if not is_valid_email(email):
        raise ValueError("邮箱格式不正确。")

    password_hash, password_salt = hash_password(password)
    display_name = username
    avatar_text = username[:1]

    ensure_mysql_schema(settings)
    connection = pymysql.connect(**get_database_connection_kwargs(settings))
    try:
        with connection.cursor() as cursor:
            cursor.execute(
                "SELECT id FROM users WHERE username = %s",
                (username,),
            )
            if cursor.fetchone() is not None:
                raise ValueError("用户名已存在。")
            cursor.execute(
                """
                INSERT INTO users (username, email, password_hash, password_salt, display_name, avatar_text)
                VALUES (%s, %s, %s, %s, %s, %s)
                """,
                (username, email, password_hash, password_salt, display_name, avatar_text),
            )
            user_id = int(cursor.lastrowid)
            seed_user_polish_templates_if_missing(cursor, user_id)
            seed_user_notification_email_settings_if_missing(cursor, user_id)
            return get_user_by_id(user_id)
    finally:
        connection.close()


def list_notifications(user_id: int) -> list[dict[str, Any]]:
    settings = get_mysql_settings()

    import pymysql

    ensure_mysql_schema(settings)
    seed_notifications_if_needed(settings)

    connection = pymysql.connect(**get_database_connection_kwargs(settings))
    try:
        with connection.cursor() as cursor:
            cursor.execute(
                """
                SELECT
                    n.id,
                    n.title,
                    n.summary,
                    n.content,
                    CASE WHEN r.user_id IS NULL THEN 0 ELSE 1 END AS is_read,
                    n.created_at
                FROM notifications n
                LEFT JOIN user_notification_reads r
                    ON r.notification_id = n.id
                   AND r.user_id = %s
                ORDER BY is_read ASC, n.created_at DESC
                """,
                (int(user_id),),
            )
            return [build_notification(row) for row in cursor.fetchall()]
    finally:
        connection.close()


def mark_notification_read(notification_id: str, user_id: int) -> dict[str, Any]:
    settings = get_mysql_settings()

    import pymysql

    ensure_mysql_schema(settings)
    seed_notifications_if_needed(settings)

    connection = pymysql.connect(**get_database_connection_kwargs(settings))
    try:
        with connection.cursor() as cursor:
            cursor.execute(
                "SELECT id FROM notifications WHERE id = %s",
                (notification_id,),
            )
            if cursor.fetchone() is None:
                raise KeyError(notification_id)

            read_at = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
            cursor.execute(
                """
                INSERT INTO user_notification_reads (user_id, notification_id, read_at)
                VALUES (%s, %s, %s)
                ON DUPLICATE KEY UPDATE read_at = VALUES(read_at)
                """,
                (int(user_id), notification_id, read_at),
            )
            cursor.execute(
                """
                SELECT
                    n.id,
                    n.title,
                    n.summary,
                    n.content,
                    CASE WHEN r.user_id IS NULL THEN 0 ELSE 1 END AS is_read,
                    n.created_at
                FROM notifications n
                LEFT JOIN user_notification_reads r
                    ON r.notification_id = n.id
                   AND r.user_id = %s
                WHERE n.id = %s
                """,
                (int(user_id), notification_id),
            )
            row = cursor.fetchone()
            if row is None:
                raise KeyError(notification_id)
            return build_notification(row)
    finally:
        connection.close()


def _extract_batch_processed_metrics_from_payload(
    payload: dict[str, Any] | None,
    *,
    fallback_word_count: int = 0,
    fallback_processed_at: Any = None,
) -> tuple[str, int, float | None]:
    payload = payload if isinstance(payload, dict) else {}
    created_at_text = normalize_datetime_string(payload.get("createdAt"))
    if not created_at_text:
        created_at_text = normalize_datetime_string(fallback_processed_at)

    word_count_payload = payload.get("wordCount")
    processed_word_count = 0
    if isinstance(word_count_payload, dict):
        processed_word_count = max(0, int(word_count_payload.get("result") or 0))
    elif isinstance(word_count_payload, (int, float)):
        processed_word_count = max(0, int(word_count_payload))
    if processed_word_count <= 0:
        processed_word_count = max(0, int(fallback_word_count or 0))

    return created_at_text, processed_word_count, _normalize_batch_score_value(payload.get("score"))


def backfill_batch_processed_metrics_from_sidecars(settings: MySQLSettings | None = None) -> None:
    settings = settings or get_mysql_settings()

    import pymysql

    ensure_mysql_schema(settings)
    connection = pymysql.connect(**get_database_connection_kwargs(settings))
    try:
        with connection.cursor() as cursor:
            cursor.execute(
                """
                SELECT
                    user_id,
                    document_id,
                    word_count,
                    storage_path,
                    result_detail_path,
                    score,
                    confirmed_at,
                    updated_at
                FROM batch_documents
                WHERE has_result = 1
                  AND (processed_at IS NULL OR processed_word_count = 0 OR score IS NULL)
                """
            )
            rows = cursor.fetchall()

            update_rows: list[tuple[int, str, float | None, int, str]] = []
            for user_id, document_id, word_count, storage_path, result_detail_path, score, confirmed_at, updated_at in rows:
                document = {
                    "filePath": str(storage_path or ""),
                    "resultDetailPath": str(result_detail_path or ""),
                }
                payload: dict[str, Any] = {}
                try:
                    payload = _load_batch_result_sidecar_payload(document)
                except Exception:
                    payload = {}

                processed_at_text, processed_word_count, score_value = _extract_batch_processed_metrics_from_payload(
                    payload,
                    fallback_word_count=int(word_count or 0),
                    fallback_processed_at=confirmed_at or updated_at,
                )
                if not processed_at_text:
                    processed_at_text = normalize_datetime_string(confirmed_at) or normalize_datetime_string(updated_at)

                update_rows.append(
                    (
                        processed_word_count,
                        processed_at_text,
                        score if score is not None else score_value,
                        int(user_id),
                        str(document_id or ""),
                    )
                )

            if update_rows:
                cursor.executemany(
                    """
                    UPDATE batch_documents
                    SET processed_word_count = CASE
                            WHEN processed_word_count = 0 THEN %s
                            ELSE processed_word_count
                        END,
                        processed_at = COALESCE(processed_at, NULLIF(%s, '')),
                        score = COALESCE(score, %s)
                    WHERE user_id = %s
                      AND document_id = %s
                      AND has_result = 1
                    """,
                    update_rows,
                )
        connection.commit()
    finally:
        connection.close()


def _query_usage_window_summary(cursor: Any, user_id: int, period_start: datetime, period_end: datetime) -> tuple[int, int]:
    cursor.execute(
        """
        SELECT COALESCE(SUM(item_count), 0), COALESCE(SUM(total_words), 0)
        FROM (
            SELECT COUNT(*) AS item_count, COALESCE(SUM(word_count), 0) AS total_words
            FROM polish_records
            WHERE user_id = %s
              AND created_at >= %s
              AND created_at < %s

            UNION ALL

            SELECT COUNT(*) AS item_count, COALESCE(SUM(processed_word_count), 0) AS total_words
            FROM batch_documents
            WHERE user_id = %s
              AND has_result = 1
              AND processed_at IS NOT NULL
              AND processed_at >= %s
              AND processed_at < %s
        ) AS usage_summary
        """,
        (
            int(user_id),
            period_start,
            period_end,
            int(user_id),
            period_start,
            period_end,
        ),
    )
    row = cursor.fetchone() or (0, 0)
    return int(row[0] or 0), int(row[1] or 0)


def get_today_usage_summary(user_id: int) -> dict[str, int]:
    settings = get_mysql_settings()

    import pymysql

    ensure_mysql_schema(settings)

    now = datetime.now()
    today_start = now.replace(hour=0, minute=0, second=0, microsecond=0)
    tomorrow_start = today_start + timedelta(days=1)
    week_start = today_start - timedelta(days=today_start.weekday())

    connection = pymysql.connect(**get_database_connection_kwargs(settings))
    try:
        with connection.cursor() as cursor:
            used, _ = _query_usage_window_summary(cursor, int(user_id), today_start, tomorrow_start)
            _, weekly_words = _query_usage_window_summary(cursor, int(user_id), week_start, tomorrow_start)
    finally:
        connection.close()

    return {
        "used": used,
        "weeklyWords": weekly_words,
    }


def format_metric_number(value: int | float) -> str:
    if isinstance(value, float) and not value.is_integer():
        return f"{value:,.1f}"
    return f"{int(value):,}"


def build_source_preview(source_text: str, limit: int = 12) -> str:
    normalized = "".join((source_text or "").split())
    if not normalized:
        return "未命名文本"
    return f"{normalized[:limit]}..." if len(normalized) > limit else normalized


def format_score_label(score: Any) -> str:
    if score is None:
        return "--"
    score_value = float(score)
    if score_value.is_integer():
        return f"{int(score_value)} 分"
    return f"{score_value:.1f} 分"


def load_dashboard_summary(user_id: int) -> list[dict[str, str]]:
    settings = get_mysql_settings()

    import pymysql

    ensure_mysql_schema(settings)
    connection = pymysql.connect(**get_database_connection_kwargs(settings))
    try:
        with connection.cursor() as cursor:
            cursor.execute(
                """
                SELECT
                    COUNT(*) AS polish_count,
                    COALESCE(SUM(word_count), 0) AS total_words,
                    AVG(score) AS average_score
                FROM usage_events
                WHERE user_id = %s
                  AND event_type = 'polish'
                """,
                (int(user_id),),
            )
            polish_count, total_words, average_score = cursor.fetchone()

            cursor.execute(
                """
                SELECT COUNT(*)
                FROM usage_events
                WHERE user_id = %s
                  AND event_type = 'export'
                """,
                (int(user_id),),
            )
            export_count = int(cursor.fetchone()[0] or 0)
    finally:
        connection.close()

    average_score_value = "0" if average_score is None else f"{round(float(average_score), 1):,.1f}"

    return [
        {"label": "累计润色次数", "value": format_metric_number(int(polish_count or 0)), "trend": "当前账号累计"},
        {"label": "累计处理字数", "value": format_metric_number(int(total_words or 0)), "trend": "当前账号累计"},
        {"label": "平均质量评分", "value": average_score_value, "trend": "当前账号累计"},
        {"label": "累计导出次数", "value": format_metric_number(export_count), "trend": "当前账号累计"},
    ]


def load_statistics_summary_since_user_registered(user_id: int) -> list[dict[str, Any]]:
    settings = get_mysql_settings()

    import pymysql

    ensure_mysql_schema(settings)
    period_end = datetime.now()
    connection = pymysql.connect(**get_database_connection_kwargs(settings))
    try:
        with connection.cursor() as cursor:
            cursor.execute(
                """
                SELECT created_at
                FROM users
                WHERE id = %s
                """,
                (int(user_id),),
            )
            user_row = cursor.fetchone()
            if user_row is None:
                raise KeyError(user_id)
            period_start = user_row[0]
            if isinstance(period_start, datetime):
                period_start = period_start.replace(microsecond=0)
            else:
                period_start = datetime.strptime(str(period_start), "%Y-%m-%d %H:%M:%S")

            cursor.execute(
                """
                SELECT COUNT(DISTINCT record_id)
                FROM polish_records
                WHERE created_at >= %s
                  AND created_at < %s
                """,
                (period_start, period_end),
            )
            document_count = int(cursor.fetchone()[0] or 0)

            cursor.execute(
                """
                SELECT
                    COUNT(*) AS polish_count,
                    COALESCE(SUM(word_count), 0) AS total_words,
                    AVG(score) AS average_score
                FROM usage_events
                WHERE event_type = 'polish'
                  AND created_at >= %s
                  AND created_at < %s
                """,
                (period_start, period_end),
            )
            polish_count, total_words, average_score = cursor.fetchone()

            cursor.execute("SELECT COUNT(*) FROM users")
            total_users = int(cursor.fetchone()[0] or 0)

            cursor.execute(
                """
                SELECT COUNT(*)
                FROM polish_records
                WHERE created_at >= %s
                  AND created_at < %s
                  AND (
                    used_template = 1
                    OR (
                      COALESCE(NULLIF(template_key, ''), NULLIF(template_label, '')) IS NOT NULL
                      AND COALESCE(template_label, '') <> '未选择'
                    )
                  )
                """,
                (period_start, period_end),
            )
            template_usage_count = int(cursor.fetchone()[0] or 0)
    finally:
        connection.close()

    average_score_value = 0 if average_score is None else round(float(average_score), 1)

    return [
        {"label": "总处理文档数", "value": document_count, "unit": "", "icon": "文", "iconTone": "tone-blue"},
        {"label": "总处理字数", "value": int(total_words or 0), "unit": "", "icon": "字", "iconTone": "tone-green"},
        {"label": "平均质量评分", "value": average_score_value, "unit": "分", "icon": "分", "iconTone": "tone-purple"},
        {"label": "总润色次数", "value": int(polish_count or 0), "unit": "", "icon": "次", "iconTone": "tone-orange"},
        {"label": "用户总数", "value": total_users, "unit": "", "icon": "人", "iconTone": "tone-cyan"},
        {"label": "模板使用次数", "value": template_usage_count, "unit": "", "icon": "模", "iconTone": "tone-teal"},
    ]


def _parse_statistics_row_date(value: Any) -> datetime.date:
    if isinstance(value, datetime):
        return value.date()
    if hasattr(value, "year") and hasattr(value, "month") and hasattr(value, "day"):
        return value
    return datetime.strptime(str(value), "%Y-%m-%d").date()


def _load_statistics_user_registered_date(cursor: Any, user_id: int) -> datetime.date:
    cursor.execute(
        """
        SELECT created_at
        FROM users
        WHERE id = %s
        """,
        (int(user_id),),
    )
    row = cursor.fetchone()
    if row is None:
        raise KeyError(user_id)
    created_at = row[0]
    if isinstance(created_at, datetime):
        return created_at.date()
    return datetime.strptime(str(created_at), "%Y-%m-%d %H:%M:%S").date()


def _format_statistics_bucket_label(
    start_date: datetime.date,
    end_date: datetime.date,
    granularity: str,
) -> str:
    if granularity == "month":
        start_label = start_date.strftime("%Y-%m")
        end_label = end_date.strftime("%Y-%m")
        return start_label if start_label == end_label else f"{start_label} ~ {end_label}"

    start_label = start_date.strftime("%m-%d")
    end_label = end_date.strftime("%m-%d")
    return start_label if start_label == end_label else f"{start_label} ~ {end_label}"


def _merge_statistics_buckets(
    buckets: list[dict[str, Any]],
    max_segments: int,
) -> list[dict[str, Any]]:
    if len(buckets) <= max_segments:
        return buckets

    group_count = max(1, int(max_segments))
    base_size = len(buckets) // group_count
    remainder = len(buckets) % group_count
    merged: list[dict[str, Any]] = []
    cursor_index = 0

    for index in range(group_count):
        size = base_size + (1 if index < remainder else 0)
        chunk = buckets[cursor_index:cursor_index + size]
        cursor_index += size
        if not chunk:
            continue
        merged.append(
            {
                "start_date": chunk[0]["start_date"],
                "end_date": chunk[-1]["end_date"],
                "value": sum(int(item["value"]) for item in chunk),
            }
        )

    return merged


def load_processing_word_trend_since_user_registered(
    user_id: int,
    granularity: str,
    max_segments: int = 30,
) -> dict[str, Any]:
    settings = get_mysql_settings()

    import pymysql

    ensure_mysql_schema(settings)
    normalized_granularity = granularity if granularity in {"day", "week", "month"} else "week"
    normalized_max_segments = max(1, int(max_segments or 30))
    today = datetime.now().date()

    connection = pymysql.connect(**get_database_connection_kwargs(settings))
    try:
        with connection.cursor() as cursor:
            start_date = _load_statistics_user_registered_date(cursor, int(user_id))
            period_start = datetime.combine(start_date, datetime.min.time())
            period_end = datetime.combine(today + timedelta(days=1), datetime.min.time())

            cursor.execute(
                """
                SELECT DATE(created_at) AS usage_date, COALESCE(SUM(word_count), 0) AS total_words
                FROM usage_events
                WHERE user_id = %s
                  AND event_type = 'polish'
                  AND created_at >= %s
                  AND created_at < %s
                GROUP BY DATE(created_at)
                ORDER BY usage_date ASC
                """,
                (int(user_id), period_start, period_end),
            )
            rows = cursor.fetchall()
    finally:
        connection.close()

    daily_word_map = {_parse_statistics_row_date(row[0]): int(row[1] or 0) for row in rows}

    daily_series: list[dict[str, Any]] = []
    daily_buckets: list[dict[str, Any]] = []
    current_date = start_date
    while current_date <= today:
        value = daily_word_map.get(current_date, 0)
        daily_series.append({"date": current_date.strftime("%Y-%m-%d"), "value": value})
        daily_buckets.append(
            {
                "start_date": current_date,
                "end_date": current_date,
                "value": value,
            }
        )
        current_date += timedelta(days=1)

    if normalized_granularity == "day":
        display_buckets = daily_buckets
    elif normalized_granularity == "week":
        display_buckets = []
        for index in range(0, len(daily_buckets), 7):
            chunk = daily_buckets[index:index + 7]
            display_buckets.append(
                {
                    "start_date": chunk[0]["start_date"],
                    "end_date": chunk[-1]["end_date"],
                    "value": sum(int(item["value"]) for item in chunk),
                }
            )
    else:
        month_buckets: list[dict[str, Any]] = []
        current_bucket: dict[str, Any] | None = None
        for item in daily_buckets:
            month_key = item["start_date"].strftime("%Y-%m")
            if current_bucket is None or current_bucket["month_key"] != month_key:
                if current_bucket is not None:
                    month_buckets.append(current_bucket)
                current_bucket = {
                    "month_key": month_key,
                    "start_date": item["start_date"],
                    "end_date": item["end_date"],
                    "value": int(item["value"]),
                }
            else:
                current_bucket["end_date"] = item["end_date"]
                current_bucket["value"] += int(item["value"])
        if current_bucket is not None:
            month_buckets.append(current_bucket)
        display_buckets = [
            {
                "start_date": item["start_date"],
                "end_date": item["end_date"],
                "value": int(item["value"]),
            }
            for item in month_buckets
        ]

    display_buckets = _merge_statistics_buckets(display_buckets, normalized_max_segments)

    return {
        "trend": {
            "labels": [
                _format_statistics_bucket_label(item["start_date"], item["end_date"], normalized_granularity)
                for item in display_buckets
            ],
            "values": [int(item["value"]) for item in display_buckets],
        },
        "series": daily_series,
    }


def load_recent_active_users_trend(days: int = 30) -> dict[str, Any]:
    settings = get_mysql_settings()

    import pymysql

    ensure_mysql_schema(settings)
    normalized_days = max(1, int(days or 30))
    today = datetime.now().date()
    start_date = today - timedelta(days=normalized_days - 1)
    period_start = datetime.combine(start_date, datetime.min.time())
    period_end = datetime.combine(today + timedelta(days=1), datetime.min.time())

    connection = pymysql.connect(**get_database_connection_kwargs(settings))
    try:
        with connection.cursor() as cursor:
            cursor.execute(
                """
                SELECT DATE(created_at) AS activity_date, COUNT(DISTINCT user_id) AS active_users
                FROM usage_events
                WHERE event_type = 'polish'
                  AND user_id IS NOT NULL
                  AND created_at >= %s
                  AND created_at < %s
                GROUP BY DATE(created_at)
                ORDER BY activity_date ASC
                """,
                (period_start, period_end),
            )
            rows = cursor.fetchall()
    finally:
        connection.close()

    active_user_map = {
        _parse_statistics_row_date(row[0]): int(row[1] or 0)
        for row in rows
    }

    labels: list[str] = []
    values: list[int] = []
    series: list[dict[str, Any]] = []
    current_date = start_date
    while current_date <= today:
        value = active_user_map.get(current_date, 0)
        labels.append(current_date.strftime("%m-%d"))
        values.append(value)
        series.append({"date": current_date.strftime("%Y-%m-%d"), "value": value})
        current_date += timedelta(days=1)

    return {
        "trend": {
            "labels": labels,
            "values": values,
        },
        "series": series,
    }


def save_polish_record(user_id: int, record: dict[str, Any]) -> None:
    settings = get_mysql_settings()

    import pymysql

    ensure_mysql_schema(settings)
    word_count = record.get("wordCount") or {}
    result_count = int(word_count.get("result") or word_count.get("source") or 0)
    score = record.get("score")
    normalized_score = None if score is None else max(0, min(100, float(score)))
    options_json = json.dumps(record.get("options") or [], ensure_ascii=False)
    revision_segments_json = json.dumps(record.get("revisionSegments") or [], ensure_ascii=False)
    changes_json = json.dumps(record.get("changes") or [], ensure_ascii=False)
    scoring_json = json.dumps(record.get("scoringJson") or {}, ensure_ascii=False)
    latency_ms = max(0, int(record.get("llmLatencyMs") or 0))
    scoring_latency_ms = max(0, int(record.get("scoringLatencyMs") or 0))

    connection = pymysql.connect(**get_database_connection_kwargs(settings))
    try:
        with connection.cursor() as cursor:
            cursor.execute(
                """
                INSERT INTO polish_records (
                    user_id,
                    record_id,
                    document_id,
                    title,
                    source_text,
                    result_text,
                    template_label,
                    score,
                    word_count,
                    created_at,
                    template_key,
                    strength_key,
                    tone_key,
                    options_json,
                    model_name,
                    used_template,
                    llm_latency_ms,
                    revision_segments_json,
                    changes_json,
                    full_summary,
                    paragraph_count,
                    llm_concurrency,
                    llm_retry_count,
                    failed_paragraph_info,
                    total_latency_ms,
                    scoring_json,
                    scoring_model_name,
                    scoring_latency_ms
                )
                VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
                ON DUPLICATE KEY UPDATE
                    document_id = VALUES(document_id),
                    title = VALUES(title),
                    source_text = VALUES(source_text),
                    result_text = VALUES(result_text),
                    template_label = VALUES(template_label),
                    score = VALUES(score),
                    word_count = VALUES(word_count),
                    created_at = VALUES(created_at),
                    template_key = VALUES(template_key),
                    strength_key = VALUES(strength_key),
                    tone_key = VALUES(tone_key),
                    options_json = VALUES(options_json),
                    model_name = VALUES(model_name),
                    used_template = VALUES(used_template),
                    llm_latency_ms = VALUES(llm_latency_ms),
                    revision_segments_json = VALUES(revision_segments_json),
                    changes_json = VALUES(changes_json),
                    full_summary = VALUES(full_summary),
                    paragraph_count = VALUES(paragraph_count),
                    llm_concurrency = VALUES(llm_concurrency),
                    llm_retry_count = VALUES(llm_retry_count),
                    failed_paragraph_info = VALUES(failed_paragraph_info),
                    total_latency_ms = VALUES(total_latency_ms),
                    scoring_json = VALUES(scoring_json),
                    scoring_model_name = VALUES(scoring_model_name),
                    scoring_latency_ms = VALUES(scoring_latency_ms)
                """,
                (
                    int(user_id),
                    str(record.get("id") or ""),
                    str(record.get("documentId") or "")[:64],
                    str(record.get("title") or "")[:255],
                    str(record.get("sourceText") or ""),
                    str(record.get("resultText") or ""),
                    str(record.get("templateLabel") or ""),
                    normalized_score,
                    result_count,
                    str(record.get("createdAt") or datetime.now().strftime("%Y-%m-%d %H:%M:%S")),
                    str(record.get("template") or ""),
                    str(record.get("strength") or ""),
                    str(record.get("tone") or ""),
                    options_json,
                    str(record.get("llmModel") or ""),
                    1 if record.get("usedTemplate") else 0,
                    latency_ms,
                    revision_segments_json,
                    changes_json,
                    str(record.get("fullSummary") or ""),
                    max(0, int(record.get("paragraphCount") or 0)),
                    max(0, int(record.get("llmConcurrency") or 0)),
                    max(0, int(record.get("llmRetryCount") or 0)),
                    str(record.get("failedParagraphInfo") or ""),
                    latency_ms + scoring_latency_ms,
                    scoring_json,
                    str(record.get("scoringModel") or ""),
                    scoring_latency_ms,
                ),
            )
    finally:
        connection.close()


def _load_json_value(raw_value: Any, fallback: Any) -> Any:
    if raw_value in (None, ""):
        return fallback
    try:
        return json.loads(str(raw_value))
    except Exception:
        return fallback


def _count_text_characters(text: str) -> int:
    return len(re.sub(r"\s+", "", str(text or "")))


def _split_record_sentences(text: str) -> list[str]:
    normalized = str(text or "").strip()
    if not normalized:
        return []
    parts = re.split(r"(?<=[。！？；.!?;])", normalized)
    sentences = [part.strip() for part in parts if part.strip()]
    return sentences or [normalized]


def _build_polish_record_summary_text(result_text: str, full_summary: str) -> str:
    summary = str(full_summary or "").strip()
    if summary:
        return summary

    normalized = str(result_text or "").strip()
    if not normalized:
        return "当前记录尚未生成润色结果。"

    sentences = _split_record_sentences(normalized)
    candidate = "".join(sentences[:2]).strip() or normalized
    return candidate[:120]


def _build_polish_record_compare_sections(source_text: str, result_text: str) -> list[dict[str, str]]:
    source_sentences = _split_record_sentences(source_text)
    result_sentences = _split_record_sentences(result_text)
    pairs: list[dict[str, str]] = []
    for index, source in enumerate(source_sentences[:3]):
        pairs.append(
            {
                "label": f"片段 {index + 1}",
                "source": source,
                "result": result_sentences[index] if index < len(result_sentences) else result_text,
            }
        )
    return pairs


def _merge_polish_record_revision_segments(segments: list[dict[str, str]]) -> list[dict[str, str]]:
    merged: list[dict[str, str]] = []
    for segment in segments:
        text = str(segment.get("text") or "")
        segment_type = str(segment.get("type") or "unchanged")
        if not text:
            continue
        if merged and merged[-1]["type"] == segment_type:
            merged[-1]["text"] += text
        else:
            merged.append({"type": segment_type, "text": text})
    return merged


def _build_polish_record_revision_segments(source_text: str, result_text: str) -> list[dict[str, str]]:
    matcher = SequenceMatcher(None, str(source_text or ""), str(result_text or ""))
    segments: list[dict[str, str]] = []
    for tag, source_start, source_end, result_start, result_end in matcher.get_opcodes():
        if tag == "equal":
            segments.append({"type": "unchanged", "text": result_text[result_start:result_end]})
        elif tag == "delete":
            segments.append({"type": "deleted", "text": source_text[source_start:source_end]})
        elif tag == "insert":
            segments.append({"type": "added", "text": result_text[result_start:result_end]})
        elif tag == "replace":
            removed = source_text[source_start:source_end]
            added = result_text[result_start:result_end]
            if removed:
                segments.append({"type": "deleted", "text": removed})
            if added:
                segments.append({"type": "added", "text": added})
    return _merge_polish_record_revision_segments(segments)


def _derive_polish_record_category(template_key: str, template_label: str) -> str:
    normalized_key = str(template_key or "").strip()
    normalized_label = str(template_label or "").strip()
    return POLISH_RECORD_CATEGORY_BY_TEMPLATE.get(normalized_key, normalized_label or "通用文稿")


def _derive_polish_record_file_type(title: str) -> str:
    normalized = str(title or "").strip().lower()
    if normalized.endswith(".pdf"):
        return "PDF"
    if normalized.endswith(".txt") or normalized.endswith(".text"):
        return "TXT"
    return "Word"


def _build_polish_record_payload_from_row(row: tuple[Any, ...]) -> dict[str, Any]:
    (
        record_id,
        document_id,
        title,
        source_text,
        result_text,
        template_label,
        score,
        word_count,
        created_at,
        template_key,
        strength_key,
        tone_key,
        options_json,
        revision_segments_json,
        changes_json,
        full_summary,
        scoring_json,
    ) = row

    source_text_value = str(source_text or "")
    result_text_value = str(result_text or "")
    has_result = bool(result_text_value.strip())
    source_count = _count_text_characters(source_text_value)
    result_count = int(word_count or (_count_text_characters(result_text_value) if has_result else 0))
    option_keys = [
        item
        for item in _load_json_value(options_json, [])
        if isinstance(item, str) and item in POLISH_RECORD_OPTION_LABELS
    ]
    option_labels = [POLISH_RECORD_OPTION_LABELS[item] for item in option_keys]
    revision_segments = _load_json_value(revision_segments_json, [])
    if not revision_segments and has_result:
        revision_segments = _build_polish_record_revision_segments(source_text_value, result_text_value)
    changes = _load_json_value(changes_json, [])
    scoring_payload = _load_json_value(scoring_json, {})
    dimensions = scoring_payload.get("dimensions") if isinstance(scoring_payload, dict) else []
    created_at_text = format_datetime(created_at)
    template_label_text = str(template_label or "通用润色")
    template_key_text = str(template_key or "")
    word_delta = result_count - source_count if has_result else 0

    return {
        "id": f"polish:{record_id or ''}",
        "recordType": "polish",
        "methodLabel": "智能润色",
        "rawId": str(record_id or ""),
        "documentId": str(document_id or ""),
        "title": str(title or "") or build_source_preview(source_text_value, limit=12),
        "category": _derive_polish_record_category(template_key_text, template_label_text),
        "fileType": _derive_polish_record_file_type(str(title or "")),
        "template": template_key_text,
        "templateLabel": template_label_text,
        "strength": str(strength_key or ""),
        "strengthLabel": POLISH_RECORD_STRENGTH_LABELS.get(str(strength_key or ""), "中度"),
        "tone": str(tone_key or ""),
        "toneLabel": POLISH_RECORD_TONE_LABELS.get(str(tone_key or ""), "正式"),
        "options": option_keys,
        "optionLabels": option_labels,
        "status": "completed" if has_result else "unprocessed",
        "hasResult": has_result,
        "score": None if score is None else float(score),
        "sourceText": source_text_value,
        "resultText": result_text_value if has_result else "",
        "summary": _build_polish_record_summary_text(result_text_value, str(full_summary or "")),
        "compareSections": _build_polish_record_compare_sections(source_text_value, result_text_value) if has_result else [],
        "revisionSegments": revision_segments if isinstance(revision_segments, list) else [],
        "dimensions": dimensions if isinstance(dimensions, list) else [],
        "suggestions": [],
        "changes": changes if isinstance(changes, list) else [],
        "sourceWordCount": source_count,
        "resultWordCount": result_count if has_result else 0,
        "wordDelta": word_delta,
        "wordCount": {
            "source": source_count,
            "result": result_count,
            "delta": word_delta,
        },
        "createdAt": created_at_text,
    }


def _resolve_polish_record_template_info(
    user_id: int,
    template_key: Any,
    template_label: Any,
    used_template_flag: Any = False,
) -> tuple[bool, dict[str, str] | None]:
    normalized_key = str(template_key or "").strip()
    raw_label = str(template_label or "").strip()
    normalized_label = normalize_template_label_value(template_label, fallback="")

    try:
        template_by_key, template_key_by_name = get_template_maps_from_database(int(user_id), include_disabled=True)
    except Exception:
        template_by_key = {}
        template_key_by_name = {}

    standard_by_key, standard_key_by_label = get_standard_template_maps()
    resolved_key = normalized_key
    if not resolved_key and normalized_label:
        resolved_key = (
            str(template_key_by_name.get(normalized_label) or "").strip()
            or str(standard_key_by_label.get(normalized_label) or "").strip()
            or str(template_key_by_name.get(raw_label) or "").strip()
            or str(standard_key_by_label.get(raw_label) or "").strip()
            or str(raw_label if raw_label in template_by_key or raw_label in standard_by_key else "").strip()
        )

    template_like_label = bool(
        normalized_label
        and normalized_label not in {"未选择", "未选择模板", "通用润色"}
        and (
            resolved_key
            or normalized_label in template_key_by_name
            or normalized_label in standard_key_by_label
            or raw_label in template_key_by_name
            or raw_label in standard_key_by_label
        )
    )
    used_template = bool(normalized_key) or bool(used_template_flag) or template_like_label
    if not used_template:
        return False, None

    template = template_by_key.get(resolved_key or normalized_key)
    if template:
        return True, {
            "key": str(template.get("key") or resolved_key or normalized_key),
            "name": str(template.get("name") or normalized_label or resolved_key or normalized_key),
            "description": str(template.get("description") or "").strip(),
        }

    fallback_name = normalize_template_label_value(normalized_label or raw_label, fallback=resolved_key or normalized_key or "已选模板")
    return True, {
        "key": resolved_key or normalized_key,
        "name": fallback_name,
        "description": "",
    }


def _resolve_storage_relative_path(path_text: Any) -> Path | None:
    normalized = str(path_text or "").strip().replace("\\", "/")
    if not normalized:
        return None
    return (Path(__file__).resolve().parent.parent / normalized).resolve()


def _load_batch_result_sidecar_payload(document: dict[str, Any]) -> dict[str, Any]:
    sidecar_path = _resolve_storage_relative_path(document.get("resultDetailPath"))
    if not sidecar_path:
        source_path = _resolve_storage_relative_path(document.get("filePath"))
        if source_path:
            sidecar_path = source_path.with_name(f"{source_path.stem}.polished.json")
    if not sidecar_path:
        return {}
    if not sidecar_path.exists():
        return {}
    try:
        payload = json.loads(sidecar_path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        raise ValueError("批量润色结果文件已损坏，请重新润色。") from exc
    if not isinstance(payload, dict):
        raise ValueError("批量润色结果格式无效，请重新润色。")
    return payload


def _normalize_batch_score_value(value: Any) -> float | None:
    if value is None or value == "":
        return None
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def _coerce_batch_word_counts(document: dict[str, Any], detail: dict[str, Any]) -> tuple[int, int | None, int | None]:
    source_default = int(document.get("wordCount") or 0)
    word_count_payload = detail.get("wordCount")
    if isinstance(word_count_payload, dict):
        source_value = int(word_count_payload.get("source") or source_default)
        result_raw = word_count_payload.get("result")
        delta_raw = word_count_payload.get("delta")
        result_value = int(result_raw) if isinstance(result_raw, (int, float)) else None
        delta_value = int(delta_raw) if isinstance(delta_raw, (int, float)) else None
        return source_value, result_value, delta_value
    if isinstance(word_count_payload, (int, float)):
        return int(word_count_payload), None, None
    return source_default, None, None


def _build_batch_record_payload(
    document: dict[str, Any],
    *,
    detail: dict[str, Any] | None = None,
    include_detail: bool = False,
) -> dict[str, Any]:
    detail_payload = detail if isinstance(detail, dict) else {}
    title = str(document.get("title") or "未命名文档")
    source_text = str(detail_payload.get("sourceText") or "")
    result_text = str(detail_payload.get("resultText") or "")
    has_result = bool(document.get("hasResult"))
    source_count, result_count, delta_count = _coerce_batch_word_counts(document, detail_payload)
    full_summary_text = str(detail_payload.get("fullSummary") or "").strip()
    summary_text = str(detail_payload.get("summary") or "").strip()
    if not summary_text and result_text:
        summary_text = _build_polish_record_summary_text(result_text, full_summary_text)
    score_value = _normalize_batch_score_value(detail_payload.get("score"))
    template_label = str(
        detail_payload.get("templateLabel")
        or detail_payload.get("templateType")
        or document.get("templateType")
        or "未选择"
    )
    created_at_text = str(document.get("updatedAt") or "")
    dimensions = detail_payload.get("dimensions") if isinstance(detail_payload.get("dimensions"), list) else []
    suggestions = detail_payload.get("suggestions") if isinstance(detail_payload.get("suggestions"), list) else []
    changes = detail_payload.get("changes") if isinstance(detail_payload.get("changes"), list) else []
    compare_sections = detail_payload.get("compareSections")
    if not isinstance(compare_sections, list):
        compare_sections = _build_polish_record_compare_sections(source_text, result_text) if source_text and result_text else []

    payload = {
        "id": f"batch:{document.get('id') or ''}",
        "recordType": "batch",
        "methodLabel": "批量处理",
        "rawId": str(document.get("id") or ""),
        "documentId": str(document.get("id") or ""),
        "title": title,
        "category": str(document.get("category") or "批量导入"),
        "fileType": str(document.get("fileType") or "Word"),
        "templateLabel": template_label,
        "templateType": str(document.get("templateType") or ""),
        "status": str(document.get("status") or "unprocessed"),
        "hasResult": has_result,
        "score": score_value,
        "fullSummary": full_summary_text,
        "summary": summary_text,
        "sourceWordCount": source_count,
        "resultWordCount": result_count,
        "wordDelta": delta_count,
        "wordCount": {
            "source": source_count,
            "result": result_count,
            "delta": delta_count,
        },
        "createdAt": created_at_text,
    }

    if not include_detail:
        return payload

    payload.update(
        {
            "sourceText": source_text,
            "resultText": result_text,
            "dimensions": dimensions,
            "suggestions": suggestions,
            "changes": changes,
            "compareSections": compare_sections,
            "revisionSegments": [],
            "confirmedAt": document.get("confirmedAt"),
            "resultFilePath": str(document.get("resultFilePath") or ""),
            "resultDetailPath": str(document.get("resultDetailPath") or ""),
        }
    )
    return payload


def _load_batch_record_detail_payload(user_id: int, document_id: str) -> dict[str, Any]:
    document = get_batch_document_from_database(int(user_id), document_id)
    detail_payload: dict[str, Any] = {}
    if document.get("hasResult"):
        try:
            detail_payload = _load_batch_result_sidecar_payload(document)
        except ValueError:
            raise
        except Exception:
            detail_payload = {}
        if not detail_payload:
            try:
                from .data_store import get_batch_processing_result

                detail_payload = get_batch_processing_result(int(user_id), document_id)
            except KeyError:
                detail_payload = {}
    return _build_batch_record_payload(document, detail=detail_payload, include_detail=True)


def list_polish_record_summaries_from_database(user_id: int, limit: int | None = None) -> list[dict[str, Any]]:
    settings = get_mysql_settings()

    import pymysql

    ensure_mysql_schema(settings)
    connection = pymysql.connect(**get_database_connection_kwargs(settings))
    try:
        with connection.cursor() as cursor:
            sql = """
                SELECT
                    record_id,
                    document_id,
                    title,
                    source_text,
                    result_text,
                    template_label,
                    score,
                    word_count,
                    created_at,
                    template_key,
                    strength_key,
                    tone_key,
                    options_json,
                    revision_segments_json,
                    changes_json,
                    full_summary,
                    scoring_json
                FROM polish_records
                WHERE user_id = %s
                ORDER BY created_at DESC, id DESC
            """
            params: list[Any] = [int(user_id)]
            if limit is not None:
                sql += " LIMIT %s"
                params.append(int(limit))
            cursor.execute(sql, tuple(params))
            rows = cursor.fetchall()
    finally:
        connection.close()

    items = [_build_polish_record_payload_from_row(row) for row in rows]
    batch_items: list[dict[str, Any]] = []
    for document in list_batch_documents_from_database(int(user_id)):
        detail_payload = {}
        if document.get("hasResult"):
            detail_payload = _load_batch_result_sidecar_payload(document)
        batch_items.append(_build_batch_record_payload(document, detail=detail_payload, include_detail=False))

    combined = sorted(
        [*items, *batch_items],
        key=lambda item: (str(item.get("createdAt") or ""), str(item.get("id") or "")),
        reverse=True,
    )
    if limit is not None:
        return combined[: int(limit)]
    return combined


def get_polish_record_detail_from_database(user_id: int, record_id: str) -> dict[str, Any]:
    normalized_id = str(record_id or "")
    if normalized_id.startswith("batch:"):
        return _load_batch_record_detail_payload(int(user_id), normalized_id.split(":", 1)[1])

    raw_record_id = normalized_id.split(":", 1)[1] if normalized_id.startswith("polish:") else normalized_id
    settings = get_mysql_settings()

    import pymysql

    ensure_mysql_schema(settings)
    connection = pymysql.connect(**get_database_connection_kwargs(settings))
    try:
        with connection.cursor() as cursor:
            cursor.execute(
                """
                SELECT
                    record_id,
                    document_id,
                    title,
                    source_text,
                    result_text,
                    template_label,
                    score,
                    word_count,
                    created_at,
                    template_key,
                    strength_key,
                    tone_key,
                    options_json,
                    revision_segments_json,
                    changes_json,
                    full_summary,
                    scoring_json,
                    used_template
                FROM polish_records
                WHERE user_id = %s
                  AND record_id = %s
                LIMIT 1
                """,
                (int(user_id), raw_record_id),
            )
            row = cursor.fetchone()
    finally:
        connection.close()

    if row is None:
        raise KeyError(record_id)
    payload = _build_polish_record_payload_from_row(row[:17])
    used_template, template_info = _resolve_polish_record_template_info(
        int(user_id),
        payload.get("template"),
        payload.get("templateLabel"),
        row[17],
    )
    payload["usedTemplate"] = used_template
    payload["templateInfo"] = template_info
    return payload


def load_recent_dashboard_records(user_id: int, limit: int = 4) -> list[dict[str, str]]:
    settings = get_mysql_settings()

    import pymysql

    ensure_mysql_schema(settings)
    connection = pymysql.connect(**get_database_connection_kwargs(settings))
    try:
        with connection.cursor() as cursor:
            cursor.execute(
                """
                SELECT source_text, template_label, word_count, score, created_at
                FROM polish_records
                WHERE user_id = %s
                ORDER BY created_at DESC, id DESC
                LIMIT %s
                """,
                (int(user_id), int(limit)),
            )
            rows = cursor.fetchall()
    finally:
        connection.close()

    records = []
    for source_text, template_label, word_count, score, created_at in rows:
        if hasattr(created_at, "strftime"):
            time_text = created_at.strftime("%Y-%m-%d %H:%M")
        else:
            time_text = str(created_at)[:16]
        records.append(
            {
                "title": build_source_preview(str(source_text or "")),
                "meta": f"{template_label or '通用润色'} · {int(word_count or 0)} 字",
                "time": time_text,
                "score": format_score_label(score),
            }
        )
    return records


def load_common_dashboard_templates(user_id: int) -> list[dict[str, str]]:
    settings = get_mysql_settings()

    import pymysql

    ensure_mysql_schema(settings)
    ensure_user_polish_templates(int(user_id), settings)
    connection = pymysql.connect(**get_database_connection_kwargs(settings))
    try:
        with connection.cursor() as cursor:
            cursor.execute(
                """
                SELECT template_key, name, usage_count, icon, tone
                FROM polish_templates
                WHERE user_id = %s
                  AND is_deleted = 0
                  AND enabled = 1
                ORDER BY usage_count DESC, updated_at DESC, id DESC
                """,
                (int(user_id),),
            )
            rows = cursor.fetchall()
    finally:
        connection.close()

    metrics_by_key = load_template_metrics_by_user(int(user_id))
    items = [
        {
            "name": str(name or ""),
            "usageCount": int(metrics_by_key.get(str(template_key or ""), {}).get("usageCount", usage_count or 0) or 0),
            "icon": str(icon or "模"),
            "tone": str(tone or "icon-blue"),
            "_index": index,
        }
        for index, (template_key, name, usage_count, icon, tone) in enumerate(rows)
    ]
    items.sort(key=lambda item: (-int(item["usageCount"]), int(item["_index"])))

    return [
        {
            "name": str(item["name"]),
            "usage": f"使用 {int(item['usageCount'])} 次",
            "icon": str(item["icon"]),
            "tone": str(item["tone"]),
        }
        for item in items
    ]


def get_user_export_count(user_id: int) -> int:
    settings = get_mysql_settings()

    import pymysql

    ensure_mysql_schema(settings)
    connection = pymysql.connect(**get_database_connection_kwargs(settings))
    try:
        with connection.cursor() as cursor:
            cursor.execute(
                """
                SELECT COUNT(*)
                FROM usage_events
                WHERE user_id = %s
                  AND event_type = 'export'
                """,
                (int(user_id),),
            )
            return int(cursor.fetchone()[0] or 0)
    finally:
        connection.close()


def record_usage_event(
    word_count: int = 0,
    *,
    user_id: int | None = None,
    score: int | float | None = None,
    event_type: str = "polish",
    source: str | None = None,
) -> None:
    settings = get_mysql_settings()

    import pymysql

    ensure_mysql_schema(settings)
    normalized_word_count = max(0, int(word_count or 0))
    normalized_score = None if score is None else max(0, min(100, float(score)))
    normalized_source = (source or "").strip()[:64] or None
    connection = pymysql.connect(**get_database_connection_kwargs(settings))
    try:
        with connection.cursor() as cursor:
            cursor.execute(
                """
                INSERT INTO usage_events (user_id, event_type, word_count, score, event_source, created_at)
                VALUES (%s, %s, %s, %s, %s, %s)
                """,
                (
                    int(user_id) if user_id is not None else None,
                    event_type,
                    normalized_word_count,
                    normalized_score,
                    normalized_source,
                    datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
                ),
            )
    finally:
        connection.close()


def record_export_event(user_id: int, source: str | None = None) -> int:
    record_usage_event(user_id=int(user_id), event_type="export", source=source)
    return get_user_export_count(int(user_id))


def check_mysql_connection() -> dict[str, Any]:
    status: dict[str, Any] = {
        "name": "",
        "connected": False,
    }

    try:
        settings = get_mysql_settings()
        status["name"] = settings.database

        import pymysql

        ensure_mysql_schema(settings)
        connection = pymysql.connect(**get_database_connection_kwargs(settings))
        try:
            with connection.cursor() as cursor:
                cursor.execute("SELECT 1")
                cursor.fetchone()
        finally:
            connection.close()
    except Exception as exc:
        status["error"] = mask_database_error(exc)
        return status

    status["connected"] = True
    return status
