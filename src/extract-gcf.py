
if __name__ == "__main__":

    from pysteam.fs.cachefile import CacheFile
    
    filename = raw_input("Path to the GCF file: ")
    output = raw_input("Output Dir: ")
    minimum = raw_input("Minimum Footprint Only [y/n]? ")
    
    cacheHandle = open(filename,"rb")
    cacheFile = CacheFile()
    cacheFile.read(cacheHandle)
    cacheHandle.close()

    import os.path
    if minimum.startswith(("t","T","Y","y","1")):
        cacheFile.extract_minimum_footprint(os.path.realpath(output))
    else:
        cacheFile.extract(os.path.realpath(output))
    cacheHandle.close()
