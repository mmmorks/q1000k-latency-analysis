# Q1000K 10G small-packet latency: evidence and proposed vendor fix

Some Q1000K users see large ping spikes on the 10G Ethernet port, particularly with very small packets. In this investigation, changing to the 1G port substantially reduced those spikes. Independent inspection of an older official firmware image found that its 10G transmit routine lacks an explicit short-frame padding step that is present in its fiber transmit driver.

**This repository contains a proposed source patch for vendor review, not a flashable firmware update. It has not been built against the vendor SDK or tested on this installation.**

## Credit and what is new here

[James Hilliard identified this issue and published the padding fix and experimental runtime workaround](https://github.com/jameshilliard/q1000k-hsgmii-pad). His reported hardware tests support the diagnosis. This repository credits and packages his proposed vendor change; it does not claim to have discovered the bug or independently tested his workaround.

The additional contribution is independent, relocation-annotated disassembly of the original modules from provider-hosted firmware **QKX001-06.00.44.00**, with hashes and a comparison of the HSGMII and XPON transmit paths. The investigated installation reported **QKX002-06.01.25.00**; its exact binary was not obtained.

## What the fix does

Ethernet has a minimum frame length. When the packet is too short, the driver should reserve space, fill the missing bytes with zeros, and update the packet length before handing it to hardware. The proposed change adds that step in `hsgmii_lan_mac.c`, inside `hsgmii_lan_mac_tx()`, before statistics accounting and the QDMA transmit handoff.

- [Proposed vendor source patch](patches/0001-pad-short-hsgmii-frames.patch)
- [Integration notes and validation requirements](VALIDATION.md)
- [Independent binary findings and provenance](evidence/findings.md)
- [Focused disassembly excerpts](evidence/driver-excerpts.txt)
- [Original runtime workaround and its firmware limitations](https://github.com/jameshilliard/q1000k-hsgmii-pad/tree/a9b6a1472a732a34a2d33ec37f6f83191774fa8a)

The patch is generated from the before/after SDK excerpt published by James Hilliard at revision `a9b6a1472a732a34a2d33ec37f6f83191774fa8a`. The full vendor source tree was unavailable, so its path and surrounding context need confirmation by the vendor. The patch hunk's line numbers refer to that excerpt, not a recovered SDK file.

## Observations from this installation

These are sequential troubleshooting samples, not a controlled laboratory benchmark. The client used Wi-Fi; background traffic, routing changes and Wi-Fi variation limit comparisons. Values below are milliseconds to the same public IPv4 ping target. Each row is a separate 12-packet sample; zero means zero bytes of ICMP payload, not a zero-byte Ethernet frame.

| ONT connection and mode | ICMP payload | Mean RTT | Maximum RTT |
| --- | ---: | ---: | ---: |
| 10G port, routing / double NAT | 0 bytes | 75.401 | 270.631 |
| 10G port, routing / double NAT | 7 bytes | 7.841 | — |
| 1G port, routing / double NAT | 0 bytes | 7.416 | 10.391 |
| 1G port, after transparent bridging | 0 bytes | 8.445 | 11.493 |

The strong improvement occurred when moving to 1G, before double NAT was removed. That supports a port-specific issue. Double NAT was a separate configuration issue; removing it does not supply a missing driver padding operation. The 10G port was not retested after bridging, so this installation does not independently establish its behavior in that final mode.

This table preserves troubleshooting summaries. Raw packet captures and complete per-packet logs are not included, so percentiles and a causal latency model cannot be independently reconstructed from it.

## What is established, and what still needs testing

The older `hsgmii_lan_mac_tx` routine has no explicit minimum-length padding step in the inspected direct transmit path. In the same image, `xpon.ko` explicitly pads and extends short packets to 60 bytes. That is concrete static evidence consistent with the reported bug.

Static inspection does not prove how every vendor hook or hardware queue behaves. The reported hardware improvement from padding comes from James Hilliard's tests, not a firmware build tested here. Vendor engineering needs to confirm the current SDK implementation, test the change on hardware, and release a supported update.

For an affected customer whose service fits within 1 Gb/s, the 1G port was an effective workaround in this installation. It limits bandwidth and is not a universal result or a reason to change VLAN settings blindly.

## Vendor follow-up

Please review the short-frame handling in the shipping HSGMII driver, confirm affected firmware versions, and provide the fixed firmware version and rollout status. The relevant stack is the Q1000K firmware and Airoha/EcoNet SDK driver; this report is not a claim about the separate upstream Linux Airoha Ethernet driver.

## License

The proposed patch is adapted from James Hilliard's GPL-2.0-only project. Original contributions in this repository are also provided under GPL-2.0-only; see [LICENSE](LICENSE) and [NOTICE](NOTICE). Disassembly excerpts retain their original rights and are presented as technical evidence. No firmware images or kernel module binaries are distributed here.
