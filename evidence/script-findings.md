# Two additional firmware-script defects

Reviewed 2026-09-10 UTC. **Both findings concern the actual files extracted from QKX001-06.00.44.00. Neither has been verified in the newer installed firmware or established as a cause of this installation's latency.** The tests execute the relevant shell logic offline with networking operations replaced by stubs.

## 1. DHCP classless-route precedence is not honored

File: `/lib/netifd/dhcp.script`, `setup_interface()` and `set_classless_routes()`.

The script first adds a default route for each gateway in the DHCP Router option (`router`, option 3), then adds the Classless Static Routes option (`staticroutes`, option 121). It does this even when option 121 is present. [RFC 3442's DHCP Client Behavior section](https://www.rfc-editor.org/info/rfc3442/) requires the client to ignore the Router option in this combination.

The extracted `/lib/netifd/proto/dhcp.sh` selects this script and requests option 121 by default unless classless routes are disabled. This is not merely an unused example file. The installed package metadata identifies BusyBox 1.34.1-10 and netifd 2021-07-26-440eb064-1. The matching [upstream BusyBox version's DHCP client source](https://github.com/mirror/busybox/blob/1_34_1/networking/udhcp/dhcpc.c) exports received options to the script; this upstream reference is not a full audit of vendor modifications to its binary.

With a synthetic lease specifying option 3 gateway `192.0.2.1` and option 121 default gateway `192.0.2.2`, the original script emits both default routes. The patched script emits only the option 121 route. When option 121 deliberately contains only a specific network route, the original still emits an unwanted default route and the patched script does not. All addresses in these tests are documentation examples.

Possible effect: unexpected or conflicting route submissions when a server supplies both options. Actual kernel route selection and provider DHCP behavior were not tested, so this is not a claim that Quantum sends such leases or that this caused the earlier outage.

[Patch 0002](../patches/0002-honor-classless-route-precedence.patch) suppresses option-3-derived route setup when option 121 is nonempty. It also gives classless next hops the same off-subnet host-route handling already used for ordinary default gateways. That preserves reachability when an option-121 gateway is outside the assigned subnet, without depending on the now-ignored option 3.

Integration limits: the legacy `CUSTOMROUTES` setting obtains its next hop from option 3, so those derived routes are also skipped when option 121 is present. Vendor integration should confirm the desired semantics for that optional setting and use explicitly configured next hops if required. The patch does not redesign option 249 precedence or malformed-option parsing. Upstream OpenWrt's publicly inspected script also contained the option-3/121 ordering; no claim of a vendor-exclusive or previously unknown bug is made.

## 2. PON DHCP-renew status refresh cannot match real PON interface names

File: `/etc/udhcpc.user.d/00-dhcp-update`.

The file's stated purpose is to refresh cached WAN status on a PON DHCP renewal where ordinary netifd notifications are insufficient. Its condition contains:

```sh
[[ "${interface}" == "pon*" ]]
```

The quoted right-hand side is literal text, not a PON-prefix pattern. For `pon0` and `pon0.201`, the original hook does not call `ifstatus`. [Patch 0003](../patches/0003-refresh-status-on-pon-dhcp-renew.patch) uses a portable shell `case` pattern and retains the requirements that the event be `renew` and the logical interface be `wan`.

The original script skipped the refresh for all three tested PON names. The patched script wrote the expected stubbed status for all three. Ethernet interfaces, other logical interfaces, initial leases, lease removals and a missing interface name still produced no refresh.

Possible effect: stale `/tmp/ifstatus/wan_status` after the specific PON renewal event. This is a status-cache bug, not proof that DHCP renewal itself fails. The installed device's actual physical interface name and execution of this hook in its current firmware were not verified. Ethernet-named WAN paths do not trigger this PON-specific hook by design.

## Provenance and verification

The firmware's package lists assign both files to `netifd`; its package metadata specifies GPL-2.0. The original files are preserved as [test fixtures](../tests/fixtures/QKX001-06.00.44.00), including [SHA-256 values](../tests/fixtures/QKX001-06.00.44.00/SHA256.json). They are unchanged from extraction.

The [test harness](../tests/test_firmware_scripts.py) applies both patches to temporary copies of those files, checks syntax, and compares original and patched behavior. It uses 13 DHCP scenarios and 8 renewal-hook scenarios, each before/after. Together with fixture hashes, patch applicability and syntax checks, **51 checks passed**. See [test results](script-test-results.md).

These checks verify component behavior on the host shell. They do not emulate the ONT, build vendor firmware, test the target BusyBox binary, install real routes, or confirm persistence across a supported firmware update. The vendor should repeat the cases with the shipping BusyBox/netifd, actual DHCP messages and real interface events before release.
