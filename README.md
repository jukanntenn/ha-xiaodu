# Xiaodu for Home Assistant

[![Tests](https://github.com/jukanntenn/ha-xiaodu/actions/workflows/tests.yml/badge.svg)](https://github.com/jukanntenn/ha-xiaodu/actions/workflows/tests.yml)
[![License: MIT](https://img.shields.io/badge/License-MIT-blue.svg)](LICENSE)
[![HACS Custom](https://img.shields.io/badge/HACS-Custom-41BDF5.svg)](https://github.com/hacs/integration)

非官方 Home Assistant 自定义集成，把百度小度（Xiaodu）智能设备接入 Home Assistant：通过百度 BDUSS Cookie 拉取家庭与设备列表，无需抓包或改装设备。可选开启巴法云（Bemfa）同步，让天猫精灵、小爱同学等第三方语音平台联动控制小度设备。

> **项目状态**：`v0.1.0rc1` 预发布（dogfooding 阶段）。核心功能已可用，配置格式与行为仍可能调整。

## 功能特性

- 六类设备平台：灯光（Light）、开关/插座（Switch）、空调（Climate）、窗帘（Cover）、门锁（Lock）、晾衣架（Button）
- 巴法云三方同步（可选）：将设备镜像到巴法云，接入天猫精灵、小爱同学等第三方语音平台
- 房间映射：按名称相似度自动建立小度房间到 Home Assistant 区域的映射，可在选项中逐个调整
- 图形化配置：全程 Config Flow，无需 YAML；Cookie 过期后可在集成卡片上一键重新认证
- 状态同步：每 30 秒轮询设备状态；设备改名、区域调整经事件监听近实时同步到巴法云
- 诊断信息导出：Cookie 与巴法云密钥自动脱敏，可安全地附到 issue 辅助排查
- 中英文界面：支持 zh-Hans 与 en

## 环境要求

- Home Assistant ≥ 2026.1.0
- 已安装 HACS（推荐）或具备手动安装能力
- 百度账号（用于获取 BDUSS Cookie）
- 巴法云账号（可选）：v2 API 需完成实名认证，v1 旧版仅需私钥

## 安装

### 方式一：HACS 安装（推荐）

1. 在 Home Assistant 中已安装 HACS
2. 将本仓库添加为自定义仓库：
   - 进入 HACS → 集成 → 右上角菜单 → 自定义仓库
   - 仓库地址：<https://github.com/jukanntenn/ha-xiaodu>
   - 类别选择「集成」
3. 在 HACS 中搜索 Xiaodu 并点击安装
4. 重启 Home Assistant

### 方式二：手动安装

1. 下载本仓库代码
2. 将 custom_components/xiaodu/ 目录完整复制到 Home Assistant 配置目录下的 custom_components/ 文件夹中（最终路径应为 config/custom_components/xiaodu/）
3. 重启 Home Assistant

### 跟踪最新开发进度（可选）

想抢在预发布版之前体验最新修复，可在 HACS 的 Xiaodu 条目中选择「重新下载」，版本选择 **main** 分支——HACS 会改为按提交跟踪，main 每次推送后都会提示更新。不保证稳定，仅供尝鲜与验证修复。

## 配置

本集成通过 Config Flow 进行配置，无需 YAML。

### 配置步骤

1. 进入「设置 → 设备与服务 → 添加集成」，搜索 Xiaodu
2. 输入百度 Cookie：填入百度 BDUSS Cookie（有效期约 180 天，获取方法见 FAQ）
3. 选择家庭：从拉取到的家庭列表中选择要同步的家庭
4. 选择设备：勾选需要同步到 Home Assistant 的设备（默认全选）
5. 房间映射：确认小度房间到 Home Assistant 区域的映射（自动生成，可逐个调整）
6. 巴法云配置（可选）：选择认证方式——**v2 API（推荐，需实名认证）**、v1 旧版（仅私钥）、或跳过
7. 配置完成后，Home Assistant 会自动弹出「命名和分配」（Name and assign）对话框，这是 HA 的标准流程，可在其中调整设备名称和分配区域，无需操作可直接关闭。设备默认名已自动剥离房间前缀（如「儿童房主灯」→「主灯」），区域自动关联到映射后的房间

若启用了巴法云同步，配置完成后还会收到一条引导通知：在米家 App 绑定巴法云账号后，即可用小爱同学等语音控制已同步的设备。通知可直接忽略，重启 Home Assistant 后不再出现。

### 重新认证

当 Cookie 过期时，集成会出现认证失败提示。点击集成卡片上的「重新认证」，输入新的百度 Cookie 即可，无需删除集成重新配置。

### 配置项

集成卡片上的「配置」选项可随时修改：

- 房间映射
- 巴法云设置（更换凭据、v1/v2 切换、禁用同步）
- 重新认证

## 支持的设备

设备类型由集成内部的设备类型映射与各平台类型集合定义：

| 平台 | 小度设备类型 | 说明 |
| ------ | ------------- | ------ |
| Light（灯） | LIGHT | 各类灯具 |
| Switch（开关） | SOCKET、SWITCH、HEATER、AIR_FRESHER、WINDOW_OPENER | 插座、开关、取暖器、新风、开窗器 |
| Climate（空调） | AIR_CONDITION | 空调 |
| Cover（窗帘） | CURTAIN | 窗帘 |
| Lock（门锁） | DOOR_LOCK | 智能门锁 |
| Button（按钮） | CLOTHES_RACK | 晾衣架 |

未在表中列出的设备类型不会生成实体（可在诊断信息的 `unsupported_devices` 中查看），欢迎通过 issue 反馈。

## FAQ

### Q1：如何获取百度 Cookie（BDUSS）？

1. 在浏览器登录百度账号
2. 打开开发者工具（F12）→ Application（应用）→ Cookies
3. 找到 BDUSS 字段，复制其值填入配置

### Q2：Cookie 过期了怎么办？

百度 BDUSS 有效期约 180 天。过期后会出现认证失败，可在集成卡片上点击「重新认证」输入新 Cookie，无需删除集成。

### Q3：巴法云同步失败怎么办？

- 确认巴法云 UID 填写正确（在巴法云控制台获取，推荐完成实名认证后使用 v2 API）
- 检查网络是否能访问巴法云 MQTT 服务
- 通过诊断信息查看 `bemfa` 部分的 `sync_status`/`sync_error` 字段确认具体失败原因
- 巴法云同步为可选功能，不影响小度设备本身的控制

### Q4：同步到巴法云的设备怎么识别？

集成创建的巴法云设备 topic 以 `xdu` 前缀开头（如 `xdu4f8e2c1a9b7d002`），由小度设备 ID 哈希生成——与设备名/昵称无关，改名不会影响关联。集成只操作带该前缀的设备，不会触碰你自己在巴法云创建的设备；删除集成时会自动清理。

### Q5：设备没有被识别 / 没有发现？

- 确认在「选择设备」步骤勾选了目标设备
- 确认设备类型在支持列表中（见「支持的设备」）
- 通过诊断信息导出查看设备原始数据
- 若为新设备类型，可提交 Issue 反馈

### Q6：状态多久同步一次？

设备状态每 30 秒轮询一次；设备改名、区域调整通过事件监听近实时同步到巴法云。

### Q7：集成会存储哪些敏感信息？

百度 BDUSS Cookie 与巴法云 UID/密钥，按 Home Assistant 标准存放于配置目录 `.storage` 的配置条目中。诊断信息导出时这些字段会自动脱敏（显示为 `**REDACTED**`）。请像保管账号密码一样保管你的 Home Assistant 配置目录。

## 诊断与日志

提交 Issue 或排查问题时，请附上 debug 日志和诊断信息：

1. 进入「设置 → 设备与服务 → Xiaodu」集成卡片
2. 点击右上角三点菜单 → **启用调试日志（Enable debug logging）**
3. 复现问题（如控制设备、触发巴法云同步）
4. 再次点击三点菜单 → **禁用调试日志（Disable debug logging）**，系统会提示下载日志文件
5. 点击三点菜单 → **下载诊断信息（Download diagnostics）**，下载诊断 JSON 文件
6. 将上述两个文件附到 Issue 中

> 诊断 JSON 已自动对 Cookie、巴法云 secretID/secretKey 等敏感字段脱敏，可放心附上。

## 社区与支持

- 使用 / 配置 / 巴法云同步问题 → [Discussions 问答区](https://github.com/jukanntenn/ha-xiaodu/discussions)（请先搜索既有讨论）
- 可复现 bug 与具体功能请求 → [Issues](https://github.com/jukanntenn/ha-xiaodu/issues/new/choose)（表单会引导填写环境信息）
- 安全漏洞 → 私密报告（见[安全政策](.github/SECURITY.md)），绝不开公开 issue
- Home Assistant 本身的问题 → [官方社区](https://community.home-assistant.io) / [中文社区](https://bbs.hassbian.com)

支持是社区性质的 best-effort，没有商业支持或 SLA，完整的分流说明见 [SUPPORT.md](.github/SUPPORT.md)。

## 参与贡献

本项目由 jukanntenn 与贡献者以 best-effort 方式维护。欢迎参与——任何变更（包括错字修正）都请先开 issue：

- 贡献指南：[CONTRIBUTING.md](CONTRIBUTING.md)
- 新手入口：[good first issue](https://github.com/jukanntenn/ha-xiaodu/labels/good%20first%20issue)

## License

本项目基于 MIT License 开源，详见 LICENSE 文件。

---

## 免责声明

本项目开发初衷仅为学习及技术交流，切勿将本工程用于任何非法用途，否则一切后果自负，与本项目的作者无关。
