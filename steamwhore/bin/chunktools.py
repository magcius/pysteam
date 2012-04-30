import struct
from steamwhore.util import ImpSocket

ipport = ('203.233.34.179', 27030)
messageid = 0
app = 1
version = 8
fileid = 0

s = ImpSocket()
s.connect(ipport)

# first we chose App mode on the server
s.send("\x00\x00\x00\x07")

# the server should return 0x01
s.recv(1)

# get banner message
message = "\x00\x00\x00\x00\x05"
s.send_withlen(s, message)
reply = s.recv(16384)
print repr(reply)

# logging in, without authentication
command = 9
message = struct.pack(">BLLLL", command, 0, messageid, app, version)
s.send_withlen(s, message)
reply = s.recv(17)
(connectionid, messageid, failure_flag, storageid, fingerprint) = struct.unpack(">LLBLL", reply)

# getting manifest
command = 4
message = struct.pack(">BLL", command, 0, messageid)
s.send_withlen(s, message)
reply = s.recv(13)
(connectionid, messageid, failure_flag, data_length) = struct.unpack(">LLBL", reply)
manifest = s.recvall(s, data_length)
print len(manifest)

messageid += 1

# getting checksums
command = 6
message = struct.pack(">BLL", command, 0, messageid)
s.send_withlen(s, message)
reply = s.recv(13)
(connectionid, messageid, failure_flag, data_length) = struct.unpack(">LLBL", reply)
checksums = s.recvall(s, data_length)
print len(checksums)

messageid += 1

# getting a single chunk of a file
command = 7
filestart = 0
numchunks = 2
message = struct.pack(">BLLLLLB", command, 0, messageid, fileid, filestart, numchunks, 0x00)
s.send_withlen(s, message)
reply = s.recv(17)
(connectionid, messageid, failure_flag, returned_chunks, file_mode) = struct.unpack(">LLBLL", reply)

chunks = []
for i in range(returned_chunks) :
    reply = s.recv(12)
    (connectionid, messageid, chunk_length) = struct.unpack(">LLL", reply)
    chunk = s.recvall(s, chunk_length)
    chunks.append(chunk)
   
print len(chunks[0]), len(chunks[1])
print "You have now received two file chunks from Steam."

s.close()