# 更新日志

本项目遵循 [Keep a Changelog](https://keepachangelog.com/en/1.1.0/) 与 [语义化版本](https://semver.org/spec/v2.0.0.html)。当前处于 SemVer `0.x.x` 早期阶段，不承诺向后兼容；首个公开发布版本为 `0.1.0rc1`。

## [Unreleased]

### Fixed

- 修复配置流程最后一步设备信息提示无法显示的问题（翻译文件结构错误导致 hassfest 校验失败）

### Changed

- 本地质量门控新增 hassfest 结构校验，与 CI 同源，提前拦截翻译文件结构错误

## [0.1.0rc1]

首个公开发布的预发布版本，进入 Dogfooding 阶段。

### Added

- 接入百度小度智能设备：通过百度 BDUSS Cookie 拉取家庭与设备列表，统一轮询同步状态
- 支持灯、开关/插座、空调、窗帘、门锁、晾衣架 6 类设备实体
- 巴法云（Bemfa）MQTT 三方同步：可接入天猫精灵、小爱同学等第三方平台
- 自动建立小度房间到 Home Assistant 区域的映射，并可在选项流程中修改
- 图形化配置流程、Cookie 过期后重新认证、脱敏诊断信息导出、中英文双语界面
