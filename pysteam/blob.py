
import os
import pprint
import struct
import zlib

from cStringIO import StringIO

class Blob(object):
    MAGIC = 0x5001
    COMPRESSED_MAGIC = 0x4301

    def __init__(self):
        self.children = {}
        self.ordered_children = []
        self.padding = 0

    def parse(self, stream, recurse=True):
        mode, = struct.unpack("<H", stream.read(2))
        if mode == Blob.MAGIC:
            length = struct.unpack("<l", stream.read(4))[0] - 10
            self.padding, = struct.unpack("<L", stream.read(4))

            while length >= 6:
                node = BlobNode()
                node.parse(stream, recurse)
                self.children[node.key] = node
                self.ordered_children.append(node)
                length -= 6 + node.desc_size + node.data_size

            stream.seek(self.padding, os.SEEK_CUR)

        elif mode == Blob.COMPRESSED_MAGIC:
            # If we are compressed, decompress and reparse.
            compressed_len, decompressed_len = struct.unpack("<l4xl6x", stream.read(18))

            # Read n bytes.
            compressed_bytes = stream.read(compressed_len)
            decompressed_bytes = zlib.decompress(compressed_bytes)

            self.parse(StringIO(decompressed_bytes), recurse)

    def serialize(self, compress=True):
        mode = Blob.COMPRESSED_MAGIC if compress else Blob.MAGIC
        data = StringIO()

        for node in self.ordered_children:
            data.write(node.serialize())

        if compress:
            data = zlib.compress(data.getvalue())
        else:
            data = data.getvalue()

        return struct.pack("<H", mode) + data + ("\0" * self.padding)

    def __len__(self):
        return len(self.children)

    def __iter__(self):
        return iter(self.ordered_children)

    def __getitem__(self, value):
        return self.children[value]

class BlobNode(object):
    def __init__(self):
        self.child = None
        self.key = None
        self.data = None
        self.data_size = 0
        self.desc_size = 0

    def parse(self, stream, recurse=True):
        # These are defined internally.
        self.desc_size, self.data_size = struct.unpack("<HL", stream.read(6))

        self.key = stream.read(self.desc_size)

        # Get temp bytes (it appears that Valve is now trying
        # to break parsers by putting null bytes after the blob node's
        # data section) This method will use more memory and is slower
        # but allows the parser to run with more sanity.
        tempbytes = stream.read(self.data_size)

        if recurse and len(tempbytes) >= 10:
            tempshort, = struct.unpack("<H", tempbytes[:2])
            if tempshort == Blob.MAGIC or (tempshort == Blob.COMPRESSED_MAGIC and len(tempbytes) >= 20):
                self.child = Blob()
                self.child.parse(StringIO(tempbytes))
                return

        self.data = tempbytes

    def serialize(self):
        if self.child is not None:
            data = self.child.serialize(False)
        else:
            data = self.data
        return struct.pack("<HL", self.desc_size, self.data_size) + self.key + data

    def __len__(self):
        if self.child is not None:
            return len(self.child)
        return len(self.data)

    def __getitem__(self, value):
        if self.child is not None:
            return self.child.__getitem__(value)
        raise IndexError(value)

    def __getattr__(self, value):
        if self.child is not None:
            return getattr(self.child, value)
        raise AttributeError(value)

    def __iter__(self):
        if self.child is not None:
            return iter(self.child)
        return iter(self.data)

    def __str__(self):
        s = ["<"]
        if self.child:
            s += ["\n  " + s for s in pprint.pformat(self.child.children)]
        elif self.data:
            s.append("Unknown Data")
        s.append(">")
        return "".join(s)
