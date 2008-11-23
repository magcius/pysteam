
import struct, sys

from pysteam.fs import DirectoryFolder, DirectoryFile, FilesystemPackage
from math import ceil
from zlib import adler32

try:
    from cStringIO import StringIO
except ImportError:
    from StringIO import StringIO

STEAM_TERMINATOR = "\\" # Hasta la vista, baby.

def unpack_dword_list(stream, count):
    return list(struct.unpack("<%dL" % count, stream.read(count*4)))

def pack_dword_list(stream, list):
    return struct.pack("<%dL" % len(list), *list)

def raise_parse_error(func):
    def internal(self, *args, **kwargs):
        if not self.is_parsed:
            raise ValueError, "Cache file needs to be read first."
        
        return func(self, *args, **kwargs)
    return internal

def raise_ncf_error(func):
    def internal(self, *args, **kwargs):
        if self.is_ncf():
            raise ValueError, "NCF files do not have contents."
        
        return func(self, *args, **kwargs)
    return internal

class CacheFile(object):

    # Constructor
    def __init__(self):
        self.is_parsed = False
        self.blocks = None
        self.alloc_table = None
        self.manifest = None
        self.checksum_map = None
        self.data_header = None
        self.complete_total = 0
        self.complete_available = 0
        self.sector_data = []
        self.dot_replacement = "."
        self.ncf_folder_pattern = "common/{NAME}"
    
    def __del__(self):
        del self.is_parsed
        del self.blocksFilesystemPackage
        del self.alloc_table
        del self.manifest
        del self.checksum_map
        del self.data_header
        del self.sector_data
    
    # Main methods.
    
    def read(self, stream):

        import os
        try:
            self.filename = os.path.split(os.path.realpath(stream.name))[1]
        except AttributeError:
            pass
        
        # Header
        self.header = CacheFileHeader(self)
        self.header.read(stream.read(44))
        self.header.validate()
        
        if self.is_gcf():
            
            # Block Entries
            self.blocks = CacheFileBlockAllocationTable(self)
            self.blocks.read(stream)
            self.blocks.validate()
            
            # Allocation Table
            self.alloc_table = CacheFileAllocationTable(self)
            self.alloc_table.read(stream)
            self.alloc_table.validate()
        
        # Manifest
        self.manifest = CacheFileManifest(self)
        self.manifest.read(stream)
        self.manifest.validate()
        
        # Checksum Map
        self.checksum_map = CacheFileChecksumMap(self)
        self.checksum_map.read(stream)
        self.checksum_map.validate()
        
        if self.is_gcf():
            # Data Header.
            self.data_header = CacheFileSectorHeader(self)
            self.data_header.read(stream.read(24)) # size of BlockDataHeader (6 longs)
            self.data_header.validate()
            
            # Read Sector Data.
            stream.seek(self.data_header.first_sector_offset, os.SEEK_SET)
            for i in xrange(self.data_header.sector_count):
                self.sector_data.append(CacheFileSector(self, stream.read(self.data_header.sector_size), i))
        
        self.is_parsed = True
        self.__read_directory()
    
    def write(self, stream):
        
        self.header.validate()
        self.header.write(stream)
        
        if self.is_gcf():
            
            self.blocks.validate()
            self.blocks.write(stream)
            
            self.alloc_table.validate()
            self.alloc_table.write(stream)
        
        self.directory.validate()
        self.directory.write(stream)
        
        self.checksum_map.validate()
        self.checksum_map.write(stream)
        
        if self.is_gcf():
            
            self.data_header.validate()
            self.data_header.write(stream)
            
            import os
            stream.seek(self.data_header.first_sector_offset, os.SEEK_SET)
            for data in self.sector_data:
                stream.write(data)
    
    
    # Private Methods
    
    def __read_directory(self):

        if self.is_ncf():
            # Make NCF files "readable" by a configurable folder much like Steam's "common" folder
            import os
            path = self.ncf_folder_pattern.replace("/", os.sep)
            if ("{NAME}" in path or "{FILE}" in path) and not hasattr(self, "filename"):
                raise ValueError, "NCF folder path has {NAME} or {FILE} but filename couldn't be figured out. Please set manually."
            
            path = path.replace("{NAME}", ".".join(self.filename.split(".")[:-1]))
            path = path.replace("{FILE}", self.filename)
            
            package = FilesystemPackage()
            package.dot_replacement = self.dot_replacement
            package.read(path)
        
        elif self.is_gcf():
            package = self
        
        dir_entry = self.directory.directory_entries[0]
        
        # Fill in root.
        self.root = DirectoryFolder(self)
        self.root.index = 0
        self.root.package = package
        self.root.name = ""
        self.root._dir_entry = dir_entry
        self.__read_directory_table(self.root)
        self.root.build_split_map()
    
    def __read_directory_table(self, folder):
        
        i = folder._dir_entry.first_index
        
        while i != sys.maxint and i != 0:
            manifest_entry = self.manifest.manifest_entries[i]
            is_file = manifest_entry.directory_flags & CacheFileManifestEntry.FLAG_IS_FILE != 0
            
            # Create our entry.
            if is_file:
                entry = DirectoryFile(folder)
            else:
                entry = DirectoryFolder(folder)
            
            entry.package = self
            # Gives all the properties of the manifest entry to the DirectoryFile.
            for item in manifest_entry.__dict__:
                if item not in entry.__dict__:
                    entry.__dict__[item] = manifest_entry.__dict__[item]
            
            folder.items[entry.name] = entry
            
            if is_file:
                # Make sure it's a GCF before we read.
                if self.is_gcf():
                    self.__read_file_table(entry)
                
            else:
                self.__read_directory_table(entry)
            
            i = manifest_entry.next_index

    @raise_ncf_error
    def __read_file_table(self, entry):
        
        # Flags
        # entry.flags = self.blocks[entry.index].entry_flags
        # Entries of sectors
        entry.sectors = []
        # Number of blocks in this entry.
        entry.num_of_blocks = ceil(float(entry.size()) / float(self.data_header.block_size))
        
        # Hasta la vista, baby.
        terminator = 0xFFFFFFFF if self.alloc_table.is_long_terminator == 1 else 0xFFFF
        
        for block in entry.blocks:
            
            # Sectors
            sector_index = block.first_sector_index
            while sector_index != terminator:
                
                if self.alloc_table.entries[sector_index] != terminator and \
                  self.alloc_table.entries[sector_index] - sector_index != -1:
                    entry.is_fragmented = True
                
                entry.sectors.append(sector_index)
                sector_index = self.alloc_table[sector_index]
            
            self.complete_available += block.file_data_size
        
        
        entry.is_user_config = entry.index in self.manifest.user_config_entries
        entry.is_minimum_footprint = entry.index in self.manifest.minimum_footprint_entries
    
    @raise_ncf_error
    def __merge_file_blocks(self, entry):
        
        terminator = 0xFFFFFFFF if self.alloc_table.is_long_terminator == 1 else 0xFFFF
        deleted_blocks = []
        
        # If we are in one block, return plz.
        if not entry.first_block.next_block is not None:
            return
        
        # Go through the blocks of each file.
        for block in entry.blocks:
            
            # Get our first sector.
            sector_index = block.first_sector_index
            
            # From that, find the last sector in the block.
            while self.alloc_table[sector_index] != terminator:
                sector_index = self.alloc_table[sector_index]
            
            # Set the link from the last sector in the previous block to the first sector in this block.
            self.alloc_table[sector_index] = block.first_sector_index
            
            # Set the block to be deleted later.
            deleted_blocks.append(block)
        
        # Delete the block.
        for block in deleted_blocks:
            del block
        
    # Internal methods.
    
    def _path_sep(self):
        return STEAM_TERMINATOR
    
    def _join_path(self, *args):
        return STEAM_TERMINATOR.join(args)
    
    def _split_path(self, name):
        return name.split(STEAM_TERMINATOR)
    
    @raise_parse_error
    @raise_ncf_error
    def _size(self, file):
        return self.manifest.manifest_entries[file.index].item_size
    
    @raise_parse_error
    @raise_ncf_error
    def _open_file(self, file, mode):
        return GCFFileStream(file, self, mode)
    
    @raise_parse_error
    @raise_ncf_error
    def _extract_folder(self, folder, where, recursive, keep_folder_structure, item_filter=None):
        
        if keep_folder_structure:
            try:
                import os
                os.makedirs(os.path.join(where, folder.sys_path()))
            except Exception:
                pass
        
        # Loop over the folder and extract files and folders (if recursive)
        for entry in folder:
            # Don't bother recursing (and creating the folder) if no files are left after the filter.
            if entry.is_folder() and recursive and (item_filter is None or (len([x for x in entry.all_files() if item_filter(x)]) > 0)):
                self._extract_folder(entry, where, True, keep_folder_structure, item_filter)
            elif entry.is_file() and (item_filter is None or item_filter(entry)):
                self._extract_file(entry, where, keep_folder_structure)
        
    @raise_parse_error
    @raise_ncf_error
    def _extract_file(self, file, where, keep_folder_structure):
        import os
        if keep_folder_structure:
            fsHandle = open(os.path.join(where, file.sys_path()), "wb")
        else:
            fsHandle = open(os.path.join(where, file.name), "wb")
        cacheStream = self._open_file(file, "rb")
        fsHandle.write(cacheStream.readall())
        
        cacheStream.close()
        fsHandle.close()
    
    # Public Methods
    
    def is_ncf(self):
        return self.header.is_ncf()
    
    def is_gcf(self):
        return self.header.is_gcf()
    
    @raise_parse_error
    @raise_ncf_error
    def complete_percent(self, range=100):
        return float(self.complete_available) / float(self.complete_total) * float(range)
    
    @raise_parse_error
    @raise_ncf_error
    def extract(self, where, recursive=True, keep_folder_structure=True, filter=None):
        self._extract_folder(self.root, where, recursive, keep_folder_structure, filter)
    
    @raise_parse_error
    @raise_ncf_error
    def extract_minimum_footprint(self, where, keep_folder_structure=True):
        import os
        self._extract_folder(self.root, where, True, keep_folder_structure, lambda x:x.is_minimum_footprint and not (os.path.exists(os.path.join(where, x.find_path())) and x.is_user_config))
    
    def open(self, filename, mode):
        # Use file.open instead of _open_file as we may be parsing an NCF
        return self.root.find_item(filename).open(mode)
    
    # Magic/Special Methods
    
    @raise_parse_error
    def __len__(self):
        return len(self.root)
    
    @raise_parse_error
    def __iter__(self):
        # for i in gcf:
        return self.root.__iter__()
    
    @raise_parse_error
    def __getattr__(self, name):
        # gcf.folder1.folder2.file.txt
        return self.root.__getattr__(name)
    
    @raise_parse_error
    def __getitem__(self, name):
        # gcf["folder1"]["folder2"]["file.txt"]
        return self.root.__getitem__(name)
    
class CacheFileHeader(object):
    
    def __init__(self, owner):
        self.owner = owner
    def read(self, data):
        (self.header_version,
         self.cache_type,
         self.format_version,
         self.application_id,
         self.application_version,
         self.is_mounted,
         self.dummy1,
         self.file_size,
         self.sector_size,
         self.sector_count,
         self.checksum) = struct.unpack("<11L", data)
    
    def write(self, stream):
        stream.write(self.serialize())
    
    def serialize(self):
        data = struct.pack("<11L", self.header_version, self.cache_type, self.format_version, self.application_id, self.application_version, self.is_mounted, self.dummy1, self.file_size, self.sector_size, self.sector_count)
        self.checksum = sum(ord(x) for x in data)
        return data + struct.pack("<L", self.checksum)
    
    def calculate_checksum(self):
        # Calculate Checksum..
        return sum(ord(x) for x in self.serialize()[:-4])
    
    def validate(self):
        # Check the usual stuff.
        if self.header_version != 1:
            raise ValueError, "Invalid Cache File Header [HeaderVersion is not 1]"
        if not (self.is_ncf() or self.is_gcf()):
            raise ValueError, "Invalid Cache File Header [Not GCF or NCF]"
        if self.is_ncf() and self.format_version != 1:
            raise ValueError, "Invalid Cache File Header [Is NCF and version is not 1]"
        elif self.is_gcf() and self.format_version != 6:
            raise ValueError, "Invalid Cache File Header [Is GCF and version is not 6]"
        # UPDATE: This fails on some files, namely the half-life files.
        #if self.is_mounted != 0:
        #   raise ValueError, "Invalid Cache File Header [Updating is not 0... WTF?]"
        if self.is_ncf() and self.file_size != 0:
            raise ValueError, "Invalid Cache File Header [Is NCF and FileSize is not 0]"
        if self.is_ncf() and self.sector_size != 0:
            raise ValueError, "Invalid Cache File Header [Is NCF and BlockSize is not 0]"
        if self.is_ncf() and self.sector_count != 0:
            raise ValueError, "Invalid Cache File Header [Is NCF and BlockCount is not 0]"
        
        if self.checksum != self.calculate_checksum():
            raise ValueError, "Invalid Cache File Header [Checksums do not match]"
    
    def is_ncf(self):
        return self.cache_type == 2
    def is_gcf(self):
        return self.cache_type == 1
    def blocks_length(self):
        return self.block_size * self.block_count + 32 # Block Size * Block Count + Block Header

class CacheFileBlockAllocationTable(object):
    
    def __init__(self, owner):
        self.owner = owner
        self.blocks = []
    
    def read(self, stream):
        
        # Blocks Header
        (self.block_count,
         self.blocks_used,
         self.last_block_used,
         self.dummy1,
         self.dummy2,
         self.dummy3,
         self.dummy4) = struct.unpack("<7L", stream.read(28))
        self.checksum = sum(ord(x) for x in stream.read(4))
        
        # Block Entries
        for i in xrange(self.block_count):
            block = CacheFileBlockAllocationTableEntry(self)
            block.index = i
            block.read(stream)
            self.blocks.append(block)
    
    def write(self, stream):
        stream.write(self.serialize())
    
    def serialize(self):
        data = struct.pack("<7L", self.block_count, self.blocks_used, self.last_block_used, self.dummy1, self.dummy2, self.dummy3, self.dummy4)
        self.checksum = sum(ord(x) for x in data)
        
        return data + struct.pack("<L", self.checksum) + "".join([x.serialize for x in self.blocks])
    
    def calculate_checksum(self):
        return sum(ord(x) for x in self.serialize()[:-4])
    
    def validate(self):
        if self.owner.header.sector_count != self.block_count:
            raise ValueError, "Invalid Cache Block [Sector/BlockCounts do not match]"
        if self.checksum != self.calculate_checksum():
            raise ValueError, "Invalid Cache Block [Checksums do not match]"

class CacheFileBlockAllocationTableEntry(object):
    
    FLAG_DATA    = 0x200F8000
    FLAG_DATA_2  = 0x200FC000
    FLAG_NO_DATA = 0x200F0000
    
    next_block = property(__get_next_block, __set_next_block)
    prev_block = property(__get_prev_block, __set_prev_block)
    first_sector = property(__get_first_sector, __set_first_sector)
    
    def __init__(self, owner):
        self.owner = owner
    
    def read(self, stream):
        # Block Entry
        (self.flags,
         self.dummy1,
         self.file_data_offset,
         self.file_data_size,
         self._first_sector_index,
         self._next_block_index,
         self._prev_block_index,
         self.manifest_index) = struct.unpack("<2H6L", stream.read(28))
    
    def __del__(self):
        self.flags = 0
        self.dummy1 = 0
        self.file_data_offset = 0
        self.file_data_size = 0
        self._first_sector_index = 0
        self._next_block_index = 0
        self._prev_block_index = 0
        self.manifest_index = 0
    
    def __iter__(self):
        return CacheFileSectorIterator(self.first_sector)
    
    def __get_next_block(self):
        try:
            return self.owner.blocks[self._next_block_index]
        except IndexError:
            return None
    
    def __set_next_block(self, value):
        if value is None:
            self._next_block_index = 0
        else:
            self._next_block_index = value.index
            value._prev_block_index = self.index
    
    def __get_prev_block(self):
        try:
            return self.owner.blocks[self.prev_block_index]
        except IndexError:
            return None
    
    def __set_prev_block(self, value):
        if value is None:
            self._prev_block_index = 0
        else:
            self._prev_block_index = value.index
            value._next_block_index = self.index
    
    def __get_first_sector(self):
        return self.owner.owner.sector_data[self._first_sector_index]
    
    def __set_first_sector(self, value):
        self._first_sector_index = value.index
    
    def write(self, stream):
        stream.write(self.serialize())
    
    def serialize(self):
        return struct.pack("<2H6L", self.flags, self.dummy1, self.file_data_offset, self.file_data_size, self._first_sector_index, self._next_block_index, self._previous_block_index, self.manifest_index)
        
class CacheFileAllocationTable(object):
    
    def __init__(self, owner):
        self.owner = owner
        self.entries = []
    
    def __getitem__(self, i):
        return self.entries[i]
    
    def __setitem__(self, i, v):
        self.entries[i] = v
    
    def __len__(self):
        return len(self.entries)
    
    def __iter__(self):
        return self.entries
    
    def read(self, stream):
        
        # Block Header
        (self.sector_count,
         self.first_unused_entry,
         self.is_long_terminator) = struct.unpack("<3L", stream.read(12))
        self.checksum = sum(ord(x) for x in stream.read(4))
        
        self.entries = unpack_dword_list(self.sector_count, stream)
    
    def write(self, stream):
        stream.write(self.serialize())
    
    def serialize(self):
        data = struct.pack("<3L", self.block_count, self.first_unused_entry, self.terminator)
        self.checksum = sum(ord(x) for x in data)
        return data + struct.pack("<L", self.checksum) + pack_dword_list(self.entries)
    
    def calculate_checksum(self):
        # Fun with arrays.
        return sum(ord(x) for x in self.serialize()[:-4])
    
    def validate(self):
        if self.owner.header.sector_count != self.sector_count:
            raise ValueError, "Invalid Cache Allocation Table [SectorCounts do not match]"
        if self.checksum != self.calculate_checksum():
            raise ValueError, "Invalid Cache Allocation Table [Checksums do not match]"

class CacheFileManifest(object):
    
    FLAG_BUILD_MODE   = 0x00000001
    FLAG_IS_PURGE_ALL = 0x00000002
    FLAG_IS_LONG_ROLL = 0x00000004
    FLAG_DEPOT_KEY    = 0xFFFFFF00
    
    def __init__(self, owner):
        self.owner = owner
        self.manifest_entries = []
        self.hash_table_keys = []
        self.hash_table_indices = []
        
        # Contains ManifestIndex
        self.user_config_entries = []
        
        # Contains ManifestIndex
        self.minimum_footprint_entries = []
        
        # Contains FirstBlockIndex
        self.manifest_map_entries = []
    
    def read(self, stream):
        # Header
        self.header_data = stream.read(56)
        (self.header_version,
         self.application_id,
         self.application_version,
         self.node_count,
         self.file_count,
         self.compression_block_size,
         self.binary_size,
         self.name_size,
         self.hash_table_key_count,
         self.num_of_user_config_files,
         self.num_of_minimum_footprint_files,
         self.depot_info,
         self.fingerprint,
         self.checksum) = struct.unpack("<14L", self.header_data)
        
        # 56 = size of header
        self.manifest_stream = StringIO(stream.read(self.binary_size-56))
        
        # Manifest Entries
        for i in xrange(self.node_count):
            entry = CacheFileManifestEntry(self)
            entry.index = i
            # 28 = size of ManifestEntry
            data = self.manifest_stream.read(28)
            entry.read(data)
            self.manifest_entries.append(entry)
            if (entry.directory_flags & CacheFileManifestEntry.FLAG_IS_FILE) != 0:
                self.owner.complete_total += entry.item_size
        
        # Name Table
        self.filename_table = self.manifest_stream.read(self.name_size)
        
        # Info1 / HashTableKeys
        self.hash_table_keys = unpack_dword_list(self.manifest_stream, self.hash_table_key_count)
        
        # Info2 / HashTableIndices
        self.hash_table_indices = unpack_dword_list(self.manifest_stream, self.node_count)
        
        # User Config Entries
        self.user_config_entries = unpack_dword_list(self.manifest_stream, self.num_of_user_config_files)
        
        # Minimum Footprint Entries
        self.minimum_footprint_entries = unpack_dword_list(self.manifest_stream, self.num_of_minimum_footprint_files)
        
        # Manifest Map Header
        (self.map_header_version,
         self.map_dummy1) = struct.unpack("<2L", stream.read(8))
        
        # Manifest Map Entries (FirstBlockIndex)
        self.manifest_map_entries = [self.blocks[i] for i in unpack_dword_list(stream, self.item_count)]
    
    def write(self, stream):
        return stream.write(self.serialize())
    
    def serialize(self):
        # 56 = size of Header
        # 32 = size of ManifestEntry + size of DWORD for HashTableIndices
        self.name_size = len(self.filename_table)
        self.binary_size = 56 + 32*self.node_count + self.name_size + 4*(self.hash_table_key_count+self.num_of_user_config_entries+self.num_of_minimum_footprint_entries)
        self.header_data = struct.pack("<12L",
          self.header_version,
          self.application_id,
          self.application_version,
          self.node_count,
          self.file_count,
          self.compression_block_size,
          self.binary_size,
          self.name_size,
          self.depot_info)
        
        manifest_data = []
        for i in self.manifest_entries:
            manifest_data.append(i.serialize())
        
        manifest_data.append(self.filename_table)
        manifest_data.append(pack_dword_list(self.hash_table_keys))
        manifest_data.append(pack_dword_list(self.hash_table_indices))
        manifest_data.append(pack_dword_list(self.user_config_entries))
        manifest_data.append(pack_dword_list(self.hash_table_keys))
        manifest_data.append(struct.pack("<2L", self.map_header_version, self.map_dummy1))
        manifest_data.append(pack_dword_list(self.manifest_map_entries))
        manifest_data = "".join(manifest_data)
        
        self.checksum = adler32(self.header_data + "\0\0\0\0\0\0\0\0" + manifest_data, 0)
        return self.header_data + struct.pack("<2L", self.fingerprint, self.checksum) + manifest_data
    
    def validate(self):
        if self.owner.header.application_id != self.application_id:
            raise ValueError, "Invalid Cache File Manifest [Application ID mismatch]"
        if self.owner.header.application_version != self.application_version:
            raise ValueError, "Invalid Cache File Manifest [Application version mismatch]"
        if self.checksum != self.calculate_checksum():
            raise ValueError, "Invalid Cache File Manifest [Checksum mismatch]"
        if self.map_header_version != 1:
            raise ValueError, "Invalid Cache File Manifest [ManifestHeaderMap's HeaderVersion is not 1]"
        if self.map_dummy1 != 0:
            raise ValueError, "Invalid Cache File Manifest [ManifestHeaderMap's Dummy1 is not 0]"
    
    def calculate_checksum(self):
        # Blank out checksum and fingerprint + hack to get unsigned value.
        data = self.serialize()
        return adler32(data[:48] + "\0\0\0\0\0\0\0\0" + data[56:], 0) & 0xffffffffL
    
class CacheFileManifestEntry(object):
    
    FLAG_IS_FILE        = 0x00004000
    FLAG_IS_EXECUTABLE  = 0x00000800
    FLAG_IS_HIDDEN      = 0x00000400
    FLAG_IS_READ_ONLY   = 0x00000200
    FLAG_IS_ENCRYPTED   = 0x00000100
    FLAG_IS_PURGE_FILE  = 0x00000080
    FLAG_BACKUP_PLZ     = 0x00000040
    FLAG_IS_NO_CACHE    = 0x00000020
    FLAG_IS_LOCKED      = 0x00000008
    FLAG_IS_LAUNCH      = 0x00000002
    FLAG_IS_USER_CONFIG = 0x00000001
    
    blocks = property(__get_block_iterator)
    first_block = property(__get_first_block, __set_first_block)
    name = property(__get_name, __set_name)
    
    def __init__(self, owner):
        self.owner = owner
    
    def __get_name(self):
        return self.owner.filename_table[self.name_offset:].split("\0")[0]
    
    def __set_name(self, value):
        name_end = self.owner.filename_table[self.name_offset:].find("\0")
        self.owner.filename_table[self.name_offset:name_end] = value
    
    def __get_block_iterator(self):
        return CacheFileBlockIterator(self.__get_first_block)
    
    def __get_first_block(self):
        return self.owner.blocks[self.owner.manifest_map_entries[self.index]]
    
    def __set_first_block(self, value):
        self.owner.manifest_map_entries[self.index] = value
    
    def read(self, data):
        (self.name_offset,
         self.item_size,
         self.checksum_index,
         self.directory_flags,
         self.parent_index,
         self.next_index,
         self.child_index) = struct.unpack("<7L", data)
    
    def serialize(self):
        return struct.pack("<7L", self.name_offset, self.item_size, self.checksum_index, self.directory_flags, self.parent_index, self.next_index, self.first_index)

class CacheFileChecksumMap(object):
    
    FLAG_IS_SIGNED      = 0x00000001
    FLAG_UNKNOWN        = 0xFFFFFFFE
    
    def __init__(self, owner):
        self.owner = owner
        
        # Contains (ChecksumCount, FirstChecksumIndex)
        self.entries = []
        
        # Contains Checksum
        self.checksums = []
    
    def read(self, stream):
        
        (self.header_version,
         self.checksum_size,
         self.format_code,
         self.version,
         self.file_id_count,
         self.checksum_count) = struct.unpack("<6L", stream.read(24))
        
        for i in xrange(self.file_id_count):
            self.entries.append(struct.unpack("<2L", stream.read(8)))
        
        self.checksums = unpack_dword_list(stream, self.checksum_count)
        
        self.signature = stream.read(128)
    
    def write(self, stream):
        stream.write(self.serialize())
    
    def serialize(self):
        data = [struct.pack("<6L", self.header_version, self.checksum_size, self.format_code, self.version, self.file_id_count, self.checksum_count)]
        data += [struct.pack("<2L", *i) for i in self.entries]
        data.append(pack_dword_list(self.checksums))
        data.append(self.signature)
        return "".join(data)
    
    def validate(self):
        pass
        # NOTE: This check is incorrect on the test file (half-life 2 game dialog.gcf) I have.
        # if self.owner.directory.file_count != self.item_count:
        #     raise ValueError, "Invalid Cache File Checksum Map [ItemCount and FileCount don't match]"

class CacheFileSectorHeader(object):
    
    def __init__(self, owner):
        self.owner = owner
    
    def read(self, data):
        (self.application_version,
         self.sector_count,
         self.sector_size,
         self.first_sector_offset,
         self.sectors_used,
         self.checksum) = struct.unpack("<6L", data)
    
    def write(self, stream):
        stream.write(self.serialize())
    
    def serialize(self):
        self.checksum = self.calculate_checksum()
        return struct.pack("<6L", self.sector_count, self.sector_size, self.first_sector_offset, self.sectors_used)
    
    def validate(self):
        if self.application_version != self.owner.header.application_version:
            raise ValueError, "Invalid Cache File Sector Header [ApplicationVersion mismatch]"
        if self.sector_count != self.owner.header.sector_count:
            raise ValueError, "Invalid Cache File Sector Header [SectorCount mismatch]"
        if self.sector_size != self.owner.header.sector_size:
            raise ValueError, "Invalid Cache File Sector Header [SectorSize mismatch]"
        if self.checksum != self.calculate_checksum():
            raise ValueError, "Invalid Cache File Sector Header [Checksum mismatch]"
    
    def calculate_checksum(self):
        return self.sector_count + self.sector_size + self.first_block_offset + self.sectors_used

class CacheFileSector(object):
    
    next_sector = property(__get_next_sector, __set_next_sector)
    
    def __init__(self, owner, data, index):
        self.owner = owner
        self.index = index
        self.data = data
        self._next_index = self.owner.alloc_table[index]
    
    def __get_data(self):
        return self.data
    
    def __set_data(self, value):
        self.data = value
    
    def __get_next_sector(self):
        return self.owner.sector_data[self._next_index]
    
    def __set_next_sector(self, value):
        self._next_index = value.index

class CacheFileSectorIterator(object):
    
    def __init__(self, first_sector):
        self.current_sector = first_sector
    
    def __iter__(self):
        return self
    
    def next(self):
        yield self.current_sector
        if self.current_sector.next_sector is None:
            raise StopIteration
        self.current_sector = self.current_sector.next_sector


class CacheFileBlockIterator(object):
    
    def __init__(self, start_block):
        self.current_block = start_block
    
    def __iter__(self):
        return self
    
    def next(self):
        yield self.current_block
        if self.current_block.next_block is None:
            raise StopIteration
        self.current_block = self.current_block.next_block

class GCFFileStream(object):
    
    def __init__(self, entry, owner, mode):
        self.entry = entry
        self.owner = owner
        self.mode = mode
        self.sectors = list(self.entry.sectors)
        
        self.position = 0
    
    # Iterator protocol.
    def __iter__(self):
        return self
    
    def next(self):
        return self.readline()
    
    # File protocol.
    def flush(self):
        # Nothing right now...
        pass
    
    def close(self):
        # Nothing right now...
        pass
        
    def tell(self):
        return self.position
    
    def seek(self, offset, origin=None):
        
        import os
        
        def err():
            raise IOError, "Attempting to seek past end of file"
        
        if origin == os.SEEK_SET or origin is None:
            if offset > self.entry.file_size:
                err()
            self.position = offset
            
        elif origin == os.SEEK_CUR:
            if offset + self.position > self.entry.file_size:
                err()
            self.position += offset
            
        elif origin == os.SEEK_END:
            if offset > self.entry.file_size or offset < 0:
                err()
            self.position = self.entry.file_size - offset
    
    def readall(self):
        return self.read(self.entry._dir_entry.item_size - self.position)
    
    def readline(self, size=-1):
        
        # Our count for the size parameter.
        count = 0
        # Strings are immutable... use a list
        chars = []
        
        lastchar = ""
        
        # Loop over our data one character at a time
        # looking for line breaks
        while True:
            lastchar = self.read(1)
            # If we get a CR
            if lastchar == "\r":
                # Strip out a LF if it comes next
                if self.read(1) != "\n":
                    self.position -= 1
                break
            elif lastchar == "\n":
                break
            elif count > size and size > 0:
                # FIXME: What does the file module do when we have a size
                # hint? Does it include newline in the count? What about
                # CRLF? Does count as one or two chars?
                break
            
            # Characters
            chars.append(lastchar)
            
        return "".join(chars) 
    
    def readlines(self, sizehint=-1):
        
        # Our count for the size parameter.
        count = 0
        lines = []
        
        while True:
            data = self.readline()
            lines.append(data)
            count += len(data)
            # If we have surpassed the sizehint, break
            if count > sizehint and sizehint > 0:
                break
        
        return lines
    
    def read(self, size=0):
        
        if not self.is_read_mode():
            raise AttributeError, "Cannot read from file with current mode"
        
        sector_size = self.owner.data_header.sector_size
        sector_index = self.position / sector_size 
        
        # Raise an error if we read past end of file.
        if self.position + size > self.entry.item_size:
            raise IOError, "Attempting to read past end of file"
        
        # One file isn't always in just one block.
        # We have to read multiple blocks sometimes in order to get a file.
        read_pos = 0
        
        # Strings are immutable... use a list.
        data = []
        
        # This block is or is part of a file.
        # Get the virtual block offset.
        offset = self.position % sector_size
        
        if size < 1:
            
            # Get all the data by looping over the sectors.
            for sector in self.sectors[sector_index:]:
                data.append(sector[offset:])
                offset = 0
            
        else:
            
            while read_pos < size:
                
                # It can't be bigger than the sector size or
                # Take the minimum of the two and get the rest of the data on the next iteration.
                read_length = min(size - read_pos, sector_size - offset)
                data.append(self.sectors[sector_index][offset:read_length])
                
                sector_index += 1
                offset = 0
                
            self.position += size
            read_pos += size
        
        # TYPE CHANGE!
        # Data - from list to str.
        data = "".join(data)
        
        # Text mode; strip all \r's
        if self.is_text_mode():
            data = data.replace("\r", "")
        
        return data
    
    def write(self, data):
        
        pass
    
    def is_binary_mode(self):
        return "b" in self.mode
    
    def is_text_mode(self):
        return "b" not in self.mode
    
    def is_read_mode(self):
        return "r" in self.mode
    
    def is_write_mode(self):
        return "w" in self.mode or "r+" in self.mode
    
    def is_append_mode(self):
        return "a" in self.mode
