
from pysteam.blob import Blob
import struct

class Registry(object):

    def __init__(self):
        self.root = None

    def read(self, blob):
        self.root = RegistryKey(self, None)
        try:
            self.root.read(blob["TopKey"])
        except KeyError:
            self.root.read(blob[0])

    def __getattr__(self, name):
        return self.root.__getattr__(name)
    def __getitem__(self, i):
        return self.root.__getitem__(i)
    def __len__(self):
        return self.root.__len__()
    def __repr__(self):
        return self.root.__repr__()
    def __iter__(self):
        return self.root.__iter__()

class RegistryKey(object):

    def __init__(self, registry, owner):
        self.owner = owner
        self.registry = registry
        self.items = {}

    def read(self, blob):
        self.name = blob.key
        for node in blob[1]: # Subkeys
            subkey = RegistryKey(self.registry, self)
            subkey.read(node)
            self.items[subkey.name] = subkey

        for node in blob[2]: # Values
            value = RegistryValue(self)
            value.read(node)
            self.items[value.name] = value

    def __getattr__(self, name):
        return self.items[name]
    def __getitem__(self, i):
        return self.items[i]

    def __len__(self):
        return len(self.items)
    def __repr__(self):
        return repr(self.items)
    def __iter__(self):
        return self.items.itervalues()

class RegistryValue(object):

    TYPE_STRING = 0
    TYPE_DWORD = 1
    TYPE_BINARY = 2

    def __init__(self, owner):
        self.owner = owner
        self.base_type = 0

    def read(self, blob):
        def clean_str(s):
            if "\0" in s:
                return s[:s.find("\0")]
            return s

        self.name = clean_str(blob.key)

        self.type, = struct.unpack("<l", blob[1].data)
        if self.type == RegistryValue.TYPE_STRING:
            self.data = clean_str(blob[2].data)
        elif self.type == RegistryValue.TYPE_DWORD:
            self.data = struct.unpack("<L", blob[2].data[:4])
        else: # elif self.type == RegistryValue.TYPE_BINARY:
            if blob[2].child is not None:
                self.data = blob[2].child
            else:
                self.data = blob[2].data

    def __str__(self):
        return self.__repr__()
    def __repr__(self):
        if self.type == RegistryValue.TYPE_STRING:
            return str("'" + self.data + "'")
        elif self.type == RegistryValue.TYPE_DWORD:
            return str(self.data)
        elif self.type == RegistryValue.TYPE_BINARY:
            if type(self.data) is str:
                return str("".join(["\\x%s" % hex(ord(c))[2:] for c in self.data])) + "'"
            else:
                return repr(self.data)

if __name__ == "__main__":
    handle = open("ClientRegistry.blob", "rb")
    blob = Blob()
    blob.read(handle)
    registry = Registry()
    registry.read(blob)
