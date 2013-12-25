"""
A DPS Meter for Guild Wars 2. The meter reads the selected target's health
and calculates the dps done.
"""
from ConfigParser import ConfigParser
from ui.elements import HealthBar, DPSDisplay, Timer
from ui.elements import DisplayEnableCheckbox, Logger, parsegeometry
from ctypes import windll
import Tkinter as tk
import aproc
import os
import sys
import pickle
import win32api, win32gui, win32con

_DIR = os.path.split(__file__)[0]
_POSPKL = os.path.join(_DIR, 'pos.pkl')

TARGET_HEALTH_BASE = 0x013F2AB4
TARGET_HEALTH_OFFSET = [0x34, 0x150, 0x8]
# if target is a structure, i.e dummy, wall etc.
TARGET_HEALTH_OBJ_BASE = 0x013F2B18
TARGET_HEALTH_OBJ_OFFSET = [0x34, 0x168, 0x8]
# target is a "world boss"
TARGET_HEALTH_WBOSS_BASE = TARGET_HEALTH_OBJ_BASE
TARGET_HEALTH_WBOSS_OFFSET = [0x34, 0x44, 0x3C, 0x17C, 0x8]

INCOMBAT_ADDR1 = 0x0171DF1C
INCOMBAT_ADDR2 = 0x0171D330
INCOMBAT_VALUE = 1065353216


# Ability to change the addr offsets without changing the code.
# useful for when it is packaged as .exe
CONFIG_DCT = { 'TARGET_HEALTH' : ['BASE', 'OFFSET',
                                  'OBJ_BASE', 'OBJ_OFFSET',
                                  'WBOSS_BASE', 'WBOSS_OFFSET'],
               'INCOMBAT': ['ADDR1', 'ADDR2', 'VALUE']}

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

        self._possible_targets = [ (self.gw2base + TARGET_HEALTH_BASE,
                                    TARGET_HEALTH_OFFSET),
                                   (self.gw2base + TARGET_HEALTH_WBOSS_BASE,
                                    TARGET_HEALTH_WBOSS_OFFSET),
                                   (self.gw2base + TARGET_HEALTH_OBJ_BASE,
                                    TARGET_HEALTH_OBJ_OFFSET)]
        self._ms = ms

        self._sample_size_1s = int(1000/self._ms)
        self._health_base = self.gw2base + TARGET_HEALTH_BASE
        self._prev_health = 0
        self._ptargetaddr = None

    def get_health_value_pairs(self, target_addr):
        """
        Read the current health and max health at the specified addrs
        """
        if target_addr:
            chealth = self._proc.read_memory(target_addr, rtntype='float')
            mhealth = self._proc.read_memory(target_addr + 0x4, rtntype='float')
            return chealth, mhealth

    def incombat(self):
        """
        Returns True if we are in combat, False otherwise
        """
        # value one is 0 when in combat, 1 when not in combat
        value1 = self._proc.read_memory(INCOMBAT_ADDR1)
        # this is a 4byte value equal to IN_COMBAT_VALUE when in combat
        value2 = self._proc.read_memory(INCOMBAT_ADDR2)
        return value1 == 0 or value2 == INCOMBAT_VALUE

    def selected_target(self):
        """
        Returns a tuple of (health address, current health, max health) of the
        selected targed. If no tharget is selected returns a tuple of
        (None, None, -1)
        """
        mhealth = -1

        # go throught all the possible target types, and return the valid addrs
        for addr, offset in self._possible_targets:
            ptrail = self._proc.pointer_trail(addr,
                                              offset,
                                              rtntype='float')
            if ptrail.addr and int(ptrail.value):
                mhealth = self._proc.read_memory(ptrail.addr + 0x4, 'float')
                if mhealth > 0 and mhealth >= int(ptrail.value):
                    break

        return ptrail.addr, ptrail.value, mhealth

    def get_health(self):
        """
        Returns the health of the target. Health can also be -1 to indicate
        no target is selected.
        """
        taddr, thealth, mhealth = self.selected_target()

        health = thealth if thealth else 0

        self._target_change = False
        if taddr is None:
            # If ptrail is none no target selected
            # No target return -1
            health = -1
            if self._ptargetaddr:
                if not self._proc.read_memory(self._ptargetaddr, rtntype='int'):
                    health = 0
        else:
            if taddr != self._ptargetaddr:
                # Target Change
                self._target_change = True

        self._ptargetaddr = taddr
        return health, mhealth

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
        self._ms = 250
        self._sustained_dps = []
        self._instant_dps = []
        self._second = int(1000/self._ms)
        self._tick = 0

        self._dmg = DamageMeter(ms=self._ms)

        self.dps_display = DisplayEnableCheckbox(self, "Display DPS",
                                                 DPSDisplay, bg=BACKGROUND)
        self.dps_display.grid(row=0, column=0)

        self.health_bar = DisplayEnableCheckbox(self, "Display Taget Health",
                                                HealthBar, bg=BACKGROUND)
        self.health_bar.grid(row=1, column=0)

        self.timer = DisplayEnableCheckbox(self, "Timer", Timer,
                                           self._dmg, bg=BACKGROUND)
        self.timer.grid(row=2, column=0)


        self.toplevel_wins = {   'Main'        : self,
                                 'Health Bar'  : self.health_bar,
                                 'DPS Display' : self.dps_display,
                                 'Timer'       : self.timer}

        self.logger = Logger(self, "Log to file",
                             os.path.join(_DIR, 'dps.txt'))
        self.logger.grid(row=3, column=0)

        self.load_data()
        self.protocol('WM_DELETE_WINDOW', self._onclose)

    def log_tofile(self, inst):
        """
        Everysecond log the inst damage to the file
        """
        self._tick += 1
        if self._tick >= self._second:
            self.logger.log(inst)
            self._tick = 0

    def click_control(self, control):
        """
        Disables/Enables click control.

        control = True to enable click
        control = False to disable click
        """
        cal_nval = lambda val: val & (~ win32con.WS_EX_TRANSPARENT) if control\
                              else val | win32con.WS_EX_TRANSPARENT


        for ui in [self.health_bar, self.timer, self.dps_display]:
            hwnd = ui.get_window_hwnd()
            if hwnd:
                val  = win32gui.GetWindowLong(hwnd, win32con.GWL_EXSTYLE)
                nval = cal_nval(val)
                if nval != val:
                    win32gui.SetWindowLong(hwnd, win32con.GWL_EXSTYLE, nval)

    def check_control_loop(self):
        """
        Poll to see if the ALT key is pressed, if it is, allow control, else
        control is disabled
        """
        state = win32api.GetAsyncKeyState(win32con.VK_MENU)
        self.click_control(state != 0)
        self.after(100, self.check_control_loop)

    def run(self):
        dps, chealth, mhealth = self._dmg.target_health_values()
        inst = self._dmg.calculate_dps(self._instant_dps, dps)
        sustained = self._dmg.calculate_dps(self._sustained_dps, dps,
                                            sample_window_size=5)

        incombat = self._dmg.incombat()
        self.dps_display.update_data(inst, sustained, incombat)
        self.health_bar.update_data(chealth, mhealth)

        if incombat:
            self.log_tofile(inst)

        self.after(self._ms, self.run)

    def get_position(self):
        """
        Get the x, y position
        """
        return parsegeometry(self.geometry())[2:]

    def set_position(self, x, y):
        """
        Set the x, y position
        """
        self.geometry('%s%s' % (x, y))

    def _onclose(self):
        """
        Pickle the positions when closing the app
        """
        dat = {name: obj.get_position()
               for name, obj in self.toplevel_wins.iteritems()}

        with open(_POSPKL, 'wb') as fpkl:
            pickle.dump(dat, fpkl)
        self.quit()

    def load_data(self):
        """
        Load the pickle if it exists
        """
        if os.path.isfile(_POSPKL):
            with open(_POSPKL, 'rb') as fpkl:
                dat = pickle.load(fpkl)
                for name, obj in self.toplevel_wins.iteritems():
                    if dat.get(name, None):
                        obj.set_position(*dat[name])

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
                if config.has_option(prefix, suffix):
                    val = config.get(prefix, suffix)
                    if 'OFFSET' in suffix:
                        val = [int(i, 0) for i in filter(None, val.split(','))]
                    else:
                        val = int(val, 0)
                    globals()[prefix + '_' + suffix] = val

    app = Main()
    app.wm_attributes("-topmost", 1)
    app.resizable(width=False, height=False)
    app.wm_title("DPS Display by balkanpy")
    app.health_bar.set_object_attributes('-alpha', 0.6)
    app.dps_display.set_object_attributes('-alpha', 0.6)
    app.timer.set_object_attributes('-alpha', 0.6)
    app.run()
    app.check_control_loop()
    #hide the console window
    aproc.hide_window(None, sys.argv[0])
    app.mainloop()