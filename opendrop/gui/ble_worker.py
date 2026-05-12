"""
Qt-friendly BLE worker for AirDrop.

The bleak BLE library is asyncio-based but Qt isn't, so this module bridges
the two: each worker runs a private asyncio loop on a dedicated thread and
exposes Qt signals that the UI thread can connect to.

Two workers are provided:

    BLEScanWorker      — emits a signal whenever an Apple AirDrop BLE beacon
                         is seen. Use this to populate the device list.

    BLEAdvertiseWorker — broadcasts our own AirDrop BLE beacon while it's
                         running. Use this to wake up Apple devices in
                         "Everyone" mode so they activate AWDL.

Both workers fail soft: if BlueZ or the bleak library is unavailable, they
emit an `error` signal and stay otherwise quiet. The rest of the app keeps
working over mDNS / AWDL alone.
"""

from __future__ import annotations

import asyncio
import logging
import threading
from dataclasses import asdict
from typing import Dict, Optional

from PyQt6.QtCore import QThread, pyqtSignal

from opendrop.ble import AppleBLEDevice, BLEAdvertiser, BLEScanner

logger = logging.getLogger(__name__)


class BLEScanWorker(QThread):
    """
    Background BLE scanner. Emits one signal per detection callback.

    Signals:
        device_found:   AppleBLEDevice rendered as a dict for cross-thread
                        passing. The GUI is expected to deduplicate by
                        ``short_id`` and merge with mDNS data when possible.
        error:          Human-readable error string when BLE is unusable.
        started:        Emitted once the scanner is actually running.
        stopped:        Emitted when the thread exits cleanly.
    """

    device_found = pyqtSignal(dict)
    error = pyqtSignal(str)
    started = pyqtSignal()
    stopped = pyqtSignal()

    def __init__(self, parent=None) -> None:
        super().__init__(parent)
        self._loop: Optional[asyncio.AbstractEventLoop] = None
        self._stop_event: Optional[asyncio.Event] = None
        self._thread_started = threading.Event()

    def run(self) -> None:
        """Thread entry point: spin up an asyncio loop and run the scanner."""
        try:
            self._loop = asyncio.new_event_loop()
            asyncio.set_event_loop(self._loop)
            self._stop_event = asyncio.Event()
            self._thread_started.set()
            self._loop.run_until_complete(self._main())
        except Exception as e:
            logger.error(f"BLEScanWorker crashed: {e}")
            self.error.emit(str(e))
        finally:
            try:
                if self._loop is not None and not self._loop.is_closed():
                    self._loop.close()
            except Exception:
                pass
            self._loop = None
            self.stopped.emit()

    async def _main(self) -> None:
        def on_device(device: AppleBLEDevice) -> None:
            try:
                self.device_found.emit(asdict(device))
            except Exception as e:
                logger.debug(f"emit device_found failed: {e}")

        scanner = BLEScanner(on_device=on_device)
        try:
            await scanner.start()
        except RuntimeError as e:
            logger.warning(f"BLE scan unavailable: {e}")
            self.error.emit(str(e))
            return

        self.started.emit()
        logger.info("BLE scan worker is running")
        try:
            await self._stop_event.wait()
        finally:
            await scanner.stop()

    def stop(self) -> None:
        """Ask the worker to wind down. Safe to call from any thread."""
        # The asyncio loop and stop event live on the worker thread; we have
        # to schedule the set() on that loop or it does nothing.
        if not self._thread_started.is_set():
            return
        loop = self._loop
        if loop is None or loop.is_closed():
            return
        try:
            loop.call_soon_threadsafe(self._stop_event.set)
        except Exception as e:
            logger.debug(f"call_soon_threadsafe failed: {e}")
        # Wait for the thread to exit. Use a generous timeout — bleak's
        # scanner.stop() can take a few seconds on some BlueZ builds.
        if not self.wait(5000):
            logger.warning("BLEScanWorker did not stop within 5s")


class BLEAdvertiseWorker(QThread):
    """
    Background BLE advertiser. Broadcasts an AirDrop beacon until stopped.

    Signals:
        started:  Emitted once BlueZ has accepted our advertisement.
        error:    Human-readable error string when advertising fails.
        stopped:  Emitted when the thread exits cleanly.
    """

    started = pyqtSignal()
    error = pyqtSignal(str)
    stopped = pyqtSignal()

    def __init__(self, parent=None, adapter: str = "hci0") -> None:
        super().__init__(parent)
        self.adapter = adapter
        self._loop: Optional[asyncio.AbstractEventLoop] = None
        self._stop_event: Optional[asyncio.Event] = None
        self._thread_started = threading.Event()

    def run(self) -> None:
        try:
            self._loop = asyncio.new_event_loop()
            asyncio.set_event_loop(self._loop)
            self._stop_event = asyncio.Event()
            self._thread_started.set()
            self._loop.run_until_complete(self._main())
        except Exception as e:
            logger.error(f"BLEAdvertiseWorker crashed: {e}")
            self.error.emit(str(e))
        finally:
            try:
                if self._loop is not None and not self._loop.is_closed():
                    self._loop.close()
            except Exception:
                pass
            self._loop = None
            self.stopped.emit()

    async def _main(self) -> None:
        advertiser = BLEAdvertiser(adapter=self.adapter)
        try:
            await advertiser.start()
        except RuntimeError as e:
            logger.warning(f"BLE advertise unavailable: {e}")
            self.error.emit(str(e))
            return

        self.started.emit()
        logger.info("BLE advertise worker is running")
        try:
            await self._stop_event.wait()
        finally:
            await advertiser.stop()

    def stop(self) -> None:
        if not self._thread_started.is_set():
            return
        loop = self._loop
        if loop is None or loop.is_closed():
            return
        try:
            loop.call_soon_threadsafe(self._stop_event.set)
        except Exception as e:
            logger.debug(f"call_soon_threadsafe failed: {e}")
        if not self.wait(5000):
            logger.warning("BLEAdvertiseWorker did not stop within 5s")
