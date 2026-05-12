# OpenDrop-GUI: an Open Source AirDrop Implementation for Linux

[![Release](https://img.shields.io/pypi/v/opendrop?color=%23EC6500&label=release)](https://pypi.org/project/opendrop/)
[![Language grade](https://img.shields.io/lgtm/grade/python/github/seemoo-lab/opendrop?label=code%20quality)](https://lgtm.com/projects/g/seemoo-lab/opendrop/context:python)

**🎉 Welcome to OpenDrop-GUI** — A user-friendly desktop application for AirDrop file sharing on Linux!

*OpenDrop* is a command-line tool that allows sharing files between devices directly over Wi-Fi with Apple AirDrop protocol compatibility. **OpenDrop-GUI** extends this with a modern PyQt6 graphical interface, systemd-integrated OWL AWDL support, and automatic dependency management.

**Available in two modes:**
- **CLI**: `opendrop` — Command-line interface (original upstream tool)
- **GUI**: `opendrop-gui` — Desktop application with system tray integration (this fork)

---

## 🙏 Credits & Attribution

**This project is a fork of [seemoo-lab/opendrop](https://github.com/seemoo-lab/opendrop).**

**Original Authors & Research:**
- **Milan Stute** — Primary author, SEEMOO Lab, TU Darmstadt
- **Alexander Heinrich** — Co-author, SEEMOO Lab, TU Darmstadt
- **SEEMOO Lab** — Open Wireless Link project (https://owlink.org)

**GUI Extension & Enhancements (this fork):**
- Ravindra K. — GUI implementation, OWL systemd integration, uv migration

**Original Research Papers:**
- [PrivateDrop: Practical Privacy-Preserving Authentication for Apple AirDrop](https://www.usenix.org/conference/usenixsecurity21/presentation/heinrich) — USENIX Security '21
- [A Billion Open Interfaces for Eve and Mallory: MitM, DoS, and Tracking Attacks on iOS and macOS Through Apple Wireless Direct Link](https://www.usenix.org/conference/usenixsecurity19/presentation/stute) — USENIX Security '19

**All original GPL-3.0 code and AirDrop reverse engineering belong to the original authors.**

---

## Features

✅ **AirDrop Compatible** — Send/receive files with iOS and macOS devices  
✅ **Graphical Interface** — Modern PyQt6 GUI with system tray integration  
✅ **OWL AWDL Support** — Integrated Linux AWDL implementation  
✅ **Easy Setup** — One-command installation with `scripts/install.sh`  
✅ **uv Managed** — Modern Python package management  
✅ **Contacts Mode** — Support for Apple ID-based authentication (via keychain extractor)  

---

## Quick Start

### 1. Installation

```bash
# Clone this fork
git clone https://github.com/YOURUSERNAME/opendrop opendrop-gui
cd opendrop-gui

# Universal installer (auto-detects your distro: Debian/Ubuntu/Parrot,
# Fedora/RHEL, Arch/Manjaro, openSUSE, Alpine, Void).
sudo bash scripts/install.sh
```

### 1a. Check hardware compatibility

Before launching the GUI, run the diagnostic:

```bash
opendrop-doctor
```

It tells you, in plain English:
- whether your Wi-Fi chipset can run AWDL (some Intel CNVi chips cannot),
- whether Bluetooth is set up for BLE wake-up (required to discover Apple devices),
- whether OWL is installed,
- and exactly which features will work right now.

### 2. Launch the GUI

```bash
# Start OpenDrop GUI
opendrop-gui
```

The application will appear in your system tray. Click the tray icon to open the window.

### 3. Start AWDL

Click **"Start OWL"** in the GUI, or manually:

```bash
sudo systemctl start owl-awdl.service
```

Verify the interface is up:
```bash
ip link show awdl0
ip -6 addr show awdl0
```

### 4. Send & Receive Files

**Receiving:**
- Open OpenDrop GUI
- Check "Accept incoming files"
- Files from nearby Apple devices will be saved to your Downloads folder

**Sending:**
- Click "Refresh Devices" to discover nearby Apple devices
- Select a device and click "Send File"
- Choose the file and wait for the device to accept

---

## WiFi Warning ⚠️

This system uses OWL (Open Wireless Link) to emulate Apple's AWDL protocol. On most Linux hardware, this requires your WiFi adapter to be in **monitor mode**, which **temporarily disconnects WiFi**.

**What happens:**
1. Click "Start OWL" → WiFi briefly disconnects
2. OWL creates the `awdl0` interface for AirDrop
3. Your WiFi automatically reconnects in the background
4. You can send/receive files while OWL runs
5. Click "Stop OWL" → Normal WiFi operation resumes

**Hardware Note:** Some Wi-Fi chips support concurrent monitor+managed mode (no Wi-Fi interruption). Most Intel CNVi chips (AX201, AX210, AX211, Wireless-AC 9560/9462) do **not** — OWL will fail on them with `Operation not supported`. If `opendrop-doctor` says your chipset is `UNLIKELY`, use a USB Wi-Fi adapter with an Atheros AR9271 or Realtek RTL8812 chipset instead. See [docs/HOW_IT_WORKS.md](docs/HOW_IT_WORKS.md) for the full hardware compatibility matrix.

To check your hardware:
```bash
iw phy phy0 info | grep -A 20 "valid interface combinations"
```

Look for a combination that includes both `managed` and `monitor` modes simultaneously.

---

## Requirements

### For the GUI (opendrop-gui)

- **Linux** (Debian/Ubuntu/Parrot/Arch/Fedora)
- **Python 3.10+**
- **uv** package manager
- **PyQt6** (installed automatically)
- **OWL** (installed as per setup guide)
- **System tray support** (most modern desktops have this)

### For the CLI (opendrop)

- **Python 3.10+**
- **libarchive** (system library)
- **Network access** via AWDL interface
- No GUI framework needed

### Hardware

**AWDL Compatibility:**
OpenDrop requires a Linux system running OWL (Open Wireless Link). This provides the AWDL wireless protocol layer that AirDrop uses.

- Supported: Any Linux system with a WiFi adapter that OWL supports
- OWL uses monitor mode which may temporarily affect WiFi connectivity
- Recommended: Systems with WiFi chips supporting concurrent monitor+managed mode

---

## Disclaimer

OpenDrop is experimental software and is the result of reverse engineering efforts by the [Open Wireless Link](https://owlink.org) project.
Therefore, it does not support all features of AirDrop or might be incompatible with future AirDrop versions.
OpenDrop is not affiliated with or endorsed by Apple Inc. Use this code at your own risk.

This fork (OpenDrop-GUI) maintains the same GPL-3.0 license and disclaimer as the original project.


## Requirements

To achieve compatibility with Apple AirDrop, OpenDrop requires the target platform to support a specific Wi-Fi link layer.
In addition, it requires Python >=3.6 as well as several libraries.

**Apple Wireless Direct Link.**
As AirDrop exclusively runs over Apple Wireless Direct Link (AWDL), OpenDrop is only supported on macOS or on Linux systems running an open re-implementation of AWDL such as [OWL](https://github.com/seemoo-lab/owl).

**Libraries.**
OpenDrop relies on a current version of [libarchive](https://www.libarchive.org).
macOS ships with a rather old version, so you will need to install a newer version, for example, via [Homebrew](https://brew.sh):
```bash
brew install libarchive
```
OpenDrop automatically sets `DYLD_LIBRARY_PATH` to look for the Homebrew version. You may need to update the variable yourself if you install the libraries differently.

Linux distributions should ship with more up-to-date versions, so this won't be necessary.


## Installation 

### Option 1: From PyPI (CLI only)

For the command-line interface only (no GUI):

```bash
pip3 install opendrop
```

### Option 2: From Source (CLI + GUI)

For the full GUI experience with OWL integration:

```bash
# Clone this fork
git clone https://github.com/YOURUSERNAME/opendrop opendrop-gui
cd opendrop-gui

# Install Python dependencies with uv
uv sync --extra gui

# One-time system setup (requires sudo).
# Auto-detects Debian/Ubuntu/Parrot, Fedora/RHEL, Arch/Manjaro, openSUSE,
# Alpine, and Void. Installs system dependencies, builds OWL from source,
# installs the polkit policy, and registers .desktop entries.
sudo bash scripts/install.sh
```

`scripts/install.sh` does:
- Detect distro and install matching system packages (libpcap, libev,
  libnl, bluez, build tools).
- Build OWL from source if not already on PATH.
- Install the polkit policy at /usr/share/polkit-1/actions so the GUI
  can ask for privileges via a graphical dialog instead of a tty sudo.
- Install opendrop.desktop / opendrop-doctor.desktop into the app menu.
- pip-install OpenDrop with the GUI extra.

### Option 3: Development Installation

If you want to modify the code:

```bash
git clone https://github.com/YOURUSERNAME/opendrop opendrop-gui
cd opendrop-gui

# Install in editable mode with dev dependencies
uv sync --all-groups
```


## Usage

### Using the GUI (Recommended)

```bash
opendrop-gui
```

The GUI appears in your system tray. **First time setup:**

1. **Start OWL**: Click "Start OWL" button
   - Your WiFi may briefly disconnect (normal on single-radio systems)
   - The `awdl0` interface will be created
2. **Find Devices**: Click "Refresh Devices" to discover nearby Apple devices
3. **Send Files**: Select a device and click "Send File"
4. **Receive Files**: Check "Accept incoming files" to receive

**System Tray Features:**
- **Left-click**: Show/hide window
- **Middle-click**: Toggle OWL
- **Right-click**: Context menu (Start OWL, Stop OWL, Settings, Quit)

**Settings**:
- Computer name (displayed to others)
- Receive directory (where files are saved)
- Interface names (advanced)
- Auto-start OWL on launch
- WiFi disruption warning

---

### Using the CLI (Original)

We briefly explain how to send and receive files using `opendrop`.
To see all command line options, run `opendrop -h`.

### Sending a File or a Link

Sending a file is typically a two-step procedure. You first discover devices in proximity using the `find` command.
Stop the process once you have found the receiver.
```
$ opendrop find
Looking for receivers. Press Ctrl+C to stop ...
Found  index 0  ID eccb2f2dcfe7  name John’s iPhone
Found  index 1  ID e63138ac6ba8  name Jane’s MacBook Pro
```
You can then `send` a file (or link, see below) using 
```
$ opendrop send -r 0 -f /path/to/some/file
Asking receiver to accept ...
Receiver accepted
Uploading file ...
Uploading has been successful
```
Instead of the `index`, you can also use `ID` or `name`.
OpenDrop will try to interpret the input in the order (1) `index`, (2) `ID`, and (3) `name` and fail if no match was found.

**Sending a web link.** Since v0.13, OpenDrop supports sending web links, i.e., URLs, so that receiving Apple devices will immediately open their browser upon accepting. 
(Note that OpenDrop _receivers_ still only support receiving regular files.)

```
$ opendrop send -r 0 -f https://owlink.org --url
```

### Receiving Files

Receiving is much easier. Simply use the `receive` command. OpenDrop will accept all incoming files automatically and put received files in the current directory.
```
$ opendrop receive
```


## Architecture

### System Architecture

```
┌─────────────────────────────────────────────────────────┐
│  OpenDrop GUI (PyQt6)                                   │
│  ├─ System Tray Icon                                    │
│  ├─ Main Window (Device List, Send/Receive Controls)    │
│  ├─ Settings Dialog                                     │
│  └─ OWLManager (systemd integration)                    │
└─────────────────────────────────────────────────────────┘
                          │
                          ▼
┌─────────────────────────────────────────────────────────┐
│  systemd Service (owl-awdl.service) [Root]              │
│  ├─ Creates mon0 virtual monitor interface              │
│  ├─ Runs OWL daemon (/usr/local/bin/owl -i mon0)        │
│  └─ Cleanup on stop (mon0 removal, WiFi restore)        │
└─────────────────────────────────────────────────────────┘
                          │
                          ▼
┌─────────────────────────────────────────────────────────┐
│  OWL (Open Wireless Link) [Open Source AWDL]            │
│  ├─ Creates awdl0 virtual interface                     │
│  ├─ Implements AWDL protocol                            │
│  └─ Manages channel switching, peer discovery           │
└─────────────────────────────────────────────────────────┘
                          │
                          ▼
┌─────────────────────────────────────────────────────────┐
│  OpenDrop Protocol Stack (Python)                       │
│  ├─ mDNS/Bonjour service discovery (zeroconf)           │
│  ├─ AirDrop protocol implementation (HTTPS)             │
│  ├─ File transfer (libarchive)                          │
│  └─ TLS with self-signed certificates                   │
└─────────────────────────────────────────────────────────┘
                          │
                          ▼
┌─────────────────────────────────────────────────────────┐
│  awdl0 Interface (IPv6 Link-Local)                      │
│  └─ Communicates with nearby Apple devices              │
└─────────────────────────────────────────────────────────┘
```

### WiFi Coexistence Strategy

OpenDrop uses a "virtual monitor interface" approach:

1. **Physical WiFi Interface** (`wlo1`)
   - Remains in station mode
   - Connected to your normal WiFi network
   - Managed by NetworkManager/systemd-networkd
   - **Preserved and functional**

2. **Virtual Monitor Interface** (`mon0`)
   - Created from `wlo1` via `iw dev wlo1 interface add mon0 type monitor`
   - Used exclusively by OWL for frame capture/injection
   - Disabled when OWL stops

3. **AWDL Interface** (`awdl0`)
   - Virtual TUN interface created by OWL
   - IPv6 link-local address assigned by OWL
   - Used by OpenDrop for AirDrop protocol

**Hardware Limitation:** On single-radio systems (most laptops), creating a monitor interface requires briefly taking the physical interface offline. This causes a momentary WiFi disconnect. On systems with supportive drivers (Intel AX200, newer Realtek), concurrent mode is possible—WiFi stays connected. The GUI checks and warns about this.

### Privilege Escalation

The GUI runs as a regular user. Only OWL (running via systemd service)
needs root. Privilege escalation uses **polkit** (pkexec) when available,
with a graphical authentication dialog. The polkit policy is installed
by `scripts/install.sh` at `/usr/share/polkit-1/actions/org.opendrop.policy`.

If polkit isn't present we fall back to `sudo`, prompting via the GUI.
No `NOPASSWD` sudoers entry is required.

For details on the abstraction, see `opendrop/platform_compat.py`.

---

## Current Limitations/TODOs

OpenDrop is the result of a research project and, thus, has several limitations (non-exhaustive list below). I do not have the capacity to work on them myself but am happy to provide assistance if somebody else want to take them on.

* *Triggering macOS/iOS receivers via Bluetooth Low Energy.* Apple devices start their AWDL interface and AirDrop server only after receiving a custom advertisement via Bluetooth LE (see USENIX paper for details). This means, that Apple AirDrop receivers may not be discovered even if they are discoverable by *everyone*.

* *Sender/Receiver authentication and connection state.* Currently, there is no peer authentication as in Apple's AirDrop, in particular, (1) OpenDrop does not verify that the TLS certificate is signed by [Apple's root](opendrop/certs/apple_root_ca.pem) and (2) that the Apple ID validation record is correct (see USENIX paper for details). In addition, OpenDrop automatically accepts any file that it receives due to a missing connection state.

* *Sending multiple files.* Apple AirDrop supports sending multiple files at once, OpenDrop does not (would require adding more files to the archive, modify HTTP /Ask request, etc.).

* *GUI-specific:* The GUI is functional but future enhancements could include:
  - Device icon support (iPhone, MacBook, iPad)
  - Transfer progress visualization
  - History/log of transfers
  - Drag-and-drop file sending


## Our Papers

* Alexander Heinrich, Matthias Hollick, Thomas Schneider, Milan Stute, and Christian Weinert. **PrivateDrop: Practical Privacy-Preserving Authentication for Apple AirDrop.** *30th USENIX Security Symposium (USENIX Security ’21)*, August 14–16, 2019, virtual Event. [Paper](https://www.usenix.org/conference/usenixsecurity21/presentation/heinrich) [Website](https://privatedrop.github.io) [Code](https://github.com/seemoo-lab/privatedrop)
* Milan Stute, Sashank Narain, Alex Mariotto, Alexander Heinrich, David Kreitschmann, Guevara Noubir, and Matthias Hollick. **A Billion Open Interfaces for Eve and Mallory: MitM, DoS, and Tracking Attacks on iOS and macOS Through Apple Wireless Direct Link.** *28th USENIX Security Symposium (USENIX Security ’19)*, August 14–16, 2019, Santa Clara, CA, USA. [Paper](https://www.usenix.org/conference/usenixsecurity19/presentation/stute)


## Authors

### Original Authors (seemoo-lab/opendrop)

* **Milan Stute** ([email](mailto:mstute@seemoo.tu-darmstadt.de), [web](https://seemoo.de/mstute)) — Primary author, SEEMOO Lab TU Darmstadt
* **Alexander Heinrich** — Co-author, SEEMOO Lab TU Darmstadt

### GUI Fork Contributors

* **Ravindra K.** — PyQt6 GUI implementation, OWL systemd integration, uv migration

All original protocol research, AirDrop reverse engineering, and core OpenDrop code are credited to the SEEMOO Lab team.

---

## License

OpenDrop is licensed under the [**GNU General Public License v3.0**](LICENSE).

This fork maintains the same GPL-3.0 license as the original project. All contributions are under GPL-3.0.

---

## Contributing

Contributions are welcome! Please:

1. Fork the repository
2. Create a feature branch (`git checkout -b feature/my-feature`)
3. Make your changes with proper documentation
4. Run the test suite (`uv run pytest`) and make sure everything passes
5. Run `opendrop-doctor` on your machine and include the output in the PR
6. Submit a pull request

**Code Style:**
- Follow PEP 8
- Use type hints in function signatures  
- Document all modules and functions with docstrings
- Run `black`, `isort`, and `pylint` before committing

**Running Tests:**
```bash
uv run pytest
```

**Installing Development Dependencies:**
```bash
uv sync --all-groups
```

---

## Support

- **Issues:** GitHub Issues
- **Upstream Help:** [SEEMOO Lab OpenDrop](https://github.com/seemoo-lab/opendrop)
- **OWL Documentation:** https://owlink.org

---

## Sponsors & Research

This project builds upon decades of WiFi security research by the [SEEMOO Lab](https://seemoo.de) at TU Darmstadt. If you find this project useful, consider supporting their ongoing work in open wireless security.

OpenDrop-GUI was created as an educational project to make AirDrop compatibility accessible to Linux users while respecting the original authors' work and GPL-3.0 license.
