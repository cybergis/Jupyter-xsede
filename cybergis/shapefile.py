"""
shapefile.py
Provides read and write support for ESRI Shapefiles.
author: jlawhead<at>geospatialpython.com
date: 20110927
version: 1.1.4
Compatible with Python versions 2.4-3.x
"""

from struct import pack, unpack, calcsize, error
import os
import sys
import time
import array
import math
#from rdp import rdp
from pyproj import Proj, transform
#
# Constants for shape types
NULL = 0
POINT = 1
POLYLINE = 3
POLYGON = 5
MULTIPOINT = 8
POINTZ = 11
POLYLINEZ = 13
POLYGONZ = 15
MULTIPOINTZ = 18
POINTM = 21
POLYLINEM = 23
POLYGONM = 25
MULTIPOINTM = 28
MULTIPATCH = 31

PYTHON3 = sys.version_info[0] == 3

def b(v):
    if PYTHON3:
        if isinstance(v, str):
            # For python 3 encode str to bytes.
            return v.encode('utf-8')
        elif isinstance(v, bytes):
            # Already bytes.
            return v
        else:
            # Error.
            raise Exception('Unknown input type')
    else:
        # For python 2 assume str passed in and return str.
        return v

def u(v):
    if PYTHON3:
        if isinstance(v, bytes):
            # For python 3 decode bytes to str.
            return v.decode('utf-8')
        elif isinstance(v, str):
            # Already str.
            return v
        else:
            # Error.
            raise Exception('Unknown input type')
    else:
        # For python 2 assume str passed in and return str.
        return v

def is_string(v):
    if PYTHON3:
        return isinstance(v, str)
    else:
        return isinstance(v, basestring)

class _Array(array.array):
    """Converts python tuples to lits of the appropritate type.
    Used to unpack different shapefile header parts."""
    def __repr__(self):
        return str(self.tolist())

class _Shape:
    def __init__(self, shapeType=None):
        """Stores the geometry of the different shape types
        specified in the Shapefile spec. Shape types are
        usually point, polyline, or polygons. Every shape type
        except the "Null" type contains points at some level for
        example verticies in a polygon. If a shape type has
        multiple shapes containing points within a single
        geometry record then those shapes are called parts. Parts
        are designated by their starting index in geometry record's
        list of shapes."""
        self.shapeType = shapeType
        self.points = []

class _ShapeRecord:
    """A shape object of any type."""
    def __init__(self, shape=None, record=None):
        self.shape = shape
        self.record = record

class ShapefileException(Exception):
    """An exception to handle shapefile specific problems."""
    pass

class Reader:
    """Reads the three files of a shapefile as a unit or
    separately.  If one of the three files (.shp, .shx,
    .dbf) is missing no exception is thrown until you try
    to call a method that depends on that particular file.
    The .shx index file is used if available for efficiency
    but is not required to read the geometry from the .shp
    file. The "shapefile" argument in the constructor is the
    name of the file you want to open.

    You can instantiate a Reader without specifying a shapefile
    and then specify one later with the load() method.

    Only the shapefile headers are read upon loading. Content
    within each file is only accessed when required and as
    efficiently as possible. Shapefiles are usually not large
    but they can be.
    """
    def __init__(self, *args, **kwargs):
        self.shp = None
        self.shx = None
        self.dbf = None
        self.shapeName = "Not specified"
        self._offsets = []
        self.shpLength = None
        self.numRecords = None
        self.fields = []
        self.__dbfHdrLength = 0
        # See if a shapefile name was passed as an argument
        if len(args) > 0:
            if type(args[0]) is type("stringTest"):
                self.load(args[0])
                return
        if "shp" in kwargs.keys():
            if hasattr(kwargs["shp"], "read"):
                self.shp = kwargs["shp"]
                if hasattr(self.shp, "seek"):
                    self.shp.seek(0)
            if "shx" in kwargs.keys():
                if hasattr(kwargs["shx"], "read"):
                    self.shx = kwargs["shx"]
                    if hasattr(self.shx, "seek"):
                        self.shx.seek(0)
        if "dbf" in kwargs.keys():
            if hasattr(kwargs["dbf"], "read"):
                self.dbf = kwargs["dbf"]
                if hasattr(self.dbf, "seek"):
                    self.dbf.seek(0)
        if self.shp or self.dbf:
            self.load()
        else:
            raise ShapefileException("Shapefile Reader requires a shapefile or file-like object.")

    def load(self, shapefile=None):
        """Opens a shapefile from a filename or file-like
        object. Normally this method would be called by the
        constructor with the file object or file name as an
        argument."""
        if shapefile:
            (shapeName, ext) = os.path.splitext(shapefile)
            self.shapeName = shapeName
            try:
                self.shp = open("%s.shp" % shapeName, "rb")
            except IOError:
                raise ShapefileException("Unable to open %s.shp" % shapeName)
            try:
                self.shx = open("%s.shx" % shapeName, "rb")
            except IOError:
                raise ShapefileException("Unable to open %s.shx" % shapeName)
            try:
                self.dbf = open("%s.dbf" % shapeName, "rb")
            except IOError:
                raise ShapefileException("Unable to open %s.dbf" % shapeName)
        if self.shp:
            self.__shpHeader()
        if self.dbf:
            self.__dbfHeader()

    def __getFileObj(self, f):
        """Checks to see if the requested shapefile file object is
        available. If not a ShapefileException is raised."""
        if not f:
            raise ShapefileException("Shapefile Reader requires a shapefile or file-like object.")
        if self.shp and self.shpLength is None:
            self.load()
        if self.dbf and len(self.fields) == 0:
            self.load()
        return f

    def __restrictIndex(self, i):
        """Provides list-like handling of a record index with a clearer
        error message if the index is out of bounds."""
        if self.numRecords:
            rmax = self.numRecords - 1
            if abs(i) > rmax:
                raise IndexError("Shape or Record index out of range.")
            if i < 0: i = range(self.numRecords)[i]
        return i

    def __shpHeader(self):
        """Reads the header information from a .shp or .shx file."""
        if not self.shp:
            raise ShapefileException("Shapefile Reader requires a shapefile or file-like object. (no shp file found")
        shp = self.shp
        # File length (16-bit word * 2 = bytes)
        shp.seek(24)
        self.shpLength = unpack(">i", shp.read(4))[0] * 2
        # Shape type
        shp.seek(32)
        self.shapeType= unpack("<i", shp.read(4))[0]
        # The shapefile's bounding box (lower left, upper right)
        self.bbox = _Array('d', unpack("<4d", shp.read(32)))
        # Elevation
        self.elevation = _Array('d', unpack("<2d", shp.read(16)))
        # Measure
        self.measure = _Array('d', unpack("<2d", shp.read(16)))

    def __shape(self):
        """Returns the header info and geometry for a single shape."""
        f = self.__getFileObj(self.shp)
        record = _Shape()
        nParts = nPoints = zmin = zmax = mmin = mmax = None
        (recNum, recLength) = unpack(">2i", f.read(8))
        shapeType = unpack("<i", f.read(4))[0]
        record.shapeType = shapeType
        # For Null shapes create an empty points list for consistency
        if shapeType == 0:
            record.points = []
        # All shape types capable of having a bounding box
        elif shapeType in (3,5,8,13,15,18,23,25,28,31):
            record.bbox = _Array('d', unpack("<4d", f.read(32)))
        # Shape types with parts
        if shapeType in (3,5,13,15,23,25,31):
            nParts = unpack("<i", f.read(4))[0]
        # Shape types with points
        if shapeType in (3,5,8,13,15,23,25,31):
            nPoints = unpack("<i", f.read(4))[0]
        # Read parts
        if nParts:
            record.parts = _Array('i', unpack("<%si" % nParts, f.read(nParts * 4)))
        # Read part types for Multipatch - 31
        if shapeType == 31:
            record.partTypes = _Array('i', unpack("<%si" % nParts, f.read(nParts * 4)))
        # Read points - produces a list of [x,y] values
        if nPoints:
            record.points = [_Array('d', unpack("<2d", f.read(16))) for p in range(nPoints)]
        # Read z extremes and values
        if shapeType in (13,15,18,31):
            (zmin, zmax) = unpack("<2d", f.read(16))
            record.z = _Array('d', unpack("<%sd" % nPoints, f.read(nPoints * 8)))
        # Read m extremes and values
        if shapeType in (13,15,18,23,25,28,31):
            (mmin, mmax) = unpack("<2d", f.read(16))
            # Measure values less than -10e38 are nodata values according to the spec
            record.m = []
            for m in _Array('d', unpack("%sd" % nPoints, f.read(nPoints * 8))):
                if m > -10e38:
                    record.m.append(m)
                else:
                    record.m.append(None)
        # Read a single point
        if shapeType in (1,11,21):
            record.points = [_Array('d', unpack("<2d", f.read(16)))]
        # Read a single Z value
        if shapeType == 11:
            record.z = unpack("<d", f.read(8))
        # Read a single M value
        if shapeType in (11,21):
            record.m = unpack("<d", f.read(8))
        return record

    def __shapeIndex(self, i=None):
        """Returns the offset in a .shp file for a shape based on information
        in the .shx index file."""
        shx = self.shx
        if not shx:
            return None
        if not self._offsets:
            # File length (16-bit word * 2 = bytes) - header length
            shx.seek(24)
            shxRecordLength = (unpack(">i", shx.read(4))[0] * 2) - 100
            numRecords = shxRecordLength // 8
            # Jump to the first record.
            shx.seek(100)
            for r in range(numRecords):
                # Offsets are 16-bit words just like the file length
                self._offsets.append(unpack(">i", shx.read(4))[0] * 2)
                shx.seek(shx.tell() + 4)
        if not i == None:
            return self._offsets[i]

    def shape(self, i=0):
        """Returns a shape object for a shape in the the geometry
        record file."""
        shp = self.__getFileObj(self.shp)
        i = self.__restrictIndex(i)
        offset = self.__shapeIndex(i)
        if not offset:
            # Shx index not available so use the full list.
            shapes = self.shapes()
            return shapes[i]
        shp.seek(offset)
        return self.__shape()

    def shapes(self):
        """Returns all shapes in a shapefile."""
        shp = self.__getFileObj(self.shp)
        shp.seek(100)
        shapes = []
        while shp.tell() < self.shpLength:
            shapes.append(self.__shape())
        return shapes

    def __dbfHeaderLength(self):
        """Retrieves the header length of a dbf file header."""
        if not self.__dbfHdrLength:
            if not self.dbf:
                raise ShapefileException("Shapefile Reader requires a shapefile or file-like object. (no dbf file found)")
            dbf = self.dbf
            (self.numRecords, self.__dbfHdrLength) = \
                    unpack("<xxxxLH22x", dbf.read(32))
        return self.__dbfHdrLength

    def __dbfHeader(self):
        """Reads a dbf header. Xbase-related code borrows heavily from ActiveState Python Cookbook Recipe 362715 by Raymond Hettinger"""
        if not self.dbf:
            raise ShapefileException("Shapefile Reader requires a shapefile or file-like object. (no dbf file found)")
        dbf = self.dbf
        headerLength = self.__dbfHeaderLength()
        numFields = (headerLength - 33) // 32
        for field in range(numFields):
            fieldDesc = list(unpack("<11sc4xBB14x", dbf.read(32)))
            name = 0
            idx = 0
            if b("\x00") in fieldDesc[name]:
                idx = fieldDesc[name].index(b("\x00"))
            else:
                idx = len(fieldDesc[name]) - 1
            fieldDesc[name] = fieldDesc[name][:idx]
            fieldDesc[name] = u(fieldDesc[name])
            fieldDesc[name] = fieldDesc[name].lstrip()
            fieldDesc[1] = u(fieldDesc[1])
            self.fields.append(fieldDesc)
        terminator = dbf.read(1)
        assert terminator == b("\r")
        self.fields.insert(0, ('DeletionFlag', 'C', 1, 0))

    def __recordFmt(self):
        """Calculates the size of a .shp geometry record."""
        if not self.numRecords:
            self.__dbfHeader()
        fmt = ''.join(['%ds' % fieldinfo[2] for fieldinfo in self.fields])
        fmtSize = calcsize(fmt)
        return (fmt, fmtSize)

    def __record(self):
        """Reads and returns a dbf record row as a list of values."""
        f = self.__getFileObj(self.dbf)
        recFmt = self.__recordFmt()
        recordContents = unpack(recFmt[0], f.read(recFmt[1]))
        if recordContents[0] != b(' '):
            # deleted record
            return None
        record = []
        for (name, typ, size, deci), value in zip(self.fields, recordContents):
            if name == 'DeletionFlag':
                continue
            elif not b'''value.strip().strip('*')''':
                record.append(value)
                continue
            elif typ == "N":
                value = value.replace(b('\0'), b('')).strip()
                if value == b(''):
                    value = 0
                elif deci:
                    try:
                        value = float(value)
                    except:
                        value = float(value.replace(b('#INF'),b('')))
                else:
                    value = int(value)
            elif typ == b('D'):
                try:
                    y, m, d = int(value[:4]), int(value[4:6]), int(value[6:8])
                    value = [y, m, d]
                except:
                    value = value.strip()
            elif typ == b('L'):
                value = (value in b('YyTt') and b('T')) or \
                                        (value in b('NnFf') and b('F')) or b('?')
            else:
                value = u(value)
                value = value.strip()
            record.append(value)
        return record

    def record(self, i=0):
        """Returns a specific dbf record based on the supplied index."""
        f = self.__getFileObj(self.dbf)
        if not self.numRecords:
            self.__dbfHeader()
        i = self.__restrictIndex(i)
        recSize = self.__recordFmt()[1]
        f.seek(0)
        f.seek(self.__dbfHeaderLength() + (i * recSize))
        return self.__record()

    def records(self):
        """Returns all records in a dbf file."""
        if not self.numRecords:
            self.__dbfHeader()
        records = []
        f = self.__getFileObj(self.dbf)
        f.seek(self.__dbfHeaderLength())
        for i in range(self.numRecords):
            r = self.__record()
            if r:
                records.append(r)
        return records

    def shapeRecord(self, i=0):
        """Returns a combination geometry and attribute record for the
        supplied record index."""
        i = self.__restrictIndex(i)
        return _ShapeRecord(shape=self.shape(i),
                                                        record=self.record(i))

    def shapeRecords(self):
        """Returns a list of combination geometry/attribute records for
        all records in a shapefile."""
        shapeRecords = []
        return [_ShapeRecord(shape=rec[0], record=rec[1]) \
                                for rec in zip(self.shapes(), self.records())]

class Writer:
    """Provides write support for ESRI Shapefiles."""
    def __init__(self, shapeType=None):
        self._shapes = []
        self.fields = []
        self.records = []
        self.shapeType = shapeType
        self.shp = None
        self.shx = None
        self.dbf = None
        self.___bbox = None
        # Geometry record offsets and lengths for writing shx file.
        self._offsets = []
        self._lengths = []
        # Use deletion flags in dbf? Default is false (0).
        self.deletionFlag = 0
        self.lens = 0

    def __getFileObj(self, f):
        """Safety handler to verify file-like objects"""
        if not f:
            raise ShapefileException("No file-like object available.")
        elif hasattr(f, "write"):
            return f
        else:
            pth = os.path.split(f)[0]
            if pth and not os.path.exists(pth):
                os.makedirs(pth)
            return open(f, "wb")

    def __shpFileLength(self):
        """Calculates the file length of the shp file."""
        # Start with header length
        size = 100
        # Calculate size of all shapes
        for s in self._shapes:
            # Add in record header and shape type fields
            size += 12
            # nParts and nPoints do not apply to all shapes
            #if self.shapeType not in (0,1):
            #       nParts = len(s.parts)
            #       nPoints = len(s.points)
            if hasattr(s,'parts'):
                nParts = len(s.parts)
            if hasattr(s,'points'):
                nPoints = len(s.points)
            # All shape types capable of having a bounding box
            if self.shapeType in (3,5,8,13,15,18,23,25,28,31):
                size += 32
            # Shape types with parts
            if self.shapeType in (3,5,13,15,23,25,31):
                # Parts count
                size += 4
                # Parts index array
                size += nParts * 4
            # Shape types with points
            if self.shapeType in (3,5,8,13,15,23,25,31):
                # Points count
                size += 4
                # Points array
                size += 16 * nPoints
            # Calc size of part types for Multipatch (31)
            if self.shapeType == 31:
                size += nParts * 4
            # Calc z extremes and values
            if self.shapeType in (13,15,18,31):
                # z extremes
                size += 16
                # z array
                size += 8 * nPoints
            # Calc m extremes and values
            if self.shapeType in (23,25,31):
                # m extremes
                size += 16
                # m array
                size += 8 * nPoints
            # Calc a single point
            if self.shapeType in (1,11,21):
                size += 16
            # Calc a single Z value
            if self.shapeType == 11:
                size += 8
            # Calc a single M value
            if self.shapeType in (11,21):
                size += 8
        # Calculate size as 16-bit words
        size //= 2
        return size

    def __bbox(self, shapes, shapeTypes=[]):
        x = []
        y = []
        for s in shapes:
            shapeType = self.shapeType
            if shapeTypes:
                shapeType = shapeTypes[shapes.index(s)]
            px, py = list(zip(*s.points))[:2]
            x.extend(px)
            y.extend(py)
        return [min(x), min(y), max(x), max(y)]

    def __zbox(self, shapes, shapeTypes=[]):
        z = []
        for s in shapes:
            try:
                for p in s.points:
                    z.append(p[2])
            except IndexError:
                pass
        if not z: z.append(0)
        return [min(z), max(z)]

    def __mbox(self, shapes, shapeTypes=[]):
        m = [0]
        for s in shapes:
            try:
                for p in s.points:
                    m.append(p[3])
            except IndexError:
                pass
        return [min(m), max(m)]

    def bbox(self):
        """Returns the current bounding box for the shapefile which is
        the lower-left and upper-right corners. It does not contain the
        elevation or measure extremes."""
        if not self.___bbox:
            self.___bbox = self.__bbox(self._shapes)
        return self.___bbox

    def zbox(self):
        """Returns the current z extremes for the shapefile."""
        return self.__zbox(self._shapes)

    def mbox(self):
        """Returns the current m extremes for the shapefile."""
        return self.__mbox(self._shapes)

    def __shapefileHeader(self, fileObj, headerType='shp'):
        """Writes the specified header type to the specified file-like object.
        Several of the shapefile formats are so similar that a single generic
        method to read or write them is warranted."""
        f = self.__getFileObj(fileObj)
        f.seek(0)
        # File code, Unused bytes
        f.write(pack(">6i", 9994,0,0,0,0,0))
        # File length (Bytes / 2 = 16-bit words)
        if headerType == 'shp':
            f.write(pack(">i", self.__shpFileLength()))
        elif headerType == 'shx':
            f.write(pack('>i', ((100 + (len(self._shapes) * 8)) // 2)))
        # Version, Shape type
        f.write(pack("<2i", 1000, self.shapeType))
        # The shapefile's bounding box (lower left, upper right)
        if self.shapeType != 0:
            try:
                f.write(pack("<4d", *self.bbox()))
            except error:
                raise ShapefileException("Failed to write shapefile bounding box. Floats required.")
        else:
            f.write(pack("<4d", 0,0,0,0))
        # Elevation
        z = self.zbox()
        # Measure
        m = self.mbox()
        try:
            f.write(pack("<4d", z[0], z[1], m[0], m[1]))
        except error:
            raise ShapefileException("Failed to write shapefile elevation and measure values. Floats required.")

    def __dbfHeader(self):
        """Writes the dbf header and field descriptors."""
        f = self.__getFileObj(self.dbf)
        f.seek(0)
        version = 3
        year, month, day = time.localtime()[:3]
        year -= 1900
        # Remove deletion flag placeholder from fields
        for field in self.fields:
            if field[0].startswith("Deletion"):
                self.fields.remove(field)
        numRecs = len(self.records)
        numFields = len(self.fields)
        headerLength = numFields * 32 + 33
        recordLength = sum([int(field[2]) for field in self.fields]) + 1
        header = pack('<BBBBLHH20x', version, year, month, day, numRecs,
                headerLength, recordLength)
        f.write(header)
        # Field descriptors
        for field in self.fields:
            name, fieldType, size, decimal = field
            name = b(name)
            name = name.replace(b(' '), b('_'))
            name = name.ljust(11).replace(b(' '), b('\x00'))
            fieldType = b(fieldType)
            size = int(size)
            fld = pack('<11sc4xBB14x', name, fieldType, size, decimal)
            f.write(fld)
        # Terminator
        f.write(b('\r'))

    def __shpRecords(self):
        """Write the shp records"""
        f = self.__getFileObj(self.shp)
        f.seek(100)
        recNum = 1
        for s in self._shapes:
            self._offsets.append(f.tell())
            # Record number, Content length place holder
            f.write(pack(">2i", recNum, 0))
            recNum += 1
            start = f.tell()
            # Shape Type
            f.write(pack("<i", s.shapeType))
            # All shape types capable of having a bounding box
            if s.shapeType in (3,5,8,13,15,18,23,25,28,31):
                try:
                    f.write(pack("<4d", *self.__bbox([s])))
                except error:
                    raise ShapefileException("Falied to write bounding box for record %s. Expected floats." % recNum)
            # Shape types with parts
            if s.shapeType in (3,5,13,15,23,25,31):
                # Number of parts
                f.write(pack("<i", len(s.parts)))
            # Shape types with multiple points per record
            if s.shapeType in (3,5,8,13,15,23,25,31):
                # Number of points
                f.write(pack("<i", len(s.points)))
            # Write part indexes
            if s.shapeType in (3,5,13,15,23,25,31):
                for p in s.parts:
                    f.write(pack("<i", p))
            # Part types for Multipatch (31)
            if s.shapeType == 31:
                for pt in s.partTypes:
                    f.write(pack("<i", pt))
            # Write points for multiple-point records
            if s.shapeType in (3,5,8,13,15,23,25,31):
                try:
                    [f.write(pack("<2d", *p[:2])) for p in s.points]
                except error:
                    raise ShapefileException("Failed to write points for record %s. Expected floats." % recNum)
            # Write z extremes and values
            if s.shapeType in (13,15,18,31):
                try:
                    f.write(pack("<2d", *self.__zbox([s])))
                except error:
                    raise ShapefileException("Failed to write elevation extremes for record %s. Expected floats." % recNum)
                try:
                    [f.write(pack("<d", p[2])) for p in s.points]
                except error:
                    raise ShapefileException("Failed to write elevation values for record %s. Expected floats." % recNum)
            # Write m extremes and values
            if s.shapeType in (23,25,31):
                try:
                    f.write(pack("<2d", *self.__mbox([s])))
                except error:
                    raise ShapefileException("Failed to write measure extremes for record %s. Expected floats" % recNum)
                try:
                    [f.write(pack("<d", p[3])) for p in s.points]
                except error:
                    raise ShapefileException("Failed to write measure values for record %s. Expected floats" % recNum)
            # Write a single point
            if s.shapeType in (1,11,21):
                try:
                    f.write(pack("<2d", s.points[0][0], s.points[0][1]))
                except error:
                    raise ShapefileException("Failed to write point for record %s. Expected floats." % recNum)
            # Write a single Z value
            if s.shapeType == 11:
                try:
                    f.write(pack("<1d", s.points[0][2]))
                except error:
                    raise ShapefileException("Failed to write elevation value for record %s. Expected floats." % recNum)
            # Write a single M value
            if s.shapeType in (11,21):
                try:
                    f.write(pack("<1d", s.points[0][3]))
                except error:
                    raise ShapefileException("Failed to write measure value for record %s. Expected floats." % recNum)
            # Finalize record length as 16-bit words
            finish = f.tell()
            length = (finish - start) // 2
            self._lengths.append(length)
            # start - 4 bytes is the content length field
            f.seek(start-4)
            f.write(pack(">i", length))
            f.seek(finish)

    def __shxRecords(self):
        """Writes the shx records."""
        f = self.__getFileObj(self.shx)
        f.seek(100)
        for i in range(len(self._shapes)):
            f.write(pack(">i", self._offsets[i] // 2))
            f.write(pack(">i", self._lengths[i]))

    def __dbfRecords(self):
        """Writes the dbf records."""
        f = self.__getFileObj(self.dbf)
        for record in self.records:
            if not self.fields[0][0].startswith("Deletion"):
                f.write(b(' ')) # deletion flag
            for (fieldName, fieldType, size, dec), value in zip(self.fields, record):
                fieldType = fieldType.upper()
                size = int(size)
                if fieldType.upper() == "N":
                    value = str(value).rjust(size)
                elif fieldType == 'L':
                    value = str(value)[0].upper()
                else:
                    value = str(value)[:size].ljust(size)
                assert len(value) == size
                value = b(value)
                f.write(value)

    def null(self):
        """Creates a null shape."""
        self._shapes.append(_Shape(NULL))
        self.lens += 1

    def point(self, x, y, z=0, m=0):
        """Creates a point shape."""
        pointShape = _Shape(self.shapeType)
        pointShape.points.append([x, y, z, m])
        self._shapes.append(pointShape)
        self.lens += 1

    def line(self, parts=[], shapeType=POLYLINE):
        """Creates a line shape. This method is just a convienience method
        which wraps 'poly()'.
        """
        self.poly(parts, shapeType, [])

    def poly(self, parts=[], shapeType=POLYGON, partTypes=[]):
        """Creates a shape that has multiple collections of points (parts)
        including lines, polygons, and even multipoint shapes. If no shape type
        is specified it defaults to 'polygon'. If no part types are specified
        (which they normally won't be) then all parts default to the shape type.
        """
        polyShape = _Shape(shapeType)
        polyShape.parts = []
        polyShape.points = []
        for part in parts:
            polyShape.parts.append(len(polyShape.points))
            for point in part:
                # Ensure point is list
                if not isinstance(point, list):
                    point = list(point)
                # Make sure point has z and m values
                while len(point) < 4:
                    point.append(0)
                polyShape.points.append(point)
        if polyShape.shapeType == 31:
            if not partTypes:
                for part in parts:
                    partTypes.append(polyShape.shapeType)
            polyShape.partTypes = partTypes
        self._shapes.append(polyShape)
        self.lens += 1

    def field(self, name, fieldType="C", size="50", decimal=0):
        """Adds a dbf field descriptor to the shapefile."""
        self.fields.append((name, fieldType, size, decimal))

    def record(self, *recordList, **recordDict):
        """Creates a dbf attribute record. You can submit either a sequence of
        field values or keyword arguments of field names and values. Before
        adding records you must add fields for the record values using the
        fields() method. If the record values exceed the number of fields the
        extra ones won't be added. In the case of using keyword arguments to specify
        field/value pairs only fields matching the already registered fields
        will be added."""
        record = []
        fieldCount = len(self.fields)
        # Compensate for deletion flag
        if fieldCount > 0:
            if self.fields[0][0].startswith("Deletion"): fieldCount -= 1
        if recordList:
            [record.append(recordList[i]) for i in range(fieldCount)]
        elif recordDict:
            for field in self.fields:
                if field[0] in recordDict:
                    val = recordDict[field[0]]
                    if val:
                        record.append(val)
                    else:
                        record.append("")
        if record:
            self.records.append(record)

    def shape(self, i):
        return self._shapes[i]

    def shapes(self):
        """Return the current list of shapes."""
        return self._shapes

    def saveShp(self, target):
        """Save an shp file."""
        if not hasattr(target, "write"):
            target = os.path.splitext(target)[0] + '.shp'
        if not self.shapeType:
            self.shapeType = self._shapes[0].shapeType
        self.shp = self.__getFileObj(target)
        self.__shapefileHeader(self.shp, headerType='shp')
        self.__shpRecords()

    def saveShx(self, target):
        """Save an shx file."""
        if not hasattr(target, "write"):
            target = os.path.splitext(target)[0] + '.shx'
        if not self.shapeType:
            self.shapeType = self._shapes[0].shapeType
        self.shx = self.__getFileObj(target)
        self.__shapefileHeader(self.shx, headerType='shx')
        self.__shxRecords()

    def saveDbf(self, target):
        """Save a dbf file."""
        if not hasattr(target, "write"):
            target = os.path.splitext(target)[0] + '.dbf'
        self.dbf = self.__getFileObj(target)
        self.__dbfHeader()
        self.__dbfRecords()

    def save(self, target=None, shp=None, shx=None, dbf=None):
        """Save the shapefile data to three files or
        three file-like objects. SHP and DBF files can also
        be written exclusively using saveShp, saveShx, and saveDbf respectively."""
        # TODO: Create a unique filename for target if None.
        if shp:
            self.saveShp(shp)
        if shx:
            self.saveShx(shx)
        if dbf:
            self.saveDbf(dbf)
        elif target:
            self.saveShp(target)
            self.shp.close()
            self.saveShx(target)
            self.shx.close()
            self.saveDbf(target)
            self.dbf.close()


class Feature:
    ''' Class for convenient visit of shapefile '''

    def __init__(self, shapeEditor, index):
        self.shpfile = shapeEditor
        self.id = index
        self.lens = len(shapeEditor.shape(index).points)
        #self.r = {}
        #for i in range(len(shapeEditor.fields) - 1):
        #    self.r[shapeEditor.fields[i + 1][0]] = shapeEditor.records[index][i]
        self.shp = shapeEditor.shape(index)
        self.p = self.shp.points
        self.v = shapeEditor.records[index]
        ##fields = shapeEditor.fields
        ##if fields[0][0] == 'DeletionFlag':
        ##    del(fields[0])
        ##for i in range(len(fields)):
        ##    setattr(self.__class__,fields[i][0],self.v[i])

    def does_contain_points(self, x, y):
        start = 0
        for i in self.shp.parts[1:]:
            if point_in_poly(x, y, self.p[start:i]):
                return True
            start = i

        return point_in_poly(x, y, self.p[self.shp.parts[-1]:])

    def __refreshR(self):
        pass
        #for i in range(len(self.shp.fields) - 1):
        #    self.r[self.shp.fields[i + 1][0]] = self.shp.records[self.id][i]

    def __getitem__(self, ind):
        if is_string(ind):
            m = map(lambda f: f[0], self.shpfile.fields)
            p = m.index(ind) - 1
            return self.shpfile.records[self.id][p]
        else:
            return self.shpfile.shape(self.id).points[ind]

    def __setitem__(self, ind, value):
        if is_string(ind):
            m = map(lambda f: f[0], self.shpfile.fields)
            p = m.index(ind) - 1
            self.shpfile.records[self.id][p] = value
            self.__refreshR()
        else:
            self.shpfile.shape(self.id).points[ind] = value

    def __iter__(self):
        self.nowIndex = -1
        return self

    def next(self):
        if self.nowIndex >= self.lens - 1:
            raise StopIteration
        else:
            self.nowIndex += 1
            return self.shpfile.shape(self.id).points[self.nowIndex]
    
    #def DPSimplify(self, epsilon):
    #    pp = list(self.shp.parts) + []
    #    self.shp.points, self.shp.parts=DPSimplify(self.p, epsilon, self.shp.parts)

    def area(self):
	    """
	    the area of a polygon
	    """
	    return areaOf(self.p,self.shp.parts)

    def length(self):
        return lengthOf(self.p, self.shp.parts)

def point_in_poly(x,y,poly):
    n = len(poly)
    inside = False
    p1x,p1y = poly[0]
    for i in range(1,n):
        p2x,p2y = poly[i]
        if y > min(p1y,p2y) and y <= max(p1y,p2y) and x <= max(p1x,p2x):
            if p1y != p2y:
                xints = (y-p1y)*(p2x-p1x)/(p2y-p1y)+p1x
            if p1x == p2x or x <= xints:
                inside = not inside
        p1x,p1y = p2x,p2y
    return inside
    
def is_point_inbox(point, bbox):
    return bbox[0] < point[0] < bbox[2] and bbox[1] < point[1] < bbox[3]
    
def isBoxDisjoin(boxa,boxb):
    return boxa[0] > boxb[2] or boxa[1] > boxb[3] or boxb[0] > boxa[2] or boxb[1] > boxa[3]

def is_poly_intersect(square_bboxP, polygon, bboxP):
    """
    whether a polygon share a common part with a square given in bbox form
    :rtype : bool
    """
    # quick filter: if their bboxes don't intersect, return False (90% of all cases)
    if isBoxDisjoin(square_bboxP,bboxP):
        return False

    square_bbox = [[square_bboxP[0],square_bboxP[1]],[square_bboxP[2],square_bboxP[3]]]
    p_bbox = [[bboxP[0],bboxP[1]],[bboxP[2],bboxP[3]]]    

    # if any point of the polygon is inside the square, return True. (8% of all cases, 95% of intersection)
    for point in polygon:
        if square_bbox[0][0] < point[0] < square_bbox[1][0] and square_bbox[0][1] < point[1] < square_bbox[1][1]:            
            return True

    # vice versa. (1.9% of all cases, 4.9% of intersection) [scanning line]
    y = [square_bbox[0][1], square_bbox[1][1]]
    count = [[[0, 0], [0, 0]], [[0, 0], [0, 0]]]  # low/high, left/right, /left/right
    for i in range(2):
        flag = (polygon[0][1] >= y[i])
        for j in range(1, len(polygon)):
            next_flag = (polygon[j][1] >= y[i])
            if next_flag != flag:
                if polygon[j][1] == polygon[j - 1][1]:
                    tmp_x = polygon[j][0]
                else:
                    tmp_x = float((y[i] - polygon[j - 1][1])) / (polygon[j][1] - polygon[j - 1][1]) * (
                        polygon[j][0] - polygon[j - 1][0]) \
                            + polygon[j - 1][0]
                if tmp_x < square_bbox[0][0]:
                    count[i][0][0] += 1
                else:
                    count[i][0][1] += 1

                if tmp_x < square_bbox[1][0]:
                    count[i][1][0] += 1
                else:
                    count[i][1][1] += 1
            flag = next_flag

    for group_count in count:
        for point_count in group_count:
            if point_count[0] & 1 == 1 and point_count[1] & 1 == 1:                
                return True
    
    # if any line of polygon intersects with any line of the square, return True (rarely the case, almost impossible)
    if count[0][0][0] < count[0][1][0] or count[1][0][0] < count[1][1][0]:        
        return True
    x = [square_bbox[0][0], square_bbox[1][0]]
    for i in range(2):
        flag = (polygon[0][0] >= x[i])
        for j in range(1, len(polygon)):
            next_flag = (polygon[j][0] >= x[i])
            if next_flag != flag:
                if polygon[j][0] == polygon[j - 1][0]:
                    tmp_y = polygon[j][1]
                else:
                    tmp_y = float((x[i] - polygon[j - 1][0])) / (polygon[j][0] - polygon[j - 1][0]) * \
                            (polygon[j][1] - polygon[j - 1][1]) + polygon[j - 1][1]
                if y[0] <= tmp_y <= y[1]:                    
                    return True
            flag = next_flag
    
    return False  # Disjoin

def dist_ponit_to_seg(p,a,b):
    ''' distance of point p to segment ab
    '''
    ap=[p[0]-a[0],p[1]-a[1]]
    ab=[b[0]-a[0],b[1]-a[1]]
    base=math.sqrt(ab[0]*ab[0]+ab[1]*ab[1])
    if base == 0:
        return math.sqrt(ap[0]*ap[0]+ap[1]*ap[1])
    tp=(ap[0]*ab[0]+ap[1]*ab[1])/base
    if tp<=0:
        return math.sqrt(ap[0]*ap[0]+ap[1]*ap[1])
    elif tp<=base:
        return abs((ap[0]*ab[1]-ap[1]*ab[0])/base)
    else:
        return math.sqrt((b[0]-p[0])*(b[0]-p[0])+(b[1]-p[1])*(b[1]-p[1]))


class Editor(Writer):
    def __init__(self, shapefile=None, shapeType=POINT, autoBalance=1):
        self.autoBalance = autoBalance
        if not shapefile:
            Writer.__init__(self, shapeType)
        elif is_string(shapefile):
            base = os.path.splitext(shapefile)[0]
            if os.path.isfile("%s.shp" % base):
                r = Reader(base)
                Writer.__init__(self, r.shapeType)
                self._shapes = r.shapes()
                self.fields = r.fields
                self.records = r.records()
                self.lens = len(self.records)

    def select(self, expr):
        """Select one or more shapes (to be implemented)"""
        # TODO: Implement expressions to select shapes.
        pass

    def delete(self, shape=None, part=None, point=None):
        """Deletes the specified part of any shape by specifying a shape
        number, part number, or point number."""
        # shape, part, point
        if shape and part and point:
            del self._shapes[shape][part][point]
        # shape, part
        elif shape and part and not point:
            del self._shapes[shape][part]
        # shape
        elif shape and not part and not point:
            del self._shapes[shape]
        # point
        elif not shape and not part and point:
            for s in self._shapes:
                if s.shapeType == 1:
                    del self._shapes[point]
                else:
                    for part in s.parts:
                        del s[part][point]
        # part, point
        elif not shape and part and point:
            for s in self._shapes:
                del s[part][point]
        # part
        elif not shape and part and not point:
            for s in self._shapes:
                del s[part]

    def point(self, x=None, y=None, z=None, m=None, shape=None, part=None, point=None, addr=None):
        """Creates/updates a point shape. The arguments allows
        you to update a specific point by shape, part, point of any
        shape type."""
        # shape, part, point
        if shape and part and point:
            try: self._shapes[shape]
            except IndexError: self._shapes.append([])
            try: self._shapes[shape][part]
            except IndexError: self._shapes[shape].append([])
            try: self._shapes[shape][part][point]
            except IndexError: self._shapes[shape][part].append([])
            p = self._shapes[shape][part][point]
            if x: p[0] = x
            if y: p[1] = y
            if z: p[2] = z
            if m: p[3] = m
            self._shapes[shape][part][point] = p
        # shape, part
        elif shape and part and not point:
            try: self._shapes[shape]
            except IndexError: self._shapes.append([])
            try: self._shapes[shape][part]
            except IndexError: self._shapes[shape].append([])
            points = self._shapes[shape][part]
            for i in range(len(points)):
                p = points[i]
                if x: p[0] = x
                if y: p[1] = y
                if z: p[2] = z
                if m: p[3] = m
                self._shapes[shape][part][i] = p
        # shape
        elif shape and not part and not point:
            try: self._shapes[shape]
            except IndexError: self._shapes.append([])

        # point
        # part
        if addr:
            shape, part, point = addr
            self._shapes[shape][part][point] = [x, y, z, m]
        else:
            Writer.point(self, x, y, z, m)
        if self.autoBalance:
            self.balance()

    def index_of_first_feature_contains_point(self, x, y):
        if hasattr(self,'root'):
            return self.treeQuery(x,y,self.root)
        try:
            return list(map(lambda i:self[i].does_contain_points(x,y), range(self.lens))).index(True)
        except ValueError:
            return -1
    
    def index_of_closest_feature_to_points(self, x, y):
        if self.shapeType != POINT:
            raise TypeError("This function can only be called by POINT shapefiles")
        if hasattr(self, 'root'):
            return self.treeClosest(x,y,self.root)
        try:
            return sorted([(distp2p(self.shape(i).points[0],[x,y]),i) for i in range(self.lens)])[0][1]
        except ValueError:
            return -1

    def dist_to_boundary(self,x,y):
        polyind=self.index_of_first_feature_contains_point(x,y)
        if polyind==-1:
            return -1,-1
        pts=self[polyind].p
        return polyind,min(map(lambda i: dist_ponit_to_seg([x,y],pts[i],pts[i+1]),range(len(pts)-1)))

    def reproj(self, inprj, outprj):
        inprj=Proj(init=inprj)
        outprj=Proj(init=outprj)
        for i,shp in enumerate(self.shapes()):
            for j,p in enumerate(shp.points):
                shp.points[j]=list(transform(inprj, outprj, *p))
            x,y=zip(*shp.points)
            self.shape(i).bbox=[min(x),min(y),max(x),max(y)]
                

    def validate(self):
        """An optional method to try and validate the shapefile
        as much as possible before writing it (not implemented)."""
        #TODO: Implement validation method
        pass

    def balance(self):
        """Adds a corresponding empty attribute or null geometry record depending
        on which type of record was created to make sure all three files
        are in synch."""
        if len(self.records) > len(self._shapes):
            self.null()
        elif len(self.records) < len(self._shapes):
            self.record()

    def __fieldNorm(self, fieldName):
        """Normalizes a dbf field name to fit within the spec and the
        expectations of certain ESRI software."""
        if len(fieldName) > 11: fieldName = fieldName[:11]
        fieldName = fieldName.upper()
        fieldName.replace(' ', '_')

    def __getitem__(self, index):
        return Feature(self, index)

    def appendField(self, fieldname, fieldtype, valueFunction):
        '''
        appendField(fieldname, fieldtype, valueFunction)
        fieldname = string
        fiedltype in ['double', 'int']
        valueFunction = lambda index:value_from(index)
        '''
        if fieldtype == 'double':
            self.fields.append([fieldname, 'F', 19, 11])
            for i in range(self.lens):
                self.records[i].append(valueFunction(i))
        elif fieldtype == 'int':
            self.fields.append([fieldname, 'N', 6, 0])
            for i in range(self.lens):
                self.records[i].append(valueFunction(i))

    def setField(self, fieldname, valueFunction):
        m = map(lambda x: x[0], self.fields)
        p = m.index(fieldname)
        for i in range(self.lens):
            self.records[i][p] = valueFunction(i)

    def clip(self, bbox):
        return self.subshp([i for i in range(self.lens) if not isBoxDisjoin(self.shape(i).bbox, bbox) ])
        
    def subshp(self,indiceslist):
        """ return a sub shapefile including records and geometries from
        startind to endind(not included)"""
        sub=Editor(None,self.shapeType)
        sub._shapes=[self._shapes[i] for i in indiceslist]
        sub.fields=self.fields
        sub.records=[self.records[i] for i in indiceslist]
        sub.lens=len(indiceslist)
        return sub

    def setrec(self,condition,op,standard,field,value):
        """ set field=value where condition<op>standard
        op=0,equl, op=0, less, op=1, greater """
        standard=float(standard)
        value=float(value)
        for i in range(self.lens):
            candidate=float(self[i][condition])
            flag=False
            if op=='=':
                flag=(candidate==standard)
            elif op=='<':
                flag=(candidate<standard)
            elif op=='>':
                flag=(candidate>standard)
            if flag:
                self[i][field]=value
        return self

    def select(self,condition,op,standard):
        """ select sub set of self which meets the condition """
        resultlist=[]
        standard=float(standard)
        for i in range(self.lens):
            flag=False
            candidate=float(self[i][condition])
            if op=='=':
                flag=(candidate==standard)
            elif op=='<':
                flag=(candidate<standard)
            elif op=='>':
                flag=(candidate>standard)
            if flag:
                resultlist.append(i)
        return self.subshp(resultlist)

    def sqlprocess(self,sqlstring):
        com=sqlstring.split(' ')
        print(com)
        if com[0]=='set':
            print(com[5],com[6],com[7],com[1],com[3])
            return self.setrec(com[5],com[6],com[7],com[1],com[3])
        else:
            print(com[3],com[4],com[5])
            return self.select(com[3],com[4],com[5])

    def strech_extent(self,targetbbox):
        '''bbox: [[lx,ly],[hx,hy]]
        '''
        selfbbox=self.bbox()
        selfbbox=[[selfbbox[0],selfbbox[1]],[selfbbox[2],selfbbox[3]]]
        width_scale=float(targetbbox[1][0]-targetbbox[0][0])/float(selfbbox[1][0]-selfbbox[0][0])
        height_scale=float(targetbbox[1][1]-targetbbox[0][1])/float(selfbbox[1][1]-selfbbox[0][1])
        for shp in self._shapes:
            for p in shp.points:
                p[0]=(p[0]-selfbbox[0][0])*width_scale+targetbbox[0][0]
                p[1]=(p[1]-selfbbox[0][1])*height_scale+targetbbox[0][1]




    def is_feature_intersect_box(self, i, box):
        if self.shapeType == POINT:
            return is_point_inbox(self.shape(i).points[0], box)
        elif self.shapeType == POLYGON:
            return is_poly_intersect(box,self.shape(i).points,self.shape(i).bbox)
        else:
            raise NotImplementedError('Feature intersection: only POINT and POLYGON are supported')
            
    def birth(self,node):
        if len(node[0])<2 or node[-1]>10:            
            return node
        tmp=node[1]
        bbox=[[tmp[0],tmp[1]],[tmp[2],tmp[3]]]
        mid=[0.5*(tmp[0]+tmp[2]),0.5*(tmp[1]+tmp[3])]
        for i in range(4):            
            x=(mid[0],bbox[i & 1][0])
            y=(mid[1],bbox[i >> 1][1])
            newbbox=[min(x),min(y),max(x),max(y)]            
            newshps=filter(lambda k: self.is_feature_intersect_box(k, newbbox), node[0])
            node[2].append(self.birth([newshps,newbbox,[],node[-1]+1])) # feature_id_set, boundingbox, children, depth
        #if node[-1]<6:
        #    print node[-1], node[1]
        return node

    def treeClosest(self, x, y, node):
        choice = len(node[0])
        if choice == 0:
            return -1
            
        if choice < 100:
            return sorted([(distp2p(self.shape(k).points[0],[x,y]),k) for k in node[0]])[0][1]
            
        if len(node[2])>0:
            midx=0.5*(node[1][0]+node[1][2])
            midy=0.5*(node[1][1]+node[1][3])            
            return self.treeClosest(x,y,node[2][(x>midx)+(y>midy)*2])    
        
        return sorted([(distp2p(self.shape(k).points[0],[x,y]),k) for k in node[0]])[0][1]
        
    def treeQuery(self,x,y,node):
        choice=len(node[0])
        if choice==0:
            return -1
        if choice == 1:
            return node[0][0] if self[node[0][0]].does_contain_points(x,y) else -1
        if len(node[2])>0:
            midx=0.5*(node[1][0]+node[1][2])
            midy=0.5*(node[1][1]+node[1][3])            
            return self.treeQuery(x,y,node[2][(x>midx)+(y>midy)*2])    
        tmp=node[0][-2]
        for p in node[0]:
            if self[p].does_contain_points(x,y):
                return p
            if p == tmp:
                return node[0][-1]

    def printNode(self, node, f):        
        f.write(str(node[-1])+'\n')
        for i in node[1]:
            f.write(str(i)+' ')
        f.write('\n')
        for i in node[0]:
            f.write(str(i)+' ')
        f.write('\n')
        for k in node[2]:
            self.printNode(k,f)
            
    def readNode(self,f):
        depth=int(f.readline().strip())
        bbox=map(float,f.readline().strip().split())
        choice=map(int,f.readline().strip().split())
        if len(choice)<2 or depth>10:
            child=[]            
        else:
            child=[self.readNode(f) for i in range(4)]
        #if depth < 3:
        #    print depth, bbox
        return [choice,bbox,child,depth]

    def buildQuadTree(self,quadFile=None):
        if quadFile == None:
            self.root=self.birth([range(self.lens),self.bbox(),[],0])
        else:
            f=open(quadFile)
            self.root=self.readNode(f)
            f.close()

    def loadFromTxt(self, inFile):
        with open(inFile) as input:
            for i in range(self.lens):
                for j in range(len(self[i].p)):
                    line = input.next()
                    if line == '\n':
                        line = input.next()
                    self[i].p[j]=map(float,line.split()[:2])

    def export2txt(self, outFile):
        with open(outFile,'w') as output:
            output.write('\n'.join(''.join('%f %f\n'%(p[0],p[1]) for p in self[i].p) for i in range(self.lens)))
    
    #def DPSimplify(self, epsilon):
    #    for i in range(self.lens):
    #        self[i].DPSimplify(epsilon)
    #    return self
    
def areaOf(polygon,parts=[0]):
    pp = list(parts) + [len(polygon)]
    return sum(simplex_area(polygon[pp[i]:pp[i+1]]) for i in range(len(pp) - 1))

def simplex_area(polygon):
    """
    the area of a single polygon
    """
    if len(polygon) < 3:
        return 0
    ans = 0
    last = polygon[0]
    for i in range(1, len(polygon))+[0]:
        new = polygon[i]
        ans += last[1]*new[0]-last[0]*new[1]
        last = new
    return ans/2.0

def lengthOf(polygon, parts=[0]):    
    pp = list(parts) + [len(polygon)]
    return sum(distp2p(polygon[k],polygon[k+1]) for i in range(len(pp)-1) for k in range(pp[i],pp[i+1] - 1))


def distp2p(a,b):
    return math.sqrt((a[0]-b[0])**2+(a[1]-b[1])**2)

#def DPSimplify(polygon, epsilon, parts=[0]):
#    pp = list(parts) + [len(polygon)]
#    res = [rdp(polygon[pp[i]:pp[i+1]], epsilon) for i in range(len(pp) - 1)]
#    newparts = [0] * len(parts)
#    for i in range(len(parts)-1):
#        newparts[i+1] = newparts[i] + len(res[i])        
#    return [p for pts in res for p in pts], newparts
    
def mergeshp(e1,e2):
    """ merge editor1 and editor2 into one shapefile if their fields and
    shapeType matches"""
    if e1.shapeType==e2.shapeType and e1.fields==e2.fields:
        e=Editor(None,e1.shapeType)
        e.fields=e1.fields
        e._shapes=e1._shapes+e2._shapes
        e.records=e1.records+e2.records
        e.lens=e1.lens+e2.lens
        return e
    else:
        raise Exception('attempt to merge unmatch shapefiles!')

def buildQuadTree(shpfile):
	e = Editor(shpfile)
	e.buildQuadTree()
	with open(shpfile.partition('.')[0]+'.qdt','w') as output:
		e.printNode(e.root,output)

# Begin Testing
def test():
    import doctest
    doctest.NORMALIZE_WHITESPACE = 1
    doctest.testfile("README.txt", verbose=1)

if __name__ == "__main__":
    """
    Doctests are contained in the module 'pyshp_usage.py'. This library was developed
    using Python 2.3. Python 2.4 and above have some excellent improvements in the built-in
    testing libraries but for now unit testing is done using what's available in
    2.3.
    """
    test()

