"""
A DPS Meter for Guild Wars 2. The meter reads the selected target's health
and calculates the dps done.
"""
from ConfigParser import ConfigParser
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

def last_nonzero_value_index(lst):
    """
    Return index of the last non-zeron value. If no zeros found, return None
    """
    for index, value in enumerate(reversed(lst)):
        if value != 0:
            return len(lst) - 1 - index
    return None

class SummaryTab(tk.Frame):
    """
    Fram that will pop up when hovered over the damage indicators
    """
    def __init__(self, *args, **kwargs):

        if 'text' in kwargs:
            text = kwargs.pop('text')
        else:
            text = ''

        tk.Frame.__init__(self, *args, **kwargs)
        tk.Label(self, text=text, font=("Helvetica", 8), width=8,
                 fg='white', bg='#222222', anchor=tk.E).grid(row=0,column=0)

        self._value1label = tk.Label(self, text='', font=("Helvetica", 8),
                                     width=6, bg='#222222',
                                     fg='red', anchor=tk.W)

        self._value2label = tk.Label(self, text='', font=("Helvetica", 8),
                                     fg='orange',width=6,
                                     bg='#222222', anchor=tk.W)

        self._value1label.grid(row=0, column=1)
        self._value2label.grid(row=0, column=2)
        # inital values
        self.value1, self.value2 = None, None

    def setvalues(self, value1, value2):
        """
        Set the values in the labels only if they are different
        """
        if value1 != self.value1:
            self._value1label.config(text='%s' % value1)
            self.value1 = value1

        if value2 != self.value2:
            self._value2label.config(text='%s' % value2)
            self.value2 = value2

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
        return health

    def get_dmg(self):
        """
        Get the damage done on the target. Damage is
        calculated based on health[n] - health[n-1].

        This method needs to be called periodically at the specified sample
        period (ms) for everything to work properly
        """
        health = self.get_health()
        dmg = 0
        if health != -1 and not self._target_change:
            # There is a target selected and htis is the same target on the
            # previous iteration. Calculate the dmg
            dmg = self._prev_health - health

        self._prev_health = health
        return dmg if dmg > 0 else 0

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

class DamageDisplay(tk.Frame):
    """
    TK frame used fro displaying the damage
    """
    def __init__(self, root, text, refresh_ms, *args, **kwargs):
        tk.Frame.__init__(self, root, *args, **kwargs)
        bg = kwargs.get('bg')

        tk.Label(self, font=('times', 15, 'bold'), borderwidth=0,
                 text=text, bg=bg, fg='white', anchor=tk.E, width=8).grid(row=0)

        self._label = tk.Label(self, font=(None, 15), width=6, bg=bg)
        self._label.grid(row=0, column=1)

        self._ms = refresh_ms
        self._max_display_ticks = 0

        self._incombat_samples = []
        self.prev_incombat_avg = 0
        self.max = 0

        # dict to store the info about the display
        self._display_info = {'value': 0,
                              'font': ('times',15, 'bold'),
                              'colour': 'white'}

    def _display_max(self, period=3):
        """
        Display the max dps for the specified period in seconds

        period - Number of seconds to keep the display
        """
        self.freeze_display(self.max, period, colour='red')

    def freeze_display(self, value, period, **kwargs):
        """
        Freeze the display to display the value for the speficied period (secs)
        """
        self._max_display_ticks = int(period*1000/self._ms)
        kwargs['overwrite'] = True
        self._set_display(value, **kwargs)

    def _set_display(self, value,
                     font='time',
                     size=15,
                     colour='white',
                     typeface='bold',
                     overwrite=False):
        """
        Set the display with the specified value. The kwargs determined the
        colour, size, typeface and font of the text.

        overwrite - change display even if it was "frozen"
        """
        if not self._isfrozen() or overwrite:
            self._display_info['font'] = (font, size, typeface)
            self._display_info['value'] = value
            self._display_info['colour'] = colour

    def _isfrozen(self):
        """
        Return True if the display is set as frozen, False other wise.
        A display can only be frozen for the _max_display_ticks. When
        _max_display_ticks is 0, the display is "defrosed"
        """
        rtn = False
        if self._max_display_ticks > 0:
            rtn = True
            self._max_display_ticks -= 1
        return rtn

    def update_display(self):
        """
        Updates the display
        """
        value = self._display_info['value']
        font = self._display_info['font']
        fg = self._display_info['colour']

        self._label.config(text = '%s' % value,
                   fg=fg, anchor=tk.W, font=font)

    def display_dps(self, dps, incombat_indicator):
        """
        Display the dps.

        dps - dps to display

        incomabt_indicator - Used to calculate the incombat averages.
                    This needs to be True if in combat false otherwises
        """
        if self.max < dps:
            self.max = dps
            self._display_max()

        if incombat_indicator:
            self._incombat_samples.append(dps)
        else:
            # out of combat, calculate and display the averages
            if self._incombat_samples:
                nzero = last_nonzero_value_index(self._incombat_samples)
                if nzero:
                    nzero += 1
                new_lst = self._incombat_samples[:nzero]
                self.prev_incombat_avg = sum(new_lst)/len(new_lst)
                self.freeze_display(self.prev_incombat_avg, 5, colour='orange')
                self._incombat_samples = []

        self._set_display(dps)
        self.update_display()


class MainApp(tk.Tk):
    """
    Main tk app
    """
    def __init__(self, *args, **kwargs):
        tk.Tk.__init__(self, *args, **kwargs)
        self.overrideredirect(True)
        label = tk.Label(self, text="Click & drag to move",
                         font=("Helvetica", 8), fg='white',
                         bg='#222222', anchor=tk.E)
        label.grid(row=0, column=0)

        tk.Button(self, text='x', font=("Times", 6), command=self.quit,
                  bg='#222222', fg='white').grid(row=0, column=1)

        self._ms = kwargs.get('ms', 250)
        self._dmg = DamageMeter(ms=self._ms)
        # lists for storing the dmg samples
        self._sustained_dps = []
        self._instant_dps = []

        # isntant dps display
        instant, sustained = "Instant:", "Sustained:"
        self.instant = DamageDisplay(self, instant, self._ms, bg='#222222')
        self.instant.grid(row=1, column=0)
        self._pop_up_frame1 = SummaryTab(self, text=instant)

        # sustainted dps
        self.sustained = DamageDisplay(self, sustained, self._ms, bg='#222222')
        self._pop_up_frame2 = SummaryTab(self, text=sustained)
        self.sustained.grid(row=2, column=0)

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
            self._pop_up_frame1.grid()
            self._pop_up_frame2.grid()
        else:
            self._pop_up_frame1.grid_forget()
            self._pop_up_frame2.grid_forget()

    def run(self):
        """
        Main loop of the app
        """
        dps = self._dmg.get_dmg()
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

        # loop back to this method
        self.after(self._ms, self.run)

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
    app.config(background='#222222')
    app.wm_attributes('-toolwindow', 1)
    app.wm_attributes("-topmost", 1)
    app.attributes("-alpha", 0.6)
    app.run()
    app.mainloop()