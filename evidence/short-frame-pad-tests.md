# Short-frame delay on the 10G port: hardware test of both fixes

Measured on 2026-10-03 on a Q1000K running **QKX001-06.00.44.00**. Its `hsgmii_lan.ko` is the module hashed in [findings.md](findings.md) (`798ac4be…`).

**The delay reproduces on QKX001, and only on the 10G port. Either fix removes it:**
- **0001, the software pad** in `hsgmii_lan_mac_tx`.
- **0004, the frame engine's own pad on the 10G port's egress** (GDMA4_FWD_CFG bit 28). The vendor SDK and upstream Linux both set this bit; the shipped firmware does not.

**Using both is no better than either alone, and neither has a measurable throughput or CPU cost.**

## Method

A host on the 10G port sends ARP requests for the Q1000K's own address, 400 per run, 50 ms apart, and times each request/reply pair to the microsecond. The Q1000K answers with a **42-byte ARP reply** that it sends itself out the 10G port.

The same probe from a host on the Q1000K's 1G port is the control. The test needs no change to either device's network configuration. The unit was in transparent-bridge mode, with the 10G port linked at 2.5 Gb/s.

Each leg also ran one throughput sample through the bridge:
- **download:** a 1 GB file from a nearby Hetzner speed-test host;
- **upload:** a 300 MB POST to Cloudflare's speed-test endpoint;
- **CPU:** per-core load on the Q1000K over the transfer, from `/proc/stat`.

The software leg replaced the running `hsgmii_lan.ko` with a build carrying 0001's pad. That build came from source that reproduces the stock QKX001 module byte for byte; the only change is 0001's hunk. The hardware leg set GDMA4_FWD_CFG bit 28 with a masked register write.

## Results

Legs in run order. "Short replies" are the 42 B ARP replies on the 10G port.

| leg | software pad | GDMA4 bit 28 | short replies < 1 ms | 5–20 ms | ≥ 20 ms | lost | p99 | max | 1G-port control, max |
| --- | --- | --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| stock | — | 0 | 288 / 390 | 43 | 21 | 2 | 39.9 ms | 41.6 ms | 0.6 ms |
| hardware | — | 1 | 393 / 400 | 1 | 0 | 0 | 1.8 ms | 7.2 ms | 14.3 ms * |
| software | ✓ | 0 | 395 / 400 | 1 | 0 | 0 | 1.6 ms | 9.8 ms | 1.6 ms |
| both | ✓ | 1 | 392 / 400 | 1 | 0 | 0 | 1.8 ms | 13.3 ms | 13.8 ms * |
| stock | — | 0 | 306 / 385 | 38 | 18 | 8 | 29.4 ms | 34.8 ms | 1.0 ms |

\* A single outlier in a 100-reply control run.

Separate hardware-pad runs on the same day (bit set, then cleared, then set again) gave the same picture:
- **bit set:** 197/200 and 394/400 replies under 1 ms, max 3.9 ms, none lost;
- **bit clear:** 20–28% of replies over 1 ms, 5–9% at 20 ms or more, and some lost.

Throughput: download 473–655 Mb/s, upload 304–596 Mb/s. The spread follows the internet path, not the leg: the two stock legs alone span 322–596 Mb/s upload. Q1000K CPU stayed at 0–2% per core in every transfer, because bulk traffic is forwarded by the PPE.

**Bridged short frames did not show the delay.** In the same configuration, ICMP replies from an internet host travelled pon → bridge → 10G port and passed through `hsgmii_lan_mac_tx`; the netdev's software TX counter confirms it. They carried 0–6 byte payloads, which makes 46–52 byte frames because the WAN is VLAN-tagged. They returned with flat medians and no size-dependent tail, with GDMA4 bit 28 clear. Frames the Q1000K generates itself did show the delay. An acceptance test should therefore include frames the device originates, such as ARP replies, and not rely on ICMP to internet hosts alone.

## Register state

FE base is physical `0x1fb50000`. Values on the stock unit:

| register | value | pad bit |
| --- | --- | --- |
| GDMA1_FWD_CFG `+0x0500` | `0x07f04444` | bit 28 = 0 |
| FE_CPORT_CFG `+0x0540` | `0x76000a02` | bit 26 = 1 (CPU-port pad, set by the `eth` driver's init) |
| GDMA2_FWD_CFG `+0x1500` | `0x07f18888` | bit 28 = 0 |
| GDMA3_FWD_CFG `+0x1100` | `0x07f14444` | bit 28 = 0 |
| GDMA4_FWD_CFG `+0x2500` | `0x07f14444` | **bit 28 = 0** |

GDMA1, GDMA2 and CPORT match the firmware's own `/proc/tc3162/fe_reg`. That dump stops before GDMA3/GDMA4.

The CPU-port pad is already on, yet the 10G port still delays short frames, so that bit does not cover this path.

GDMA4 is the 10G port's egress:
- the port's netdev is driven by `hsgmii_lan_eth`;
- the SDK's `hsgmii_lan_mac.c` sets `fport = DPORT_GDMA4` for it on EN7581;
- the live GDMA4 TX counters advance while GDMA3's stay at zero.

Once set, bit 28 survived a link down/up of the 10G port.

## The vendor change, and why the shipped firmware lacks it

The public Airoha EN7581 SDK sets the bit unconditionally at FE init, with the comment *"Enable padding before sending to HSGMII, otherwise it may cause delay"* ([call](https://github.com/lotusmomo/airoha_sdk/blob/32b5aa356c2406edef8806aaf75451ff0a5286f2/private/fe/fe.c#L6449-L6450), [helpers](https://github.com/lotusmomo/airoha_sdk/blob/32b5aa356c2406edef8806aaf75451ff0a5286f2/private/fe/fe.c#L2338-L2355)). `SUPPORT_GDMA2/3/4` are all true for EN7581 (`private/fe/fe_ic_dis.h`).

Upstream Linux does the same in [`airoha_fe_init`](https://github.com/torvalds/linux/blob/25d576ed11108470d0999054265108400db1b881/drivers/net/ethernet/airoha/airoha_eth.c#L561-L562). See also [`GDM4_BASE`](https://github.com/torvalds/linux/blob/25d576ed11108470d0999054265108400db1b881/drivers/net/ethernet/airoha/airoha_regs.h#L24) and [`GDM_PAD_EN_MASK`](https://github.com/torvalds/linux/blob/25d576ed11108470d0999054265108400db1b881/drivers/net/ethernet/airoha/airoha_regs.h#L125-L126).

The QKX001-06.00.44.00 `fe_core.ko` (SHA-256 `8571f396…ea60e7`) contains neither helper and no store of bit 28 to any GDMA FWD_CFG register. Its only `0x10000000` immediates are in `fe_set_cdm_oq_map`, which writes CDM registers. It was evidently built from an SDK revision that predates this change.

## Choosing between the fixes

- **0001** pads in software. It covers every frame the CPU hands to the 10G port, the case measured above. It needs a rebuilt `hsgmii_lan.ko`.
- **0004** pads in hardware at the port's egress. It covers the same frames, and also frames the PPE forwards straight to the 10G port without entering `hsgmii_lan_mac_tx`. That is most traffic on an accelerated unit; about 86% of GDMA4 egress on the test unit. It is a two-line init change in `fe_core`, and the bit can also be set at runtime.

The two are equivalent on the measured path, and they do not interact. Shipping both gives driver hygiene and hardware coverage.

## Patch 0004 provenance

The vendor source for the shipped `fe_core.ko` is not published. Patch 0004 is therefore expressed against the public SDK `fe.c` (`lotusmomo/airoha_sdk` at `32b5aa35`, file SHA-256 `6a8ba518c07a77fa8cf9ad4ebd2613e0e47c2c0d72e3fe2e10253da1c0081486`), with the vendor's lines removed to model the shipped module.

Every `+` line is the vendor's code verbatim:
- applied forward, the patch reproduces the public file byte for byte;
- `patch -R` applies cleanly to the public file.

Hunk line numbers refer to that model. The patch relies on the SDK's existing `GDMA{2,3,4}_FWD_CFG` and `GDMA_PAD_EN_BIT` definitions in `fe_reg_en7512.h`.
