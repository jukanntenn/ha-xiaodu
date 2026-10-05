# ha-xiaodu architecture

English | [中文](architecture.zh.md)

Read this before changing the source tree. It is the ordered map of the codebase — components, their boundaries, and where new behavior goes; decision rationale lives in the linked RFCs.

## What this package is

ha-xiaodu is a Home Assistant custom integration that surfaces Xiaomi Xiaodu cloud devices (lights, switches, climates, covers, locks) as HA entities through cloud polling. It ships to end users via HACS, and optionally mirrors device state to a Bemfa MQTT account for voice-assistant scenes.

## Components

| Component | Responsibility | Public surface |
|---|---|---|
| `custom_components/xiaodu/api/` | Xiaodu cloud client, typed models, and errors | `XiaoduClient` consumed by the coordinator |
| `custom_components/xiaodu/bemfa/` | Bemfa MQTT sync: client, API, sync manager, state publisher | `BemfaSyncManager` lifecycle |
| platform files (`light.py`, `switch.py`, `climate.py`, `cover.py`, `lock.py`, `button.py`) | One HA entity platform per device class | HA platform setup functions |
| `coordinator.py` / `entity.py` | Polling coordinator and shared entity base | `XiaoduCoordinator` consumed by every platform |
| `config_flow.py` / `const.py` / `room_mapping.py` | Setup UI, constants, room-to-area mapping | config-entry options schema |
| `tests/` | pytest suite over mocked HTTP with real API clients | `aioclient_mock_fixture` in `conftest.py` |
| `scripts/` | Tooling: hassfest wrapper, version bump, commit-msg check | developer scripts, prek hook entries |

## Where new behavior goes

A new device class gets its own platform file wired through `entity.py`; a new cloud capability grows `api/` first; anything about Bemfa mirroring stays inside `bemfa/` behind `BemfaSyncManager`. Constants land in `const.py` or `bemfa/const.py`, never as inline literals, and module dependency stays one-way: platform → entity → coordinator → api/bemfa. The owning reference documents are the [documentation standard](AGENTS.md), the [bilingual documentation contract](i18n/README.md), and the [RFC rules](../.agents/rfcs/README.md).

The contributor entry points are in [development.md](development.md).
