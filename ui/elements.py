"""
UI Elements for the DPS Display
"""
import Tkinter as tk
from base_ui_elements import FloatingWindow, Display
import re, time

def parsegeometry(geometry):
    """
    Taken from tk's documentation
    """
    m = re.match("(\d+)x(\d+)([-+]-?\d+)([-+]-?\d+)", geometry)
    if not m:
        raise ValueError("failed to parse geometry string")
    return m.groups()

def ifobject(func):
    """
    Decorator to check if the object exits befoe calling a function, must
    decorate a class method
    """
    def ifobject_dec(self, *args, **kwargs):
        if self._object_init:
            return func(self, *args, **kwargs)
    return ifobject_dec

def last_nonzero_value_index(lst):
    """
    Return index of the last non-zeron value. If no zeros found, return None
    """
    for index, value in enumerate(reversed(lst)):
        if value != 0:
            return len(lst) - 1 - index
    return None


class DPSDisplay(FloatingWindow):
    """
    FloatingWindow of the DPS Display
    """
    def __init__(self, *args, **kwargs):
        FloatingWindow.__init__(self,  *args, **kwargs)

        self._ms = kwargs.get('ms', 250)

        # lists for storing the dmg samples
        self._sustained_dps = []
        self._instant_dps = []
        self._sum = False

        bg = kwargs.get('bg')
        # isntant dps display
        instant, sustained = "Instant:", "Sustained:"
        self.instant = DamageDisplay(self, instant, self._ms, bg=bg)
        self.instant.grid(row=2, column=1)
        self._pop_up_frame1 = SummaryTab(self, text=instant, bg=bg)

        # sustainted dps
        self.sustained = DamageDisplay(self, sustained, self._ms, bg=bg)
        self._pop_up_frame2 = SummaryTab(self, text=sustained, bg=bg)
        self.sustained.grid(row=3, column=1)

        self.bind('<Double-Button-1>', self.toggle_summary)


    def set_background(self, bg):
        for display in [self.instant, self.sustained,
                        self._pop_up_frame1, self._pop_up_frame2]:
            display.set_background(bg)
        self.config(bg=bg)

    def toggle_summary(self, event):
        """
        On double click display the summary tab
        """
        self._sum = not self._sum
        if self._sum:
            self._pop_up_frame1.grid(row=5, column=1)
            self._pop_up_frame2.grid(row=6, column=1)
        else:
            self._pop_up_frame1.grid_forget()
            self._pop_up_frame2.grid_forget()

    def update_data(self, instant_dps, sustained_dps, incombat_indicator):
        self.instant.display_dps(instant_dps, incombat_indicator)
        self.sustained.display_dps(sustained_dps, incombat_indicator)

        self._pop_up_frame1.setvalues(self.instant.max,
                                      self.instant.prev_incombat_avg)
        self._pop_up_frame2.setvalues(self.sustained.max,
                                      self.sustained.prev_incombat_avg)


class Timer(FloatingWindow):
    def __init__(self, dmg_object, *args, **kwargs):
        """
        Timer to record the time it took for the locked target to die.
        """
        FloatingWindow.__init__(self, *args, **kwargs)
        self._timer_name = tk.Label(self, text='Timer:', fg='white',
                 font=(None, 12, 'bold'), **kwargs)
        self._timer_name.grid(row=0,column=0)

        self.label = tk.Label(self, text='Lock Target',
                              font=(None, 12, 'bold'), anchor=tk.CENTER,
                              fg='white', width=12, **kwargs)
        self.label.grid(row=0, column=1)

        self._dmg = dmg_object
        self._target_lock = False
        self.bind('<Double-Button-1>', self.transition)

        self._target = (None, None, -1)
        self._time, self._ptime = 0, 0
        self._stop = False
        self._cstate = 0

    def set_background(self, bg):
        """
        Actively set the background
        """
        for widget in [self.label, self, self._timer_name]:
            widget.config(bg=bg)

    def transition(self, event):
        """
        State transition
        """
        self._target = self._dmg.selected_target()
        if self._target[1] and self._cstate != 2:
            self.label.config(text='Target Locked')
            if self._cstate != 1:
                self.run()
            self._cstate = 1
        elif self._cstate == 2:
            self._cstate = 0
            self._stop   = True
            self._timereset()
        else:
            self._cstate = 0
            self.label.config(text='Lock Target')

    def run(self):
        """
        Timer running
        """
        if not self._target[0]:
            return None

        ch, chmax = self._dmg.get_health_value_pairs(self._target[0])

        if ch != self._target[1]:
            self._cstate = 2
            if self._ptime:
                self._time += round(time.time() - self._ptime, 2)
                self.label.config(text='%.2fs'% self._time )

        self._ptime = time.time()

        if self._stop:
            self._stop = False
        elif ch != 0:
            self.after(100, self.run)
        else:
            self._cstate = 0
            self._timereset()

    def _timereset(self):
        """
        Reset the time values
        """
        self._time = 0
        self._ptime = 0

class HealthBar(FloatingWindow):
    """
    FloatingWindow Displaying the target health
    """
    def __init__(self, *args, **kwargs):
        FloatingWindow.__init__(self, *args, **kwargs)
        self._target_health =  tk.Label(self, text='%s'%(0),
                                       font=("Times", 16, 'bold'), fg='#A4F3A7',
                                       anchor=tk.E, width=10,
                                       bg=kwargs.get('bg'))

        self._other = tk.Label(self, text='/',
                   font=("Times", 16, 'bold'), fg='#A4F3A7',
                   anchor=tk.CENTER,
                   bg=kwargs.get('bg'))
        self._other.grid(row=0, column=1)

        self._target_max_health = tk.Label(self, text='%s'%(0),
                                       font=("Times", 16, 'bold'), fg='#A4F3A7',
                                       anchor=tk.W, width=10,
                                       bg=kwargs.get('bg'))


        self._target_max_health.grid(row=0, column=2)
        self._target_health.grid(row=0, column=0)
        self._percent_health = tk.Label(self, text='%s'%(0),
                                       font=("Times", 16, 'bold'), fg='#A4F3A7',
                                       anchor=tk.CENTER, width=21,
                                       bg=kwargs.get('bg'))

        self._percent_view = False
        self.bind('<Double-Button-1>', self.change_view)

    def change_view(self, event):
        self._percent_view = not self._percent_view

        widgets = [self._other, self._target_max_health, self._target_health]
        if self._percent_view:
            # remove the labels for regular view
            for widget in widgets:
                widget.grid_remove()
            # place the % label
            self._percent_health.grid(row=0, column=0)
        else:
            # remove the % label
            self._percent_health.grid_remove()
            # place tje regular labels
            for widget in widgets:
                widget.grid()


    def set_background(self, bg):
        """
        Actively set the background
        """
        for widget in [self._target_health, self._target_max_health,
                       self, self._other]:
            widget.config(bg=bg)

    def update_data(self, current_health, max_health):
        """
        Update the health display
        """
        current_health = current_health if current_health >= 0 else 0
        max_health = max_health if max_health >= 0 else 0
        percent = 0
        if max_health:
            percent = current_health/max_health*100

        self._percent_health.config(text='%s'% int(percent) + '%')
        self._target_health.config(text='%s' % (int(current_health)))
        self._target_max_health.config(text='%s' % (int(max_health)))


class SummaryTab(tk.Frame):
    """
    Frame that will pop up when hovered over the damage indicators
    """
    def __init__(self, *args, **kwargs):

        if 'text' in kwargs:
            text = kwargs.pop('text')
        else:
            text = ''

        tk.Frame.__init__(self, *args, **kwargs)
        self._name_label = tk.Label(self, text=text, font=("Helvetica", 8),
                 width=8, fg='white', bg=kwargs.get('bg'),
                 anchor=tk.E)

        self._name_label.grid(row=0, column=0)

        self._value1label = tk.Label(self, text='', font=("Helvetica", 8),
                                     width=6, bg=kwargs.get('bg'),
                                     fg='red', anchor=tk.W)

        self._value2label = tk.Label(self, text='', font=("Helvetica", 8),
                                     fg='orange',width=6,
                                     bg=kwargs.get('bg'), anchor=tk.W)

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

    def set_background(self, bg):
        """
        Actively set the background
        """
        for widget in [self, self._value1label,
                       self._value2label, self._name_label]:
            widget.config(bg=bg)


class DamageDisplay(Display):
    """
    Frame used for displaying the DPS
    """
    def __init__(self, root, text, refresh_ms, *args, **kwargs):
        Display.__init__(self, root, text, refresh_ms, *args, **kwargs)
        bg = kwargs.get('bg')

        self._name_label = tk.Label(self, font=('times', 15, 'bold'),
                                    borderwidth=0, text=text, bg=bg, fg='white',
                                    anchor=tk.E, width=8)

        self._name_label.grid(row=0)

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

    def reset_display(self):
        """
        Ability to reset the max and prev incombat avg
        """
        self.max, self.prev_incombat_avg = 0, 0
        self._set_display(0, overwrite=True)

    def set_background(self, bg):
        """
        Actively set the background
        """
        for widget in [self, self._name_label, self._label]:
            widget.config(bg=bg)
        self._set_background(bg)

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
                if new_lst:
                    self.prev_incombat_avg = sum(new_lst)/len(new_lst)
                    self.freeze_display(self.prev_incombat_avg, 5,
                                        colour='orange')
                self._incombat_samples = []

        self._set_display(dps)
        self.update_display()


class Settings(tk.Toplevel):
    """
    Settings popup menu to allow for live configuration
    TODO: For future versions
    """
    def __init__(self, *args, **kwargs):
        tk.Toplevel.__init__(self, *args, **kwargs)


class Checkbox(tk.Frame):
    """
    Frame that consits of a name, checkbox
    """
    def __init__(self, parent, name, *args, **kwargs):
        tk.Frame.__init__(self, *args, **kwargs)

        self.ckvalue = tk.IntVar()
        self.ckvalue.set(False)
        self.ck = tk.Checkbutton(self, text='%s' % (name), width=15,
                                 variable=self.ckvalue, anchor=tk.W)
        self.ck.grid(row=1, column=1)

        self._name = name

    @property
    def checkbox_value(self):
        return self.ckvalue.get()

    def attach_callback(self, func):
        self.ck.config(command=func)

class Logger(Checkbox):
    """
    """
    def __init__(self, parent, name, fname, *args, **kwargs):
        Checkbox.__init__(self, parent, name)
        self.attach_callback(self.checkbox_callback)
        self._fname = fname
        self._logging = False

    def checkbox_callback(self):
        if self.checkbox_value:
            # clear file
            self._filename = self._fname
            open(self._filename, 'w').close()
        self._logging = not self._logging

    def log(self, value):
        if self._logging:
            with open(self._filename, 'a') as f:
                f.write('%s\n' % value)


class DisplayEnableCheckbox:
    """
    Check box that starts, and closes the display window
    """
    def __init__(self, parent, name, onbject, *argsobj, **kwargsobj):
        """
        onbject is a class object for the window to popup when the check
        box is selected. The window will close when checkbox unselected

        onbject must have the following methods:
            update_data
            attributes
            set_background
        """
        self.ck = Checkbox(parent, name)
        self.ck.attach_callback(self.checkbox_callback)

        self._objectparms = (argsobj, kwargsobj)
        self._onobject = onbject
        self._object_init = None
        self._x_y_position = None
        self._attributes = []

    def grid(self, *args, **kwargs):
        self.ck.grid(*args, **kwargs)

    def checkbox_callback(self):
        """
        Checkbox event callback
        The windows position is saved when the checkbox is unckecked, so that
        next time it appears in the same position
        """
        if self.ck.checkbox_value:
            # checkbox is selected, open up the window
            self._object_init = self._onobject(*self._objectparms[0],
                                                **self._objectparms[1])
            if self._x_y_position:
                self._object_init.geometry("%s%s" % (self._x_y_position[0],
                                                     self._x_y_position[1]))
            for arg, value in self._attributes:
                self._object_init.attributes(arg, value)
        else:
            # checkbox is deselected, close the window
            self._geometry_set = self._object_init.geometry()
            self._x_y_position = parsegeometry(self._geometry_set)[2:]
            self._object_init.destroy()
            self._object_init=None

    @ifobject
    def update_data(self, *args, **kwargs):
        """
        Calls the update_data method of the onbject
        """
        self._object_init.update_data(*args, **kwargs)

    def set_object_attributes(self, arg, value):
        """
        Appends the attributes to a list. the attributes will be applied
        when the object is created
        """
        self._attributes.append((arg, value))

    @ifobject
    def get_window_hwnd(self):
        return int(self.wm_frame(), 0)

    def get_position(self):
        if self._object_init:
            return parsegeometry(self._object_init.geometry())[2:]
        else:
            return self._x_y_position

    def set_position(self, x, y):
        if self._object_init:
            self._object_init.geometry('%s%s' % (x, y))
        else:
            self._x_y_position = (x, y)

    def __getattr__(self, attr):
        if self._object_init:
            if hasattr(self._object_init, attr):
                return getattr(self._object_init, attr)