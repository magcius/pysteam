import setup_django, hashlib
from django.conf import settings
from steamwhore.cdr.models import CDR
from steamwhore.util import ImpSocket, decode_host

##########################################################################
# Directory Server Address and Port.

def get_cdr(data="", address="gds1.steampowered.com", port=27030):
    
    sock = ImpSocket()
    sock.connect((address, port))
    
    # Directory Server.
    sock.send('\x00\x00\x00\x02')
    if sock.recv(1) == '\x01':
        # Second command...
        sock.send_withlen('\x03')
        # Length - int (4 bytes)
        responseLength = sock.recv(4)
        # Unknown - short (2 bytes)
        sock.recv(2)
        # IP and Host - 6 bytes
        host = decode_host(sock.recv(6))

        # Config Sever.
        sock.close()
        sock = ImpSocket()
        sock.connect(host)
        sock.send('\x00\x00\x00\x03')
        
        # Are we accepted?
        accepted = sock.recv(1)
        uIP = sock.recv(4)
        
        # Construct our request.
        # First four bytes = length
        s = '\x09'
        s += hashlib.sha1(data).digest()
        
        sock.send_withlen(s)
        
        unknown = sock.recv(11)
        
        return sock.recv_withlen()
    return None

if __name__ == "__main__":
    
    from os.path import join
    pCDR = join(settings.DATA_DIR, "CDR")
    pCDR_D = join(settings.DATA_DIR, "CDR_decompressed")
    
    try:
        handle = open(pCDR, "rb")
        data = get_cdr(handle.read())
        handle.close()
    except IOError:
        data = get_cdr()
    
    if len(data) > 0:
        handle = open(pCDR, "wb")
        handle.write(data)
        handle.close()
        c = CDR()
        c.parse(data)
        c.save()
    elif settings.DEBUG:
        handle = open(pCDR, "rb")
        c = CDR()
        try:
            c.parse(handle)
        except KeyError:
            bytes = c.blob.serialize(False)
            handle2 = open(pCDR_D, "wb")
            handle2.write(bytes)
            handle2.close()
        c.save()
        handle.close()
    print "done"
        