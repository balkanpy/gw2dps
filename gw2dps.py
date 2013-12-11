"""
A DPS Meter for Guild Wars 2. The meter reads the selected target's health
and calculates the dps done.
"""
from ConfigParser import ConfigParser
from ui.elements import HealthBar, DPSDisplay
from ui.elements import DisplayEnableCheckbox
from ctypes import windll
import Tkinter as tk
import aproc
import os
import sys

TARGET_HEALTH_BASE = 0x013F2AB4
TARGET_HEALTH_OFFSET = [0x34, 0x150, 0x8]
# if target is a structure, i.e dummy, wall etc.
TARGET_HEALTH_OBJ_BASE = 0x013F2B18
TARGET_HEALTH_OBJ_OFFSET = [0x34, 0x168, 0x8]


INCOMBAT_ADDR1 = 0x0171DF1C
INCOMBAT_ADDR2 = 0x0171D330
INCOMBAT_VALUE = 1065353216

TARGET_TYPE_INDICATOR_ADDR = 0x0131DF60
TARGET_TYPE_NONE = 1149386752
TARGET_TYPE_REGULAR = 1148387328
TARGET_TYPE_OBJ = 1149009920


# Ability to change the addr offsets without changing the code.
# useful for when it is packaged as .exe
CONFIG_DCT = { 'TARGET_HEALTH' : ['BASE', 'OFFSET'],
               'INCOMBAT': ['ADDR1', 'ADDR2', 'VALUE'],
               'TARGET_TYPE': ['INDICATOR_ADDR', 'NONE', 'REGULAR', 'OBJ']}

BACKGROUND ='#222222'
class DamageMeter:
    """
    DamageMeter class used for getting the dmg done onto target, and calculate
    the dps based on the sample period in milliseconds (ms)
    The get_dmg needs to be called periodically at the specified sample period
    for the calculations to be accurate
    """
    def __init__(self, ms=500):
        hwnd = aproc.FindWindow('ArenaNet_Dx_Window_Class', 'Guild Wars 2')

        if hwnd:
            pid = aproc.GetWindowThreadProcessId(hwnd)
        else:
            err = "Please start Guild Wars 2, and wait for " + \
                  "the Character Select Screen to load before " + \
                  "starting the DPS Meter"

            windll.user32.MessageBoxA(None, err, 'DPS Meter Error', 0)
            sys.exit(-1)

        self._proc = aproc.Proc(pid)
        self.gw2base = self._proc.base_addr
        self._target_addr_table = \
        {
            # Selected Target type: (base addr, offsets)
            # "regular" target, enemies
            TARGET_TYPE_REGULAR: (self.gw2base + TARGET_HEALTH_BASE,
                                      TARGET_HEALTH_OFFSET),
            # object target, e.i walls, dummies, etc
            TARGET_TYPE_OBJ: (self.gw2base + TARGET_HEALTH_OBJ_BASE,
                                  TARGET_HEALTH_OBJ_OFFSET)
        }
        self._ms = ms

        self._sample_size_1s = int(1000/self._ms)
        self._health_base = self.gw2base + TARGET_HEALTH_BASE

        self._prev_health = 0
        self._ptargetaddr = None

    def incombat(self):
        """
        Returns True if we are in combat, False otherwise
        """
        # value one is 0 when in combat, 1 when not in combat
        value1 = self._proc.read_memory(INCOMBAT_ADDR1)
        # this is a 4byte value equal to IN_COMBAT_VALUE when in combat
        value2 = self._proc.read_memory(INCOMBAT_ADDR2)
        return value1 == 0 or value2 == INCOMBAT_VALUE

    def get_health(self):
        """
        Returns the health of the target. Health can also be -1 to indicate
        no target is selected.
        """
        target_type = self._proc.read_memory(self.gw2base + TARGET_TYPE_INDICATOR_ADDR,
                                             rtntype='int')

        if target_type in self._target_addr_table:
            health_base_addr = self._target_addr_table[target_type][0]
            health_offset = self._target_addr_table[target_type][1]
        else:
            return -1, -1

        ptrail = self._proc.pointer_trail(health_base_addr,
                                          health_offset,
                                          rtntype='float')

        max_health = -1
        if ptrail.addr:
            max_health = self._proc.read_memory(ptrail.addr + 0x4, 'float')

        health = ptrail.value if ptrail.value else 0

        self._target_change = False
        if ptrail.addr is None:
            # If ptrail is none no target selected
            # No target return -1
            health = -1
            if self._ptargetaddr:
                if not self._proc.read_memory(self._ptargetaddr, rtntype='int'):
                    health = 0
        else:
            if ptrail.addr != self._ptargetaddr:
                # Target Change
                self._target_change = True

        self._ptargetaddr = ptrail.addr
        return health, max_health

    def target_health_values(self, normalize=False):
        """
        Get the damage done on the target. Damage is
        calculated based on health[n] - health[n-1].

        This method needs to be called periodically at the specified sample
        period (ms) for everything to work properly
        """
        health, max_health = self.get_health()
        dmg = 0
        if health != -1 and not self._target_change:
            # There is a target selected and this is the same target on the
            # previous iteration. Calculate the dmg
            dmg = self._prev_health - health

        if normalize:
            dmg = (dmg / max_health)*10000

        self._prev_health = health
        return dmg if dmg > 0 else 0, health, max_health

    def calculate_dps(self, sample_lst, dmg, sample_window_size=1):
        """
        Calculate the dps.
        By deafult it returns the dps averaged over 1s (sample_window_size=1)
        this is defined as the Instant dps.

        sample_lst -
            a list used to store the dmg samples. Number of samples it
            would store is based on sample_window_size and the sample period.
            For sample period of 250ms, and sample_window_size, sample_lst will
            have at most 4 values (4 * 250ms= 1 seconds). When list is filled,
            the first sample will be removed and a new one will be appended.

        dmg -
            Damage taked by target.

        sample_window_size -
            Number of seconds to average the dps.

        This method needs to be called everytime a dmg is calculated
        """
        sample_lst.append(dmg)
        dps = 0
        if len(sample_lst) >= sample_window_size * self._sample_size_1s:
            dps = sum(sample_lst)/sample_window_size
            del sample_lst[0]
        return int(dps)


class Main(tk.Tk):
    def __init__(self, *args, **kwargs):
        tk.Tk.__init__(self, *args, **kwargs)
        self.dps_display = DisplayEnableCheckbox(self, "DPS",
                                                 DPSDisplay, bg=BACKGROUND)
        self.dps_display.grid(row=0, column=0)

        self.health_bar = DisplayEnableCheckbox(self, "Taget Health",
                                                HealthBar, bg=BACKGROUND)
        self.health_bar.grid(row=1, column=0)
        self._dmg = DamageMeter(ms=250)

        self._sustained_dps = []
        self._instant_dps = []

    def run(self):
        dps, chealth, mhealth = self._dmg.target_health_values()
        inst = self._dmg.calculate_dps(self._instant_dps, dps)
        sustained = self._dmg.calculate_dps(self._sustained_dps, dps,
                                            sample_window_size=5)

        self.dps_display.update_data(inst, sustained, self._dmg.incombat())
        self.health_bar.update_data(chealth, mhealth)
        self.after(250, self.run)

if __name__ == '__main__':
    # ability to change the memory addresses, and offesets without chaning
    # in the file. This is useful then packaged as an exe. If there is a
    # memory.txt file in the working directory of the script, it will be loaded
    # and the global variables overwritten
    if os.path.exists('./memory.txt'):
        config = ConfigParser()
        config.read('./memory.txt')

        for prefix, suffixes in CONFIG_DCT.iteritems():
            for suffix in suffixes:
                val = config.get(prefix, suffix)
                if 'OFFSET' in suffix:
                    val = [int(i, 0) for i in filter(None, val.split(','))]
                else:
                    val = int(val, 0)
                globals()[prefix + '_' + suffix] = val

    app = Main()
    app.wm_attributes("-topmost", 1)
    app.geometry("%dx%d" % (150, 50))
    app.resizable(width=False, height=False)
    app.wm_title("DPS Display by balkanpy")
    app.health_bar.set_object_attributes('-alpha', 0.6)
    app.dps_display.set_object_attributes('-alpha', 0.6)
    app.run()
    app.mainloop()