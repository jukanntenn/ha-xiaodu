# RFC: Reconcile Bemfa device state against the last published payload

Status: proposed

English | [中文](2026-10-05-bemfa-state-reconciliation.zh.md)

## Problem

The Bemfa topics are supposed to mirror what the integration holds — the same states the HA entities display — and they don't. State flows one way by design ([issue #37](https://github.com/jukanntenn/ha-xiaodu/issues/37)): Xiaodu-side changes propagate to HA and to Bemfa; nothing ever syncs back to Xiaodu. Within that one-way flow, the HA side and the Bemfa side have drifted apart, and once drifted they stay wrong indefinitely. Three-way browser-verified on 2026-10-05, with the Xiaodu cloud itself ruled out as a reference (it is unreliable — stale attributes with month-old timestamps — and the HA log shows 89 `Connection timeout to xiaodu.baidu.com` failures, so polling gaps are routine, not exceptions):

- Four lights showed `off` in HA while their Bemfa topics still said `on`, frozen one to two days earlier.
- All five air-conditioner topics had carried **no state at all** since their creation three weeks earlier, while HA showed two of them actively running (`cool`) and three off. A mirror with a hole where the initial state should be.
- One light showed `on` in HA while its Bemfa topic (created earlier under a pre-rename nickname) was equally empty.

The publishing pipeline has exactly one path — publish when a *new* Xiaodu poll snapshot differs from the *previous* one — and that path skips every state it never saw change:

- The first poll after startup publishes nothing (`self.data` is `None` for that round), so states that changed while HA was down, while a poll was failing, or while the entry was frozen on an expired cookie are never replayed: the next successful round diffs two identical fresh snapshots.
- A device newly mapped to a Bemfa topic has no previous snapshot, so its initial state is never published. This is why the five air-conditioner topics have been empty since creation.
- A publish that fails because MQTT is momentarily disconnected returns `False` and is dropped: no queue, no retry, no re-publish on reconnect.
- A narrower amplifier: when the Xiaodu cookie expires, the coordinator stops scheduling polls (`ConfigEntryAuthFailed`) while the MQTT client stays connected, so the Bemfa side freezes while looking healthy.

The net effect: the Bemfa cloud is a **cache without reconciliation** — any missed transition is permanent until the same device happens to change state again through the running integration.

## Proposal

Make state publishing idempotent and self-healing by reconciling against the **last successfully published payload** instead of diffing consecutive API snapshots:

1. `DeviceMapping` gains `last_published_payload: str | None`, reset to `None` whenever a topic is (re)created, and surviving across polls otherwise.
2. `BemfaDeviceSyncManager.update_device_state` becomes the single reconciliation point: encode the state; if the payload equals `last_published_payload`, return without touching the network; otherwise publish to `{topic}/up` and, **only on a successful publish**, record the payload. A publish dropped while MQTT is disconnected leaves the record untouched, so the next poll retries it unchanged.
3. The coordinator drops `_publish_state_changes` (the old/new snapshot diff). On every successful poll, **after** `sync_devices` has created topics and **after** the optimistic-lock rewrite, it calls `update_device_state` for every mapped device with the *final* data it is about to return — exactly what the HA entities will display. Publishing the post-lock data also stops a mid-lock-window poll from flashing a stale cloud value over the optimistic payload that `apply_optimistic_state` just published. Unchanged devices cost one in-memory encode-and-compare each; the wire stays silent.
4. The optimistic-publish path after control commands already funnels through `update_device_state`, so it records its payload too. When the command's optimistic state later disagrees with the coordinator's final data, the next poll publishes that data and the record converges — replacing today's reliance on snapshot diff plus the 5-second entity lock to correct a wrong optimistic state.

Nothing changes in `BemfaMQTTClient` (no reconnect callback, no queue), in the downlink command path, in the lock semantics (locks keep governing what HA entities display), or in the one-way state flow — nothing ever publishes toward Xiaodu. The Bemfa side simply mirrors the coordinator's final data faithfully.

### What each failure mode heals into

- **Restart / polling gap / poll failures**: the first successful poll publishes every mapped device's current state once; the record then keeps the wire silent. With flaky Baidu networking this also makes the (frequent) failed-poll windows self-healing.
- **New device**: `sync_devices` creates the topic in the same round, and the reconciliation pass that follows publishes its initial state.
- **Dropped publish (MQTT down)**: record stays empty, next poll with MQTT up re-publishes; no re-publish loop once recorded.
- **Auth-freeze window**: first successful poll after re-authentication reconciles everything the freeze froze. The freeze itself is HA's reauth flow working as designed and is intentionally left alone.

## Alternatives considered

**Startup-only full publish plus MQTT-reconnect re-publish.** Hook "poller just started" and "MQTT just (re)connected" events and push all states at each. Rejected: it needs a new reconnect callback threaded from the paho client into the sync manager, it heals publish drops only at reconnect boundaries (a publish dropped after the last reconnect waits for the next restart), it does nothing for the poll-failure windows the flaky Baidu network makes routine, and it keeps the fragile snapshot diff with its three skip paths. Reconciliation-by-record needs no events at all — the 30-second poll is the retry loop.

**Client-side publish queue in `BemfaMQTTClient`.** Queue payloads on a disconnected broker and flush on reconnect. Rejected: it adds mutable state shared between the paho thread and the event loop for a problem the poll already re-solves, and a queue replays *intermediate* payloads, whereas reconciliation replays only the *current* one, which is all the Bemfa console displays.

**Keep the snapshot diff and special-case the first round.** Publish when `old is None` and skip the `self.data` guard on round one. Rejected as insufficient: it covers restarts and new devices but still drops publishes that fail while MQTT is disconnected, still misses changes that happened during failed-poll windows (the diff only compares consecutive *successful* snapshots), and it leaves three coordinated special cases where one idempotent mechanism suffices.

**Publish from the pre-lock API snapshot instead of the final data.** Keeping today's ordering (publish, then lock rewrite) would carry the freshest cloud value but diverge from what HA entities display during the 5-second lock window and can overwrite a just-published optimistic payload with a stale cloud value mid-window. Rejected: the mirroring target is HA's displayed state, and the post-lock data is exactly that.

## Acceptance criteria

- After a restart with no state changes anywhere, the first successful poll publishes exactly one `{topic}/up` message per mapped device carrying its current encoded state; subsequent polls publish nothing.
- A device newly mapped to a topic receives its initial state within the same poll round that created the topic.
- A publish attempted while MQTT is disconnected is retried verbatim on the next poll once the broker is reachable; a recorded payload is never re-published while unchanged.
- The divergent devices from issue #37 converge to **what HA displays** on the first successful poll after upgrading and reloading the integration: the four stale-`on` lights flip to `off`, the five empty topics (three off air conditioners, two running in `cool`) receive their states, and the light that HA shows as `on` reports `on`.
- During an optimistic-lock window, a concurrent poll does not publish over the optimistic payload; after the window, the payload converges to the coordinator's final data.
- Coordinator tests cover: first-round publish-all, idempotent silence on unchanged rounds, convergence after a failed publish, and no mid-lock overwrite; the sync-manager tests cover record lifecycle around MQTT failures.

## Risks

- **Burst publishes.** The first poll after every restart fires one message per device (24 in the issue-#37 account). These are small QoS-1 messages to a broker the client is already connected to; the Bemfa limits that matter (QoS-2 bans, topic counts) are untouched.
- **Return-value semantics.** `update_device_state` now returns `True` for "consistent, no publish needed" as well as "published". Current callers ignore the return value except in tests; the docstring must state the new meaning so future callers don't mistake it for "bytes on the wire".
- **Mirror fidelity is bounded by the coordinator data.** Bemfa will faithfully mirror whatever HA displays, including states the flaky Xiaodu cloud reports wrongly (the two running-but-cloud-`off` air conditioners mirror as running). That is the one-way state-flow decision working as designed: HA is the reference, and inventing a separate "truth" for Bemfa would diverge the two sides this RFC exists to align.
- **encode-None devices.** Types whose state cannot be encoded keep returning `False` each round without side effects; the record stays empty so they retry harmlessly — worth one test to pin the behavior.
