
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

    def __getitem__(self, i):
        return self.root[i]

    def __len__(self):
        return len(self.root)

    def __repr__(self):
        return repr(self.root)

    def __iter__(self):
        return iter(self.root)

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
        self.data = None
        self.child = None

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
        elif self.type == RegistryValue.TYPE_BINARY:
            self.child = blob[2].child
            self.data = blob[2].data
        else:
            assert False, "should not be reached"

    def __str__(self):
        return repr(self)

    def __repr__(self):
        if self.type == RegistryValue.TYPE_STRING:
            return "%r" % (self.data,)
        elif self.type == RegistryValue.TYPE_DWORD:
            return "%s" % (self.data,)
        elif self.type == RegistryValue.TYPE_BINARY:
            if self.child is not None:
                return repr(self.child)
            else:
                return repr(self.data)

if __name__ == "__main__":
    handle = open("ClientRegistry.blob", "rb")
    blob = Blob()
    blob.read(handle)
    registry = Registry()
    registry.read(blob)
