import ctypes
import threading
import time
import unittest

from smart_snipper import (
    DEFAULT_HOTKEY_MOD,
    DEFAULT_HOTKEY_VK,
    HOTKEY_ID,
    MOD_NOREPEAT,
    HotkeyListener,
)


@unittest.skipUnless(__import__("sys").platform == "win32", "Windows-only hotkey test")
class HotkeyListenerTests(unittest.TestCase):
    def test_listener_keeps_pumping_messages_and_can_update_hotkey(self):
        triggered = threading.Event()
        listener = HotkeyListener(triggered.set)
        listener.start()
        self.assertTrue(listener._ready.wait(timeout=3))

        try:
            time.sleep(0.1)
            self.assertTrue(listener.is_alive())
            self.assertTrue(listener.update_hotkey(
                DEFAULT_HOTKEY_MOD, DEFAULT_HOTKEY_VK
            ))

            # Exercise the same WM_HOTKEY dispatch used by registered hotkeys.
            self.assertTrue(ctypes.windll.user32.PostMessageW(
                listener._hwnd, 0x0312, HOTKEY_ID, 0
            ))
            self.assertTrue(triggered.wait(timeout=1))

            # F24 is unlikely to be occupied and exercises the RegisterHotKey path.
            self.assertTrue(listener.update_hotkey(MOD_NOREPEAT, 0x87))
            self.assertTrue(listener.is_alive())
        finally:
            listener.stop()
            listener.join(timeout=3)

        self.assertFalse(listener.is_alive())


if __name__ == "__main__":
    unittest.main()
