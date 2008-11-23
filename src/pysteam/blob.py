
import zlib, struct, os

try:
    from cStringIO import StringIO
except ImportError:
    from StringIO import StringIO


class Blob(object):

    MAGIC = 0x5001
    COMPRESSED_MAGIC = 0x4301
    
    def __init__(self):
        self.children = {}
        self.padding = 0
    
    def read(self, stream, recurse=True):
        
        # Convert the stream if we need to.
        if isinstance(stream, Blob):
            self.children = stream.children
            self.padding = stream.padding
            del stream
            return
        
        # Read our magic please.
        mode, = struct.unpack("<H", stream.read(2))
        if mode == Blob.MAGIC:
            # logging.debug("Uncompressed Blob")
            length = struct.unpack("<l", stream.read(4))[0] - 10
            self.padding, = struct.unpack("<L", stream.read(4))
            
            # Not really sure how I could do this loop python-esque
            count = 0
            while length >= 6:
                node = BlobNode()
                node.read(stream, recurse)
                self.children[node.key] = node
                self.children[count] = node
                length -= 6 + len(node.key) + node.data_size
                count += 1

            stream.seek(self.padding, os.SEEK_CUR)
            
        elif mode == Blob.COMPRESSED_MAGIC:
            # logging.debug("Compressed Blob")
            # If we are compressed, decompress and reparse.
            compressed, = struct.unpack("<l4xl6x", stream.read(18))[0]
            
            # Read n bytes.
            compressedBytes = stream.read(compressed)
            decompressedBytes = zlib.decompress(compressedBytes)
        
            self.read(StringIO(decompressedBytes), recurse)

    def serialize(self, compress=True):
        mode = Blob.COMPRESSED_MAGIC if compress else Blob.MAGIC
        data = StringIO()
        
        if compress:
            zlib.compress(data.buf)
        return struct.pack("<H", mode)
    
    def __len__(self):
        return len(self.children)
    
    def __str__(self):
        return str(self.children)
    
    def __iter__(self):
        return self.children.itervalues()
    
    def __getitem__(self, value):
        try:
            return self.children[struct.pack("<l", value)]
        except Exception:
            return self.children[value]
    
    def __getattr__(self, value):
        return self.__getitem__(value)
    
class BlobNode(object):
    
    def __init__(self):
        self.child = None
        self.key = None
        self.data = None
        self.data_size = 0
    
    def read(self, stream, recurse=True):
        
        # These are defined internally.
        desc_size, data_size = struct.unpack("<HL", stream.read(6))
        
        # If it's negative then it's a huge unsigned value..
        # Stop here, as it could crash Python.
        if desc_size < 0 or data_size < 0:
            raise ValueError, "Numeric value too large!"
        
        self.key = stream.read(desc_size)
        
        # Get temp bytes (it appears that Valve is now trying
        # to break parsers by putting null bytes after the blob node's
        # data section) This method will use more memory and is slower
        # but allows the parser to run with more sanity.
        tempbytes = stream.read(data_size)
        
        if recurse and len(tempbytes) >= 10:
            tempshort, = struct.unpack("<H", tempbytes[:2])
            if tempshort == Blob.MAGIC or (tempshort == Blob.COMPRESSED_MAGIC and len(tempbytes) >= 20):
                self.child = Blob()
                self.child.read(StringIO(tempbytes))
                return
        self.data = tempbytes

    def serialize(self):
        desc_size = len(self.key)
        if self.child is not None:
            data = self.child.serialize(False)
            data_size = len(data)
        else:
            data = self.data
            data_size = len(data)
        return struct.pack("<HL", desc_size, data_size) + self.key + data
        
    def __len__(self):
        if self.child is not None:
            return self.child.__len__()
        return len(self.data)
    
    def __getitem__(self, value):
        if self.child is not None:
            return self.child.__getitem__(value)
        raise IndexError, value
    
    def __getattr__(self, value):
        if self.child is not None:
            return self.child.__getattr__(value)
        raise AttributeError, value
    
    def __iter__(self):
        if self.child is not None:
            return iter(self.child)
        return iter(self.data)
    
    def __repr__(self):
        s = ["<", self.key]
        if self.child:
            s.append(str(self.child))
        if self.data:
            s.append("Unknown Data")
        return "".join(s) + ">"
