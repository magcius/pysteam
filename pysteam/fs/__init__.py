
import os

class DirectoryFile(object):
    def __init__(self, folder, name="", package=None):
        self.folder = folder
        self.name = name
        self.package = package

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
    def __init__(self, parent, name="", package=None):
        self.owner = parent
        self.name = name
        self.package = package
        self.items = {}

    def __getitem__(self, name):
        return self.items[name]

    def __iter__(self):
        return self.items.itervalues()

    def __len__(self):
        return len(self.items)

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
        fs_map = {rootpath: self.root}

        for path, dirs, files in gen:
            parent_path, name = os.path.split(path)
            parent = fs_map[parent_path]

            folder = DirectoryFolder(parent, name, self)

            parent.items[name] = folder
            fs_map[path] = folder

            for filename in files:
                folder.items[filename] = DirectoryFile(folder, filename, self)

    def _join_path(self, *args):
        return os.path.join(*args)

    def _size(self, entry):
        return os.path.getsize(entry.sys_path())

    def _open_file(self, entry, mode):
        return open(entry.sys_path(), mode)

    def _extract_file(self, *a, **b):
        # Not used.
        pass

    def _extract_folder(self, *a, **b):
        # Not used.
        pass
