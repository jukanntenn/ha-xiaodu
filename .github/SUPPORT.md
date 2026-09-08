# 支持与求助

issue 列表只接受**可复现的 bug** 与**具体的功能请求**。其他问题按下面的渠道分流——找对地方，能更快得到解答。

## 求助渠道

1. **使用 / 配置 / 巴法云同步问题** → [Discussions 问答区](https://github.com/jukanntenn/ha-xiaodu/discussions)（请先搜索既有讨论）
2. **可复现 bug 与具体功能请求** → [Issues](https://github.com/jukanntenn/ha-xiaodu/issues/new/choose)，模板表单会引导你填写环境信息
3. **安全漏洞** → 私密报告，见[安全政策](SECURITY.md)——绝不开公开 issue

## 上游问题（在本项目提了也解决不了）

- **Home Assistant 本身**的安装 / 使用 / 配置问题 → [官方社区论坛](https://community.home-assistant.io) / [中文社区（瀚思彼岸）](https://bbs.hassbian.com)
- **小度 App 或百度云平台**的问题（语音助手、设备分享、App 功能等）→ 百度官方渠道
- **巴法云平台**的问题（控制台、MQTT 服务本身）→ 巴法云官方

在本项目提的上游问题会被礼貌地引导转出，不是不欢迎你，是这里真的修不了。

## 可操作的 bug 报告长什么样

- **精确的复现步骤**：从打开配置页到出错，一步步能照着做
- **环境信息**：Home Assistant Core 版本与安装类型（OS / Container / Supervised / Core）、集成版本、涉及的设备类型、是否启用巴法云同步
- **期望结果 vs 实际结果**，附上**诊断信息 JSON**（集成卡片 → 三点菜单 → 下载诊断信息；敏感字段已自动脱敏）

bug 表单会逐一引导这些字段，照着填即可。

## 我们帮不上的

- 模糊报告（如「设备控制不了！」）会被关闭并指向本页——不是刁难，是没有环境与现象细节就无法分诊
- 家庭网络或百度账号本身的问题请先自行排查：Cookie 是否过期、网络是否可达巴法云 MQTT 服务
- 本项目没有商业支持，没有 SLA——所有支持都是社区 best-effort
