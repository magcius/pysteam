
import os.path
import hashlib
import socket
import struct
from cStringIO import StringIO

import steamwhore
DATA_DIR = os.path.join(os.path.dirname(steamwhore.__file__), "data")

from steamwhore.cdr.models import CDR
from steamwhore.util import decode_host

##########################################################################
# Directory Server Address and Port.

def pack_length(data):
    return struct.pack('>L', len(data)) + data

def get_cdr(address="gds1.steampowered.com", port=27030):
    sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    sock.connect((address, port))

    # Directory Server.
    sock.send('\x00\x00\x00\x02')
    if sock.recv(1) == '\x01':
        sock.send(pack_length('\x03'))
        # Length - int (4 bytes)
        responseLength = sock.recv(4)
        # Unknown - short (2 bytes)
        sock.recv(2)
        # IP and Host - 6 bytes
        host = decode_host(sock.recv(6))

        # Config Sever.
        sock.close()
        sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        sock.connect(host)
        sock.send('\x00\x00\x00\x03')

        # Are we accepted?
        accepted = sock.recv(1)
        uIP = sock.recv(4)

        # Request CDR
        sock.send(pack_length('\x09' + hashlib.sha1(data).digest()))

        unknown = sock.recv(11)
        length, = struct.unpack('>L', sock.recv(4))

        data = []
        received = 0
        while received < length:
            chunk = sock.recv(length - received)
            received += len(chunk)
            data.append(chunk)

        return ''.join(data)

    return None

if __name__ == "__main__":
    pCDR = os.path.join(DATA_DIR, "CDR")
    pCDR_D = os.path.join(DATA_DIR, "CDR_decompressed")

    try:
        handle = open(pCDR, "rb")
        data = handle.read()
        handle.close()
    except IOError:
        data = get_cdr()

    handle = open(pCDR, "wb")
    handle.write(data)
    handle.close()

    cdr = CDR()
    cdr.parse(StringIO(data))
    print cdr
