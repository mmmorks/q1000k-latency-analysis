# Offline script regression results

Date: 2026-09-10 UTC.

Host: Darwin arm64, Python 3.10.1, `/bin/sh`. This is not the target Linux/BusyBox environment.

Command, from repository root:

```sh
python3 tests/test_firmware_scripts.py
```

Observed final result:

```text
51 checks passed; 13 DHCP scenarios and 8 status-hook scenarios, each before/after.
Script component tests only; no target kernel, firmware or live network test.
```

- 3 original-file SHA-256 checks passed.
- 2 patches applied to the actual extracted files.
- 4 shell syntax checks passed: the two relevant files before and after patching.
- 26 DHCP comparisons passed: 13 scenarios for each version.
- 16 status-hook comparisons passed: 8 scenarios for each version.

The original-version expectations explicitly reproduce the defects; a “PASS” on an original case means the defective output was reproduced, not that the original implementation is correct. The patched expectations encode the corrected behavior and preserved unaffected cases.

Networking functions are stubs. The DHCP test evaluates only the route/setup function definitions, with IPv6 tunnel creation disabled. The status-hook test redirects its output into a temporary directory. No firmware binary is launched, and no router settings, host routes or live DHCP leases are changed.
