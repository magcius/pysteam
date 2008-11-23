
import time, datetime, socket, binascii, struct

def bytes_as_bool(data):
    return all(x != "\0" for x in data)

# Host (IP and Port) encoding and decoding
# Little endian for some reason...
# First four bytes = IP
# Last two bytes = Port

def encode_host((ip, port)):
    n = tuple(ip.split(".")) + (port)
    return struct.pack("<BBBBH", *n)

def decode_host(data):
    ip = ".".join(map(str, struct.unpack("<BBBB", data[:4])))
    port, = struct.unpack("<H", data[4:])
    return (ip, port)

def py_time(steam_time):
    unix = (steam_time / 1000000) - 62135596800
    microseconds = steam_time % 1000000
    return datetime.datetime.fromtimestamp(unix) - datetime.timedelta(0, 0, microseconds)

def steam_time(py_time):
    return time.mktime(py_time) + 62135596800 * 1000000


class Logging:
    
    def __init__(self, filename="log.txt"):
        self.handle = open(filename, "a")
    def __del__(self):
        self.handle.close()
    def debug(self, msg):
        self.handle.write(str(datetime.datetime.now()) + " - DEBUG: " + msg + "\n")
    def warning(self, msg):
        self.handle.write(str(datetime.datetime.now()) + " - WARN: " + msg + "\n")
    def error(self, msg):
        self.handle.write(str(datetime.datetime.now()) + " - ERROR: " + msg + "\n")



class ImpSocket:
    "improved socket class - this is REALLY braindead because the socket class doesn't let me override some methods, so I have to build from scratch"
    
    def __init__(self, sock = None):
        self.logging = Logging()
        if sock is None :
            self.s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        else :
            self.s = sock

    def accept(self) :
        (returnedsocket, address) = self.s.accept()
        newsocket = ImpSocket(returnedsocket)
        newsocket.address = address

        return newsocket, address


    def bind(self, address) :
        self.address = address
        self.s.bind(address)


    def connect(self, address, log = False) :
        self.address = address
        self.s.connect(address)

        if log:
            self.logging.debug(str(self.address) + ": Connecting to address")


    def close(self) :
        self.s.close()


    def listen(self, connections) :
        self.s.listen(connections)


    def send(self, data, log = True) :
        sentbytes = self.s.send(data)

        if log :
            self.logging.debug(str(self.address) + ": Sent data - " + binascii.b2a_hex(data))

        if sentbytes != len(data) :
            self.logging.warning("NOTICE!!! Number of bytes sent doesn't match what we tried to send " + str(sentbytes) + " " + str(len(data)))

        return sentbytes

    def sendto(self, data, address, log = True) :
        sentbytes = self.s.sendto(data, address)

        if log :
            self.logging.debug(str(address) + ": sendto Sent data - " + binascii.b2a_hex(data))

        if sentbytes != len(data) :
            self.logging.warning("NOTICE!!! Number of bytes sent doesn't match what we tried to send " + str(sentbytes) + " " + str(len(data)))

        return sentbytes


    def send_withlen(self, data, log = True) :
        lengthstr = struct.pack(">L", len(data))

        if log :
            self.logging.debug(str(self.address) + ": Sent data with length - " + binascii.b2a_hex(lengthstr) + " " + binascii.b2a_hex(data))

        totaldata = lengthstr + data
        totalsent = 0
        while totalsent < len(totaldata) :
            sent = self.send(totaldata, False)
            if sent == 0:
                raise RuntimeError, "socket connection broken"
            totalsent = totalsent + sent


    def recv(self, length, log = True) :
        data = self.s.recv(length)

        if log :
            self.logging.debug(str(self.address) + ": Received data - " + binascii.b2a_hex(data))

        return data

    def recvfrom(self, length, log = True) :
        (data, address) = self.s.recvfrom(length)

        if log :
            self.logging.debug(str(address) + ": recvfrom Received data - " + binascii.b2a_hex(data))

        return (data, address)

    def recv_all(self, length, log = True) :
        data = ""
        while len(data) < length :
            chunk = self.recv(length - len(data), False)
            if chunk == '':
                raise RuntimeError, "socket connection broken"
            data = data + chunk

        if log :
            self.logging.debug(str(self.address) + ": Received all data - " + binascii.b2a_hex(data))

        return data

    def recv_withlen(self, log = True) :
        lengthstr = self.recv(4, False)
        if len(lengthstr) != 4 :
            print "HEADER NOT LONG ENOUGH"
        length = struct.unpack(">L", lengthstr)[0]

        data = self.recv_all(length, False)

        if log :
            self.logging.debug(str(self.address) + ": Received data with length  - " + binascii.b2a_hex(lengthstr) + " " + binascii.b2a_hex(data))

        return data

