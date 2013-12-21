"""
This ia prototype module i created for reading process memories. Had no time
to finish it and organised it nicely but it still eneded up being used in the
dps meter.
"""
from ctypes import *
import struct
import os

kernel32 = windll.kernel32
psapi = WinDLL('Psapi.dll')

PROCESS_ALL_ACCESS = 0x1F0FFF

MAX_PATH = 260
STRUCT_CTYPE_CODE_AND_SIZE =  { 'short' : ('h' , 2),
                                'unsigned_short' : ('H', 2),
                                'int'   : ('i', 4),
                                'float' : ('f', 4)}

def GetWindowThreadProcessId(hwnd):
    """
    GetWindowThreadProcessId
    """
    pid = c_int(0)
    windll.user32.GetWindowThreadProcessId(hwnd, byref(pid))
    return pid.value

def FindWindow(class_name, window_text):
    """
    FindWindow Function
    """
    return windll.user32.FindWindowA(c_char_p(class_name),
                                     c_char_p(window_text))


def hide_window(class_name, window_text):
    """
    Hides the Window
    """
    hwnd = FindWindow(class_name, window_text)

    if not hwnd:
        return False

    windll.user32.ShowWindow(hwnd, c_int(0))
    return True


class MODULEINFO(Structure):
    _fields_ = [
        ("lpBaseOfDll",     c_void_p),    # remote pointer
        ("SizeOfImage",     c_uint),
        ("EntryPoint",      c_void_p),    # remote pointer
        ]

def _struct_type(cdatatype):
    """
    Returns the type to convert
    """
    return STRUCT_CTYPE_CODE_AND_SIZE[cdatatype][0]

def _convert(buf, datatype = 'int'):
    """
    Attempt to conver the buffer to standard endian for the lenght type specified
    """
    rtn_str = struct.Struct('@' + _struct_type(datatype))
    return rtn_str.unpack_from(buf)[0]

class Proc(object):
    def __init__(self, pid):
        self.hproc = None
        self.pid = pid
        self.open_process()
        self.base_addr = self.find_base_addr(self.get_image_name())

    def open_process(self):
        self.hproc = kernel32.OpenProcess(PROCESS_ALL_ACCESS, False, self.pid)
        return self.hproc

    def read_memory(self, address, rtntype='int'):
        """
        Reads the process memory and returns it in little endian
        """
        length = STRUCT_CTYPE_CODE_AND_SIZE[rtntype][1]

        buf = create_string_buffer(length)
        count = c_ulong()

        rv = kernel32.ReadProcessMemory(self.hproc, address,
                                        buf, length, byref(count))

        if not rv:
            # failed to read
            return False
        else:
            return _convert(buf, rtntype)

    def get_image_name(self):
        """
        Returns the image name of the process
        """
        img = (c_char*MAX_PATH)()
        psapi.GetProcessImageFileNameA(self.hproc, img, MAX_PATH)
        return os.path.split(img.value)[-1]

    def enum_modules(self):
        """
        Calls EnumProcessModules to enumerate all the processes

        Returns: A list of hModules
        """
        size = 0x1000

        lpcbNeeded = c_uint(size)
        lphModule = (c_void_p * (size//sizeof(c_void_p)))()
        psapi.EnumProcessModules(self.hproc, byref(lphModule),
                                 lpcbNeeded, byref(lpcbNeeded))

        return  [lphModule[index] for index in
                    xrange(0, int(lpcbNeeded.value // sizeof(c_void_p)))]

    def get_module_names(self):
        """
        Returns module names
        """
        for module in self.enum_modules():
            modname = c_buffer(280)
            psapi.GetModuleFileNameExA(self.hproc, module,
                                       modname, sizeof(modname))
            print modname.value

    def _get_base(self, hmodule):
        """
        Returns the lpBaseOfDll for the specified hmodule
        """
        info = MODULEINFO()
        psapi.GetModuleInformation(self.hproc, hmodule,
                                   byref(info),sizeof(info))
        return info.lpBaseOfDll

    def find_base_addr(self, module_name):
        """
        Attempts to find the base address for the specified module_name
        """
        modules = self.enum_modules()

        for module in modules:
            modname = c_buffer(280)
            psapi.GetModuleFileNameExA(self.hproc, module,
                                       modname, sizeof(modname))
            if module_name in modname.value:
                return self._get_base(module)

    def pointer_trail(self, base, offsets, size=4, rtntype='int'):
        """
        Goes throug the pointer trails to find the value pointed by the
        last pointer

        Returns None if failed to read the trail (Null pointer found)
        """
        starting = base
        pointed = self.read_memory(starting, 'int')
        ptrail = type('ptrail', (), {'addr': None, 'value': None})

        isvalid = lambda pointer: pointer > 0

        if not isvalid(pointed):
            return ptrail

        for offset in offsets[:-1]:
            addr = pointed + offset
            pointed = self.read_memory(addr, 'int')
            if not isvalid(pointed):
                return ptrail

        addr = pointed + offsets[-1]
        if not isvalid(addr):
            return ptrail

        ptrail.addr = addr
        ptrail.value = self.read_memory(ptrail.addr, rtntype)

        return ptrail