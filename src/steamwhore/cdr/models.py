
import struct, datetime
from django.db import models
from steamwhore.util import Logging, py_time, bytes_as_bool
from pysteam.blob import Blob

logging = Logging("cdrparse.log")

class CDR(models.Model):
    
    CURRENT_VER = 10
    
    version = models.IntegerField()
    last_changed = models.DateTimeField()
    
    def read(self, stream):
        
        self.pk = 0
        
        self.version = CDR.CURRENT_VER
        self.last_changed = datetime.datetime.now()
        
        blob = Blob()
        blob.parse(stream)
        
        node = blob[0] # Version number.
        if not node.data:
            logging.error("Version number invalid. [No Data]")
            continue
        elif len(node.data) != 2:
            logging.error("Version number invalid. [Length Invalid, Got %d]" % len(node.data))
            continue
        self.version = struct.unpack("<h", node.data)[0]
        if self.version != CDR.CURRENT_VER:
            self.save()
            logging.error("Unhandled version number. Cannot continue using version number: %d" % self.version)
            continue
        
        node = blob[2] # App Records
        if node.child is None:
            logging.warning("Applications Record blob invalid. [No Blob Container]")
        else:
            self.save()
            for subnode in node.child:
                app = Application()
                app.cdr = self
                app.parse(subnode)
                app.save()
        
        node = blob[3] # LastChanged...
        if node.data is None:
            logging.error("LastChangedExistingAppOrSubscriptionTime number invalid. [No Data]")
            continue
        elif len(node.data) != 8:
            logging.error("LastChangedExistingAppOrSubscriptionTime number invalid [Length Invalid, Got %d]" % len(node.data))
            continue
        self.last_changed = py_time(struct.unpack("<q", node.data)[0])
        self.save()

################################
### Application
################################

class Application(models.Model):
    
    cdr = models.ForeignKey(CDR)
    app_id = models.IntegerField(primary_key=True)
    app_name = models.TextField()
    install_dir = models.TextField()
    min_cache = models.PositiveIntegerField()
    max_cache = models.PositiveIntegerField()
    on_first_launch = models.IntegerField()
    is_bandwidth_greedy = models.BooleanField()
    current_version_id = models.PositiveIntegerField()
    trickle_version_id = models.IntegerField()
    beta_version_password = models.TextField()
    beta_version_id = models.IntegerField()
    install_dir_legacy = models.TextField()
    use_filesystem_dvr = models.BooleanField()
    manifest_only_app = models.BooleanField()
    app_of_manifest_only_cache = models.IntegerField()
    
    def __unicode__(self):
        return "%s (App ID %d): %s" % ("Cache File" if self.is_cache() else "Application", self.app_id, self.app_name)
    
    def is_cache(self):
        return len(self.applicationfilesystemrecord_set.get_query_set()) < 1
    
    def is_ncf(self):
        if self.is_cache():
            return (self.app_of_manifest_only_cache > 0) and Application.objects.get(app_id=self.app_of_manifest_only_cache).manifest_only_app
        return False
    
    def get_mount_name(self):
        if self.is_cache():
            return self.app_name + (".ncf" if self.is_ncf() else ".gcf")
        return self.app_name
    
    def read(self, node):
        
        self.app_name = ""
        self.install_dir = ""
        self.min_cache = 0
        self.max_cache = 0
        self.on_first_launch = 0
        self.is_bandwidth_greedy = False
        self.current_version_id = 0  
        self.trickle_version_id = 0
        self.beta_version_password = ""
        self.beta_version_id = 0
        self.install_dir_legacy = ""
        self.use_filesystem_dvr = False
        self.manifest_only_app = False
        self.app_of_manifest_only_cache = False
        
        if len(node.children) == 0:
            raise ValueError, "Blob has no children"
        self.app_id = struct.unpack("<l", node.key)[0]
        
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
        self.save()
        
        #logging.warning ("AppIconsRecords not implemented")
        
        for n in node[6]:
            tempblob = ApplicationLaunchOptionRecord()
            tempblob.owner = self
            tempblob.read(n)
            tempblob.save()
        
        for n in node[10]:
            tempblob = ApplicationVersionRecord()
            tempblob.owner = self
            tempblob.read(n)
            tempblob.save()
            
        for n in node[12]:
            tempblob = ApplicationFilesystemRecord()
            tempblob.owner = self
            tempblob.read(n)
            tempblob.save()
            
        for n in node[14]:
            tempblob = ApplicationUserDefinedRecord()
            tempblob.owner = self
            tempblob.read(n)
            tempblob.save()
                        

class ApplicationLaunchOptionRecord(models.Model):
    
    owner = models.ForeignKey(Application)
    option_id = models.IntegerField()
    description = models.TextField()
    command_line = models.TextField()
    icon_index = models.IntegerField()
    no_desktop_shortcut = models.BooleanField()
    no_start_menu_shortcut = models.BooleanField()
    long_running_unattended = models.BooleanField()
    
    def __unicode__(self):
        return "%s's Launch Option Record %d" % (unicode(self.owner), self.option_id)
    
    def read(self, node):
        
        self.option_id = 0
        self.description = ""
        self.command_line = ""
        self.icon_index = 0
        self.no_desktop_shortcut = False
        self.no_start_menu_shortcut = False
        self.long_running_unattended
        blob = node.child
        if len(blob.children) == 0:
            raise ValueError, "Blob has no children"
        self.option_id = struct.unpack("<l", node.key)[0]
        
        # Save us the trouble.. Edit existing items when possible.
        qs = ApplicationLaunchOptionRecord.objects.filter(owner=self.owner).filter(option_id=self.option_id)
        if len(qs) == 1:
            self.pk = qs[0].pk
        elif len(qs) > 1:
            logging.warning("Two ApplicationLaunchOptionRecord object with the same owner and option_id exist")
            
            
        self.description = node[1].data
        self.command_line = node[2].data
        self.icon_index = node[3].data
        self.no_desktop_shortcut = bytes_as_bool(node[4].data)
        self.no_start_menu_shortcut = bytes_as_bool(node[5].data)
        self.long_running_unattended = bytes_as_bool(node[6].data)

class ApplicationVersionRecord(models.Model):
    
    version_id = models.IntegerField()
    owner = models.ForeignKey(Application)
    
    description = models.TextField()
    is_not_available = models.BooleanField()
    depot_encryption_key = models.TextField()
    is_encryption_key_available = models.BooleanField()
    is_rebased = models.BooleanField()
    is_long_version_roll = models.BooleanField()
    
    def __unicode__(self):
        return "%s's Version Record %d" % (unicode(self.owner), self.version_id)
    def read(self, node):
        
        self.version_id = 0
        self.description = ""
        self.is_not_available = False
        self.depot_encryption_key = ""
        self.is_encryption_key_available = False
        self.is_rebased = False
        self.is_long_version_roll = False
        
        self.version_id = struct.unpack("<l", node.key)[0]
        
        # Save us the trouble.. Edit existing items when possible.
        qs = ApplicationVersionRecord.objects.filter(owner=self.owner, version_id=self.version_id)
        if len(qs) == 1:
            self.pk = qs[0].pk
        elif len(qs) > 1:
            logging.warning("Two ApplicationVersionRecord object with the same owner and version_id exist")
        
        self.description = node[1].data
        #temp_version_id = struct.unpack("<l", tempnode.data)[0]
        #if temp_version_id != self.version_id:
        #   logging.error("Version ID mismatch: %d and %d" % (temp_version_id, self.version_id))
        
        self.is_not_available = bytes_as_bool(node[3].data)
        self.depot_encryption_key = node[5].data
        self.is_encryption_key_available = bytes_as_bool(node[6].data)
        self.is_rebased = bytes_as_bool(node[7].data)
        self.is_long_version_roll = bytes_as_bool(node[8].data)
        self.save()
        
        for n in node[4]:
            tempblob = ApplicationVersionLaunchRecord()
            tempblob.owner = self
            tempblob.read(n)
            tempblob.save()

class ApplicationVersionLaunchRecord(models.Model):
    
    owner = models.ForeignKey(ApplicationVersionRecord)
    launch_option_id = models.IntegerField()

    
    def __unicode__(self):
        return "%s: Version %d's Launch Record %d" % (unicode(self.owner.owner), self.owner.version_id, self.launch_option_id)
    def parse(self, node):
        self.launch_option_id = struct.unpack("<l", node.key)[0]
    
class ApplicationFilesystemRecord(models.Model):
    
    owner = models.ForeignKey(Application)
    app_id = models.IntegerField()
    mount_name = models.TextField()
    is_optional = models.BooleanField()
    
    def get_mount_name(self):
        if len(self.mount_name) > 0:
            return self.mount_name
        else:
            return Application.objects.get(app_id=self.app_id).get_mount_name()
    
    def __unicode__(self):
        return "%s: Cache import: %s" % (unicode(self.owner), self.get_mount_name())
    
    def read(self, node):
        
        self.app_id = 0
        self.mount_name = ""
        self.is_optional = False
        
        qs = ApplicationFilesystemRecord.objects.filter(owner=self.owner, app_id=self.app_id)
        if len(qs) == 1:
            self.pk = qs[0].pk
        elif len(qs) > 1:
            logging.warning("Two ApplicationVersionRecord object with the same owner and option_id exist")
        
        self.app_id = struct.unpack("<l", node[1].data)[0]
        self.mount_name = node[2].data
        self.is_optional = bytes_as_bool(node[3].data)
    
class ApplicationUserDefinedRecord(models.Model):
    
    owner = models.ForeignKey(Application)
    key = models.TextField()
    data = models.TextField()
    
    def __unicode__(self):
        return "%s: User Defined Record" % unicode(self.owner)
    
    def read(self, node):
        self.key = node.key
        self.data = node.data
