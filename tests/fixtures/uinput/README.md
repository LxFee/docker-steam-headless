# dumb-udev regression fixture

`service.py` is the unmodified upstream source at
<https://raw.githubusercontent.com/Steam-Headless/dumb-udev/64d1427/dumb_udev/service.py>.
SHA-256: `09aa1517fe0cc80d8ec61e78e6a1b9f2a4c4f9a4f5d1616f2efa06404d52bb2e`.
The upstream license is retained in `LICENSE.dumb-udev`.

Tests patch temporary copies only. The helper under test is the actual
`overlay/usr/bin/start-dumb-udev.sh`, not a historical helper fixture.

Run from the image repository root (Python standard library and Bash only):

```sh
PYTHONDONTWRITEBYTECODE=1 python3 -m unittest discover -s tests -p 'test_uinput.py' -v
```

Docker builds additionally set `UINPUT_HELPER` and `UINPUT_SERVICE` to check the
actual installed helper and patched service against the tested output.
