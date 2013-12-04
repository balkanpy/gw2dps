"""
UI Elements for the DPS Display
"""
import Tkinter as tk
from base_ui_elements import FloatingWindow, Display

def last_nonzero_value_index(lst):
    """
    Return index of the last non-zeron value. If no zeros found, return None
    """
    for index, value in enumerate(reversed(lst)):
        if value != 0:
            return len(lst) - 1 - index
    return None

class HealthBar(FloatingWindow):
    def __init__(self, *args, **kwargs):
        FloatingWindow.__init__(self, *args, **kwargs)
        self._target_health =  tk.Label(self, text='%s'%(0),
                                       font=("Times", 16, 'bold'), fg='#A4F3A7',
                                       anchor=tk.E, width=10,
                                       bg=kwargs.get('bg'))

        tk.Label(self, text='/',
                   font=("Times", 16, 'bold'), fg='#A4F3A7',
                   anchor=tk.CENTER,
                   bg=kwargs.get('bg')).grid(row=0,column=1)

        self._target_max_health = tk.Label(self, text='%s'%(0),
                                       font=("Times", 16, 'bold'), fg='#A4F3A7',
                                       anchor=tk.W, width=10,
                                       bg=kwargs.get('bg'))


        self._target_max_health.grid(row=0, column=2)
        self._target_health.grid(row=0, column=0)

    def update_health(self, current_health, max_health):
        """
        Update the health display
        """
        self._target_health.config(text='%s' % (int(current_health)))
        self._target_max_health.config(text='%s' % (int(max_health)))


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
        tk.Label(self, text=text, font=("Helvetica", 8),
                 width=8, fg='white', bg=kwargs.get('bg'),
                 anchor=tk.E).grid(row=0, column=0)

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


class DamageDisplay(Display):
    """
    TK frame used fro displaying the damage
    """
    def __init__(self, root, text, refresh_ms, *args, **kwargs):
        Display.__init__(self, root, text, refresh_ms, *args, **kwargs)
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

    def reset_display(self):
        """
        Ability to reset the max and prev incombat avg
        """
        self.max, self.prev_incombat_avg = 0, 0
        self._set_display(0, overwrite=True)

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
