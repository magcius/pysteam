
import os

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

    def __getitem__(self, name):
        return self.items[name]

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

    def all_files(self):
        # Simple recursive function to get all files in this folder and its subfolders.
        files = []
        for entry in self:

            if entry.is_file():
                files.append(entry)

            elif entry.is_folder():
                files += entry.all_files()

        return files

class FilesystemPackage(object):

    def parse(self, dirname):
        rootpath = os.path.abspath(dirname)
        gen = os.walk(rootpath)
        self.root = DirectoryFolder(self)
        self.root.package = self
        self.root.name = rootpath
        map = {rootpath: self.root}

        for path, dirs, files in gen:
            owner_key, name = os.path.split(path)
            if owner_key in map:
                owner = map[owner_key]
            else:
                owner = self.root

            entry = DirectoryFolder(owner)
            entry.package = self
            entry.name = name

            owner.items[name] = entry
            map[path] = entry

            for filename in files:
                file = DirectoryFile(entry)
                file.name = filename
                file.package = self
                entry.items[filename] = file

    def _join_path(self, *args):
        return os.path.join(*args)

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
