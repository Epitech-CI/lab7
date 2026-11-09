#!/usr/bin/env python3
"""
COMP 445: Data Communications & Computer Networks
Lab 7: Reliable UDP Starter Skeleton

Name(s): GUERINAULT
Student ID(s): 40374063

Instructions:
  Complete the designated TODO sections below.
  Do NOT import external packet manipulation libraries (scapy, dpkt, etc.).
  Use only Python standard libraries.
"""

import socket
import struct
import argparse
import os
import sys

# Protocol Message Types
TYPE_REQUEST = 1
TYPE_DATA    = 2
TYPE_ACK     = 3
TYPE_ERROR   = 4

# Header Format:
# ! = Network (Big-Endian)
# H = 2 bytes (Magic Identifier)
# B = 1 byte  (Message Type)
# B = 1 byte  (Sequence Number: 0 or 1)
# I = 4 bytes (Connection ID)
# H = 2 bytes (Payload Length)
HEADER_FORMAT = "!H B B I H"
HEADER_SIZE = struct.calcsize(HEADER_FORMAT)

# =====================================================================
# TASK 1: Header Packing and Unpacking (10 Marks)
# =====================================================================
def pack_packet(magic_id: int, msg_type: int, seq_num: int, conn_id: int, payload: bytes) -> bytes:
    """
    TODO 1.1: Pack the binary header fields using struct.pack(HEADER_FORMAT, ...)
              and concatenate the raw payload bytes to the end.
    Returns: Complete packet as bytes.
    """
    # === STUDENT CODE HERE ===
    return struct.pack(HEADER_FORMAT, magic_id, msg_type, seq_num, conn_id, len(payload))
    # =========================


def unpack_packet(raw_bytes: bytes):
    """
    TODO 1.2: Unpack the header from the first HEADER_SIZE bytes.
              Separate and extract the remaining payload bytes.
    Returns: Tuple: (magic_id, msg_type, seq_num, conn_id, length, payload)
             Or None if raw_bytes is shorter than HEADER_SIZE.
    """
    # === STUDENT CODE HERE ===
    if (raw_bytes.__sizeof__() < HEADER_SIZE):
        return None
    return struct.unpack(HEADER_FORMAT, raw_bytes)
    # =========================


# =====================================================================
# TASKS 2 & 3: Server Implementation (Sender of File)
# =====================================================================
def run_server(ip: str, port: int, magic: int, mss: int):
    sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    sock.bind((ip, port))
    print(f"[SERVER] Listening on {ip}:{port} | Magic: {hex(magic)} | MSS: {mss}B")

    # -----------------------------------------------------------------
    # TODO 2.1: Wait for the initial REQUEST packet from the client.
    #   1. Receive packet using sock.recvfrom().
    #   2. Unpack packet using unpack_packet().
    #   3. Verify that magic == magic_id and msg_type == TYPE_REQUEST.
    #      If invalid, print a warning and ignore.
    #   4. Extract the requested filename from the payload.
    #   5. If the file does not exist on disk:
    #      Send an ERROR packet (TYPE_ERROR) back to the client and return.
    # -----------------------------------------------------------------

    # === STUDENT CODE HERE (REQUEST Handling) ===

    # ============================================

    # -----------------------------------------------------------------
    # TODO 3.1: Implement Lossless Stop-and-Wait Data Transfer:
    #   1. Open the file in binary read mode ('rb').
    #   2. Read chunks of at most 'mss' bytes.
    #   3. Alternate sequence numbers: starting at seq_num = 0.
    #   4. Pack each chunk into a DATA packet (TYPE_DATA) and sendto() client.
    #   5. Wait for the client's ACK packet.
    #   6. Verify the ACK has msg_type == TYPE_ACK and matching seq_num.
    #   7. Toggle sequence number: 0 -> 1 -> 0.
    #   8. Detect End-of-File (when len(chunk) < mss) and break.
    # -----------------------------------------------------------------

    # === STUDENT CODE HERE (Stop-and-Wait Sender Loop) ===

    # ====================================================

    print("[SERVER] Transfer complete. Closing socket.")
    sock.close()


# =====================================================================
# TASKS 2 & 3: Client Implementation (Requester & Receiver of File)
# =====================================================================
def run_client(server_ip: str, port: int, magic: int, filename: str):
    sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    server_addr = (server_ip, port)
    conn_id = 12345  # Session Connection ID

    # -----------------------------------------------------------------
    # TODO 2.2: Send the initial REQUEST packet to the server.
    #   1. Encode filename to bytes.
    #   2. Pack packet with msg_type = TYPE_REQUEST, seq_num = 0, conn_id.
    #   3. Send to server_addr using sock.sendto().
    # -----------------------------------------------------------------

    # === STUDENT CODE HERE (Send REQUEST) ===
    filename_encoded = filename.encode()
    packet = pack_packet(magic, TYPE_REQUEST, 0, conn_id, filename_encoded);
    sock.sendto(packet, server_addr)
    # ========================================

    output_filename = f"received_{filename}"
    expected_seq = 0

    # -----------------------------------------------------------------
    # TODO 3.2: Implement Stop-and-Wait Receiver Loop:
    #   1. Open output_filename in binary write mode ('wb').
    #   2. Loop and receive packets using sock.recvfrom().
    #   3. Unpack and verify: magic matches, conn_id matches, msg_type == TYPE_DATA.
    #   4. Check if server returned TYPE_ERROR (e.g. file not found).
    #   5. If seq_num == expected_seq:
    #        - Write payload to output file.
    #        - Pack and send ACK packet (TYPE_ACK) with seq_num back to server.
    #        - Toggle expected_seq: 0 -> 1 -> 0.
    #   6. Detect EOF (when payload length < MSS or final flag) and exit cleanly.
    # -----------------------------------------------------------------

    # === STUDENT CODE HERE (Stop-and-Wait Receiver Loop) ===

    with open(output_filename, 'wb') as opened_file:
        while True:
            data, _ = sock.recvfrom(HEADER_SIZE + 512)
            packet = unpack_packet(data)
            if (packet is None or packet[2] == TYPE_ERROR):
                return TYPE_ERROR
            if (packet[3] == expected_seq):
                opened_file.write(packet[4])
                ack = pack_packet(magic, TYPE_ACK, expected_seq, conn_id, bytes(packet[4]))
                sock.sendto(ack, server_addr)
                expected_seq = 1 if expected_seq == 0 else 0
            if len(packet[4]) < 512:
                break
    # ======================================================

    print(f"[CLIENT] Successfully received '{output_filename}'. Closing socket.")
    sock.close()


# =====================================================================
# CLI Entrypoint (Boilerplate provided)
# =====================================================================
if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="COMP 445: Lab 7")
    parser.add_argument("--mode", choices=["client", "server"], required=True, help="Mode: client or server")
    parser.add_argument("--ip", default="127.0.0.1", help="Target IP address (default: 127.0.0.1)")
    parser.add_argument("--port", type=int, default=8080, help="UDP port (default: 8080)")
    parser.add_argument("--magic", type=lambda x: int(x, 0), required=True, help="Magic Identifier from whiteboard (e.g. 0x4331)")
    parser.add_argument("--file", default="test.txt", help="Filename to request (client mode)")
    parser.add_argument("--mss", type=int, default=512, help="Max Segment Size in bytes (default: 512)")
    args = parser.parse_args()

    if args.mode == "server":
        run_server(args.ip, args.port, args.magic, args.mss)
    else:
        run_client(args.ip, args.port, args.magic, args.file)
