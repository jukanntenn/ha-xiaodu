"""巴法云（Bemfa）配置后的引导提醒。

config flow 完成且启用巴法云同步时，创建一条 persistent_notification，
提醒用户还需在米家 App 绑定巴法云账号才能启用语音控制。

设计取舍（为什么用 persistent_notification 而非 repairs issue）：
「去米家绑定」是信息性引导而非故障，repairs issue 的 WARNING 语义
（官方定义 = "将来会坏"）过重；persistent_notification 显示在通知中心
铃铛下，视觉重量轻，是 HA core 里 hue（「去 Hue app 更新固件」）、
ps4 等集成做同类「外部 App 操作引导」的标准范式。

生命周期：仅在 config flow 完成时创建一次。persistent_notification 是
纯内存的（``@singleton`` dict，无 storage），HA 重启即消失；用户 dismiss
后永久不复现（除非重新配置）。绝不持续打扰。
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from homeassistant.components.persistent_notification import (
    async_create as async_create_persistent_notification,
)

from .const import DOMAIN

if TYPE_CHECKING:
    from homeassistant.core import HomeAssistant

# 确定性的 notification_id：保证同一集成多次调用是幂等的（覆盖而非堆叠）。
NOTIFICATION_ID = f"{DOMAIN}_bemfa_mihome_binding"

_NOTIFICATION_TITLE = "巴法云语音控制尚未激活"
_NOTIFICATION_MESSAGE = (
    "设备已同步到巴法云。要使用小爱同学/小度语音控制，"
    "还需在米家 App 绑定巴法云账号：\n\n"
    "我的 → 其他平台设备 → 添加 → 选择「巴法」→ "
    "输入巴法云账号（即配置时填写的私钥对应的账号），设备即会自动同步到米家。\n\n"
    "完成后可忽略此提醒。"
)


def create_bemfa_binding_notification(hass: HomeAssistant) -> None:
    """创建「去米家绑定巴法云」的引导通知。

    在 config flow 完成（启用巴法云同步）时调用一次。
    用户 dismiss 或 HA 重启后即消失，不会持续打扰。
    """
    async_create_persistent_notification(
        hass,
        _NOTIFICATION_MESSAGE,
        title=_NOTIFICATION_TITLE,
        notification_id=NOTIFICATION_ID,
    )
