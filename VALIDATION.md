# Vendor integration and validation

This section describes the HSGMII driver patch. The additional DHCP and PON-status patches have separate [findings, applicability limits](evidence/script-findings.md) and [offline test results](evidence/script-test-results.md). Run their regressions with `python3 tests/test_firmware_scripts.py`. Both apply to the extracted older firmware files; verify the current vendor copies before integration.

## Proposed change

Apply the logic in `patches/0001-pad-short-hsgmii-frames.patch` to the actual SDK copy of `hsgmii_lan_mac.c:hsgmii_lan_mac_tx()`. Placement is after the oversize rejection and before `update_xsi_sw_mib()` and the QDMA transmit handoff, following the source excerpt published by James Hilliard.

The required software length is `ETH_ZLEN` (60 bytes without FCS). `skb_padto()` must successfully reserve and zero-fill the tail before `skb_put()` extends the recorded packet length. Merely increasing `skb->len` would be incorrect.

On padding failure, the standard helper consumes the buffer. The proposed branch increments the driver's existing error/drop counters and returns `NETDEV_TX_OK`; it must not free the buffer again or return a busy status for retry. Verify the shipping kernel's helper semantics and counter types during integration.

The 48/49-byte boundary reported by the original researcher is a hardware symptom, not the Ethernet minimum. Do not narrow this fix to that observed boundary.

## Checks performed for this repository

- Independently inspected older official firmware's HSGMII and XPON disassembly; see the evidence directory for exact versions, hashes and offsets.
- Generated the unified diff directly from the original researcher's published before/after source excerpt.
- Checked that the diff applies to that excerpt and reproduces the published result byte for byte.

These checks do not establish applicability to a complete vendor checkout. No vendor SDK build, automated kernel test, runtime module installation, firmware flashing or patched-hardware test was performed here.

## Acceptance tests for the vendor

1. Build against the exact shipping kernel and SDK, with normal warning checks. Confirm the padding occurs before all relevant DMA submissions and that packet ownership/error handling matches the actual transmit contract.
2. Exercise packet lengths below, at and above 60 bytes, including 42, 48, 49, 59, 60 and 61 bytes as seen by this function. Check zero-filled padding and unchanged existing packet bytes. Exercise shared/cloned and non-linear buffers, insufficient tailroom and allocation failure; verify no leak, double-free or transmission of uninitialized bytes.
3. On a wired downstream capture host, compare stock and patched firmware on the same Q1000K, cable, port and negotiated speed. Use controlled background traffic and measure at idle as well as under load. Capture both on-device and downstream timestamps, accounting for timestamp-source differences.
4. Run low-rate IPv4 ICMP payload sweeps from 0 through 18 bytes, especially 6 and 7, plus standard 56-byte payloads. Include ARP and small TCP/IPv6 control traffic; do not infer general application behavior from ICMP alone. Collect enough samples to report sample count, loss, median, p95, p99 and maximum RTT.
5. Cover 1G and 10G ports, supported negotiated speeds, router mode and supported transparent bridge/VLAN configurations. Keep the topology fixed within each stock-versus-patched comparison.
6. Check ordinary throughput, offloads, MTU/jumbo behavior and long-running stability. Confirm the change survives reboot as part of the supported firmware image.

Acceptance means removal of the size-dependent excess delay without regressions or memory-safety failures. Absolute internet ping time is not an appropriate universal pass threshold.

## Sources

- [Original proposed SDK correction](https://github.com/jameshilliard/q1000k-hsgmii-pad/blob/a9b6a1472a732a34a2d33ec37f6f83191774fa8a/README.md#vendor-driver-fix)
- [Original analysis and hardware results](https://github.com/jameshilliard/q1000k-hsgmii-pad/blob/a9b6a1472a732a34a2d33ec37f6f83191774fa8a/docs/bug-analysis.md)
