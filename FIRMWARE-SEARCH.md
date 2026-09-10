# Firmware availability search — 2026-09-10 UTC

**The newest version for which we found identifiable primary-source evidence is QKX002-06.01.25.00. The newest complete image we could actually obtain remains QKX001-06.00.44.00.** These are different claims. This search did not locate a later release, but cannot establish that none exists in a staged or private provider rollout.

| Version | Evidence | Image obtained? |
| --- | --- | --- |
| QKX002-06.01.25.00 | Installed version recorded during the local investigation; [James Hilliard's hardware test](https://github.com/jameshilliard/q1000k-hsgmii-pad/blob/a9b6a1472a732a34a2d33ec37f6f83191774fa8a/README.md#status); a separate [public Q1000K API implementation](https://github.com/jeremybanka/celilo/blob/7356e45b7d9d0f3f1edd5479365a9c9a5a33a9d7/modules/axon/scripts/router-api.ts) also identifies this build | No; `.bin` and `.img` requests at the known provider download location returned 404 |
| QKX002-06.01.14.00 | Earlier version reported in customer discussions, used as a search lead | No; `.bin` and `.img` requests at the known location returned 404 |
| QKX001-06.00.44.00 | [Provider-hosted image](https://internethelp.centurylink.com/internethelp/modems/Q1000K/firmware/QKX001-06.00.44.00.bin), verified against its embedded version | Yes; HTTP 200; the image analyzed in this repository |

The available `.bin` has SHA-256 `dfdd23ffa8cbab9f3338835083d5a27c2ef0e27130d47b5d4a283d69df038972`. Its HTTP Last-Modified value is January 8, 2026, while the embedded filesystem timestamp is November 5, 2024. A file-server timestamp is not evidence that this is a newly built firmware release.

## Search coverage

- Reviewed the official [Quantum Fiber Q1000K support page](https://www.quantumfiber.com/support/equipment/user-guides/q1000k-smartnid.html), searched Quantum/AT&T/Axon domains for firmware releases and source packages, and checked the manufacturer's public website. No newer image link was located.
- Searched exact version strings, `Q1000K firmware download`, `.bin` references, release notes, recent rollout reports, and a possible `QKX003` version family. General web searches, public GitHub repository/code/issue search, and GitLab/archive-targeted searches yielded no newer downloadable firmware. Forum reports were discovery leads, not substitutes for a binary.
- Checked the original research repository's release list: no release assets were returned. Public code references to `QKX002` led to the workaround and an API client, not a complete image. An exact-version GitHub issue search returned this repository's existing report.
- Checked both image extensions used by the embedded upgrade UI, `.bin` and `.img`, for all three known versions at the provider's established firmware path. The [recorded HTTP results](evidence/firmware-url-probes.json) distinguish 404 responses from a directory-listing 403. The directory was not enumerable; no access restriction was bypassed.
- Queried the public Wayback CDX index for successful captures under the provider's Q1000K directory, collapsed by URL. It returned only the older `.bin` URL. The [archive response](evidence/firmware-archive-index.json) is preserved; it is not an exhaustive record of every image ever distributed.
- Inspected the older firmware's embedded upgrade UI offline. It obtains the image base URL and filename from its management data model; it contains no fixed newer image URL. Its fallback uses an `.img` suffix, which is why that extension was checked as well.

The initial Python HTTPS probe failed because that Python runtime lacked a trusted issuer certificate. All recorded final HTTP results were retried using curl with normal certificate verification; certificate errors were not counted as evidence of missing images.

## Analysis scope and next input needed

The expanded review used the newest obtainable image above. It covered the HSGMII/XPON transmit comparison, DHCP route setup and renewal hooks, IPv6/6rd setup scripts, and firmware-upgrade UI references. It is a bounded review, not an assertion that every firmware component has been audited or that all bugs have been found.

Two additional script defects were reproduced and patched offline; see [the script findings](evidence/script-findings.md). They are established for the extracted older files. Their presence in QKX002-06.01.25.00 or any later build remains unverified.

To verify the shipping release, the vendor can provide a supported download URL and checksum, a complete image, or the corresponding SDK/source files and read-only copies of the relevant installed modules/scripts. We did not request a firmware upgrade, alter the ONT, or use a service-access workaround to obtain these files.
