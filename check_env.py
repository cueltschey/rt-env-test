#!/usr/bin/env python3

import argparse
import os
import sys
import socket
import requests
import time

from influxdb_client import InfluxDBClient
from influxdb_client.client.exceptions import InfluxDBError

class ApiInterface:
    def __init__(self, control_ip, control_port, control_token):
        self.control_url = f"http://{control_ip}:{control_port}"
        self.auth_header = f"Bearer {control_token}"
        self.headers = {}

    def make_request(self, target_endpoint, payload=None):
        if(payload):
            return self._post_endpoint(target_endpoint, payload)
        else:
            return self._get_endpoint(target_endpoint)

    def _post_endpoint(self, target_endpoint, json_payload):
        self.headers = {"Authorization": self.auth_header, "Accept": "application/json", "User-Agent": "llm_worker/1.0", "Content-Type": "application/json"}
        try:
            response = requests.post(url=f"{self.control_url}/{target_endpoint}", headers=self.headers, json=json_payload, verify=False)
            if response.status_code == 200:
                return True, response.json()
            return False, {"error": response.text}
        except requests.exceptions.RequestException as e:
            return False, {"error":str(e)}

    def _get_endpoint(self, target_endpoint):
        self.headers = {"Authorization": self.auth_header, "Accept": "application/json", "User-Agent": "llm_worker/1.0"}
        try:
            response = requests.get(url=f"{self.control_url}/{target_endpoint}", headers=self.headers, verify=False)
            if response.status_code == 200:
                return True, response.json()
            return False, {"error": response.text}
        except requests.exceptions.RequestException as e:
            return False, {"error":str(e)}


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
            f"http://{url}:{port}",
            org=org,
            token=token
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


def check_api(host, port, token):
    interface = ApiInterface(host, port, token)

    time.sleep(1) # Give time for controller to initialize
    worked, output = interface.make_request("list")

    if not worked:
        print(f"  ❌ Encountered error when making GET to /list: {output}")
        return False

    print(f" ✅ GET to /list worked with JSON: '{output}'")
    return True


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
    parser.add_argument("--influx-url", default=os.environ.get("INFLUX_HOST"), help="InfluxDB URL (e.g. http://localhost:8086)")
    parser.add_argument("--influx-token", default=os.environ.get("INFLUX_TOKEN"), help="InfluxDB access token")
    parser.add_argument("--influx-org", default=os.environ.get("INFLUX_ORG"), help="InfluxDB organization")
    parser.add_argument("--influx-bucket", default=os.environ.get("INFLUX_BUCKET"), help="InfluxDB bucket")
    parser.add_argument("--influx-port", default=os.environ.get("INFLUX_PORT"), help="InfluxDB port")

    parser.add_argument("--check-control-api", action="store_true",
                        help="Check the control API")

    parser.add_argument("--control-host", default=os.environ.get("CONTROL_HOST"), help="control API host")
    parser.add_argument("--control-port", default=os.environ.get("CONTROL_PORT"), help="Control API port")
    parser.add_argument("--control-token", default=os.environ.get("CONTROL_TOKEN"), help="Control API token")

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
        if not check_influxdb(
            args.influx_url,
            args.influx_token,
            args.influx_org,
            args.influx_bucket,
            args.influx_port
        ):
            failed = True

    if args.check_control_api:
        if not check_api(args.control_host, args.control_port, args.control_token):
            failed = True

    if failed:
        print("\n❌ One or more checks FAILED")
        sys.exit(1)

    print("\n✅ All checks PASSED")
    sys.exit(0)


if __name__ == "__main__":
    main()

