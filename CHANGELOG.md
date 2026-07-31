# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

> 本项目处于 SemVer `0.x.x` 早期阶段，不承诺向后兼容。首个公开发布版本为 `0.1.0rc1`。

## [Unreleased]

## [0.1.0rc1] - 2026-07-31

首个公开发布的预发布版本，进入 Dogfooding 阶段。

### Added

- 接入百度小度智能设备：通过百度 BDUSS Cookie 拉取家庭与设备列表，采用 `DataUpdateCoordinator` 统一轮询架构
- 6 个实体平台：`light`（灯）、`switch`（开关/插座/取暖器/新风/开窗器）、`climate`（空调）、`cover`（窗帘）、`lock`（门锁）、`button`（晾衣架）
- Config Flow 图形化配置：Cookie → 选择家庭 → 选择设备 → 房间映射 → 巴法云配置（可选）
- 巴法云（Bemfa）MQTT 三方同步：灯、插座、开关、空调、窗帘可同步到巴法云，便于接入天猫精灵、小爱同学等第三方平台
- 房间映射：自动建立小度房间到 Home Assistant 区域的映射，并可在选项流程中修改
- 重新认证：Cookie 过期后可在集成卡片上重新认证，无需删除重新添加
- 诊断信息导出：支持下载诊断信息（已脱敏 Cookie），便于问题排查
- 国际化（i18n）：英文（`en`）与简体中文（`zh-Hans`）
