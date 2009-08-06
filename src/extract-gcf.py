
from pysteam.fs.cachefile import CacheFile
from optparse import OptionParser

parser = OptionParser()
parser.add_option("-m", "--minimum", action="store_true", dest="minimum", help="Extract minimum footprint only?")
parser.add_option("-o", "--output", dest="output", help="Output directory for extraction.")
options, args = parser.parse_args()

cacheHandle = open(args[0],"rb")
cacheFile = CacheFile()
cacheFile.parse(cacheHandle)
cacheHandle.close()

import os.path
if options.minimum:
    cacheFile.extract_minimum_footprint(os.path.realpath(options.output))
else:
    cacheFile.extract(os.path.realpath(options.output))
cacheHandle.close()
