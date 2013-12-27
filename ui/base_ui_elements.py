"""
UI base elements
"""
import Tkinter as tk


class FloatingWindow(tk.Toplevel):
    """
    TopLevel Floating window base class
    """
    def __init__(self, *args, **kwargs):
        tk.Toplevel.__init__(self, *args, bg=kwargs.get('bg'))
        self.overrideredirect(True)
        self.wm_attributes('-toolwindow', 1)
        self.wm_attributes("-topmost", 1)

        self.bind("<ButtonPress-1>", self._start_move)
        self.bind("<ButtonRelease-1>", self._stop_move)
        self.bind("<B1-Motion>", self._motion)

    def set_size(self, width, length):
        self.geometry("%sx%s"%(width,length))

    def set_position(self, x, y):
        self.geometry("+%s+%s"%(x, y))

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
        if self.x is not None \
            and self.y is not None:
            dx = event.x - self.x
            dy = event.y - self.y
            self.geometry("+%s+%s" % (self.winfo_x() + dx, self.winfo_y() + dy))


class Display(tk.Frame):
    """
    Base Display Class
    """
    def __init__(self, root, text, refresh_ms, defdisplay, *args, **kwargs):
        tk.Frame.__init__(self, root, *args, bg=kwargs.get('bg'))
        self._label = tk.Label(self, **kwargs)
        self._label.grid(row=0, column=0)

        self._ms = refresh_ms
        self._max_display_ticks = 0
        self._display_info = {'value' : 0,
                              'font'  : defdisplay.get('font',
                                                       ('times', 15, 'bold')),
                              'colour': defdisplay.get('color', 'white')}
        self._display_definfo = self._display_info.copy()

    def freeze_display(self, value, period, **kwargs):
        """
        Freeze the display to display the value for the speficied period (secs)
        """
        self._max_display_ticks = int(period*1000/self._ms)
        kwargs['overwrite'] = True
        self._set_display(value, **kwargs)

    def _set_display(self, value,
                     font='',
                     size=None,
                     colour='',
                     typeface='',
                     overwrite=False):
        """
        Set the display with the specified value. The kwargs determined the
        colour, size, typeface and font of the text.

        overwrite - change display even if it was "frozen"
        """

        if not self._isfrozen() or overwrite:
            self._display_info['font'] = \
                    tuple([self._display_definfo['font'][i] if not val else val
                           for i,val in enumerate([font, size, typeface])])
            self._display_info['value'] = value
            self._display_info['colour'] = self._display_definfo['colour'] \
                                           if not colour else\
                                           colour

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

    def _set_background(self, bg):
        for widget in [self, self._label]:
            widget.config(bg=bg)

    def update_display(self):
        """
        Updates the display
        """
        value = self._display_info['value']
        font = self._display_info['font']
        fg = self._display_info['colour']
        self._label.config(text = '%s' % value, fg=fg, anchor=tk.W, font=font)