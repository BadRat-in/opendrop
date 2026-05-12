# How OpenDrop Actually Works (Honest Version)

This document is the single source of truth about what OpenDrop on Linux
can and cannot do, and why. It supersedes the earlier `OPTION_A_*.md`
documents that overstated the without-OWL capabilities.

---

## TL;DR — what works, what doesn't

| Capability                                    | Without OWL | With OWL (compatible HW) |
|-----------------------------------------------|-------------|---------------------------|
| OpenDrop ↔ OpenDrop (Linux to Linux)         | ✅ yes      | ✅ yes                    |
| Apple device → see OpenDrop in their list    | ✅ yes\*    | ✅ yes                    |
| Apple device → send file to OpenDrop         | ⚠️ flaky    | ✅ yes                    |
| OpenDrop → discover Apple devices            | ❌ no       | ✅ yes\*\*                |
| OpenDrop → send file to Apple device         | ❌ no       | ✅ yes\*\*                |

\* Apple's AirDrop UI listens for `_airdrop._tcp` on *all* interfaces, so
they will see our mDNS advertisement even over plain Wi-Fi.

\*\* Apple devices only put themselves on mDNS *after* they receive a
BLE wake-up beacon. OpenDrop sends those beacons automatically when
"Accept incoming files" is enabled, but the Apple side has to be set
to **Everyone for 10 Minutes** (or you have to be in its contacts).

---

## Why this asymmetry exists

AirDrop is fundamentally a three-layer protocol:

```
┌─────────────────────────────────────────────┐
│  Layer 3 — mDNS + HTTPS + plist payloads    │  ← OpenDrop implements this
├─────────────────────────────────────────────┤
│  Layer 2 — AWDL (Apple Wireless Direct Link) │  ← OWL provides this on Linux
├─────────────────────────────────────────────┤
│  Layer 1 — BLE AirDrop wake-up beacon       │  ← opendrop.ble does this now
└─────────────────────────────────────────────┘
```

Apple devices keep AWDL and the AirDrop HTTPS server **completely
inactive** to save power. The service only wakes up when a nearby device
emits a BLE AirDrop advertisement (manufacturer data `0x004C`, type
`0x05`). Until that happens, `_airdrop._tcp` simply isn't on the network
anywhere, and no amount of mDNS scanning will find it.

This means three things must align for full bidirectional AirDrop on
Linux:

1. **BLE wake-up** — OpenDrop must broadcast an AirDrop beacon to nudge
   nearby Apple devices into activating AWDL. (`opendrop.ble.BLEAdvertiser`)

2. **AWDL** — Once Apple devices are awake, communication happens on
   their `awdl0` interface (a virtual peer-to-peer link on Wi-Fi
   channels 6/44/149). OpenDrop on Linux can only join this network if
   OWL creates its own `awdl0`.

3. **Compatible hardware** — OWL requires a Wi-Fi chipset that allows
   monitor + managed concurrent mode. Intel CNVi (AX201, AX210, AX211,
   Wireless-AC 9560/9462) chipsets do not, and OWL fails on them.

---

## What OpenDrop does today

### Discovery layer

- **mDNS via zeroconf** for `_airdrop._tcp.local.` — present from upstream.
- **BLE scanning** — `opendrop.ble.BLEScanner` watches for Apple
  AirDrop beacons over Bluetooth LE and surfaces nearby devices in the
  GUI even before AWDL is up.
- **BLE advertising** — `opendrop.ble.BLEAdvertiser` broadcasts our own
  AirDrop beacon when receiving is enabled. This wakes nearby Apple
  devices.
- **Self-filter** — `_airdrop._tcp` services advertised by this host
  are filtered out of the device list (no more "parrot.local" appearing
  as a remote device).

### Transport layer

- **OWL integration** is optional. If `awdl0` exists, OpenDrop will use
  it. If not, OpenDrop falls back to whichever interface has IPv6 (your
  Wi-Fi).
- **`opendrop-doctor`** tells you up front whether OWL is likely to work
  on your hardware.

### Protocol layer

- **HTTPS with self-signed certificates** generated via the
  `cryptography` library (no `openssl` CLI required).
- **`/Discover`** (capability handshake), **`/Ask`** (with user
  confirmation dialog in the GUI), **`/Upload`** (cpio over chunked
  encoding).

---

## Required setup per role

### "I want to receive from my iPhone/Mac"

This works *today* with our changes. Walk-through:

1. `opendrop-doctor` — should be green or yellow (not red).
2. `opendrop-gui` — open the window.
3. Tick **Accept incoming files**.
4. On the iPhone/Mac, open the share sheet, choose AirDrop. Make sure
   the Apple device is set to **Everyone for 10 Minutes** (Control
   Center → AirDrop, or Finder → AirDrop → Allow me to be discovered).
5. OpenDrop's BLE advertiser will wake the Apple device; it will show
   "OpenDrop" in the share sheet within ~10 seconds.
6. Tap "OpenDrop". A confirmation dialog appears on the Linux side.
   Accept → file lands in `~/Downloads`.

### "I want to send to my iPhone/Mac"

This needs OWL with a compatible Wi-Fi chip. Walk-through:

1. `opendrop-doctor` — must report **LIKELY** for AWDL.
2. Click **Start OWL** in the GUI. (Requires the polkit policy installed
   by `scripts/install.sh`, or root.)
3. Wait for **AWDL Active** indicator (~3-5 seconds).
4. Click **Refresh Devices**. Open AirDrop on the iPhone/Mac.
5. The Apple device should appear in OpenDrop's device list.
6. Select it → **Send File** → choose file.

If `opendrop-doctor` reports **UNLIKELY** for your Wi-Fi chip, see the
"Hardware compatibility" section below.

### "I have Linux on both ends"

Easiest case: skip the BLE/AWDL parts entirely.

1. Both ends: `opendrop-gui` → check **Accept incoming files**.
2. Both ends: click **Refresh Devices**.
3. The Linux peer appears in each side's list. Send normally.

---

## Hardware compatibility

The single biggest issue OpenDrop users hit is incompatible Wi-Fi
hardware. The matrix below is what `opendrop-doctor` uses internally.

### Known-good (LIKELY)

- Broadcom FullMAC (BCM43xx) — older MacBook adapters work great.
- Atheros AR9271 / AR9170 — most cheap USB Wi-Fi dongles. Best price /
  reliability ratio if you need to add a compatible adapter.
- Realtek RTL8812 series — used in larger USB Wi-Fi dongles with
  external antennas.

### Known-bad (UNLIKELY)

- Intel **CNVi** (Companion Radio): AX201, AX210, AX211, Wireless-AC
  9560, Wireless-AC 9462. These chipsets cannot run a monitor interface
  alongside the managed one OWL needs.
- Any chipset whose `iw phy phy0 info` does not list a `managed +
  monitor` combination.

### Recommended workaround for known-bad chipsets

Buy a cheap USB Wi-Fi adapter with a compatible chip. ~$15-30 USD.
Suggested models:

- Alfa AWUS036NHA (Atheros AR9271)
- TP-Link TL-WN722N **v1 only** (Atheros AR9271)
- Alfa AWUS036ACH (Realtek RTL8812AU)

Plug it in, run `opendrop-doctor`; the new adapter should appear and be
LIKELY.

---

## What's still TODO

- USB adapter auto-detection: the GUI doesn't currently surface which
  Wi-Fi interface OWL should bind to when multiple adapters are present.
- Polkit policy: the installer ships one but it isn't yet fully wired
  into the GUI; OWL start/stop still uses sudo on first run.
- iOS-side BLE quirks: some iOS versions ignore beacons with all-zero
  contact hashes. We mitigate by sending random hashes, but iOS
  sometimes still wants a few seconds of dwell.
