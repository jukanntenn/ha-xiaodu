# Home Assistant Xiaodu integration

English | [中文](README.zh.md)

[![Tests](https://github.com/jukanntenn/ha-xiaodu/actions/workflows/tests.yml/badge.svg)](https://github.com/jukanntenn/ha-xiaodu/actions/workflows/tests.yml) [![Version](https://img.shields.io/badge/version-v0.1.0rc1-orange)](https://github.com/jukanntenn/ha-xiaodu/releases) [![License: MIT](https://img.shields.io/badge/License-MIT-blue.svg)](LICENSE) [![HACS Custom](https://img.shields.io/badge/HACS-Custom-41BDF5.svg)](https://github.com/hacs/integration)

An unofficial custom integration that brings Xiaodu smart devices into Home Assistant. Built-in Bemfa cloud sync bridges to voice assistants such as Xiao AI speakers for voice control.

> 🚧 **Project status**: pre-release. Core features work, but configuration formats and behavior may still change.

## Features

- 💡 **Broad device coverage**: common smart-device categories; supported and tested devices are listed under [Supported devices](#supported-devices)
- ⚡ **Zero-friction onboarding**: enter your Baidu cookie and complete everything through the guided config flow
- 🏠 **Automatic room mapping**: Xiaodu rooms are matched to Home Assistant areas by name similarity, with per-device overrides
- 🔊 **Bemfa cloud sync**: built-in Bemfa (巴法云) sync bridges to voice assistants such as Xiao AI speakers for voice control

## Installation

> Home Assistant version requirement: ≥ 2026.1.0

### Option 1: HACS (recommended)

1. Open HACS → Integrations → top-right menu → Custom repositories
2. Add <https://github.com/jukanntenn/ha-xiaodu> with category "Integration" and click "Add"
3. Search HACS for **Xiaodu** and install it
4. Restart Home Assistant

> HACS not installed yet? See the [HACS guide](https://www.hacs.xyz/).

### Option 2: Manual installation

1. Download the latest `xiaodu.zip` from [Releases](https://github.com/jukanntenn/ha-xiaodu/releases)
2. Create a `xiaodu` folder under `custom_components/` in your configuration directory and unpack the archive into it (the final path is `config/custom_components/xiaodu/`)
3. Restart Home Assistant

## Configuration

### Adding the integration

1. Go to "Settings → Devices & services → Add integration" and search for **Xiaodu**
2. Enter your Baidu BDUSS cookie (how to obtain it: see the [FAQ](#faq))
3. Pick the home to sync from the fetched list
4. Check the devices to sync into Home Assistant (all selected by default)
5. Confirm the mapping from Xiaodu rooms to Home Assistant areas (auto-matched, adjustable one by one)
6. Bemfa cloud configuration (optional): **v2 API (recommended, requires identity verification)** / legacy v1 (private key only) / skip

After setup, Home Assistant opens its standard "Name and assign" dialog — feel free to fine-tune names and area assignments there, or simply close it: device names already have the room prefix stripped ("儿童房主灯" → "主灯"), and areas are already linked through the room mapping.

### Enabling voice control (optional)

With Bemfa sync enabled, bind your Bemfa account in the Mi Home app, and Xiao AI speakers can voice-control the synced devices.

### Re-authentication

When the cookie expires, the integration reports an authentication failure. Click "Re-authenticate" on the integration card and enter a fresh Baidu cookie.

### Changing configuration

The ⚙️ "Configure" option on the integration card can at any time:

- change the room mapping
- change the Bemfa cloud configuration (new credentials, v1/v2 switch, disable sync)
- re-authenticate

## Supported devices

The supported device categories and their Home Assistant entity forms are listed below. Test status has two tiers:

- 🧪 **Automated integration tests**: run in CI against device data captured from real devices
- 📡 **Real-device tests**: verified on physical hardware

| Device | Xiaodu type code | Home Assistant entity | Tests | Notes |
| ------ | ---------------- | --------------------- | :---: | ----- |
| Light | `LIGHT` | Light |  🧪 📡 | On/off; brightness, color temperature, and scenes adapt to device capabilities |
| Plug | `SOCKET` | Switch |  🧪 📡 | |
| Wall switch | `SWITCH` | Switch |    🧪    | |
| Heater | `HEATER` | Switch |    🧪    | |
| Fresh-air unit | `AIR_FRESHER` | Switch |    🧪    | |
| Window opener | `WINDOW_OPENER` | Switch |    —     | Not yet tested |
| Air conditioner | `AIR_CONDITION` | Climate |  🧪 📡 | Target temperature, five modes, fan speed; on/off verified on hardware only |
| Curtain | `CURTAIN` | Cover |    🧪    | Position control supported |
| Smart lock | `DOOR_LOCK` | Lock |    🧪    | Lock / unlock |
| Clothes rack | `CLOTHES_RACK` | Button |    🧪    | One-shot device actions |

> 👏 Real-device test reports for more models are welcome.

## FAQ

### Q1: How do I get the Baidu cookie (BDUSS)?

1. Sign in to your Baidu account in a browser
2. Press F12 to open developer tools, then open Application → Cookies
3. Find the BDUSS field and copy its value for configuration

### Q2: How are synced devices identified in the Bemfa cloud?

Every Bemfa device topic the integration creates starts with the `xdu` prefix (for example `xdu4f8e2c1a9b7d002`), derived from the Xiaodu device ID — renaming never breaks the association. The integration only touches devices carrying this prefix and never touches devices you created manually in Bemfa; everything is cleaned up when the integration is removed.

### Q3: How often does state sync?

Device state refreshes automatically every 30 seconds; with Bemfa sync enabled, renames and area adjustments propagate to Bemfa near real time.

### Q4: What sensitive information does the integration store?

The Baidu BDUSS cookie and the Bemfa UID/secret, stored in the config entry under the standard `.storage` directory of your Home Assistant configuration. Guard your configuration directory the way you guard account passwords.

## Diagnostics and logs

When filing an issue or troubleshooting, attach debug logs and diagnostics:

1. Open the "Settings → Devices & services → Xiaodu" integration card
2. Choose **Download diagnostics** from the three-dot menu and save the diagnostics JSON
3. Attach the file contents to the issue

> ⚠️ The diagnostics JSON may contain sensitive fields — review and redact before publishing.

## Community and support

- Usage / configuration / Bemfa sync questions → [Discussions Q&A](https://github.com/jukanntenn/ha-xiaodu/discussions) (search existing discussions first)
- Reproducible bugs and concrete feature requests → [Issues](https://github.com/jukanntenn/ha-xiaodu/issues/new/choose) (the form guides you through environment details)
- Security vulnerabilities → private reporting (see the [security policy](.github/SECURITY.md)); never open a public issue
- Home Assistant itself → [official community](https://community.home-assistant.io) / [Chinese community](https://bbs.hassbian.com)

Support is provided by volunteers; the full routing guide is in [SUPPORT.md](.github/SUPPORT.md).

## Contributing

Contributions are welcome. Open an issue first for any change (including typo fixes); the workflow and conventions:

- Contributing guide: [CONTRIBUTING.md](CONTRIBUTING.md)
- Getting started: [good first issue](https://github.com/jukanntenn/ha-xiaodu/labels/good%20first%20issue)

## License

This project is open source under the [MIT License](LICENSE).

---

## Disclaimer

This project exists for learning and technical exchange only. Do not use it for any illegal purpose; the consequences of such use are solely yours and unrelated to the author.
