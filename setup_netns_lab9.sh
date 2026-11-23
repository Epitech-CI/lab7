#!/bin/bash
# COMP 445 - Lab 9: Network Namespace & Veth Setup Script (Robust Version)

set -e

# 1. Enforce root privileges
if [ "$EUID" -ne 0 ]; then
    echo "[!] Error: Please run as root: sudo bash setup_netns.sh [up|down]"
    exit 1
fi

ACTION=$1

cleanup() {
    echo "[*] Cleaning up existing namespaces and virtual interfaces..."
    ip netns del ns_client 2>/dev/null || true
    ip netns del ns_server 2>/dev/null || true
    ip link del veth_c 2>/dev/null || true
    ip link del veth_s 2>/dev/null || true
}

if [ "$ACTION" == "up" ]; then
    # Clean any stale interfaces first to prevent "File exists" errors
    cleanup

    echo "[*] Creating namespaces: ns_client and ns_server..."
    ip netns add ns_client
    ip netns add ns_server

    echo "[*] Creating virtual ethernet pair: veth_c <--> veth_s..."
    ip link add veth_c type veth peer name veth_s

    echo "[*] Moving interfaces into respective namespaces..."
    ip link set veth_c netns ns_client
    ip link set veth_s netns ns_server

    echo "[*] Configuring IP addresses (ns_client: 10.0.0.1, ns_server: 10.0.0.2)..."
    ip netns exec ns_client ip addr add 10.0.0.1/24 dev veth_c
    ip netns exec ns_client ip link set veth_c up
    ip netns exec ns_client ip link set lo up

    ip netns exec ns_server ip addr add 10.0.0.2/24 dev veth_s
    ip netns exec ns_server ip link set veth_s up
    ip netns exec ns_server ip link set lo up

    echo "[+] Setup complete! Testing baseline ping connectivity..."
    ip netns exec ns_client ping -c 2 10.0.0.2

elif [ "$ACTION" == "down" ]; then
    cleanup
    echo "[+] Namespaces and virtual interfaces removed successfully."

else
    echo "Usage: sudo bash setup_netns.sh [up|down]"
    exit 1
fi