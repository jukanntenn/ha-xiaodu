# ha-xiaodu 架构

[English](architecture.md) | 中文

改动源码树之前先读本文。它是代码库的有序地图——组件、边界、以及新行为的归属；决策理由在链接的 RFC（决策记录）里。

## 这个包是什么

ha-xiaodu 是一个 Home Assistant 自定义集成，通过云轮询把小度云设备（灯、开关、空调、窗帘、门锁）接入 HA 实体。经 HACS 分发给最终用户，并可选地把设备状态镜像到巴法云 MQTT 账户供语音助手场景使用。

## 组件

| 组件 | 职责 | 公共接口 |
|---|---|---|
| `custom_components/xiaodu/api/` | 小度云客户端、类型模型与错误 | 供 coordinator 消费的 `XiaoduClient` |
| `custom_components/xiaodu/bemfa/` | 巴法云 MQTT 同步：客户端、API、同步管理器、状态发布 | `BemfaSyncManager` 生命周期 |
| 平台文件（`light.py`、`switch.py`、`climate.py`、`cover.py`、`lock.py`、`button.py`） | 每类设备一个 HA 实体平台 | HA 平台 setup 函数 |
| `coordinator.py` / `entity.py` | 轮询协调器与实体基类 | 各平台消费的 `XiaoduCoordinator` |
| `config_flow.py` / `const.py` / `room_mapping.py` | 配置向导、常量、房间映射 | config entry options schema |
| `tests/` | 跑在 mock HTTP 上的 pytest 套件 | `conftest.py` 的 `aioclient_mock_fixture` |
| `scripts/` | 工具：hassfest 封装、发版、commit-msg 校验 | 开发者脚本与 prek 钩子入口 |

## 新行为去哪里

新设备类新增一个平台文件并经 `entity.py` 接线；新的云端能力先落 `api/`；巴法云镜像的任何改动都收在 `bemfa/` 的 `BemfaSyncManager` 之后。常量进 `const.py` 或 `bemfa/const.py`，禁止内联字面量；模块依赖保持单向：platform → entity → coordinator → api/bemfa。归属参考文档：[文档标准](AGENTS.md)、[双语文档契约](i18n/README.zh.md)与 [RFC 规则](../.agents/rfcs/README.zh.md)。

贡献者入口见 [development.md](development.zh.md)。
