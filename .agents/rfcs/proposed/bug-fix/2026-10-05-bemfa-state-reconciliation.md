# RFC: Reconcile Bemfa device state against the last published payload

Status: proposed

English | [中文](2026-10-05-bemfa-state-reconciliation.zh.md)

## Problem

Bemfa topic states drift from the Xiaodu cloud states they mirror, and once drifted they stay wrong indefinitely. Browser-verified on 2026-10-05 ([issue #37](https://github.com/jukanntenn/ha-xiaodu/issues/37)): every light and every air conditioner reported `turnOnState = OFF` by the Xiaodu console, while the Bemfa console still showed four lights as `on` (timestamps frozen between one and two days earlier) and all five air-conditioner topics showed an empty message — they had never carried a state at all since their creation three weeks earlier, while the integration's MQTT client was connected the whole time.

The publishing pipeline has exactly one path — publish when a *new* Xiaodu poll snapshot differs from the *previous* one — and that path skips every state it never saw change:

- The first poll after startup publishes nothing (`self.data` is `None` for that round), so states that changed while HA was down are never replayed: the next round diffs two identical fresh snapshots.
- A device newly mapped to a Bemfa topic has no previous snapshot, so its initial state is never published. This is why the five air-conditioner topics have been empty since creation.
- A publish that fails because MQTT is momentarily disconnected returns `False` and is dropped: no queue, no retry, no re-publish on reconnect.
- A narrower amplifier: when the Xiaodu cookie expires, the coordinator stops scheduling polls (`ConfigEntryAuthFailed`) while the MQTT client stays connected, so the Bemfa side freezes while looking healthy. The four stale lights are consistent with this window.

The net effect: the Bemfa cloud is a **cache without reconciliation** — any missed transition is permanent until the same device happens to change state again through the running integration.

## Proposal

Make state publishing idempotent and self-healing by reconciling against the **last successfully published payload** instead of diffing consecutive API snapshots:

1. `DeviceMapping` gains `last_published_payload: str | None`, reset to `None` whenever a topic is (re)created, and surviving across polls otherwise.
2. `BemfaDeviceSyncManager.update_device_state` becomes the single reconciliation point: encode the state; if the payload equals `last_published_payload`, return without touching the network; otherwise publish to `{topic}/up` and, **only on a successful publish**, record the payload. A publish dropped while MQTT is disconnected leaves the record untouched, so the next poll retries it unchanged.
3. The coordinator drops `_publish_state_changes` (the old/new snapshot diff) and instead calls `update_device_state` for every mapped device on every successful poll, after `sync_devices` has created topics and before the optimistic-lock rewrite. Unchanged devices cost one in-memory encode-and-compare each; the wire stays silent.
4. The optimistic-publish path after control commands already funnels through `update_device_state`, so it records its payload too. When the command's optimistic state later disagrees with the API truth, the next poll publishes the truth and the record converges — replacing today's reliance on snapshot diff plus the 5-second entity lock to correct a wrong optimistic state.

Nothing changes in `BemfaMQTTClient` (no reconnect callback, no queue), in the downlink command path, or in the lock semantics — locks keep governing what HA entities display, while publishes always carry the API truth.

### What each failure mode heals into

- **Restart / polling gap**: first successful poll publishes every mapped device's current state once; the record then keeps the wire silent.
- **New device**: `sync_devices` creates the topic in the same round, and the reconciliation pass that follows publishes its initial state.
- **Dropped publish (MQTT down)**: record stays empty, next poll with MQTT up re-publishes; no re-publish loop once recorded.
- **Auth-freeze window**: first successful poll after re-authentication reconciles everything the freeze froze. The freeze itself is HA's reauth flow working as designed and is intentionally left alone.

## Alternatives considered

**Startup-only full publish plus MQTT-reconnect re-publish.** Hook "poller just started" and "MQTT just (re)connected" events and push all states at each. Rejected: it needs a new reconnect callback threaded from the paho client into the sync manager, it heals publish drops only at reconnect boundaries (a publish dropped after the last reconnect waits for the next restart), and it keeps the fragile snapshot diff with its three skip paths. Reconciliation-by-record needs no events at all — the 30-second poll is the retry loop.

**Client-side publish queue in `BemfaMQTTClient`.** Queue payloads on a disconnected broker and flush on reconnect. Rejected: it adds mutable state shared between the paho thread and the event loop for a problem the poll already re-solves, and a queue replays *intermediate* payloads, whereas reconciliation replays only the *current* one, which is all the Bemfa console displays.

**Keep the snapshot diff and special-case the first round.** Publish when `old is None` and skip the `self.data` guard on round one. Rejected as insufficient: it covers restarts and new devices but still drops publishes that fail while MQTT is disconnected, and it leaves three coordinated special cases where one idempotent mechanism suffices.

## Acceptance criteria

- After a restart with no state changes anywhere, the first successful poll publishes exactly one `{topic}/up` message per mapped device carrying its current encoded state; subsequent polls publish nothing.
- A device newly mapped to a topic receives its initial state within the same poll round that created the topic.
- A publish attempted while MQTT is disconnected is retried verbatim on the next poll once the broker is reachable; a recorded payload is never re-published while unchanged.
- The four stale lights and five empty air-conditioner topics from issue #37 converge to the Xiaodu truth on the first successful poll after upgrading and reloading the integration.
- Coordinator tests cover: first-round publish-all, idempotent silence on unchanged rounds, and convergence after a failed publish; the sync-manager tests cover record lifecycle around MQTT failures.

## Risks

- **Burst publishes.** The first poll after every restart fires one message per device (24 in the issue-#37 account). These are small QoS-1 messages to a broker the client is already connected to; the Bemfa limits that matter (QoS-2 bans, topic counts) are untouched.
- **Return-value semantics.** `update_device_state` now returns `True` for "consistent, no publish needed" as well as "published". Current callers ignore the return value except in tests; the docstring must state the new meaning so future callers don't mistake it for "bytes on the wire".
- **Cloud-stale Xiaodu states stay mirrored.** If the Xiaodu cloud itself reports a stale `turnOnState` (device unreachable behind a wall switch), reconciliation faithfully mirrors that stale value. That is the same fidelity the HA entities have; inventing an "offline" payload would diverge from the API truth and is deliberately out of scope.
- **encode-None devices.** Types whose state cannot be encoded keep returning `False` each round without side effects; the record stays empty so they retry harmlessly — worth one test to pin the behavior.
