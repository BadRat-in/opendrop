# OpenDrop Code Audit Report
## Date: 2026-05-12

This document is the honest assessment of code state before bug fixes.
**Do NOT delete this file — it's the source of truth for Phase 1 work.**

---

## A. Real Code Bugs (Fixable in Phase 1)

### A1. Self-Discovery Duplicate ("parrot.local x2")
- **Location**: `opendrop/client.py` — `AirDropBrowser.add_service` (lines 88-92)
- **Problem**: When OpenDrop advertises itself via mDNS and then browses for services, it discovers its own advertisement. Combined with re-registration cycles, this can show "parrot.local" twice.
- **Fix**: Filter out services whose IP matches one of our local interface IPs.

### A2. HTTPSConnectionAWDL Mutable Default at Import
- **Location**: `opendrop/client.py` line 285
- **Problem**: `timeout=socket.getdefaulttimeout()` is evaluated at module import, not call time. If timeout changes later in process lifetime, this default is stale.
- **Fix**: Use a sentinel object and resolve at call time.

### A3. AirDropServer Mutates Shared Config (`self.config.port`)
- **Location**: `opendrop/server.py` lines 113-117
- **Problem**: When port conflict happens, `self.config.port = self.config.port + 1` modifies the shared `AirDropConfig` object. Other components reading `config.port` get unexpected values.
- **Fix**: Use a local `self.port` attribute on the server, don't mutate config.

### A4. ReceiveWorker `os.chdir` — Thread-Unsafe Global State Mutation
- **Location**: `opendrop/gui/worker.py` — `ReceiveWorker.run()`
- **Problem**: `os.chdir(recv_dir)` changes the process-global current directory. This affects every other thread in the GUI (file dialogs, etc.).
- **Fix**: Pass directory to the upload handler via thread-local config, or extract in a chdir-context manager scoped to the request handler.

### A5. Service Name Uses computer_name Instead of service_id
- **Location**: `opendrop/server.py` line 93
- **Problem**: Service name is `{computer_name}._airdrop._tcp.local.`. Apple's AirDrop uses a hex `service_id` (UUID-like) for the service name and puts the friendly name in the TXT record.
- **Impact**: May cause incompatibility or duplicate service handling on Apple devices.
- **Note**: The original opendrop upstream uses `service_id` here. The current code was changed at some point — needs review.

### A6. mDNS `interface_index=None`
- **Location**: `opendrop/server.py` line 101
- **Problem**: Passing `interface_index=None` to `ServiceInfo` doesn't actually pin the service to an interface. mDNS announces on all interfaces.
- **Fix**: Either set actual interface_index or remove the parameter.

### A7. Config Stores `key_file`/`cert_file` But Server Uses `get_ssl_context()`
- **Location**: `opendrop/config.py` lines 121-122 vs `server.py` line 124
- **Problem**: Config has `self.key_file`, `self.cert_file` strings but `get_ssl_context()` is the actual entry point. The strings are unused dead code (except possibly during cert creation, which uses `key_dir` directly).
- **Fix**: Keep them; they're used by some code paths. But document this clearly.

### A8. `apple_p2p=platform.system() == "Darwin"` Is Dead on Linux
- **Location**: `opendrop/client.py` line 66, `opendrop/server.py` line 83
- **Problem**: Always False on Linux. The parameter is meaningful only on macOS.
- **Fix**: Keep as-is; no harm but it's noise. Comment that it's macOS-only.

### A9. AirDropConfig Default Interface is `awdl0`
- **Location**: `opendrop/config.py` line 98
- **Problem**: Default `interface="awdl0"` assumes OWL is running. For a Linux user without OWL, this is the wrong default.
- **Fix**: Make the default auto-detect: try `awdl0`, fall back to the primary WiFi interface, fall back to first non-loopback interface.

### A10. Race Condition in BrowseWorker Stop
- **Location**: `opendrop/gui/worker.py` BrowseWorker
- **Problem**: `self.browser.cancel()` and `self.zeroconf.close()` can hang if called from wrong thread.
- **Fix**: Ensure cleanup happens on the worker thread, with timeout.

### A11. `update_service` Re-Emits `add` Signal
- **Location**: `opendrop/client.py` line 109-120
- **Problem**: When a service updates (e.g., TXT record changes), we emit `callback_add` which adds it as a new device. GUI handles this via deduplication, but it's wasteful and confusing.
- **Fix**: Add a separate `callback_update` if needed, or just log and skip.

---

## B. Architectural Issues (Phase 2-4 Work)

### B1. No BLE Wake-Up (Critical for Apple Discovery)
- Apple devices keep AWDL/AirDrop dormant until they hear a BLE AirDrop beacon
- Without BLE, even with OWL running, Apple devices won't appear
- **Needs**: New module for BLE scanner + advertiser

### B2. OWL Hardware Compatibility (Intel iwlwifi)
- OWL fails on Intel WiFi: "ERROR: Error while receiving via netlink: Operation not supported"
- Likely missing nl80211 feature in iwlwifi
- **Needs**: USB adapter recommendation, OWL upstream patch investigation

### B3. No Interface Type Abstraction
- Code uses same path for `awdl0` (AWDL P2P) and `wlo1` (regular WiFi)
- But behavior is fundamentally different on these interfaces
- **Needs**: Discovery strategy class with different backends

---

## C. Cross-Distro Issues (Phase 4)

### C1. Hardcoded systemd Dependency
- `owl_manager.py` uses `systemctl` directly
- **Fix**: Abstract service manager (systemd/openrc/runit/s6/launchd)

### C2. Sudo Instead of polkit
- `privilege.py` uses `sudo -S` with password prompt
- **Fix**: Try polkit (pkexec) first, fall back to sudo

### C3. Hardcoded `phy0` for `iw phy phy0`
- `owl_manager.py` line 94 assumes phy0
- **Fix**: Find phy that backs the WiFi interface

### C4. `openssl` CLI Dependency
- `config.py` `create_default_key()` shells to `openssl`
- **Fix**: Use Python `cryptography` library (already a transitive dep)

### C5. Package Installation Not Automated
- User must install dependencies manually per distro
- **Fix**: Distro detection + auto-install script

---

## D. Misleading Documentation

### D1. `docs/technical/OPTION_A_ANALYSIS.md`
- Claims: "OpenDrop uses Bonjour/mDNS (not AWDL) for device discovery"
- Reality: AirDrop fundamentally requires AWDL for Apple device discovery
- Apple devices don't advertise on regular WiFi
- **Fix**: Update with honest assessment

### D2. `docs/troubleshooting/DEVICE_DISCOVERY_FIX.md`
- Claims switching from `awdl0` to `wlo1` "fixes" discovery
- Reality: Switching makes OpenDrop discoverable BY Apple devices, not the reverse
- **Fix**: Update to explain the asymmetry

### D3. `BUGFIX_SUMMARY.md` (just created by me)
- Some claims are accurate (HTTPSConnection fix, dialog)
- Other claims overstate progress
- **Fix**: Rewrite to be honest

---

## E. Test Coverage Gaps

- Only 2 tests exist (test_browser_setup, test_server_setup) — both use loopback
- No tests for: send flow, receive flow, BLE, service deduplication, error paths
- No integration tests
- No mocked Apple device tests

---

## F. What's Actually Working (Honest Assessment)

| Feature | State | Confidence |
|---------|-------|-----------|
| HTTPSConnection (send to working host) | ✅ Works | High |
| mDNS service advertising | ✅ Works | High |
| File reception with confirmation dialog | ✅ Works | High |
| Self-signed cert generation | ✅ Works | High |
| Receive HTTP handler (Discover/Ask/Upload) | ✅ Works | High |
| Linux → Linux (OpenDrop → OpenDrop) | ⚠️ Partially | Medium |
| Apple → OpenDrop (when Apple finds us) | ⚠️ Partially | Medium |
| OpenDrop → Apple device | ❌ Doesn't work | High (protocol limitation) |
| Discover Apple devices | ❌ Doesn't work | High (protocol limitation) |

---

## Phase 1 Fix Plan (Priority Order)

1. **A1**: Self-discovery filter (highest user-visible impact)
2. **A4**: Fix `os.chdir` thread safety (potential data corruption)
3. **A3**: Fix port mutation
4. **A9**: Auto-detect interface (improves out-of-box experience)
5. **A10**: BrowseWorker race condition
6. **A2, A5, A6, A11**: Polish

**Phase 1 explicitly does NOT include**:
- BLE (Phase 2)
- OWL fixes (Phase 3)
- Cross-distro (Phase 4)

---

## Approval Required Before Code Changes

This audit is the basis for Phase 1 work. Bugs A1-A11 will be fixed in order.

Each fix will:
1. Have a clear "before" and "after"
2. Be testable
3. Be committed separately with explanation
4. Not introduce new architectural complexity

---

*End of audit. Next: begin Phase 1 fixes.*
