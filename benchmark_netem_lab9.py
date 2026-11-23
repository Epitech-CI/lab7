#!/usr/bin/env python3
"""
COMP 445 - Lab 9: Netem Benchmark Driver (Updated)
Executes swp_lab8.py inside Linux namespaces and benchmarks performance.

Usage:
  sudo python3 benchmark_netem.py --delay 60ms --jitter 10ms --loss 5% --magic 0x4331
"""

import subprocess
import argparse
import time
import os
import sys

TARGET_SCRIPT = "swp_lab8.py"

def run_command(cmd: str):
    res = subprocess.run(cmd, shell=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
    if res.returncode != 0:
        print(f"[ERROR]: {cmd}\n{res.stderr}")
    return res.stdout

def apply_netem(delay: str, jitter: str, loss: str):
    print(f"[*] Applying Netem rule: Delay={delay} Jitter={jitter} Loss={loss}")
    # Clear existing rules on both ends
    run_command("sudo ip netns exec ns_server tc qdisc del dev veth_s root 2>/dev/null || true")
    run_command("sudo ip netns exec ns_client tc qdisc del dev veth_c root 2>/dev/null || true")

    if not delay and not loss:
        return

    # Build netem rule
    netem_params = ""
    if delay:
        netem_params += f" delay {delay}"
        if jitter:
            netem_params += f" {jitter} distribution normal"
    if loss:
        netem_params += f" loss {loss}"

    # Apply symmetrically so RTT = 2 * one-way delay
    run_command(f"sudo ip netns exec ns_server tc qdisc add dev veth_s root netem {netem_params}")
    run_command(f"sudo ip netns exec ns_client tc qdisc add dev veth_c root netem {netem_params}")

def create_test_file(filename: str, size_bytes: int):
    if not os.path.exists(filename) or os.path.getsize(filename) != size_bytes:
        with open(filename, "wb") as f:
            f.write(os.urandom(size_bytes))
        print(f"[*] Generated benchmark payload file: {filename} ({size_bytes / 1024:.1f} KB)")

def main():
    parser = argparse.ArgumentParser(description="Netem Performance Benchmark")
    parser.add_argument("--delay", default="", help="One-way delay (e.g. 60ms)")
    parser.add_argument("--jitter", default="", help="Delay variation (e.g. 10ms)")
    parser.add_argument("--loss", default="", help="Packet loss percentage (e.g. 5%)")
    parser.add_argument("--magic", type=lambda x: int(x, 0), required=True, help="Assigned Magic ID")
    parser.add_argument("--size-kb", type=int, default=150, help="File size in KB (default: 150 KB)")
    args = parser.parse_args()

    if not os.path.exists(TARGET_SCRIPT):
        print(f"[!] Error: Cannot find '{TARGET_SCRIPT}' in current directory!")
        print(f"    Please place 'benchmark_netem.py' in the same folder as '{TARGET_SCRIPT}'.")
        sys.exit(1)

    test_file = "benchmark_payload.bin"
    file_size_bytes = args.size_kb * 1024
    create_test_file(test_file, file_size_bytes)

    # 1. Apply netem rule across namespaces
    apply_netem(args.delay, args.jitter, args.loss)

    # 2. Launch server inside ns_server
    print(f"[*] Starting server in 'ns_server' using {TARGET_SCRIPT}...")
    server_cmd = (
        f"sudo ip netns exec ns_server python3 {TARGET_SCRIPT} "
        f"--mode server --ip 10.0.0.2 --port 9090 --magic {hex(args.magic)} --timeout 0.8"
    )
    server_proc = subprocess.Popen(server_cmd, shell=True)
    time.sleep(0.5)

    # 3. Launch client inside ns_client and measure wall-clock duration
    print(f"[*] Transferring {args.size_kb} KB inside 'ns_client'...")
    client_cmd = (
        f"sudo ip netns exec ns_client python3 {TARGET_SCRIPT} "
        f"--mode client --ip 10.0.0.2 --port 9090 --magic {hex(args.magic)} --file {test_file}"
    )

    start_time = time.time()
    res = subprocess.run(client_cmd, shell=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
    elapsed_time = time.time() - start_time
    server_proc.terminate()

    if res.returncode != 0:
        print(f"[!] Transfer failed:\n{res.stderr}")
        return

    # 4. Display Results
    file_bits = file_size_bytes * 8
    empirical_throughput_kbps = (file_bits / elapsed_time) / 1000.0

    print("\n" + "="*60)
    print("        IN-LAB BENCHMARKING RESULTS (RECORD ON SHEET)")
    print("="*60)
    print(f"Configured Link Delay : {args.delay or 'None'} (Jitter: {args.jitter or 'None'})")
    print(f"Configured Packet Loss: {args.loss or '0%'}")
    print(f"Payload Size          : {args.size_kb} KB ({file_size_bytes} bytes)")
    print(f"Elapsed Transfer Time : {elapsed_time:.3f} seconds")
    print(f"Empirical Throughput  : {empirical_throughput_kbps:.2f} kbps")

    if args.delay and "ms" in args.delay:
        delay_ms = float(args.delay.replace("ms", ""))
        rtt_sec = (delay_ms * 2) / 1000.0  # RTT = 2 * one-way delay
        if rtt_sec > 0:
            mss_bytes = 512
            theoretical_max_kbps = ((mss_bytes * 8) / rtt_sec) / 1000.0
            print(f"Theoretical S&W Limit : {theoretical_max_kbps:.2f} kbps (MSS={mss_bytes}B, RTT={rtt_sec*1000:.1f}ms)")
    print("="*60 + "\n")

if __name__ == "__main__":
    if os.geteuid() != 0:
        print("[!] Must be run with root privileges: sudo python3 benchmark_netem.py ...")
        sys.exit(1)
    main()