#!/usr/bin/env python3

import argparse
import os
import sys
import socket

from influxdb_client import InfluxDBClient
from influxdb_client.client.exceptions import InfluxDBError


VALID_UHD_IMG_EXTENSIONSS = {".bin", ".hex", ".bit", ".img"}


def check_uhd_images(images_dir):
    print(f"\n[CHECK] UHD firmware images in: {images_dir}")

    if not os.path.isdir(images_dir):
        print("  ❌ Directory does not exist or is not a directory")
        return False

    valid_files = 0
    checked_files = 0

    for filename in os.listdir(images_dir):
        path = os.path.join(images_dir, filename)

        if not os.path.isfile(path):
            continue

        _, ext = os.path.splitext(filename)
        if ext.lower() not in VALID_UHD_IMG_EXTENSIONSS:
            continue

        checked_files += 1

        try:
            size = os.path.getsize(path)
            if size <= 0:
                print(f"  ❌ {filename}: empty file")
                continue

            with open(path, "rb") as f:
                f.read(16)

            print(f"  ✅ {filename}: {size} bytes")
            valid_files += 1

        except Exception as e:
            print(f"  ❌ {filename}: unreadable ({e})")

    if checked_files == 0:
        print("  ❌ No UHD firmware files found")
        return False

    if valid_files == 0:
        print("  ❌ No valid UHD firmware images detected")
        return False

    print(f"  ✔ {valid_files} valid UHD image(s) found")
    return True


def check_usb_mount():
    print("\n[CHECK] USB device access (/dev/bus/usb)")

    if os.path.exists("/dev/bus/usb"):
        print("  ✅ /dev/bus/usb is present")
        return True
    else:
        print("  ❌ /dev/bus/usb not found (Docker --device missing?)")
        return False


def check_reachability(host):
    print(f"\n[CHECK] Reachability of host: {host}")

    try:
        ip = socket.gethostbyname(host)
    except socket.gaierror:
        print("  ❌ DNS resolution failed")
        return False

    try:
        with socket.create_connection((ip, 80), timeout=3):
            print(f"  ✅ Host reachable ({ip})")
            return True
    except Exception:
        print(f"  ❌ Host not reachable ({ip})")
        return False


def check_env_variable(spec):
    """
    spec format:
      VAR            -> must exist
      VAR=VALUE      -> must exist and equal VALUE
    """
    print(f"\n[CHECK] Environment variable: {spec}")

    if "=" in spec:
        var, expected = spec.split("=", 1)
    else:
        var, expected = spec, None

    actual = os.environ.get(var)

    if actual is None:
        print(f"  ❌ {var} is not set")
        return False

    if expected is not None and actual != expected:
        print(f"  ❌ {var}='{actual}' (expected '{expected}')")
        return False

    if expected is not None:
        print(f"  ✅ {var}='{actual}'")
    else:
        print(f"  ✅ {var} is set")

    return True


def check_config_file(path):
    print(f"\n[CHECK] Configuration file: {path}")

    if not os.path.exists(path):
        print("  ❌ File does not exist")
        return False

    if not os.path.isfile(path):
        print("  ❌ Path is not a regular file")
        return False

    if not os.access(path, os.R_OK):
        print("  ❌ File is not readable")
        return False

    try:
        with open(path, "r") as f:
            f.read(1)
        print("  ✅ Configuration file is readable")
        return True
    except Exception as e:
        print(f"  ❌ Failed to read file ({e})")
        return False


def check_influxdb(url, token, org, bucket, port):
    print(f"\n[CHECK] InfluxDB instance: {url}")

    try:
        client = InfluxDBClient(
            url=url,
            token=token,
            org=org,
            port=port,
            timeout=3000
        )

        health = client.health()
        if health.status != "pass":
            print(f"  ❌ InfluxDB health check failed: {health.message}")
            return False
        print("  ✅ InfluxDB health check passed")

        orgs_api = client.organizations_api()
        orgs = orgs_api.find_organizations(org=org)
        if not orgs:
            print(f"  ❌ Organization '{org}' not found")
            return False
        print(f"  ✅ Organization '{org}' exists")

        buckets_api = client.buckets_api()
        bucket_obj = buckets_api.find_bucket_by_name(bucket)
        if not bucket_obj:
            print(f"  ❌ Bucket '{bucket}' not found")
            return False
        print(f"  ✅ Bucket '{bucket}' exists")

        client.close()
        return True

    except InfluxDBError as e:
        print(f"  ❌ InfluxDB API error: {e}")
        return False
    except Exception as e:
        print(f"  ❌ Failed to connect to InfluxDB: {e}")
        return False


def main():
    parser = argparse.ArgumentParser(description="UHD / USRP environment validation")

    parser.add_argument("--images-dir", help="Directory containing UHD firmware images")
    parser.add_argument("--check-usb", action="store_true",
                        help="Check that /dev/bus/usb exists (Docker)")
    parser.add_argument("--check-host", help="IP or hostname to check reachability")

    parser.add_argument(
        "--check-env",
        action="append",
        help="Check environment variable (VAR or VAR=VALUE). Can be used multiple times."
    )

    parser.add_argument(
        "--check-config",
        action="append",
        help="Check readable configuration file path. Can be used multiple times."
    )

    parser.add_argument("--check-influxdb", action="store_true",
                        help="Check InfluxDB connectivity and credentials")
    parser.add_argument("--influx-url", help="InfluxDB URL (e.g. http://localhost:8086)")
    parser.add_argument("--influx-token", help="InfluxDB access token")
    parser.add_argument("--influx-org", help="InfluxDB organization")
    parser.add_argument("--influx-bucket", help="InfluxDB bucket")
    parser.add_argument("--influx-port", help="InfluxDB port")

    args = parser.parse_args()

    failed = False

    if args.images_dir:
        if not check_uhd_images(args.images_dir):
            failed = True

    if args.check_usb:
        if not check_usb_mount():
            failed = True

    if args.check_host:
        if not check_reachability(args.check_host):
            failed = True

    if args.check_env:
        for spec in args.check_env:
            if not check_env_variable(spec):
                failed = True

    if args.check_config:
        for path in args.check_config:
            if not check_config_file(path):
                failed = True

    if args.check_influxdb:
        if not all([args.influx_url, args.influx_token, args.influx_org, args.influx_bucket, args.influx_port]):
            print("\n❌ InfluxDB check requires --influx-url, --influx-token, --influx-org, --influx-bucket, --influx-port")
            failed = True
        else:
            if not check_influxdb(
                args.influx_url,
                args.influx_token,
                args.influx_org,
                args.influx_bucket,
                args.influx_port
            ):
                failed = True

    if failed:
        print("\n❌ One or more checks FAILED")
        sys.exit(1)

    print("\n✅ All checks PASSED")
    sys.exit(0)


if __name__ == "__main__":
    main()

