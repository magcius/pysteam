
import datetime
import struct
from steamwhore.util import py_time, bytes_as_bool
from pysteam.blob import Blob

class ParseError(Exception):
    pass

class CDR(object):
    CURRENT_VER = 10

    def parse(self, stream):
        self.applications = []

        self.blob = Blob()
        self.blob.parse(stream)

        node = self.blob[0] # Version number.

        if not node.data:
            raise ParseError("Version number invalid. [No Data]")
        elif len(node.data) != 2:
            raise ParseError("Version number invalid. [Length Invalid, Got %d]" % len(node.data))

        self.version = struct.unpack("<h", node.data)[0]
        if self.version != CDR.CURRENT_VER:
            raise ParseError("Unhandled version number. Cannot continue using version number: %d" % self.version)

        node = self.blob[2] # App Records
        if node.child is None:
            logging.warning("Applications Record blob invalid. [No Blob Container]")
        else:
            for subnode in node.child:
                app = Application()
                app.cdr = self
                app.parse(subnode)
                self.applications.append(app)

        node = self.blob[3] # LastChanged...
        if node.data is None:
            raise ParseError("LastChangedExistingAppOrSubscriptionTime number invalid. [No Data]")
        elif len(node.data) != 8:
            raise ParseError("LastChangedExistingAppOrSubscriptionTime number invalid [Length Invalid, Got %d]" % len(node.data))

        self.last_changed = py_time(struct.unpack("<q", node.data)[0])

################################
### Application
################################

class Application(object):
    def __str__(self):
        return "%s (App ID %d): %s" % ("Cache File" if self.is_cache() else "Application", self.app_id, self.app_name)

    def is_cache(self):
        return len(self.fs_records) > 1

    def is_ncf(self):
        if self.is_cache():
            return (self.app_of_manifest_only_cache > 0) and self.cdr.applications[self.app_of_manifest_only_cache].manifest_only_app
        return False

    def get_mount_name(self):
        if self.is_cache():
            return self.app_name + (".ncf" if self.is_ncf() else ".gcf")
        return self.app_name

    def parse(self, node):        
        self.launch_records = []
        self.version_records = []
        self.fs_records = []
        self.user_defined_records = []

        if len(node.children) == 0:
            raise ValueError, "Blob has no children"

        self.app_id = node.smart_key
        self.app_name = node[2].data
        self.install_dir = node[3].data
        self.min_cache, = struct.unpack("<l", node[4].data)
        self.max_cache, = struct.unpack("<l", node[5].data)

        self.on_first_launch, = struct.unpack("<l", node[8].data)
        self.is_bandwidth_greedy, = bytes_as_bool(node[9].data)
        self.current_version_id, = struct.unpack("<l", node[11].data)
        self.trickle_version_id, = struct.unpack("<l", node[13].data)
        self.beta_version_password = node[15].data
        self.beta_version_id, = struct.unpack("<l", node[16].data)
        self.install_dir_legacy = node[17].data
        self.use_filesystem_dvr = bytes_as_bool(node[19].data)
        self.manifest_only_app = bytes_as_bool(node[20].data)
        self.app_of_manifest_only_cache = bytes_as_bool(node[21].data)

        for n in node[6]:
            tempblob = ApplicationLaunchOptionRecord()
            tempblob.owner = self
            tempblob.parse(n)
            self.launch_records.append(tempblob)

        for n in node[10]:
            tempblob = ApplicationVersionRecord()
            tempblob.owner = self
            tempblob.parse(n)
            self.version_records.append(tempblob)

        for n in node[12]:
            tempblob = ApplicationFilesystemRecord()
            tempblob.owner = self
            tempblob.parse(n)
            self.fs_records.append(tempblob)

        for n in node[14]:
            tempblob = ApplicationUserDefinedRecord()
            tempblob.owner = self
            tempblob.parse(n)
            self.user_defined_records.append(tempblob)

class ApplicationLaunchOptionRecord(object):
    def __str__(self):
        return "%s's Launch Option Record %d" % (unicode(self.owner), self.option_id)

    def parse(self, node):

        blob = node.child
        if len(blob.children) == 0:
            raise ValueError, "Blob has no children"
        self.option_id = struct.unpack("<l", node.key)[0]

        self.description = node[1].data
        self.command_line = node[2].data
        self.icon_index = node[3].data
        self.no_desktop_shortcut = bytes_as_bool(node[4].data)
        self.no_start_menu_shortcut = bytes_as_bool(node[5].data)
        self.long_running_unattended = bytes_as_bool(node[6].data)    

class ApplicationVersionRecord(object):
    def __str__(self):
        return "%s's Version Record %d" % (unicode(self.owner), self.version_id)

    def parse(self, node):
        self.version_id = struct.unpack("<l", node.key)[0]
        self.description = node[1].data
        #temp_version_id = struct.unpack("<l", tempnode.data)[0]
        #if temp_version_id != self.version_id:
        #   raise ParseError("Version ID mismatch: %d and %d" % (temp_version_id, self.version_id))

        self.is_not_available = bytes_as_bool(node[3].data)
        self.depot_encryption_key = node[5].data
        self.is_encryption_key_available = bytes_as_bool(node[6].data)
        self.is_rebased = bytes_as_bool(node[7].data)
        self.is_long_version_roll = bytes_as_bool(node[8].data)

        for n in node[4]:
            tempblob = ApplicationVersionLaunchRecord()
            tempblob.owner = self
            tempblob.parse(n)

class ApplicationVersionLaunchRecord(object):
    def __str__(self):
        return "%s: Version %d's Launch Record %d" % (self.owner.owner, self.owner.version_id, self.launch_option_id)

    def parse(self, node):
        self.launch_option_id = struct.unpack("<l", node.key)[0]

class ApplicationFilesystemRecord(object):
    def get_mount_name(self):
        if len(self.mount_name) > 0:
            return self.mount_name
        else:
            return Application.objects.get(app_id=self.app_id).get_mount_name()

    def __str__(self):
        return "%s: Cache import: %s" % (unicode(self.owner), self.get_mount_name())

    def parse(self, node):        
        self.app_id = struct.unpack("<l", node[1].data)[0]
        self.mount_name = node[2].data
        self.is_optional = bytes_as_bool(node[3].data)

class ApplicationUserDefinedRecord(object):
    def __str__(self):
        return "%s: User Defined Record" % unicode(self.owner)

    def parse(self, node):
        self.key = node.key
        self.data = node.data
