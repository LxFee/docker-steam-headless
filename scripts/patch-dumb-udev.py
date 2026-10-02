#!/usr/bin/env python3
"""Build-only patch for Steam-Headless/dumb-udev 64d1427; never run at startup."""
import hashlib
import sys
from pathlib import Path

SOURCE_SHA256 = "09aa1517fe0cc80d8ec61e78e6a1b9f2a4c4f9a4f5d1616f2efa06404d52bb2e"

# Literal upstream blocks deliberately retain their source indentation.
joystick_block = '''\
            file_content = [
                f"I:{init_usec}\\n",
                "E:ID_INPUT=1\\n",
                "E:ID_INPUT_JOYSTICK=1\\n",
                "E:ID_SERIAL=noserial\\n",
                "G:seat\\n",
            ]
'''
classified_block = '''\
            device_name = ""
            current = dev
            while current is not None and not device_name:
                device_name = (current.get("NAME") or "").strip('"')
                current = current.parent
            lowered_name = device_name.lower()
            if "keyboard" in lowered_name:
                input_properties = ["ID_INPUT_KEY", "ID_INPUT_KEYBOARD"]
            elif "mouse" in lowered_name:
                input_properties = ["ID_INPUT_MOUSE"]
            elif "touch" in lowered_name:
                input_properties = ["ID_INPUT_TOUCHSCREEN"]
            elif "pen" in lowered_name:
                input_properties = ["ID_INPUT_TABLET"]
            else:
                input_properties = ["ID_INPUT_JOYSTICK"]

            file_content = [
                f"I:{init_usec}\\n",
                "E:ID_INPUT=1\\n",
                *[f"E:{prop}=1\\n" for prop in input_properties],
                "E:ID_SERIAL=noserial\\n",
                "G:seat\\n",
            ]
'''


def patched_source(source):
    if hashlib.sha256(source).hexdigest() != SOURCE_SHA256:
        raise RuntimeError("unexpected dumb-udev 64d1427 source SHA-256")
    service = source.decode("utf-8")
    if service.count(joystick_block) != 1 or classified_block in service:
        raise RuntimeError('dumb-udev input classification block not found')
    service = service.replace(joystick_block, classified_block, 1)

    hash_replacements = {
        'subsys_hash = murmurhash2(subsys.encode(), 0)':
            'subsys_hash = socket.htonl(murmurhash2(subsys.encode(), 0))',
        'dev_type_hash = murmurhash2(dev_type.encode(), 0)':
            'dev_type_hash = socket.htonl(murmurhash2(dev_type.encode(), 0))',
    }
    for old, new in hash_replacements.items():
        if service.count(old) != 1 or new in service:
            raise RuntimeError(f'dumb-udev hash expression not found: {old}')
        service = service.replace(old, new, 1)
    compile(service, "dumb_udev/service.py", "exec")
    return service.encode("utf-8")


if __name__ == "__main__":
    if len(sys.argv) != 2:
        raise SystemExit("usage: patch-dumb-udev.py /path/to/dumb_udev/service.py")
    path = Path(sys.argv[1])
    # Validate the complete input and output before changing the installed file.
    path.write_bytes(patched_source(path.read_bytes()))
