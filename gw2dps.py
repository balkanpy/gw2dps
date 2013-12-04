"""
A DPS Meter for Guild Wars 2. The meter reads the selected target's health
and calculates the dps done.
"""
from ConfigParser import ConfigParser
from ui.elements import HealthBar, DamageDisplay, SummaryTab
from ctypes import windll
import Tkinter as tk
import subprocess
import aproc
import re
import os
import sys

TARGET_HEALTH_BASE = 0x13EB0B4
TARGET_HEALTH_OFFSET = [0x34, 0x150, 0x8]

INCOMBAT_ADDR1 = 0x0171654C
INCOMBAT_ADDR2 = 0x01715970
INCOMBAT_VALUE = 1065353216

# Ability to change the addr offsets without changing the code.
# useful for when it is packaged as .exe
CONFIG_DCT = { 'TARGET_HEALTH' : ['BASE', 'OFFSET'],
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
        tasklist = subprocess.check_output(
                   'tasklist /FI "Imagename eq Gw2.exe"')

        try:
            pid = int(re.search(r'Gw2.exe\s*(\d+)\s*', tasklist).group(1))
        except Exception:
            err = "Please start Guild Wars 2 before starting the DPS Meter"
            windll.user32.MessageBoxA(None, err, 'DPS Meter Error', 0)
            sys.exit(-1)
        self._proc = aproc.Proc(pid)
        self._ms = ms

        self._sample_size_1s = int(1000/self._ms)
        self.gw2base = self._proc.find_base_addr("Gw2.exe")
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
        Returns the health of the target. Health and also be -1 to indicate
        no target is selected.
        """
        ptrail = self._proc.pointer_trail(self._health_base,
                                          TARGET_HEALTH_OFFSET,
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
            # There is a target selected and htis is the same target on the
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

class MainApp(tk.Tk):
    """
    Main tk app
    """
    def __init__(self, *args, **kwargs):
        tk.Tk.__init__(self, *args, **kwargs)
        self.overrideredirect(True)
        label = tk.Label(self, text="Click & drag to move",
                         font=("Helvetica", 8), fg='white',
                         bg=BACKGROUND, anchor=tk.W)

        label.grid(row=0, column=0, columnspan=2)
        tk.Button(self, text='x', font=("Times", 6), command=self.quit,
                  bg=BACKGROUND, fg='white').grid(row=0, column=2)

        self._normalize = tk.BooleanVar()
        self._thealth_display = tk.BooleanVar()
        self._normalize.set(False)
        self._thealth_display.set(False)

        self._ms = kwargs.get('ms', 250)
        self._dmg = DamageMeter(ms=self._ms)
        # lists for storing the dmg samples
        self._sustained_dps = []
        self._instant_dps = []

        # isntant dps display
        instant, sustained = "Instant:", "Sustained:"
        self.instant = DamageDisplay(self, instant, self._ms, bg=BACKGROUND)
        self.instant.grid(row=2, column=1)
        self._pop_up_frame1 = SummaryTab(self, text=instant, bg=BACKGROUND)

        # sustainted dps
        self.sustained = DamageDisplay(self, sustained, self._ms, bg=BACKGROUND)
        self._pop_up_frame2 = SummaryTab(self, text=instant, bg=BACKGROUND)
        self.sustained.grid(row=3, column=1)

        # Create the Health Bar
        self.healthbar = HealthBar(self, bg=BACKGROUND)
        self.healthbar.attributes('-alpha', 0.6)

        label.bind("<ButtonPress-1>", self._start_move)
        label.bind("<ButtonRelease-1>", self._stop_move)
        label.bind("<B1-Motion>", self._motion)
        # bind the mouse over display for the summary tabs
        for binder in [self.sustained, self.instant]:
            binder.bind("<Enter>", self.display_on_mouse_over)
            binder.bind("<Leave>", self.display_on_mouse_over)

    def display_on_mouse_over(self, event):
        """
        On mouseover display the summary tab
        """
        if event.type == '7':
            self._pop_up_frame1.grid(row=5, column=1)
            self._pop_up_frame2.grid(row=6, column=1)
        else:
            self._pop_up_frame1.grid_forget()
            self._pop_up_frame2.grid_forget()

    def run(self):
        """
        Main loop of the app
        """
        dps, health, mhealth = self._dmg.target_health_values()
        # instand dps is the dps done in one second
        instant_dps =  self._dmg.calculate_dps(self._instant_dps, dps)
        # sustained dps is calculated over 5 seconds
        sustained_dps = self._dmg.calculate_dps(self._sustained_dps,
                                                dps, sample_window_size=5)

        incombat_indicator = self._dmg.incombat()

        self.instant.display_dps(instant_dps, incombat_indicator)
        self.sustained.display_dps(sustained_dps, incombat_indicator)

        self._pop_up_frame1.setvalues(self.instant.max,
                                      self.instant.prev_incombat_avg)
        self._pop_up_frame2.setvalues(self.sustained.max,
                                      self.sustained.prev_incombat_avg)

        health = health if health > 0 else 0
        mhealth = mhealth if mhealth > 0 else 0

        self.healthbar.update_health(health, mhealth)
        # loop back to this method
        self.after(self._ms, self.run)

    def _reset_values(self):
        """
        Reset the max, and combat average values (Not Fully Implemented!!!)
        """
        self.instant.reset()
        self.sustained.reset()
        self._sustained_dps = []
        self._instant_dps = []

    def _start_move(self, event):
        """
        Start Move
        """
        self.x , self.y = event.x, event.y

    def _stop_move(self, event):
        """
        Stop move
        """
        self.x, self.y = None, None

    def _motion(self, event):
        """
        Bind method for B1-Motion
        """
        dx = event.x - self.x
        dy = event.y - self.y
        self.geometry("+%s+%s" % (self.winfo_x() + dx, self.winfo_y() + dy))

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

    app = MainApp()
    app.config(background=BACKGROUND)
    app.wm_attributes('-toolwindow', 1)
    app.wm_attributes("-topmost", 1)
    app.attributes("-alpha", 0.6)
    app.run()
    app.mainloop()