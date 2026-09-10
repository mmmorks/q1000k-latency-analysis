#!/usr/bin/env python3
"""Offline component regressions. No router, DHCP client or network is used."""
import hashlib
import json
from pathlib import Path
import shlex
import shutil
import subprocess
import tempfile

ROOT = Path(__file__).resolve().parents[1]
FIXTURES = ROOT / "tests/fixtures/QKX001-06.00.44.00"
CHECKS = 0


def check(name, actual, expected):
    global CHECKS
    assert actual == expected, f"{name}: expected {expected!r}, got {actual!r}"
    CHECKS += 1
    print(f"PASS {name}")


def shell(code, variables, cwd):
    # A controlled environment prevents inherited DHCP variables affecting tests.
    env = {"PATH": str(cwd / "bin"), "LC_ALL": "C", **variables}
    result = subprocess.run(["/bin/sh", "-c", code], cwd=cwd, env=env,
                            text=True, capture_output=True, timeout=5)
    if result.returncode:
        raise AssertionError(f"shell failed ({result.returncode}): {result.stderr}")
    return result.stdout


def routes(source, overrides, cwd):
    # Only these two original function definitions are evaluated. Top-level
    # imports, DHCP dispatch and user hooks are excluded. Dependencies are
    # inert stubs; no host route command can be found in PATH.
    body = source[source.index("set_classless_routes() {"):
                  source.index("\ndeconfig_interface() {")]
    stubs = """
proto_init_update() { :; }
proto_add_ipv4_address() { :; }
proto_add_ipv4_route() { printf 'ROUTE|%s|%s|%s|%s\\n' "$1" "$2" "$3" "$4"; }
proto_add_dns_server() { :; }
proto_add_dns_search() { :; }
proto_add_data() { :; }
proto_close_data() { :; }
proto_send_update() { :; }
json_add_string() { :; }
json_add_int() { :; }
"""
    variables = {"ip": "192.0.2.10", "subnet": "255.255.255.0", "mask": "24",
                 "INTERFACE": "wan", "IFACE6RD": "0", **overrides}
    output = shell(stubs + body + "\nsetup_interface\n", variables, cwd)
    return [tuple(line.split("|")[1:]) for line in output.splitlines()
            if line.startswith("ROUTE|")]


def route(dest, prefix, gateway):
    return (dest, str(prefix), gateway, "192.0.2.10")


def hook(source, event, logical, physical, cwd):
    status_dir = cwd / "status"
    status_dir.mkdir(exist_ok=True)
    result_path = status_dir / "wan_status"
    if result_path.exists():
        result_path.unlink()
    # Redirect only the cache directory; the original matching logic is intact.
    assert source.count("dir=/tmp/ifstatus") == 1
    source = source.replace("dir=/tmp/ifstatus", "dir=" + shlex.quote(str(status_dir)))
    stubs = """
logger() { :; }
ifstatus() { printf '{"interface":"%s","stub":true}\\n' "$1"; }
"""
    shell(stubs + "\nset -- " + shlex.quote(event) + "\n" + source + "\n:",
          {"INTERFACE": logical, "interface": physical}, cwd)
    return json.loads(result_path.read_text()) if result_path.exists() else None


def main():
    for name, digest in json.loads((FIXTURES / "SHA256.json").read_text()).items():
        check("original fixture hash: " + name,
              hashlib.sha256((FIXTURES / name).read_bytes()).hexdigest(), digest)

    with tempfile.TemporaryDirectory(prefix="q1000k-offline-") as temp:
        temp = Path(temp)
        (temp / "bin").mkdir()
        ipcalc = temp / "bin/ipcalc.sh"
        ipcalc.write_text("""#!/bin/sh
case "$1" in
    192.0.2.*/24) printf 'NETWORK=192.0.2.0\\n';;
    198.51.100.*/24) printf 'NETWORK=198.51.100.0\\n';;
    *) exit 1;;
esac
""")
        ipcalc.chmod(0o700)
        patched = temp / "patched"
        shutil.copytree(FIXTURES, patched)
        for name in ("0002-honor-classless-route-precedence.patch",
                     "0003-refresh-status-on-pon-dhcp-renew.patch"):
            result = subprocess.run(["git", "apply", str(ROOT / "patches" / name)],
                                    cwd=patched, text=True, capture_output=True)
            check("patch applies to actual extracted file: " + name,
                  (result.returncode, result.stderr), (0, ""))

        dhcp_name = "lib/netifd/dhcp.script"
        hook_name = "etc/udhcpc.user.d/00-dhcp-update"
        sources = {"original": FIXTURES, "patched": patched}
        for label, root in sources.items():
            for name in (dhcp_name, hook_name):
                result = subprocess.run(["/bin/sh", "-n", str(root / name)],
                                        text=True, capture_output=True)
                check(f"shell syntax: {label} {name}", result.returncode, 0)

        default = route("0.0.0.0", 0, "192.0.2.1")
        alternate = route("0.0.0.0", 0, "192.0.2.2")
        specific = route("203.0.113.0", 24, "192.0.2.2")
        # name, input environment, expected original, expected patched
        cases = [
            ("router-only lease", {"router": "192.0.2.1"}, [default], [default]),
            ("121 conflicting default", {"router": "192.0.2.1", "staticroutes":
             "0.0.0.0/0 192.0.2.2"}, [default, alternate], [alternate]),
            ("121 deliberately no default", {"router": "192.0.2.1", "staticroutes":
             "203.0.113.0/24 192.0.2.2"}, [default, specific], [specific]),
            ("121 duplicate default", {"router": "192.0.2.1", "staticroutes":
             "0.0.0.0/0 192.0.2.1"}, [default, default], [default]),
            ("121 without Router option", {"staticroutes": "203.0.113.0/24 192.0.2.2"},
             [specific], [specific]),
            ("121 off-subnet next hop", {"staticroutes": "0.0.0.0/0 198.51.100.1"},
             [route("0.0.0.0", 0, "198.51.100.1")],
             [route("198.51.100.1", 32, ""), route("0.0.0.0", 0, "198.51.100.1")]),
            ("121 off-subnet next hop plus option 3", {"router": "198.51.100.1",
             "staticroutes": "0.0.0.0/0 198.51.100.1"},
             [route("198.51.100.1", 32, ""), route("0.0.0.0", 0, "198.51.100.1"),
              route("0.0.0.0", 0, "198.51.100.1")],
             [route("198.51.100.1", 32, ""), route("0.0.0.0", 0, "198.51.100.1")]),
            ("121 on-link destination", {"staticroutes": "203.0.113.0/24 0.0.0.0"},
             [route("203.0.113.0", 24, "0.0.0.0")], [route("203.0.113.0", 24, "0.0.0.0")]),
            ("multiple routers without 121", {"router": "192.0.2.1 192.0.2.2"},
             [default, alternate], [default, alternate]),
            ("off-subnet router without 121", {"router": "198.51.100.1"},
             [route("198.51.100.1", 32, ""), route("0.0.0.0", 0, "198.51.100.1")],
             [route("198.51.100.1", 32, ""), route("0.0.0.0", 0, "198.51.100.1")]),
            ("custom routes without 121", {"router": "192.0.2.1", "CUSTOMROUTES":
             "203.0.113.0/24"}, [default, route("203.0.113.0", 24, "192.0.2.1")],
             [default, route("203.0.113.0", 24, "192.0.2.1")]),
            ("249 behavior unchanged", {"router": "192.0.2.1", "msstaticroutes":
             "203.0.113.0/24 192.0.2.2"}, [default, specific], [default, specific]),
            ("no supplied routes", {}, [], []),
        ]
        for name, inputs, old_expected, new_expected in cases:
            for label, expected in (("original", old_expected), ("patched", new_expected)):
                check(f"DHCP {name} ({label})",
                      routes((sources[label] / dhcp_name).read_text(), inputs, temp), expected)

        refreshed = {"interface": "wan", "stub": True}
        hook_cases = [
            ("PON base", "renew", "wan", "pon0", None, refreshed),
            ("PON VLAN", "renew", "wan", "pon0.201", None, refreshed),
            ("PON alternate", "renew", "wan", "pon1", None, refreshed),
            ("ethernet", "renew", "wan", "eth0.8.201", None, None),
            ("other logical interface", "renew", "lan", "pon0", None, None),
            ("initial lease", "bound", "wan", "pon0", None, None),
            ("lease removal", "deconfig", "wan", "pon0", None, None),
            ("missing physical interface", "renew", "wan", "", None, None),
        ]
        for name, event, logical, physical, old_expected, new_expected in hook_cases:
            for label, expected in (("original", old_expected), ("patched", new_expected)):
                check(f"status hook {name} ({label})",
                      hook((sources[label] / hook_name).read_text(), event, logical, physical, temp),
                      expected)

    print(f"\n{CHECKS} checks passed; {len(cases)} DHCP scenarios and {len(hook_cases)} status-hook scenarios, each before/after.")
    print("Script component tests only; no target kernel, firmware or live network test.")


if __name__ == "__main__":
    main()
