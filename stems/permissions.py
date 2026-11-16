from __future__ import annotations

import ctypes
import ctypes.util
import sys


def request_accessibility_prompt() -> bool:
    """Return True if Stems already has Accessibility access.

    If not, ask macOS to show its own "allow Stems" dialog (with a button that
    opens System Settings). Does nothing on non-macOS systems.
    """
    if sys.platform != "darwin":
        return True
    try:
        app_services = ctypes.cdll.LoadLibrary(ctypes.util.find_library("ApplicationServices"))
        core = ctypes.cdll.LoadLibrary(ctypes.util.find_library("CoreFoundation"))

        core.CFDictionaryCreate.restype = ctypes.c_void_p
        core.CFDictionaryCreate.argtypes = [
            ctypes.c_void_p, ctypes.c_void_p, ctypes.c_void_p, ctypes.c_long, ctypes.c_void_p, ctypes.c_void_p,
        ]
        key = ctypes.c_void_p.in_dll(app_services, "kAXTrustedCheckOptionPrompt")
        true = ctypes.c_void_p.in_dll(core, "kCFBooleanTrue")
        keys = (ctypes.c_void_p * 1)(key)
        values = (ctypes.c_void_p * 1)(true)
        options = core.CFDictionaryCreate(
            None,
            keys,
            values,
            1,
            ctypes.c_void_p.in_dll(core, "kCFTypeDictionaryKeyCallBacks"),
            ctypes.c_void_p.in_dll(core, "kCFTypeDictionaryValueCallBacks"),
        )
        app_services.AXIsProcessTrustedWithOptions.argtypes = [ctypes.c_void_p]
        app_services.AXIsProcessTrustedWithOptions.restype = ctypes.c_bool
        return bool(app_services.AXIsProcessTrustedWithOptions(options))
    except Exception:
        return False
