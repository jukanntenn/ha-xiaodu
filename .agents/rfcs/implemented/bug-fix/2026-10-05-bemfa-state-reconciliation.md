# RFC: Reconcile Bemfa device state against the last published payload

Status: implemented

English | [中文](2026-10-05-bemfa-state-reconciliation.zh.md)

## Problem

The Bemfa topics are supposed to mirror what the integration holds — the same states the HA entities display — and they don't. State flows one way by design ([issue #37](https://github.com/jukanntenn/ha-xiaodu/issues/37)): Xiaodu-side changes propagate to HA and to Bemfa; nothing ever syncs back to Xiaodu. Within that one-way flow, the HA side and the Bemfa side had drifted apart, and once drifted they stayed wrong indefinitely. Three-way browser-verified on 2026-10-05, with the Xiaodu cloud itself ruled out as a reference (it is unreliable — stale attributes with month-old timestamps — and the HA log showed 89 `Connection timeout to xiaodu.baidu.com` failures, so polling gaps were routine, not exceptions):

- Four lights showed `off` in HA while their Bemfa topics still said `on`, frozen one to two days earlier.
- All five air-conditioner topics had carried **no state at all** since their creation three weeks earlier, while HA showed two of them actively running (`cool`) and three off. A mirror with a hole where the initial state should be.
- One light showed `on` in HA while its Bemfa topic (created earlier under a pre-rename nickname) was equally empty.

The publishing pipeline had exactly one path — publish when a *new* Xiaodu poll snapshot differed from the *previous* one — and that path skipped every state it never saw change:

- The first poll after startup published nothing (`self.data` was `None` for that round), so states that changed while HA was down, while a poll was failing, or while the entry was frozen on an expired cookie were never replayed: the next successful round diffed two identical fresh snapshots.
- A device newly mapped to a Bemfa topic had no previous snapshot, so its initial state was never published. This is why the five air-conditioner topics had been empty since creation.
- A publish that failed because MQTT was momentarily disconnected returned `False` and was dropped: no queue, no retry, no re-publish on reconnect.
- A narrower amplifier: when the Xiaodu cookie expired, the coordinator stopped scheduling polls (`ConfigEntryAuthFailed`) while the MQTT client stayed connected, so the Bemfa side froze while looking healthy.

The net effect: the Bemfa cloud was a **cache without reconciliation** — any missed transition was permanent until the same device happened to change state again through the running integration.

## Decision

State publishing is idempotent and self-healing: it reconciles against the **last successfully published payload** instead of diffing consecutive API snapshots.

1. `DeviceMapping.last_published_payload` records the last payload that reached `{topic}/up`. It is reset to `None` whenever a topic is (re)created — the mapping object is rebuilt on add and on retry — and survives across polls otherwise.
2. `BemfaDeviceSyncManager.update_device_state` is the single reconciliation point: it encodes the state; if the payload equals `last_published_payload` it returns `True` without touching the network; otherwise it publishes to `{topic}/up` and, **only on a successful publish**, records the payload. A publish dropped while MQTT is disconnected leaves the record untouched, so the next poll retries it unchanged. The return value means "consistent or published", not "bytes on the wire" — the docstring says so.
3. The coordinator's `_publish_state_changes` (old/new snapshot diff) is gone. On every successful poll, **after** `_handle_bemfa_sync` has created topics and **after** the optimistic-lock rewrite, `_reconcile_bemfa_states` calls `update_device_state` for every device in the final data it is about to return — exactly what the HA entities display. Publishing the post-lock data also stopped a mid-lock-window poll from flashing a stale cloud value over the optimistic payload that `apply_optimistic_state` had just published. Unchanged devices cost one in-memory encode-and-compare each; the wire stays silent.
4. The optimistic-publish path after control commands funnels through the same `update_device_state`, so it records its payload too. When the command's optimistic state later disagrees with the coordinator's final data, the next poll publishes that data and the record converges — replacing the earlier reliance on snapshot diff plus the 5-second entity lock to correct a wrong optimistic state.

Nothing changed in `BemfaMQTTClient` (no reconnect callback, no queue), in the downlink command path, in the lock semantics (locks keep governing what HA entities display), or in the one-way state flow — nothing ever publishes toward Xiaodu. The Bemfa side mirrors the coordinator's final data faithfully.

### What each failure mode heals into

- **Restart / polling gap / poll failures**: the first successful poll publishes every mapped device's current state once; the record then keeps the wire silent. With flaky Baidu networking the frequent failed-poll windows are self-healing.
- **New device**: `sync_devices` creates the topic in the same round, and the reconciliation pass that follows publishes its initial state.
- **Dropped publish (MQTT down)**: record stays empty, next poll with MQTT up re-publishes; no re-publish loop once recorded.
- **Auth-freeze window**: the first successful poll after re-authentication reconciles everything the freeze froze. The freeze itself is HA's reauth flow working as designed and is intentionally left alone.

## Alternatives considered

**Startup-only full publish plus MQTT-reconnect re-publish.** Hook "poller just started" and "MQTT just (re)connected" events and push all states at each. Rejected: it needs a new reconnect callback threaded from the paho client into the sync manager, it heals publish drops only at reconnect boundaries (a publish dropped after the last reconnect waits for the next restart), it does nothing for the poll-failure windows the flaky Baidu network makes routine, and it keeps the fragile snapshot diff with its three skip paths. Reconciliation-by-record needs no events at all — the 30-second poll is the retry loop.

**Client-side publish queue in `BemfaMQTTClient`.** Queue payloads on a disconnected broker and flush on reconnect. Rejected: it adds mutable state shared between the paho thread and the event loop for a problem the poll already re-solves, and a queue replays *intermediate* payloads, whereas reconciliation replays only the *current* one, which is all the Bemfa console displays.

**Keep the snapshot diff and special-case the first round.** Publish when `old is None` and skip the `self.data` guard on round one. Rejected as insufficient: it covers restarts and new devices but still drops publishes that fail while MQTT is disconnected, still misses changes that happened during failed-poll windows (the diff only compares consecutive *successful* snapshots), and it leaves three coordinated special cases where one idempotent mechanism suffices.

**Publish from the pre-lock API snapshot instead of the final data.** Keeping the old ordering (publish, then lock rewrite) would carry the freshest cloud value but diverge from what HA entities display during the 5-second lock window and can overwrite a just-published optimistic payload with a stale cloud value mid-window. Rejected: the mirroring target is HA's displayed state, and the post-lock data is exactly that.

## Testing

- Sync manager (broker-backed, real MQTT wire): `test_update_device_state_dedupes_unchanged_payload` pins that an unchanged payload returns `True` and produces exactly one `{topic}/up` message; `test_update_device_state_retries_after_failed_publish` pins that a publish dropped while disconnected leaves `last_published_payload` empty and that the same state is re-published verbatim once the broker is reachable; `test_update_device_state_unmapped_returns_false` pins that unmapped devices return `False` each round without side effects.
- Coordinator: `test_first_refresh_reconciles_all_devices` pins the issue-#37 core regression — the first successful refresh after a restart (no `self.data`) publishes every device exactly once; `test_reconcile_publishes_post_lock_data` pins that a poll inside the optimistic-lock window publishes the locked state, never the stale cloud value; `test_reconcile_bemfa_states_bemfa_error` pins that a raising publish path is logged and swallowed per device.

## Consequences

- The Bemfa console now converges to what HA displays on the first successful poll after any restart, polling gap, or MQTT outage, and stays silent while consistent. The four stale-`on` lights and five empty air-conditioner topics from issue #37 are the motivating cases.
- The first poll after every restart fires one message per device (24 in the issue-#37 account) — small QoS-1 messages to an already-connected broker; the Bemfa limits that matter (QoS-2 bans, topic counts) are untouched.
- Mirror fidelity is bounded by the coordinator data: Bemfa faithfully mirrors whatever HA displays, including states the flaky Xiaodu cloud reports wrongly (the two running-but-cloud-`off` air conditioners mirror as running). That is the one-way state-flow decision working as designed — inventing a separate "truth" for Bemfa would diverge the two sides this decision exists to align.
- `update_device_state` returning `True` for "consistent, no publish needed" is a semantic change for callers; none of them used the return value to mean "bytes on the wire", and the docstring now states the meaning.
