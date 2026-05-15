from __future__ import annotations

from typing import Any

from fastapi import FastAPI, File, HTTPException, Request, UploadFile
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, JSONResponse
from pydantic import BaseModel, Field

from .database import (
    authenticate_user,
    change_user_password,
    check_mysql_connection,
    delete_user_account,
    get_user_from_token,
    load_settings_profile_from_database,
    load_settings_notifications_from_database,
    get_today_usage_summary,
    initialize_usage_database,
    get_polish_record_detail_from_database,
    list_notifications,
    list_polish_record_summaries_from_database,
    load_common_dashboard_templates,
    load_dashboard_summary,
    load_recent_dashboard_records,
    mark_notification_read,
    mask_database_error,
    register_user,
    record_export_event,
    record_usage_event,
    save_polish_record,
    update_settings_notifications_in_database,
    update_settings_profile_in_database,
)
from .data_store import (
    confirm_batch_processing_documents,
    create_polish_record,
    create_polish_template,
    delete_batch_processing_documents,
    delete_polish_template,
    generate_summary,
    get_polish_template_detail,
    get_batch_processing_result,
    import_batch_processing_files,
    list_polish_templates,
    load_batch_processing_data,
    load_polish_config,
    load_statistics_data,
    polish_batch_processing_documents,
    record_batch_processing_export,
    record_batch_processing_template_event,
    resolve_batch_processing_download,
    toggle_polish_template_enabled,
    update_polish_template,
)
from .file_importer import parse_imported_file
from .llm import check_deepseek_connection, get_deepseek_config_status


app = FastAPI(title="Document Polish Backend", version="0.3.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://127.0.0.1:5173", "http://localhost:5173"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


PUBLIC_API_PATHS = {"/api/health", "/api/auth/login", "/api/auth/register"}


@app.middleware("http")
async def require_api_auth(request: Request, call_next):
    if (
        request.method != "OPTIONS"
        and request.url.path.startswith("/api/")
        and request.url.path not in PUBLIC_API_PATHS
    ):
        authorization = request.headers.get("Authorization", "")
        prefix = "Bearer "
        if not authorization.startswith(prefix):
            return JSONResponse(status_code=401, content={"detail": "请先登录。"})
        token = authorization[len(prefix) :].strip()
        try:
            request.state.user = get_user_from_token(token)
        except Exception:
            return JSONResponse(status_code=401, content={"detail": "登录状态已失效，请重新登录。"})

    return await call_next(request)


@app.on_event("startup")
def startup() -> None:
    try:
        initialize_usage_database()
    except Exception:
        pass


class PolishPayload(BaseModel):
    title: str = ""
    description: str = ""
    documentId: str | None = None
    content: str = Field(min_length=1)
    template: str = ""
    strength: str = "medium"
    tone: str = "formal"
    options: list[str] = []


class SummaryPayload(BaseModel):
    text: str = Field(min_length=1)


class TemplatePayload(BaseModel):
    key: str | None = None
    name: str = Field(min_length=1)
    description: str = ""
    icon: str = ""
    tone: str = "icon-blue"
    enabled: bool = True
    usageCount: int = 0
    averageScore: int = 0
    systemPrompt: str = ""
    terminology: list[str] = []
    forbiddenExpressions: list[str] = []


class TemplateEnabledPayload(BaseModel):
    enabled: bool


class BatchPolishDocumentPayload(BaseModel):
    documentId: str = Field(min_length=1)
    templateKey: str = Field(min_length=1)
    templateLabel: str = ""


class BatchPolishPayload(BaseModel):
    documents: list[BatchPolishDocumentPayload] = Field(default_factory=list)


class BatchConfirmDocumentPayload(BaseModel):
    documentId: str = Field(min_length=1)


class BatchConfirmPayload(BaseModel):
    documents: list[BatchConfirmDocumentPayload] = Field(default_factory=list)


class BatchDeleteDocumentPayload(BaseModel):
    documentId: str = Field(min_length=1)


class BatchDeletePayload(BaseModel):
    documents: list[BatchDeleteDocumentPayload] = Field(default_factory=list)


class BatchActivityDocumentPayload(BaseModel):
    documentId: str = Field(min_length=1)
    title: str = ""
    filename: str = ""


class BatchTemplateEventPayload(BaseModel):
    documents: list[BatchActivityDocumentPayload] = Field(default_factory=list)
    templateKey: str = ""
    templateLabel: str = Field(min_length=1)


class BatchExportPayload(BaseModel):
    documents: list[BatchActivityDocumentPayload] = Field(default_factory=list)


class SettingsProfilePayload(BaseModel):
    username: str = Field(min_length=1)
    email: str = Field(min_length=1)
    emailVerified: bool = True


class SettingsNotificationsPayload(BaseModel):
    notifications: list[dict[str, Any]]


class LoginPayload(BaseModel):
    username: str = Field(min_length=1)
    password: str = Field(min_length=1)


class RegisterPayload(BaseModel):
    username: str = Field(min_length=1)
    email: str = Field(min_length=1)
    password: str = Field(min_length=1)
    confirmPassword: str = Field(min_length=1)


class ChangePasswordPayload(BaseModel):
    currentPassword: str = Field(min_length=1)
    newPassword: str = Field(min_length=1)
    confirmPassword: str = Field(min_length=1)


class DeleteAccountPayload(BaseModel):
    currentPassword: str = Field(min_length=1)


class ExportEventPayload(BaseModel):
    source: str = ""


def bad_request(detail: str) -> HTTPException:
    return HTTPException(status_code=400, detail=detail)


@app.get("/api/health")
def health_check() -> dict[str, Any]:
    return {
        "status": "ok",
        "database": check_mysql_connection(),
        "llm": {
            "deepseek": get_deepseek_config_status(),
        },
    }


@app.get("/api/llm/check")
def check_llm() -> dict[str, Any]:
    return {
        "deepseek": check_deepseek_connection(),
    }


@app.get("/api/usage/today")
def get_today_usage(request: Request) -> dict[str, int]:
    try:
        return get_today_usage_summary(int(request.state.user["id"]))
    except Exception as exc:
        raise HTTPException(status_code=503, detail=mask_database_error(exc)) from exc


@app.post("/api/auth/login")
def login(payload: LoginPayload) -> dict[str, Any]:
    try:
        user = authenticate_user(payload.username.strip(), payload.password)
    except ValueError as exc:
        raise HTTPException(status_code=401, detail=str(exc)) from exc
    except Exception as exc:
        raise HTTPException(status_code=503, detail=mask_database_error(exc)) from exc

    from .database import issue_auth_token

    return {
        "token": issue_auth_token(user),
        "user": user,
    }


@app.post("/api/auth/register")
def register(payload: RegisterPayload) -> dict[str, Any]:
    if payload.password != payload.confirmPassword:
        raise HTTPException(status_code=400, detail="两次输入的密码不一致。")
    try:
        user = register_user(payload.username, payload.email, payload.password)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    except Exception as exc:
        raise HTTPException(status_code=503, detail=mask_database_error(exc)) from exc
    return {"user": user}


@app.get("/api/auth/me")
def get_current_user(request: Request) -> dict[str, Any]:
    return request.state.user


@app.post("/api/auth/change-password")
def change_password(payload: ChangePasswordPayload, request: Request) -> dict[str, Any]:
    if payload.newPassword != payload.confirmPassword:
        raise HTTPException(status_code=400, detail="两次输入的新密码不一致。")
    try:
        change_user_password(int(request.state.user["id"]), payload.currentPassword, payload.newPassword)
        return {"success": True, "message": "密码修改成功，请重新登录。"}
    except ValueError as exc:
        raise bad_request(str(exc)) from exc
    except KeyError as exc:
        raise HTTPException(status_code=404, detail="用户不存在。") from exc
    except Exception as exc:
        raise HTTPException(status_code=503, detail=mask_database_error(exc)) from exc


@app.post("/api/auth/delete-account")
def delete_account(payload: DeleteAccountPayload, request: Request) -> dict[str, Any]:
    try:
        delete_user_account(int(request.state.user["id"]), payload.currentPassword)
        return {"success": True, "message": "账号已注销。"}
    except ValueError as exc:
        raise bad_request(str(exc)) from exc
    except KeyError as exc:
        raise HTTPException(status_code=404, detail="用户不存在。") from exc
    except Exception as exc:
        raise HTTPException(status_code=503, detail=mask_database_error(exc)) from exc


@app.get("/api/dashboard")
def get_dashboard(request: Request) -> dict[str, Any]:
    try:
        user_id = int(request.state.user["id"])
        notifications = list_notifications(user_id)
        return {
            "summary": load_dashboard_summary(user_id),
            "records": load_recent_dashboard_records(user_id),
            "templates": load_common_dashboard_templates(user_id),
            "notices": [
                {
                    "id": notification["id"],
                    "title": notification["title"],
                    "date": str(notification["createdAt"]).split(" ")[0],
                    "description": notification["summary"],
                    "isRead": notification["isRead"],
                }
                for notification in notifications[:3]
            ],
        }
    except Exception as exc:
        raise HTTPException(status_code=503, detail=mask_database_error(exc)) from exc


@app.post("/api/dashboard/export-events")
def create_export_event(request: Request, payload: ExportEventPayload | None = None) -> dict[str, Any]:
    try:
        export_count = record_export_event(int(request.state.user["id"]), payload.source if payload else "")
        return {
            "success": True,
            "exportCount": export_count,
        }
    except Exception as exc:
        raise HTTPException(status_code=503, detail=mask_database_error(exc)) from exc


@app.get("/api/batch-processing")
def get_batch_processing(request: Request) -> dict[str, Any]:
    try:
        return load_batch_processing_data(int(request.state.user["id"]))
    except Exception as exc:
        raise HTTPException(status_code=503, detail=mask_database_error(exc)) from exc


@app.post("/api/batch-processing/import")
async def import_batch_processing(request: Request, files: list[UploadFile] = File(...)) -> dict[str, Any]:
    if not files:
        raise bad_request("请选择需要导入的文件。")

    file_items: list[dict[str, Any]] = []
    try:
        for file in files:
            content = await file.read()
            file_items.append(
                {
                    "filename": file.filename or "imported-file",
                    "content": content,
                }
            )
        return import_batch_processing_files(int(request.state.user["id"]), file_items)
    except Exception as exc:
        raise HTTPException(status_code=503, detail=mask_database_error(exc)) from exc
    finally:
        for file in files:
            await file.close()


@app.post("/api/batch-processing/polish")
def polish_batch_processing(request: Request, payload: BatchPolishPayload) -> dict[str, Any]:
    try:
        return polish_batch_processing_documents(
            int(request.state.user["id"]),
            [item.model_dump() for item in payload.documents],
        )
    except ValueError as exc:
        raise bad_request(str(exc)) from exc
    except Exception as exc:
        raise HTTPException(status_code=503, detail=mask_database_error(exc)) from exc


@app.post("/api/batch-processing/confirm")
def confirm_batch_processing(request: Request, payload: BatchConfirmPayload) -> dict[str, Any]:
    try:
        return confirm_batch_processing_documents(
            int(request.state.user["id"]),
            [item.model_dump() for item in payload.documents],
        )
    except ValueError as exc:
        raise bad_request(str(exc)) from exc
    except Exception as exc:
        raise HTTPException(status_code=503, detail=mask_database_error(exc)) from exc


@app.post("/api/batch-processing/delete")
def delete_batch_processing(request: Request, payload: BatchDeletePayload) -> dict[str, Any]:
    try:
        return delete_batch_processing_documents(
            int(request.state.user["id"]),
            [item.model_dump() for item in payload.documents],
        )
    except ValueError as exc:
        raise bad_request(str(exc)) from exc
    except Exception as exc:
        raise HTTPException(status_code=503, detail=mask_database_error(exc)) from exc


@app.post("/api/batch-processing/template-event")
def create_batch_processing_template_event(request: Request, payload: BatchTemplateEventPayload) -> dict[str, Any]:
    try:
        return record_batch_processing_template_event(
            int(request.state.user["id"]),
            [item.model_dump() for item in payload.documents],
            payload.templateKey,
            payload.templateLabel,
        )
    except ValueError as exc:
        raise bad_request(str(exc)) from exc
    except Exception as exc:
        raise HTTPException(status_code=503, detail=mask_database_error(exc)) from exc


@app.post("/api/batch-processing/export")
def record_batch_processing_export_event(request: Request, payload: BatchExportPayload) -> dict[str, Any]:
    try:
        return record_batch_processing_export(
            int(request.state.user["id"]),
            [item.model_dump() for item in payload.documents],
        )
    except ValueError as exc:
        raise bad_request(str(exc)) from exc
    except Exception as exc:
        raise HTTPException(status_code=503, detail=mask_database_error(exc)) from exc


@app.get("/api/batch-processing/{document_id}/result")
def get_batch_processing_result_endpoint(document_id: str, request: Request) -> dict[str, Any]:
    try:
        return get_batch_processing_result(int(request.state.user["id"]), document_id)
    except KeyError as exc:
        raise HTTPException(status_code=404, detail="批量润色结果不存在。") from exc
    except ValueError as exc:
        raise bad_request(str(exc)) from exc
    except Exception as exc:
        raise HTTPException(status_code=503, detail=mask_database_error(exc)) from exc


@app.get("/api/batch-processing/{document_id}/download")
def download_batch_processing_result(document_id: str, request: Request) -> FileResponse:
    try:
        payload = resolve_batch_processing_download(int(request.state.user["id"]), document_id)
        return FileResponse(
            path=payload["path"],
            media_type=payload["mediaType"],
            filename=payload["filename"],
        )
    except KeyError as exc:
        raise HTTPException(status_code=404, detail="批量文档不存在。") from exc
    except ValueError as exc:
        raise bad_request(str(exc)) from exc
    except Exception as exc:
        raise HTTPException(status_code=503, detail=mask_database_error(exc)) from exc


@app.get("/api/statistics")
def get_statistics(
    request: Request,
    rangeStart: str | None = None,
    rangeEnd: str | None = None,
    granularity: str = "week",
) -> dict[str, Any]:
    try:
        return load_statistics_data(rangeStart, rangeEnd, granularity, int(request.state.user["id"]))
    except Exception as exc:
        raise HTTPException(status_code=503, detail=mask_database_error(exc)) from exc


@app.get("/api/notifications")
def get_notifications(request: Request) -> list[dict[str, Any]]:
    try:
        return list_notifications(int(request.state.user["id"]))
    except Exception as exc:
        raise HTTPException(status_code=503, detail=mask_database_error(exc)) from exc


@app.get("/api/settings")
def get_settings(request: Request) -> dict[str, Any]:
    try:
        user_id = int(request.state.user["id"])
        return {
            "profile": load_settings_profile_from_database(user_id),
            "notifications": load_settings_notifications_from_database(user_id),
        }
    except Exception as exc:
        raise HTTPException(status_code=503, detail=mask_database_error(exc)) from exc


@app.put("/api/settings/profile")
def update_settings_profile_endpoint(payload: SettingsProfilePayload, request: Request) -> dict[str, Any]:
    try:
        return update_settings_profile_in_database(int(request.state.user["id"]), payload.model_dump())
    except ValueError as exc:
        raise bad_request(str(exc)) from exc
    except KeyError as exc:
        raise HTTPException(status_code=404, detail="用户不存在。") from exc
    except Exception as exc:
        raise HTTPException(status_code=503, detail=mask_database_error(exc)) from exc


@app.patch("/api/settings/notifications")
def update_settings_notifications_endpoint(
    payload: SettingsNotificationsPayload,
    request: Request,
) -> list[dict[str, Any]]:
    try:
        return update_settings_notifications_in_database(
            int(request.state.user["id"]),
            payload.model_dump(),
        )
    except ValueError as exc:
        raise bad_request(str(exc)) from exc
    except Exception as exc:
        raise HTTPException(status_code=503, detail=mask_database_error(exc)) from exc


@app.patch("/api/notifications/{notification_id}/read")
def read_notification(notification_id: str, request: Request) -> dict[str, Any]:
    try:
        return mark_notification_read(notification_id, int(request.state.user["id"]))
    except KeyError as exc:
        raise HTTPException(status_code=404, detail="通知不存在。") from exc
    except Exception as exc:
        raise HTTPException(status_code=503, detail=mask_database_error(exc)) from exc


@app.get("/api/polish/config")
def get_polish_config(request: Request) -> dict[str, Any]:
    try:
        return load_polish_config(int(request.state.user["id"]))
    except Exception as exc:
        raise HTTPException(status_code=503, detail=mask_database_error(exc)) from exc


@app.post("/api/polish/import-file")
async def import_polish_file(file: UploadFile = File(...)) -> dict[str, Any]:
    try:
        content = await file.read()
        return parse_imported_file(file.filename or "imported-file", content)
    except ValueError as exc:
        raise bad_request(str(exc)) from exc
    finally:
        await file.close()


@app.get("/api/polish/templates")
def get_polish_templates(request: Request) -> list[dict[str, Any]]:
    try:
        return list_polish_templates(int(request.state.user["id"]))
    except Exception as exc:
        raise HTTPException(status_code=503, detail=mask_database_error(exc)) from exc


@app.get("/api/polish/templates/{template_id}")
def get_polish_template(template_id: str, request: Request) -> dict[str, Any]:
    try:
        return get_polish_template_detail(int(request.state.user["id"]), template_id)
    except KeyError as exc:
        raise HTTPException(status_code=404, detail="润色模板不存在。") from exc
    except Exception as exc:
        raise HTTPException(status_code=503, detail=mask_database_error(exc)) from exc


@app.post("/api/polish/templates")
def create_polish_template_endpoint(payload: TemplatePayload, request: Request) -> dict[str, Any]:
    try:
        return create_polish_template(int(request.state.user["id"]), payload.model_dump())
    except ValueError as exc:
        raise bad_request(str(exc)) from exc
    except Exception as exc:
        raise HTTPException(status_code=503, detail=mask_database_error(exc)) from exc


@app.put("/api/polish/templates/{template_id}")
def update_polish_template_endpoint(template_id: str, payload: TemplatePayload, request: Request) -> dict[str, Any]:
    try:
        return update_polish_template(int(request.state.user["id"]), template_id, payload.model_dump())
    except KeyError as exc:
        raise HTTPException(status_code=404, detail="润色模板不存在。") from exc
    except ValueError as exc:
        raise bad_request(str(exc)) from exc
    except Exception as exc:
        raise HTTPException(status_code=503, detail=mask_database_error(exc)) from exc


@app.post("/api/polish/templates/{template_id}/toggle-enabled")
def toggle_polish_template_endpoint(
    template_id: str,
    payload: TemplateEnabledPayload,
    request: Request,
) -> dict[str, Any]:
    try:
        return toggle_polish_template_enabled(int(request.state.user["id"]), template_id, payload.enabled)
    except KeyError as exc:
        raise HTTPException(status_code=404, detail="润色模板不存在。") from exc
    except Exception as exc:
        raise HTTPException(status_code=503, detail=mask_database_error(exc)) from exc


@app.delete("/api/polish/templates/{template_id}")
def delete_polish_template_endpoint(template_id: str, request: Request) -> dict[str, bool]:
    try:
        delete_polish_template(int(request.state.user["id"]), template_id)
        return {"success": True}
    except KeyError as exc:
        raise HTTPException(status_code=404, detail="润色模板不存在。") from exc
    except Exception as exc:
        raise HTTPException(status_code=503, detail=mask_database_error(exc)) from exc


@app.post("/api/polish")
def create_polish_endpoint(payload: PolishPayload, request: Request) -> dict[str, Any]:
    try:
        record = create_polish_record(payload.model_dump(), int(request.state.user["id"]))
        word_count = record.get("wordCount", {}).get("result") or record.get("wordCount", {}).get("source") or 0
        save_polish_record(int(request.state.user["id"]), record)
        try:
            record_usage_event(
                int(word_count),
                user_id=int(request.state.user["id"]),
                score=record.get("score"),
                event_type="polish",
                source="polish",
            )
        except Exception:
            pass
        return record
    except ValueError as exc:
        raise bad_request(str(exc)) from exc


    except Exception as exc:
        raise HTTPException(status_code=503, detail=mask_database_error(exc)) from exc


@app.post("/api/polish/summary")
def create_summary_endpoint(payload: SummaryPayload) -> dict[str, str]:
    try:
        return generate_summary(payload.model_dump())
    except ValueError as exc:
        raise bad_request(str(exc)) from exc


@app.get("/api/polish/records")
def get_polish_records(request: Request) -> list[dict[str, Any]]:
    try:
        return list_polish_record_summaries_from_database(int(request.state.user["id"]))
    except Exception as exc:
        raise bad_request(mask_database_error(exc)) from exc


@app.get("/api/polish/records/{record_id}")
def get_polish_record(record_id: str, request: Request) -> dict[str, Any]:
    try:
        return get_polish_record_detail_from_database(int(request.state.user["id"]), record_id)
    except KeyError as exc:
        raise HTTPException(status_code=404, detail="润色记录不存在。") from exc
    except Exception as exc:
        raise bad_request(mask_database_error(exc)) from exc
