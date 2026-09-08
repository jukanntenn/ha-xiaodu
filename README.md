# Home Assistant 小度集成

[![Tests](https://github.com/jukanntenn/ha-xiaodu/actions/workflows/tests.yml/badge.svg)](https://github.com/jukanntenn/ha-xiaodu/actions/workflows/tests.yml) [![Version](https://img.shields.io/badge/version-v0.1.0rc1-orange)](https://github.com/jukanntenn/ha-xiaodu/releases) [![License: MIT](https://img.shields.io/badge/License-MIT-blue.svg)](LICENSE) [![HACS Custom](https://img.shields.io/badge/HACS-Custom-41BDF5.svg)](https://github.com/hacs/integration)

把小度智能设备接入 Home Assistant 的自定义集成（非官方）。内置巴法云（Bemfa）同步，可桥接小爱同学等智能音箱，实现语音控制。

> 🚧 **项目状态**：预发布阶段。核心功能已可用，但配置格式与行为等仍可能调整。

## 功能特性

- 💡 **多品类设备支持**：覆盖常见智能设备品类，已支持与已测试设备详见[支持的设备](#支持的设备)
- ⚡ **零门槛接入**：只需填入百度 Cookie，全程通过 Config Flow 完成图形化配置
- 🏠 **房间自动映射**：按名称相似度将小度房间自动匹配到 Home Assistant 区域，映射可逐个调整
- 🔊 **巴法云同步**：内置巴法云（Bemfa）同步，可桥接小爱同学等智能音箱，实现语音控制

## 安装

> Home Assistant 版本要求：≥ 2026.1.0

### 方式一：HACS 安装（推荐）

1. 进入 HACS → 集成 → 右上角菜单 → 自定义仓库
2. 仓库地址填写 <https://github.com/jukanntenn/ha-xiaodu>，类别选择「集成」，点击「新增」
3. 在 HACS 中搜索 **Xiaodu** 并安装
4. 重启 Home Assistant

> 尚未安装 HACS？参考 [HACS 官网指南](https://www.hacs.xyz/)。

### 方式二：手动安装

1. 从 [Releases](https://github.com/jukanntenn/ha-xiaodu/releases) 下载最新的 `xiaodu.zip`
2. 在配置目录的 `custom_components/` 下新建 `xiaodu` 文件夹，将压缩包内容解压进去（最终路径为 `config/custom_components/xiaodu/`）
3. 重启 Home Assistant

## 配置

### 添加集成

1. 进入「设置 → 设备与服务 → 添加集成」，搜索 **Xiaodu**
2. 填入百度 BDUSS Cookie（获取方法见 [FAQ](#faq)）
3. 从拉取到的家庭列表中选择要同步的家庭
4. 勾选需要同步到 Home Assistant 的设备（默认全选）
5. 确认小度房间到 Home Assistant 区域的映射（自动匹配，可逐个调整）
6. 巴法云配置（可选）：**v2 API（推荐，需实名认证）** / v1 旧版（仅私钥） / 跳过

配置完成后，Home Assistant 会自动弹出「命名和分配」对话框——这是 HA 的标准流程，可在其中微调设备名称与区域分配，直接关闭也没问题：设备名已自动剥离房间前缀（「儿童房主灯」→「主灯」），区域已按房间映射自动关联。

### 启用语音控制（可选）

若开启了巴法云同步，在米家 App 中绑定巴法云账号后，即可用小爱同学语音控制已同步的设备。

### 重新认证

Cookie 过期时，集成会出现认证失败提示。点击集成卡片上的「重新认证」，填入新的百度 Cookie 即可。

### 修改配置

集成卡片上的 ⚙️「配置」选项可随时：

- 修改房间映射
- 修改巴法云配置（更换凭据、v1/v2 切换、禁用同步）
- 重新认证

## 支持的设备

当前支持的设备种类及其在 Home Assistant 中的实体形态如下。测试状态分两级：

- 🧪 **自动化集成测试**：基于真实抓取的设备数据在 CI 中运行
- 📡 **真机测试**：已在真实设备上验证

| 设备种类 | 小度类型码      | Home Assistant 实体 | 测试状态 | 备注                                                 |
| -------- | --------------- | ------------------- | :------: | ---------------------------------------------------- |
| 灯光     | `LIGHT`         | 灯（Light）         |  🧪 📡   | 开关；亮度、色温、情景模式按设备能力自动适配         |
| 插座     | `SOCKET`        | 开关（Switch）      |  🧪 📡   |                                                      |
| 墙壁开关 | `SWITCH`        | 开关（Switch）      |    🧪    |                                                      |
| 取暖器   | `HEATER`        | 开关（Switch）      |    🧪    |                                                      |
| 新风     | `AIR_FRESHER`   | 开关（Switch）      |    🧪    |                                                      |
| 开窗器   | `WINDOW_OPENER` | 开关（Switch）      |    —     | 尚未测试                                             |
| 空调     | `AIR_CONDITION` | 温控器（Climate）   |  🧪 📡   | 目标温度、五种模式、风速调节；真机仅测试了开启与关闭 |
| 窗帘     | `CURTAIN`       | 窗帘（Cover）       |    🧪    | 支持位置控制                                         |
| 智能门锁 | `DOOR_LOCK`     | 锁（Lock）          |    🧪    | 上锁 / 解锁                                          |
| 晾衣架   | `CLOTHES_RACK`  | 按钮（Button）      |    🧪    | 一键触发设备动作                                     |

> 👏 欢迎提供更多的真机实测报告。

## FAQ

### Q1：如何获取百度 Cookie（BDUSS）？

1. 在浏览器登录百度账号
2. 按 F12 打开开发者工具，进入 Application（应用）→ Cookies
3. 找到 BDUSS 字段，复制其值用于配置

### Q2：同步到巴法云的设备怎么识别？

集成创建的巴法云设备 topic 均以 `xdu` 前缀开头（如 `xdu4f8e2c1a9b7d002`），由小度设备 ID 哈希生成，与设备名称无关——改名不影响关联。集成只操作带此前缀的设备，不会影响你在巴法云手动创建的设备；删除集成时会自动清理。

### Q3：状态多久同步一次？

设备状态每 30 秒自动刷新一次；若开启了巴法云同步，设备改名、区域调整会近实时同步到巴法云。

### Q4：集成会存储哪些敏感信息？

百度 BDUSS Cookie 与巴法云 UID/密钥，按 Home Assistant 标准存放于配置目录 `.storage` 的配置条目中。请像保管账号密码一样保管你的 Home Assistant 配置目录。

## 诊断与日志

提交 issue 或排查问题时，请附上调试日志与诊断信息：

1. 进入「设置 → 设备与服务 → Xiaodu」集成卡片
2. 在三点菜单中选择 **下载诊断信息（Download diagnostics）**，下载诊断 JSON
3. 将文件内容附到 issue 中

> ⚠️ 诊断 JSON 可能含敏感字段，公开前请审核脱敏。

## 社区与支持

- 使用 / 配置 / 巴法云同步问题 → [Discussions 问答区](https://github.com/jukanntenn/ha-xiaodu/discussions)（提问前请先搜索既有讨论）
- 可复现 bug 与具体功能请求 → [Issues](https://github.com/jukanntenn/ha-xiaodu/issues/new/choose)（表单会引导填写环境信息）
- 安全漏洞 → 私密报告（见[安全政策](.github/SECURITY.md)），请勿开公开 issue
- Home Assistant 本身的问题 → [官方社区](https://community.home-assistant.io) / [中文社区](https://bbs.hassbian.com)

支持由社区自愿提供，完整的分流说明见 [SUPPORT.md](.github/SUPPORT.md)。

## 参与贡献

欢迎参与贡献。任何变更（包括错字修正）都请先开 issue，流程与规范见：

- 贡献指南：[CONTRIBUTING.md](CONTRIBUTING.md)
- 新手入口：[good first issue](https://github.com/jukanntenn/ha-xiaodu/labels/good%20first%20issue)

## License

本项目基于 [MIT License](LICENSE) 开源。

---

## 免责声明

本项目开发初衷仅为学习及技术交流，切勿将本工程用于任何非法用途，否则一切后果自负，与本项目的作者无关。
