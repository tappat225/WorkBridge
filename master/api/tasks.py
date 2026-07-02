# SPDX-License-Identifier: AGPL-3.0-only
"""Task dispatch and result API endpoints."""

from starlette.requests import Request
from starlette.responses import JSONResponse
from starlette.routing import Route

import json

from pydantic import ValidationError

from shared.protocol import DispatchRequest, ErrorCode, Task, TaskPayload, TaskResult, TaskStatus
from master.auth import require_client_token, require_node_token


def _validate_dispatch(body) -> DispatchRequest | JSONResponse:
    """Validate dispatch request body, returning error response on failure."""
    if not isinstance(body, dict):
        return JSONResponse(
            {"error": "request body must be a JSON object",
             "error_code": ErrorCode.schema_invalid.value},
            status_code=400,
        )
    try:
        return DispatchRequest(**body)
    except ValidationError as e:
        errors = []
        for err in e.errors():
            loc = ".".join(str(x) for x in err["loc"])
            msg = err["msg"]
            errors.append(f"{loc}: {msg}")
        return JSONResponse(
            {"error": "; ".join(errors), "error_code": ErrorCode.schema_invalid.value},
            status_code=400,
        )


def create_routes(router, registry, task_store, node_token: str, client_token: str) -> list[Route]:

    async def dispatch(request: Request):
        err = await require_client_token(request, client_token)
        if err:
            return err
        try:
            body = await request.json()
        except json.JSONDecodeError:
            return JSONResponse(
                {"error": "invalid JSON body", "error_code": ErrorCode.schema_invalid.value},
                status_code=400)
        validated = _validate_dispatch(body)
        if isinstance(validated, JSONResponse):
            return validated
        task = Task(
            target_node=validated.target_node,
            payload=validated.payload,
            timeout=validated.timeout)
        sent = await router.dispatch(task)
        if not sent:
            return JSONResponse(
                {"error": "node offline or not connected", "error_code": ErrorCode.node_offline.value},
                status_code=503)
        return JSONResponse({"task_id": task.task_id, "status": "dispatched"})

    async def dispatch_sync(request: Request):
        err = await require_client_token(request, client_token)
        if err:
            return err
        try:
            body = await request.json()
        except json.JSONDecodeError:
            return JSONResponse(
                {"error": "invalid JSON body", "error_code": ErrorCode.schema_invalid.value},
                status_code=400)
        validated = _validate_dispatch(body)
        if isinstance(validated, JSONResponse):
            return validated
        task = Task(
            target_node=validated.target_node,
            payload=validated.payload,
            timeout=validated.timeout)
        sent = await router.dispatch(task)
        if not sent:
            return JSONResponse(
                {"error": "node offline or not connected", "error_code": ErrorCode.node_offline.value},
                status_code=503)
        result = await router.wait_result(task.task_id, timeout=task.timeout)
        if result:
            return JSONResponse(result.model_dump(mode="json"))
        return JSONResponse(
            {"error": "timeout", "error_code": ErrorCode.timeout.value},
            status_code=504)

    async def report_result(request: Request):
        err = await require_node_token(request, node_token)
        if err:
            return err
        body = await request.json()
        result = TaskResult(**body)
        router.submit_result(result)
        return JSONResponse({"status": "ok"})

    async def get_result(request: Request):
        err = await require_client_token(request, client_token)
        if err:
            return err
        task_id = request.path_params["task_id"]

        # Always return persisted metadata (no payload/result body)
        meta = task_store.get(task_id)
        if not meta:
            return JSONResponse({"error": "not found"}, status_code=404)

        resp = meta.model_dump(mode="json")

        # Optionally include in-memory result body for sync callers
        full = request.query_params.get("full", "").lower() in ("true", "1")
        if full:
            result = router.get_result(task_id)
            if result:
                resp["result"] = result.model_dump(mode="json")
            else:
                resp["result"] = None

        return JSONResponse(resp)

    return [
        Route("/api/tasks/dispatch", dispatch, methods=["POST"]),
        Route("/api/tasks/dispatch_sync", dispatch_sync, methods=["POST"]),
        Route("/api/tasks/result", report_result, methods=["POST"]),
        Route("/api/tasks/{task_id}", get_result, methods=["GET"]),
    ]
