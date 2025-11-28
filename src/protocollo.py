# protocollo.py
import pickle
import struct

# Frame format: [4-byte length prefix][pickle payload]


class ProtocolError(Exception):
    pass


def send_msg(sock, obj):
    try:
        payload = pickle.dumps(obj, protocol=pickle.HIGHEST_PROTOCOL)
    except Exception as e:
        raise ProtocolError(f"Serialization error: {e}")

    length = struct.pack('!I', len(payload))

    try:
        sock.sendall(length + payload)
    except Exception as e:
        raise ProtocolError(f"Send error: {e}")


def recv_exact(sock, n):
    data = b""
    while len(data) < n:
        chunk = sock.recv(n - len(data))
        if not chunk:
            raise ProtocolError("Connection closed unexpectedly during recv_exact.")
        data += chunk
    return data


def recv_msg(sock):
    # Read length prefix
    try:
        header = recv_exact(sock, 4)
    except Exception as e:
        raise ProtocolError(f"Header read error: {e}")

    (length,) = struct.unpack('!I', header)

    # Read payload
    try:
        payload = recv_exact(sock, length)
    except Exception as e:
        raise ProtocolError(f"Payload read error: {e}")

    # Deserialize
    try:
        obj = pickle.loads(payload)
    except Exception as e:
        raise ProtocolError(f"Deserialization error: {e}")

    return obj
