
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

    def parse(self, stream):
        mode, = struct.unpack("<H", stream.read(2))
        if mode == Blob.MAGIC:
            length = struct.unpack("<l", stream.read(4))[0] - 10
            self.padding, = struct.unpack("<L", stream.read(4))

            end = stream.tell() + length
            while stream.tell() < end:
                node = BlobNode()
                node.parse(stream)
                self.children[node.key] = node
                self.ordered_children.append(node)

            stream.seek(self.padding, os.SEEK_CUR)

        elif mode == Blob.COMPRESSED_MAGIC:
            # If we are compressed, decompress and reparse.
            compressed_len, decompressed_len = struct.unpack("<l4xl6x", stream.read(18))

            # Read n bytes.
            compressed_bytes = stream.read(compressed_len)
            decompressed_bytes = zlib.decompress(compressed_bytes)

            self.parse(StringIO(decompressed_bytes))

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

    def __getitem__(self, key):
        if isinstance(key, int):
            key = struct.pack("<L", key)
        return self.children[key]

class BlobNode(object):
    def __init__(self):
        self.key = None
        self.data = None
        self.child = None

    def parse(self, stream):
        # These are defined internally.
        key_size, data_size = struct.unpack("<HL", stream.read(6))
        self.key = stream.read(key_size)
        self.data = stream.read(data_size)
        if data_size < 2:
            return

        magic, = struct.unpack("<H", self.data[:2])
        if magic in (Blob.MAGIC, Blob.COMPRESSED_MAGIC):
            self.child = Blob()
            self.child.parse(StringIO(self.data))

    def serialize(self):
        if self.child is not None:
            data = self.child.serialize(False)
        else:
            data = self.data
        return struct.pack("<HL", len(self.key), len(data)) + self.key + data

    def __len__(self):
        if self.child is not None:
            return len(self.child)
        return len(self.data)

    def __getitem__(self, idx):
        if self.child is not None:
            return self.child[idx]
        raise IndexError(idx)

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
