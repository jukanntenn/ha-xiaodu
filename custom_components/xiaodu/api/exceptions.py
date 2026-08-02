"""Xiaodu API 的异常定义。"""

from __future__ import annotations


class XiaoduError(Exception):
    """Xiaodu API 错误的基类异常。"""


class XiaoduAuthError(XiaoduError):
    """认证（Authentication）错误。"""

    def __init__(self, message: str = "Authentication failed") -> None:
        """初始化认证错误。"""
        super().__init__(message)


class XiaoduApiError(XiaoduError):
    """API 错误。"""

    def __init__(self, message: str, status: int | None = None) -> None:
        """初始化 API 错误。"""
        super().__init__(message)
        self.status = status


class XiaoduRateLimitError(XiaoduApiError):
    """请求频率限制（Rate limit）错误。"""

    def __init__(
        self, message: str = "Rate limited", retry_after: int | None = None
    ) -> None:
        """初始化频率限制错误。"""
        super().__init__(message, status=429)
        self.retry_after = retry_after


class XiaoduNotFoundError(XiaoduApiError):
    """设备未找到错误。"""

    def __init__(self, appliance_id: str) -> None:
        """初始化未找到错误。"""
        super().__init__(f"Device not found: {appliance_id}", status=404)
        self.appliance_id = appliance_id


class XiaoduNetworkError(XiaoduError):
    """网络（Network）错误。"""

    def __init__(self, message: str = "Network error") -> None:
        """初始化网络错误。"""
        super().__init__(message)
