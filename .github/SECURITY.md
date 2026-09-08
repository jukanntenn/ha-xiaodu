# 安全政策

## 报告漏洞

**请私密报告——绝不在公开 issue、PR 或 Discussion 中报告安全漏洞，也不要在公开渠道贴 PoC。**

- **首选**：本仓库 Security 标签页的「私密报告」（[Report a vulnerability](https://github.com/jukanntenn/ha-xiaodu/security/advisories/new)）。该渠道支持协调披露，修复后可发布 GitHub Security Advisory（含可能的 CVE）
- **备选**：邮件 jukanntenn@outlook.com

## 报告应包含什么

足以分诊即可，不需要长篇报告：

- 简短描述 + 受影响的组件（小度 API 客户端 / 巴法云 MQTT 同步 / 配置流程 / CI workflow）
- 最小复现步骤
- 环境（Home Assistant 版本、集成版本）
- 一两句话说明影响：攻击者能获得什么、需要什么前提

## 处理预期

- 单人 best-effort 维护，约 3 天内确认收到（无硬性 SLA）
- 经 GitHub Security Advisory 协调披露，修复发布前细节保持私密
- 报告者会获得进展通报，并在修复发布时致谢（要求匿名的除外）
- 安全修复会在 CHANGELOG 与 Release Notes 中明确标注

## 范围与信任边界

- 仓库内的一切都在范围内
- **不在范围（上游责任）**：百度云平台自身的漏洞请报告百度；巴法云平台自身的漏洞请报告巴法云；Home Assistant core 本身的问题请报告 [HA 项目](https://www.home-assistant.io/security)；家庭网络安全不归本项目管
- **属设计而非漏洞**：百度 BDUSS Cookie 与巴法云密钥按 Home Assistant 标准存放于配置条目（`.storage`），这是 HA 全部云集成的一致行为；诊断信息导出已自动脱敏（敏感字段显示为 `**REDACTED**`），分享前仍建议自查一遍
- 依赖 CVE 由每周自动运行的 pip-audit 扫描兜底，但怀疑时仍欢迎私密报告

## 支持版本

| 版本 | 支持 |
| ---- | ---- |
| 最新发布（v0.1.0rc1）与 main 分支 | ✅ |

项目处于预发布阶段，没有 backport 分支，只有最新版本会获得修复。此政策会随正式发版演进。
