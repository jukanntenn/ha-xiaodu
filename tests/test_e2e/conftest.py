"""E2E fixtures：真实本地 HTTP server + MQTT 探针 + 端点重定向。"""

from __future__ import annotations

from collections.abc import AsyncGenerator
from typing import Any

import pytest
from aiohttp import web
from aiohttp.test_utils import TestServer

from tests.conftest import load_json_fixture


@pytest.fixture(autouse=True)
def _threaded_dns_resolver() -> None:
    """强制 aiohttp 使用线程 DNS 解析器。

    本环境安装了 aiodns，aiohttp 默认 AsyncResolver 的共享 manager
    跨测试事件循环复用 aiodns resolver，导致 "attached to a different loop"。
    """
    import aiohttp.resolver as aiohttp_resolver

    aiohttp_resolver.DefaultResolver = aiohttp_resolver.ThreadedResolver


class ApiServer:
    """记录/回放 HTTP server：按 method+path 回放 fixtures，记录请求。"""

    def __init__(self, base: str) -> None:
        self.base = base
        self.requests: list[dict[str, Any]] = []
        self._overrides: dict[str, dict[str, Any]] = {}

    def set_response(
        self, path: str, *, status: int = 200, json: Any | None = None
    ) -> None:
        """按 path 覆盖响应（用于动态场景与错误注入）。"""
        self._overrides[path] = {"status": status, "json": json}

    def _fixture_for(self, method: str, path: str) -> tuple[int, Any]:
        if path in self._overrides:
            override = self._overrides[path]
            return override["status"], override["json"]
        mapping = {
            ("POST", "/appserver/gateway/app/v1"): ("check_session_ok.json", "xiaodu"),
            ("POST", "/saiya/smarthome/multihouse"): ("home_list.json", "xiaodu"),
            ("POST", "/saiya/smarthome/appliance"): ("device_list.json", "xiaodu"),
            ("GET", "/saiya/smarthome/appliancedetails"): (
                "device_detail_light.json",
                "xiaodu",
            ),
            ("GET", "/saiya/smarthome/directivesend"): (
                "control_response_ok.json",
                "xiaodu",
            ),
            ("POST", "/vs/web/v2/createTopic"): ("create_topic_ok.json", "bemfa"),
            ("POST", "/v1/createTopic"): ("create_topic_ok.json", "bemfa"),
            ("POST", "/v1/deleteTopic"): ("delete_topic_ok.json", "bemfa"),
            ("POST", "/vb/api/v1/changeTopicRoom"): (
                "change_topic_room_ok.json",
                "bemfa",
            ),
            ("POST", "/vb/api/v1/changeTopicGroup"): (
                "change_topic_group_ok.json",
                "bemfa",
            ),
        }
        fixture, subdir = mapping.get((method, path), (None, None))
        if fixture is None:
            return 404, {"error": "not found"}
        return 200, load_json_fixture(fixture, subdir)

    async def _handler(self, request: web.Request) -> web.Response:
        body: Any = None
        if request.content_type == "application/json":
            body = await request.json()
        self.requests.append(
            {
                "method": request.method,
                "path": request.path,
                "query": dict(request.query),
                "body": body,
            }
        )
        status, payload = self._fixture_for(request.method, request.path)
        return web.json_response(payload, status=status)

    def make_app(self) -> web.Application:
        app = web.Application()
        app.router.add_route("*", "/{tail:.*}", self._handler)
        return app


@pytest.fixture
async def api_server(
    socket_enabled: None,
    aiohttp_server,
) -> AsyncGenerator[ApiServer]:
    """启动真实本地 HTTP server 并重定向集成端点。"""
    server_handle = ApiServer("")
    server: TestServer = await aiohttp_server(server_handle.make_app())
    server_handle.base = f"http://127.0.0.1:{server.port}"

    import custom_components.xiaodu as xiaodu_module
    import custom_components.xiaodu.api.xiaodu_client as xiaodu_client

    monkeypatch = pytest.MonkeyPatch()
    # 集成入口（__init__.py）按调用时读取模块绑定的常量构造客户端，
    # 因此重定向 `custom_components.xiaodu` 上的绑定即可指向本地真实服务。
    monkeypatch.setattr(xiaodu_module, "HOST", server_handle.base)
    monkeypatch.setattr(
        xiaodu_module,
        "BEMFA_CREATE_TOPIC_URL",
        f"{server_handle.base}/vs/web/v2/createTopic",
    )
    monkeypatch.setattr(
        xiaodu_module,
        "BEMFA_CREATE_TOPIC_V1_URL",
        f"{server_handle.base}/v1/createTopic",
    )
    monkeypatch.setattr(
        xiaodu_module,
        "BEMFA_DELETE_TOPIC_URL",
        f"{server_handle.base}/v1/deleteTopic",
    )
    monkeypatch.setattr(
        xiaodu_module,
        "BEMFA_CHANGE_ROOM_URL",
        f"{server_handle.base}/vb/api/v1/changeTopicRoom",
    )
    monkeypatch.setattr(
        xiaodu_module,
        "BEMFA_CHANGE_GROUP_URL",
        f"{server_handle.base}/vb/api/v1/changeTopicGroup",
    )
    # 同时重定向源模块常量，覆盖单元层直接构造客户端的路径。
    monkeypatch.setattr(xiaodu_client, "HOST", server_handle.base)
    yield server_handle
    monkeypatch.undo()
