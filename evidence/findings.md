# Q1000K 10G latency: independent driver inspection

Inspected September 9–10, 2026.

**The original 10G driver extracted from an official older Q1000K firmware image has no explicit short-frame padding in its transmit function. A fiber transmit driver in the same image does implement that padding. This independently corroborates the published diagnosis, but it is not a binary-level verification of the newer firmware currently installed on the investigated ONT.**

## What was obtained

No complete public decompilation or exact current driver binary was located. Instead, the official provider-hosted [QKX001-06.00.44.00 firmware image](https://internethelp.centurylink.com/internethelp/modems/Q1000K/firmware/QKX001-06.00.44.00.bin) was downloaded and its SquashFS filesystem read offline. The embedded `/etc/version` confirms that version.

The actual original `/lib/modules/5.4.55/hsgmii_lan.ko` was extracted and disassembled as AArch64 machine code, with ELF symbols and relocation annotations. This is disassembly plus manual interpretation, not recovered original C source or a complete decompilation.

The investigated ONT reported `QKX002-06.01.25.00`. A request for that filename in the same public download directory returned HTTP 404. The older image must not be represented as the currently installed build.

## Directly observed in the binary

All addresses below are offsets within the ELF `.text` section, not live device addresses. See [disassembly excerpts](driver-excerpts.txt).

1. **The 10G transmit function is identifiable by name.** `hsgmii_lan_mac_tx` starts at `0x1c30` and occupies 836 bytes. Its Ethernet interface branch selects its context at `0x1e54–0x1e70` and joins the common transmit path at `0x1ca4`.
2. **There is an upper-length check but no explicit lower-length correction.** At `0x1ca4–0x1cb0`, it reads the packet length at buffer offset `0x70`, compares it to `0xffff`, and branches to an error path if greater. The remainder prepares statistics and transmit metadata, then passes the original packet buffer through `__ECNT_HOOK` at `0x1dbc`. The direct transmit function has no 60-byte minimum-length comparison and no padding-helper call or packet-length extension.
3. **The driver does not import the standard `__skb_pad` helper.** It imports `skb_put`, but the observed call to that symbol is in its receive function at `0x205c`, not its transmit function. Absence of an import alone would not prove a bug; the transmit instruction sequence provides the stronger evidence.
4. **Minimum-size statistics are not actual padding.** The helper at `0xa80` selects at least 64 bytes for accounting. On the transmit branch (`0xacc–0xae4`) it stores the result in the driver's statistics structure. It does not change the packet length or contents.
5. **The same image contains a concrete padding implementation elsewhere.** In `xpon.ko`, `pwan_net_start_xmit` compares the packet length against 59 at `0x53af4`. For shorter-than-60-byte packets, it invokes a helper at `0x51dbc` with target length 60. That helper reaches `__skb_pad` through `0x51ba0`; after success, the caller extends the packet by `60 - length` using `skb_put` at `0x53b78`.

This contrast is consistent with an omitted padding step in the 10G driver. It does not establish that every downstream hook or hardware path is padding-free: vendor hook implementations and hardware queue timing were not exhaustively traced.

## Plain-language meaning

Ethernet requires a minimum frame size. The relevant software length is 60 bytes before the four-byte frame checksum. If a driver hands a shorter packet to hardware that expects software padding, that packet may be mishandled.

The independent binary inspection establishes the missing explicit step in the older 10G routine. The claim that this omission causes delayed transmission, and that adding padding fixes it on the newer build, comes from [James Hilliard's published analysis and live tests](https://github.com/jameshilliard/q1000k-hsgmii-pad/blob/master/docs/bug-analysis.md). Those tests, together with the local investigation’s strong improvement when switching physical ports, make this a well-supported diagnosis. Static inspection alone does not reproduce the hardware delay.

## What the experimental patch does

The [patch source](https://github.com/jameshilliard/q1000k-hsgmii-pad/blob/a9b6a1472a732a34a2d33ec37f6f83191774fa8a/src/qhsgpad.c) was also read. Before calling the original transmit function, it zero-pads packet buffers below 60 bytes and extends their recorded length. It wraps the existing transmit callback using firmware-specific memory offsets. It was not built, loaded, or tested on the investigated ONT during this investigation.

The essential logic, expressed as explanatory pseudocode, is:

```text
if packet length is less than 60:
    allocate/zero-fill the missing bytes
    if allocation fails: discard the packet safely
    update packet length to 60
call the original transmit function
```

This is a software correction to the Ethernet transmit path. Removing double NAT does not insert that missing driver step.

## Provenance and reproducibility

- Firmware size: 40,268,800 bytes.
- Firmware SHA-256: `dfdd23ffa8cbab9f3338835083d5a27c2ef0e27130d47b5d4a283d69df038972`.
- SquashFS starts at image offset 3,566,568; filesystem timestamp is 2024-11-05 13:28:21 UTC.
- Embedded platform: OpenWrt 21.02.1, `airoha/en7581`, AArch64; module kernel version: 5.4.55.
- `hsgmii_lan.ko` SHA-256: `798ac4be2da849e10dcbf007aea24ac9e64642ce463816c485c0c2c5f6ac6254`.
- `xpon.ko` SHA-256: `4eb54a2ac366a5154c96a464acc1e7fce02d23fddcbb8d0d3bca508e0bdfdd84`.
- Patch repository revision inspected: `a9b6a1472a732a34a2d33ec37f6f83191774fa8a`.
- Analysis used `dissect.squashfs` 1.12, `pyelftools` 0.33, and Capstone 5.0.9, installed in a workspace-only environment.

No firmware was installed, no code was run on the ONT, and no network settings were changed. Exact verification of the current build would require its firmware image or a read-only copy of its installed driver.
