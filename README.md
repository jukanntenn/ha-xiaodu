# ha-xiaodu

Home Assistant 自定义集成，用于接入百度小度智能设备（含巴法云三方同步）。

## 功能特性

- 多平台支持：灯光（Light）、开关（Switch）、空调（Climate）、窗帘（Cover）、门锁（Lock）、按钮（Button）
- 巴法云同步：可选将小度设备同步到巴法云，便于第三方平台（如天猫精灵、小爱同学）联动控制
- 房间映射：自动建立小度房间到 Home Assistant 区域的映射，并可在选项中修改
- Config Flow 配置流程：通过图形界面完成配置，无需手动编辑 YAML
- 重新认证：Cookie 过期后可在集成中直接重新认证，无需删除重新添加
- 诊断信息导出：支持下载诊断信息，便于问题排查
- 国际化（i18n）：支持英文（en）与简体中文（zh-Hans）

## 环境要求

- Home Assistant ≥ 2026.1.0
- Python ≥ 3.13（由 HA 自动管理，无需单独安装）
- 已安装 HACS（推荐）或手动安装能力

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

## 配置

本集成通过 Config Flow 进行配置，无需 YAML。

### 配置步骤

1. 进入「设置 → 设备与服务 → 添加集成」，搜索 Xiaodu
2. 输入百度 Cookie：填入百度 BDUSS Cookie（有效期约 180 天）
3. 选择家庭：从拉取到的家庭列表中选择要同步的家庭
4. 选择设备：勾选需要同步到 Home Assistant 的设备
5. 房间映射：确认小度房间到 Home Assistant 区域的映射关系
6. 巴法云配置（可选）：填入巴法云 UID 并启用同步，留空则跳过

### 重新认证

当 Cookie 过期时，集成会出现认证失败提示。点击集成卡片上的「重新认证」，输入新的百度 Cookie 即可，无需删除集成重新配置。

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

## FAQ

### Q1：如何获取百度 Cookie（BDUSS）？

1. 在浏览器登录百度账号
2. 打开开发者工具（F12）→ Application（应用）→ Cookies
3. 找到 BDUSS 字段，复制其值填入配置

### Q2：Cookie 过期了怎么办？

百度 BDUSS 有效期约 180 天。过期后会出现认证失败，可在集成卡片上点击「重新认证」输入新 Cookie，无需删除集成。

### Q3：巴法云同步失败怎么办？

- 确认巴法云 UID 填写正确（在巴法云控制台获取）
- 检查网络是否能访问巴法云 MQTT 服务
- 查看集成日志确认具体错误
- 巴法云同步为可选功能，不影响小度设备本身的控制

### Q4：设备没有被识别 / 没有发现？

- 确认在「选择设备」步骤勾选了目标设备
- 确认设备类型在支持列表中（见「支持的设备」）
- 通过诊断信息导出查看设备原始数据
- 若为新设备类型，可提交 Issue 反馈

## 参与贡献

欢迎通过 Pull Request 或 Issue 参与本项目：

- 仓库地址：<https://github.com/jukanntenn/ha-xiaodu>
- 问题反馈：<https://github.com/jukanntenn/ha-xiaodu/issues>

提交 PR 前请确保：

- 代码风格一致
- 新功能附带必要说明
- 不引入敏感信息（如 Cookie、密钥）

## 许可证

本项目基于 MIT License 开源，详见 LICENSE 文件。

---

## 免责声明

本项目开发初衷仅为学习及技术交流，切勿将本工程用于任何非法用途，否则一切后果自负，与本项目的作者无关。
