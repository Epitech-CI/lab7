#!/usr/bin/env python3
"""
COMP 445: Data Communications & Computer Networks
Lab 8: Reliable UDP (Timeouts, Loss Recovery & Integrity)

Name(s): _____________________________________________
Student ID(s): _______________________________________

Instructions:
  The binary packing and unpacking functions from lab 7 are provided below.
  Your task is to implement reliability over an unreliable channel by completing:
    - Task 1: Sender-Side Timeout & Retransmission Loop (12 Marks)
    - Task 2: Receiver Duplicate Packet Detection & ACK Loss Handling (12 Marks)
    - Task 3: Clean EOF Termination & SHA-256 Integrity Check (11 Marks)

Usage:
  Server: python3 swp_lab8.py --mode server --port 8080 --magic 0x4331 --timeout 0.5 [--drop-data N]
  Client: python3 swp_lab8.py --mode client --ip 127.0.0.1 --port 8080 --magic 0x4331 --file test.txt [--drop-ack M]
"""

import socket
import struct
import argparse
import hashlib
import time
import os
import sys

# Protocol Message Types
TYPE_REQUEST = 1
TYPE_DATA    = 2
TYPE_ACK     = 3
TYPE_ERROR   = 4

# Header Format: ! = Big-Endian, H = 2B Magic, B = 1B Type, B = 1B Seq, I = 4B ConnID, H = 2B Length
HEADER_FORMAT = "!H B B I H"
HEADER_SIZE = struct.calcsize(HEADER_FORMAT)  # 10 bytes

UNPACK_MAGIC_ID = 0
UNPACK_MSG_TYPE = 1
UNPACK_SEQ_NUM = 2
UNPACK_CONN_ID = 3
UNPACK_LENGHT = 4
UNPACK_PAYLOAD = 5


# =====================================================================
# PROVIDED: Binary Packing, Unpacking & Integrity Helpers
# =====================================================================
def pack_packet(magic_id: int, msg_type: int, seq_num: int, conn_id: int, payload: bytes) -> bytes:
    """Packs the binary header and attaches payload bytes."""
    header = struct.pack(HEADER_FORMAT, magic_id, msg_type, seq_num, conn_id, len(payload))
    return header + payload


def unpack_packet(raw_bytes: bytes):
    """Unpacks header fields. Returns None if packet is shorter than HEADER_SIZE."""
    if len(raw_bytes) < HEADER_SIZE:
        return None
    header = raw_bytes[:HEADER_SIZE]
    payload = raw_bytes[HEADER_SIZE:]
    magic_id, msg_type, seq_num, conn_id, length = struct.unpack(HEADER_FORMAT, header)
    return magic_id, msg_type, seq_num, conn_id, length, payload


def compute_sha256(filepath: str) -> str:
    """Calculates the SHA-256 hash of a file to verify byte-level integrity."""
    hasher = hashlib.sha256()
    with open(filepath, 'rb') as f:
        while chunk := f.read(4096):
            hasher.update(chunk)
    return hasher.hexdigest()


# =====================================================================
# TASK 1: Server Implementation (Sender with Timeouts & Retransmission)
# =====================================================================
def run_server(ip: str, port: int, magic: int, timeout_sec: float, drop_data_idx: int):
    sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    sock.bind((ip, port))
    print(f"[SERVER] Listening on {ip}:{port} | Magic: {hex(magic)} | Timeout: {timeout_sec}s")
    if drop_data_idx > 0:
        print(f"[SIMULATION] Configured to drop DATA packet index #{drop_data_idx} on first attempt.")

    # 1. Wait for REQUEST
    raw_data, client_addr = sock.recvfrom(2048)
    unpacked = unpack_packet(raw_data)
    if not unpacked or unpacked[0] != magic or unpacked[1] != TYPE_REQUEST:
        print("[SERVER ERROR] Invalid initial REQUEST packet. Exiting.")
        return

    conn_id = unpacked[3]
    filename = unpacked[5].decode('utf-8', errors='ignore')
    print(f"[SERVER] Client requested: '{filename}' (ConnID: {conn_id})")

    if not os.path.exists(filename):
        print(f"[SERVER ERROR] File '{filename}' not found. Sending TYPE_ERROR.")
        sock.sendto(pack_packet(magic, TYPE_ERROR, 0, conn_id, b"File not found"), client_addr)
        return

    # -----------------------------------------------------------------
    # TODO 1.1: Configure Socket Timeout
    #   Use sock.settimeout(...) to set the socket timeout to timeout_sec.
    # -----------------------------------------------------------------
    # === STUDENT CODE HERE ===
    sock.settimeout(timeout_sec)
    # =========================

    seq_num = 0
    packet_counter = 0
    total_retransmissions = 0

    with open(filename, 'rb') as f:
        while True:
            chunk = f.read(512)
            packet_counter += 1
            data_pkt = pack_packet(magic, TYPE_DATA, seq_num, conn_id, chunk)

            # -------------------------------------------------------------
            # TODO 1.2: Implement Retransmission & Loss-Hook Loop
            #   1. Handle loss simulation:
            #      If packet_counter == drop_data_idx (and this is the 1st attempt),
            #      do NOT send the packet; print a log message simulating the loss,
            #      and let the socket timeout expire!
            #      Else: send data_pkt using sock.sendto().
            #   2. Enter a loop waiting for the corresponding ACK:
            #      try:
            #          Receive packet from client.
            #          Verify ACK magic, conn_id, TYPE_ACK, and seq_num == seq_num.
            #          If valid ACK received: break out of retransmit loop.
            #      except socket.timeout:
            #          Increment total_retransmissions.
            #          Print: "[TIMEOUT] Seq #{seq_num} timed out! Retransmitting..."
            #          Retransmit data_pkt using sock.sendto().
            # -------------------------------------------------------------
            # === STUDENT CODE HERE ===
            if packet_counter == drop_data_idx:
                print(f"Packet {packet_counter} dropped")
            while True:
                try:
                    recv_packet, client_addr = sock.recvfrom(2048)
                    unpacked = unpack_packet(recv_packet)
                    if unpacked and unpacked[UNPACK_MAGIC_ID] == magic and unpacked[UNPACK_CONN_ID] == conn_id and unpacked[UNPACK_MSG_TYPE] == TYPE_ACK and unpacked[UNPACK_SEQ_NUM] == seq_num:
                        break;
                except TimeoutError:
                    total_retransmissions += 1
                    print(f"[TIMEOUT] Seq #{seq_num} timed out! Retransmitting")
                    sock.sendto(data_pkt, client_addr)

            # =========================

            # Toggle sequence number (0 -> 1 -> 0)
            seq_num = 1 - seq_num

            # Detect End-of-File: final chunk is smaller than 512 bytes
            if len(chunk) < 512:
                print("[SERVER] Final EOF chunk sent.")
                break

    # -----------------------------------------------------------------
    # TODO 3.1: Print final statistics and SHA-256 hash of source file
    # -----------------------------------------------------------------
    print(f"[SERVER] Transfer complete. Total Retransmissions: {total_retransmissions}")
    # === STUDENT CODE HERE (Print SHA-256 hash using compute_sha256) ===
    print(compute_sha256(filename))
    # ==================================================================
    sock.close()


# =====================================================================
# TASK 2: Client Implementation (Receiver with Duplicate Handling)
# =====================================================================
def run_client(server_ip: str, port: int, magic: int, filename: str, drop_ack_idx: int):
    sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    conn_id = 9999
    server_addr = (server_ip, port)

    if drop_ack_idx > 0:
        print(f"[SIMULATION] Configured to drop ACK #{drop_ack_idx}!")

    # Send Initial REQUEST
    sock.sendto(pack_packet(magic, TYPE_REQUEST, 0, conn_id, filename.encode('utf-8')), server_addr)
    print(f"[CLIENT] Sent REQUEST for '{filename}'")

    expected_seq = 0
    ack_counter = 0
    output_filename = f"received_{filename}"

    with open(output_filename, 'wb') as f_out:
        while True:
            raw_pkt, _ = sock.recvfrom(2048)
            parsed = unpack_packet(raw_pkt)
            if not parsed or parsed[0] != magic or parsed[3] != conn_id:
                continue

            _, msg_type, seq_num, _, length, payload = parsed

            if msg_type == TYPE_ERROR:
                print(f"[CLIENT ERROR] Server error: {payload.decode('utf-8')}")
                break

            if msg_type == TYPE_DATA:
                ack_counter += 1

                # ---------------------------------------------------------
                # TODO 2.1: Duplicate Sequence Detection & Payload Handling
                #   If seq_num == expected_seq:
                #     - This is new in-order data! Write payload to f_out.
                #     - Toggle expected_seq (0 -> 1 -> 0).
                #   Else (seq_num != expected_seq):
                #     - This is a DUPLICATE packet (server retransmitted because
                #       previous ACK was lost or delayed).
                #     - Print: "[CLIENT] Duplicate Seq #{seq_num} detected! Discarding redundant payload."
                #     - DO NOT write payload to f_out!
                # ---------------------------------------------------------
                # === STUDENT CODE HERE ===
                if seq_num == expected_seq:
                    f_out.write(payload)
                    expected_seq ^= 1
                else:
                    print(f"[CLIENT] Duplicate Seq #{seq_num} detected! Discarding redundant payload.")
                # =========================

                # ---------------------------------------------------------
                # TODO 2.2: ACK Loss-Hook & Transmission
                #   If ack_counter == drop_ack_idx:
                #     - Print simulation message and do NOT send ACK.
                #   Else:
                #     - Pack and send ACK packet (TYPE_ACK) with seq_num to server_addr.
                # ---------------------------------------------------------
                # === STUDENT CODE HERE ===
                if ack_counter == drop_ack_idx:
                    print(f"ACK {ack_counter} dropped !")
                else:
                    data_pack = pack_packet(magic, TYPE_ACK, seq_num, conn_id, b"")
                    sock.sendto(data_pack, server_addr)
                # =========================


                # Detect EOF: final packet received
                if length < 512:
                    print("[CLIENT] Received final chunk.")
                    break

    # -----------------------------------------------------------------
    # TODO 3.2: Print Delivered File SHA-256 Hash
    # -----------------------------------------------------------------
    print(f"[CLIENT] File saved as: {output_filename}")
    # === STUDENT CODE HERE (Print SHA-256 hash using compute_sha256) ===
    print(compute_sha256(filename))
    # ==================================================================
    sock.close()


# =====================================================================
# CLI Entrypoint (Boilerplate provided)
# =====================================================================
if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="COMP 445: Lab 8")
    parser.add_argument("--mode", choices=["client", "server"], required=True)
    parser.add_argument("--ip", default="127.0.0.1", help="Target IP address")
    parser.add_argument("--port", type=int, default=8080, help="UDP port")
    parser.add_argument("--magic", type=lambda x: int(x, 0), required=True, help="Magic Identifier (e.g. 0x4331)")
    parser.add_argument("--file", default="test.txt", help="Filename to request (client mode)")
    parser.add_argument("--timeout", type=float, default=0.5, help="Socket timeout in seconds (server mode)")
    parser.add_argument("--drop-data", type=int, default=0, help="Index of DATA packet to drop (server mode)")
    parser.add_argument("--drop-ack", type=int, default=0, help="Index of ACK packet to drop (client mode)")
    args = parser.parse_args()

    if args.mode == "server":
        run_server(args.ip, args.port, args.magic, args.timeout, args.drop_data)
    else:
        run_client(args.ip, args.port, args.magic, args.file, args.drop_ack)
