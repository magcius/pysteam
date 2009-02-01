
import os

class MagicNode(object):
    def __init__(self, map = {}):
        self.map = map
    
    def __getattr__(self, name):
        return self.map[name]
    
    def __getitem__(self, name):
        return self.map[name]
    
    def __repr__(self):
        return self.map.__repr__()
    
    def is_folder(self):
        return False
    
    def is_file(self):
        return False
    
class DirectoryFile(object):
    
    def __init__(self, folder):
        self.folder = folder
        self.name = ""
    
    def attributes(self):
        return self.package._attributes(self)
    
    def size(self):
        return self.package._size(self)
    
    def open(self, mode="rb"):
        return self.package._open_file(self, mode)
    
    def extract(self, where, keep_folder_structure=True):
        return self.package._extract_file(self, where, keep_folder_structure)
    
    def is_file(self):
        # Yep. We are a file. Peek at the class name if you need to.
        return True
    
    def is_folder(self):
        return False
    
    def find_item(self, name):
        return self
    
    def path(self):
        # Recursively find our path from the bottom up.
        return self.package._join_path(self.folder.path(), self.name)
    
    def sys_path(self):
        return os.path.join(self.folder.sys_path(), self.name)

class DirectoryFolder(object):
    
    def __repr__(self):
        return self.items.__repr__()
    
    def __init__(self, owner):
        self.owner = owner
        self.items = {}
        self.name = ""
    
    def __getattr__(self, name):
        # folder1.folder2.file.txt
        # folder1.folder2.file(dot_replacement)txt
        try:
            return self.items[name]
        except KeyError:
            raise AttributeError, "'DirectoryFolder' object has no attribute (could be file/folder) '%s'" % name
        
    def __getitem__(self, name):
        try:
            # folder1["folder2"]["file.txt"]
            return self.items[name]
        except KeyError:
            # folder1["folder2\\file.txt"]
            return self.find_item(name)
        
    def __iter__(self):
        return self.items.itervalues()
    
    def __len__(self):
        return len(self.items)
    
    def attributes(self):
        return self.package._attributes(self)
    
    def size(self):
        return sum(i.size() for i in self.items)
    
    def extract(self, where, recursive=False, keep_folder_structure=True, filter=None):
        return self.package._extract_folder(self, where, recursive, keep_folder_structure, filter)
    
    def is_file(self):
        return False
    
    def is_folder(self):
        return True
    
    def path(self):
        # Recursively find our path from the bottom up.
        try:
            return self.package._join_path(self.owner.path(), self.name)
        except AttributeError:
            return self.name
        
    def sys_path(self):
        # Recursively find our path from the bottom up.
        try:
            return os.path.join(self.owner.sys_path(), self.name)
        except AttributeError:
            return self.name
    
    
    def find_item(self, name):
        
        if len(filter(lambda x: len(x) > 0, self.package._split_path(name))) < 1:
            return self
        
        # If we start with the path separator, remove it.
        if str(name).startswith(self.package._path_sep()):
            name = str(name)[len(self.package._path_sep()):]
        
        name = self.package._split_path(name)
        
        if name[0] not in self.items:
            raise KeyError, "DirectoryFolder '%s' does not have file/folder '%s'" % (self.path(), name[0])
        
        # Yay tail-recursion. Go CAR and CDR!
        return self.items[name[0]].find_item(self.package._join_path(*name[1:]))

    def all_files(self):
        # Simple recursive function to get all files in this folder and its subfolders.
        files = []
        for entry in self:
            
            if entry.is_file():
                files.append(entry)
                
            elif entry.is_folder():
                files += entry.all_files()
                
        return files
    
    def build_split_map(self):

        self.dot_replacement = self.package.dot_replacement
        
        for key, value in self.items.copy().iteritems():
            
            # Special case for "." as dot_replacement, as
            # "." has a special use in Python.
            if "." in key and self.dot_replacement == ".":
                
                # Split "readme.txt.backup.foo"
                name = key.split(".")
                
                # Set our first part.
                # Use setdefault in case there is another
                # file, e.g "readme.gz"
                # Put it into our items map.

                # If we already have a folder with the same name as a file part, then
                # make a MagicNode and make all items in that folder point to their
                # corresponding items in that folder.
                if name[0] in self.items and self.items[name[0]].is_folder():
                    folder = self.items[name[0]]
                    magic = self.items[name[0]] = MagicNode(folder.items)
                else:
                    self.items.setdefault(name[0], MagicNode())
                    magic = self.items[name[0]]
                
                # Loop through everything but the first and last, these are
                # the head and tail, respectively. 
                for piece in name[1:-1]:
                    
                    # Make more magic nodes.
                    magic.map.setdefault(piece, MagicNode())
                    magic = magic[piece]
                
                #if name[-1] in magic:
                #    raise ValueError, "Two files have the same name."
                
                # And make a final node with our file object.
                magic.map[name[-1]] = value
            
            elif "." in key: # and self.dot_replacement != "."
                self.items[key.replace(".", self.dot_replacement)] = value
            
            try:
                value.build_split_map()
            except AttributeError: pass

class FilesystemPackage(object):
    
    def __init__(self):
        self.dot_replacement = "."
    
    def parse(self, dirname):
        rootpath = os.path.realpath(dirname)
        gen = os.walk(dirname)
        gen.next()
        self.root = DirectoryFolder(self)
        self.root.package = self
        self.root.name = rootpath
        map = {rootpath: self.root}
        
        for path, dirs, files in gen:
            owner_key, name = os.path.split(path)
            owner = map[owner_key]
            
            entry = DirectoryFolder(owner)
            entry.package = self
            entry.name = name
            
            owner.items[owner_key + name] = entry
            map[name] = entry
            
            for filename in files:
                file = DirectoryFile(entry)
                file.name = filename
                file.package = self
                entry.items[filename] = file
        
        self.root.build_split_map()
    
    def _path_sep(self):
        return os.path.sep
    
    def _join_path(self, *args):
        return os.path.join(*args)
    
    def _split_path(self, name):
        return name.split(os.path.sep)
    
    def _size(self, file):
        return os.path.getsize(file.find_path())
    
    def _open_file(self, file, mode):
        return open(file.find_path(), mode)
    
    def _attributes(self, file):
        return os.stat(file.find_path()).st_mode
        
    def _extract_file(self, *a, **b):
        # Not used.
        pass
    
    def _extract_folder(self, *a, **b):
        # Not used.
        pass
