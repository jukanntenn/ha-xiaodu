"""百度小度云（Baidu Xiaodu cloud）的 Xiaodu API 客户端。"""

from __future__ import annotations

import asyncio
import logging
from typing import Any

from aiohttp import ClientError, ClientSession

from .exceptions import (
    XiaoduApiError,
    XiaoduAuthError,
    XiaoduNetworkError,
    XiaoduNotFoundError,
    XiaoduRateLimitError,
)
from .xiaodu_types import Command, Device, DeviceDetail, Home

_LOGGER = logging.getLogger(__name__)

HOST = "https://xiaodu.baidu.com"

MAX_RETRIES = 3
RETRY_DELAYS = [1, 2, 4]


class XiaoduAPI:
    """Xiaodu API 客户端。"""

    def __init__(
        self, cookie: str, session: ClientSession, host: str | None = None
    ) -> None:
        """初始化 API 客户端。

        Args:
            cookie: 百度 BDUSS Cookie。
            session: aiohttp 客户端会话（client session）。
            host: API 主机；None 时使用模块常量 HOST（调用时解析，便于测试重定向）。
        """
        self._cookie: str = cookie
        self._session: ClientSession = session
        self._host: str = host or HOST
        self._headers: dict[str, str] = self._build_headers()

    def _build_headers(self) -> dict[str, str]:
        """构建通用请求头（headers）。"""
        return {
            "Cookie": f"BDUSS={self._cookie};BDUSS_BFESS={self._cookie}",
            "User-Agent": (
                "Mozilla/5.0 (iPhone; CPU iPhone OS 13_2_3 like Mac OS X) "
                "AppleWebKit/605.1.15 (KHTML, like Gecko) "
                "Version/13.0.3 Mobile/15E148 Safari/604.1"
            ),
            "Content-Type": "application/json",
            "device-id": "deviceid",
            "host": "xiaodu.baidu.com",
        }

    async def _request_with_retry(
        self,
        method: str,
        url: str,
        **kwargs: Any,
    ) -> dict[str, Any]:
        """发起带重试逻辑的 HTTP 请求。

        Args:
            method: HTTP 方法。
            url: 请求 URL。
            **kwargs: 请求的附加参数。

        Returns:
            响应的 JSON 数据。

        Raises:
            XiaoduAuthError: 认证失败时抛出。
            XiaoduNotFoundError: 资源未找到（404）时抛出。
            XiaoduApiError: API 返回错误时抛出。
            XiaoduNetworkError: 发生网络错误时抛出。
        """
        last_error: Exception | None = None
        for attempt in range(MAX_RETRIES):
            try:
                async with self._session.request(method, url, **kwargs) as response:
                    if response.status in (401, 403):
                        raise XiaoduAuthError()  # noqa: RSE102 - 显式实例化，语义更清晰
                    if response.status == 404:
                        raise XiaoduNotFoundError("unknown")
                    if response.status == 429:
                        last_error = XiaoduRateLimitError()
                        _LOGGER.warning(
                            "Rate limited (attempt %d/%d), retrying...",
                            attempt + 1,
                            MAX_RETRIES,
                        )
                    elif response.status >= 500:
                        last_error = XiaoduApiError(
                            f"Server error: {response.status}",
                            status=response.status,
                        )
                        _LOGGER.warning(
                            "Server error (attempt %d/%d): %d",
                            attempt + 1,
                            MAX_RETRIES,
                            response.status,
                        )
                    else:
                        data = await response.json(content_type=None)
                        return self._handle_response(data)
            except (XiaoduAuthError, XiaoduNotFoundError):
                raise
            except XiaoduRateLimitError:
                last_error = XiaoduRateLimitError()
                _LOGGER.warning(
                    "Rate limited (attempt %d/%d), retrying...",
                    attempt + 1,
                    MAX_RETRIES,
                )
            except ClientError as err:
                last_error = err
                _LOGGER.warning(
                    "Request failed (attempt %d/%d): %s",
                    attempt + 1,
                    MAX_RETRIES,
                    err,
                )
            except TimeoutError as err:
                last_error = err
                _LOGGER.warning(
                    "Request timeout (attempt %d/%d): %s",
                    attempt + 1,
                    MAX_RETRIES,
                    err,
                )
            if attempt < MAX_RETRIES - 1:
                await asyncio.sleep(RETRY_DELAYS[attempt])
        if isinstance(last_error, XiaoduRateLimitError):
            raise last_error
        raise XiaoduNetworkError(f"Failed after {MAX_RETRIES} attempts: {last_error}")

    @staticmethod
    def _handle_response(data: dict[str, Any]) -> dict[str, Any]:
        """处理 API 响应并检查错误。

        Args:
            data: 响应的 JSON 数据。

        Returns:
            成功时返回响应数据。

        Raises:
            XiaoduAuthError: 响应表明认证失败时抛出。
            XiaoduApiError: 响应表明出错时抛出。
        """
        status = data.get("status")
        msg = data.get("msg", "")

        if status == 0:
            return data
        if "not login" in msg:
            raise XiaoduAuthError("Cookie expired or invalid")
        raise XiaoduApiError(f"API error: {msg}", status=status)

    async def check_session(self) -> bool:
        """验证 Cookie 是否有效。

        Returns:
            会话有效时返回 True。

        Raises:
            XiaoduAuthError: 认证失败时抛出。
        """
        submit = {
            "url": "dueros://smarthome.bot.dueros.ai/gateway/myspeaker",
        }
        await self._request_with_retry(
            "post",
            f"{self._host}/appserver/gateway/app/v1",
            json=submit,
            headers=self._headers,
        )
        return True

    async def get_home_list(self) -> list[Home]:
        """获取家庭（Home）列表。

        Returns:
            Home 对象列表。

        Raises:
            XiaoduApiError: API 返回错误时抛出。
        """
        submit = {"method": "HOUSE_LIST"}
        data = await self._request_with_retry(
            "post",
            f"{self._host}/saiya/smarthome/multihouse",
            json=submit,
            headers=self._headers,
        )
        house_list = data.get("data", {}).get("houseList", [])
        return [
            Home(
                home_id=house["houseId"],
                home_name=house["houseName"],
            )
            for house in house_list
            if isinstance(house, dict)
        ]

    async def get_device_list(self, house_id: str) -> list[Device]:
        """获取某个家庭下的设备列表。

        Args:
            house_id: 家庭 ID。

        Returns:
            Device 对象列表。

        Raises:
            XiaoduApiError: API 返回错误时抛出。
        """
        submit = {
            "method": "GET_USER_ALL_APPLIANCES",
            "params": {"from": "h5_control", "withscene": 1, "generalscene": 3},
        }
        data = await self._request_with_retry(
            "post",
            f"{self._host}/saiya/smarthome/appliance",
            json=submit,
            headers=self._headers,
            cookies={"HOUSE_ID": house_id},
        )
        appliances = data.get("data", {}).get("appliances", [])
        return [
            Device(
                appliance_id=app["applianceId"],
                friendly_name=app.get("friendlyName", ""),
                room_name=app.get("roomName", "")
                or app.get("room", "")
                or app.get("groupName", ""),
                appliance_types=app.get("applianceTypes", []),
                state_setting=app.get("stateSetting", {}),
                bot_name=app.get("botName"),
            )
            for app in appliances
            if isinstance(app, dict)
        ]

    async def get_device_detail(self, appliance_id: str) -> DeviceDetail:
        """获取设备详情。

        Args:
            appliance_id: 设备的 appliance ID。

        Returns:
            DeviceDetail 对象。

        Raises:
            XiaoduApiError: API 返回错误时抛出。
        """
        submit = {
            "applianceId": appliance_id,
            "version": 2,
            "from": "h5",
        }
        data = await self._request_with_retry(
            "get",
            f"{self._host}/saiya/smarthome/appliancedetails",
            headers=self._headers,
            json=submit,
        )
        appliance = data.get("data", {}).get("appliance", {})
        return DeviceDetail(
            appliance_id=appliance.get("applianceId", appliance_id),
            friendly_name=appliance.get("friendlyName", ""),
            room_name=appliance.get("roomName", "")
            or appliance.get("room", "")
            or appliance.get("groupName", ""),
            appliance_types=appliance.get("applianceTypes", []),
            state_setting=appliance.get("stateSetting", {}),
            bot_name=appliance.get("botName"),
            group_name=appliance.get("groupName"),
            manufacturer=appliance.get("manufacturer"),
            model=appliance.get("model"),
            firmware_version=appliance.get("firmwareVersion"),
        )

    async def control_device(self, appliance_id: str, command: Command) -> bool:
        """向设备发送控制指令。

        Args:
            appliance_id: 设备的 appliance ID。
            command: 要发送的指令。

        Returns:
            指令发送成功时返回 True。

        Raises:
            XiaoduApiError: API 返回错误时抛出。
        """
        submit = self._build_command_payload(appliance_id, command)
        await self._request_with_retry(
            "get",
            f"{self._host}/saiya/smarthome/directivesend?from=h5_control",
            headers=self._headers,
            json=submit,
        )
        return True

    def _build_command_payload(
        self, appliance_id: str, command: Command
    ) -> dict[str, Any]:
        """构建 API 请求的指令载荷（payload）。

        Args:
            appliance_id: 设备的 appliance ID。
            command: 要发送的指令。

        Returns:
            指令载荷字典。
        """
        action = command.action
        params = command.params or {}

        # 构建基础 payload 结构
        parameters: dict[str, Any] = {
            "proxyConnectStatus": False,
        }
        payload: dict[str, Any] = {
            "applianceId": appliance_id,
            "parameters": parameters,
            "appliance": {"applianceId": [appliance_id]},
        }

        # 将指令名称映射为 API header 名称
        action_map = {
            "turnOn": ("TurnOnRequest", 3),
            "turnOff": ("TurnOffRequest", 3),
            "setBrightness": ("SetBrightnessPercentageRequest", 3),
            "setColorTemperatureInKelvin": ("SetColorTemperatureRequest", 3),
            "lightSetMode": ("SetModeRequest", 3),
            "stop": ("PauseRequest", 3),
            "temperatureUp": ("IncrementTemperatureRequest", 1),
            "temperatureDown": ("DecrementTemperatureRequest", 1),
            "setMode": ("SetModeRequest", 1),
            "setFanSpeed": ("IncrementFanSpeedRequest", 1),
        }

        header_name, payload_version = action_map.get(action, (f"{action}Request", 3))

        # 添加特定指令的参数
        if action == "setBrightness":
            parameters["attribute"] = "brightness"
            parameters["attributeValue"] = params.get("attributeValue", 100)
        elif action == "setColorTemperatureInKelvin":
            parameters["attribute"] = "colorTemperatureInKelvin"
            parameters["attributeValue"] = params.get("attributeValue", 5000)
        elif action == "lightSetMode":
            parameters["attribute"] = "mode"
            parameters["attributeValue"] = params.get("mode", "")
        elif action in ("turnOn", "turnOff"):
            value = "ON" if action == "turnOn" else "OFF"
            parameters["attribute"] = "turnOnState"
            parameters["attributeValue"] = value
            payload["turnOnState"] = {"value": value}
        elif action == "setMode":
            mode = params.get("mode", "cool")
            parameters["attribute"] = "mode"
            parameters["attributeValue"] = mode.upper()
            payload["mode"] = {"value": mode.upper()}
        elif action == "setFanSpeed":
            speed = params.get("speed", 2)
            parameters["attribute"] = "fanSpeed"
            parameters["attributeValue"] = speed
            payload["fanSpeed"] = {"value": speed}

        return {
            "header": {
                "namespace": "DuerOS.ConnectedHome.Control",
                "name": header_name,
                "payloadVersion": payload_version,
            },
            "payload": payload,
        }
