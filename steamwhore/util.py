
import time, datetime, struct

def bytes_as_bool(data):
    return all(x != "\0" for x in data)

# Host (IP and Port) encoding and decoding
# Little endian for some reason...
# First four bytes = IP
# Last two bytes = Port

def encode_host(t):
    ip, port = t
    n = tuple(ip.split(".")) + (port)
    return struct.pack("<BBBBH", *n)

def decode_host(data):
    ip = ".".join(str(s) for s in struct.unpack("<BBBB", data[:4]))
    port, = struct.unpack("<H", data[4:])
    return (ip, port)

def py_time(steam_time):
    unix = (steam_time / 1000000) - 62135596800
    microseconds = steam_time % 1000000
    return datetime.datetime.fromtimestamp(unix) - datetime.timedelta(0, 0, microseconds)

def steam_time(py_time):
    return (time.mktime(py_time) + 62135596800) * 1000000 
