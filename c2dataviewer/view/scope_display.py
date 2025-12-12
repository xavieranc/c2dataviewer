# -*- coding: utf-8 -*-

"""
C2 DATA VIEWER is distributed subject to a Software License Agreement found
in the file LICENSE that is included with this distribution.
SPDX-License-Identifier: EPICS

Copyright 2018 UChicago Argonne LLC
 as operator of Argonne National Laboratory

PVA object viewer utilities for image display

@author: Guobao Shen <gshen@anl.gov>
"""
from datetime import datetime
import numpy as np
import pyqtgraph
from pyqtgraph.Qt import QtCore
import enum
import logging
import time
from enum import Enum

class DisplayMode(Enum):
    """
    Display mode for the plot
    """
    NORMAL = 'normal'
    FFT = 'fft'
    PSD = 'psd'
    DIFF = 'diff'
    AUTOCORFFT = 'autocorrelate_fft'
    
    def __str__(self):
        return self.value
    def is_fft(self):
        return self in [DisplayMode.FFT, DisplayMode.PSD]

class FFTFilter(Enum):
    """
    FFT filter type
    """
    NONE = 'none'
    HAMMING = 'hamming'

    def __str__(self):
        return self.value

class PlotChannel:
    """
    Channel data to plot
    """
    
    def __init__(self, pvname, color, dc_offset = 0, axis_location = 'left', started = True, array_id = None):
        """
        pvname: (str) PV data name.  Either is the PV name or PV.field1.field2 format.  
        """
        self.color = color
        self.pvname = pvname
        self.dc_offset = dc_offset
        self.axis_location = axis_location
        self.started = started
        self.test_array_id = array_id
        self.last_test_array = None

    def should_be_drawn(self, xaxes : str, trigger_data_time_field : str) -> bool :
        '''
        Tells if PlotChannel should be drawn on screen.
        It should not if PV name is None, empty or if PV is used as x-axis, trigger data time field or not started.
        
        :param xaxes: The name of the PV used as x-axis.
        :param trigger_data_time_field: The name of the PV used as trigger data time field.
        '''
        return self.pvname not in ['None', '', xaxes, trigger_data_time_field] and self.started

    def __str__(self):
        return self.pvname

class TriggerType(enum.Enum):
    ON_CHANGE = 'onchange'
    GT_THRESHOLD = 'gtthreshold'
    LT_THRESHOLD = 'ltthreshold'

    def __str__(self):
        return self.value
    
class Trigger:
    def __init__(self, parent):
        self.parent = parent
        self.trig_data = {}
        
        # Is trigger mode enabled
        self.trigger_mode = False

        # True if (in trigger mode and) trigger was received (trigger PV monitor fired).
        self.is_triggered_ = False

        # Counts trigger PV monitor fired callback (count monitor updates)
        self.trigger_count = 0

        #trigger position in trig_data
        self.trigger_index = 0
        #index in trig_data where to plot data
        self.display_start_index = 0

        self.trigger_data_done = True

        # True if data is behind trigger time (index -2 of self.__is_trigger_in_array). Won't trigger until it turns False by self.add_to_trig_data.
        self.data_behind = False
        
        # double sec past epoch timestamp from the trig pv
        self.trigger_timestamp = None

        self.trigger_level = 0.0
        class TriggerSignal(QtCore.QObject):
            my_signal = QtCore.pyqtSignal()

            def emit(self):
                self.my_signal.emit()
                
            def __init__(self):
                QtCore.QObject.__init__(self)

        self.plot_trigger_signal_emitter = TriggerSignal()
        
        self.trigger_type = None
        self.trigger_time_field = 'timeStamp'
        self.data_time_field = None
        self.is_triggered_func = None

        self.trigger_value = None
        self.missed_triggers = 0
        self.missed_adjust_buffer_size = 0
        self.enable_trigger_marker = True

        self.data_time_field_on_error = False # Did an error occur when trying to use data time field. 

        class WarningSignal(QtCore.QObject):
            ''' Signal aiming to trigger parent error callback (which should be ScopeController.notify_warning). '''
            signal = QtCore.pyqtSignal(str)
            def emit(self, message : str) -> None : self.signal.emit(message)
            def __init__(self): super().__init__()

        self.warning = WarningSignal()
        self.warning.signal.connect(self.parent.error_callback)
        
    def __trigger_on_change(self, val):
        return True

    def __trigger_gt_threshold(self, val):
        return val > self.trigger_level
    
    def __trigger_lt_threshold(self, val):
        return val < self.trigger_level
    
    def set_trigger_type(self, val):
        func_table = { TriggerType.ON_CHANGE: self.__trigger_on_change,
                       TriggerType.GT_THRESHOLD: self.__trigger_gt_threshold,
                       TriggerType.LT_THRESHOLD: self.__trigger_lt_threshold }
        self.trigger_type = TriggerType(val)
        self.is_triggered_func = func_table[self.trigger_type]
        
    def set_trigger_mode(self, flag):
        self.trigger_mode = flag

    def is_triggered(self):
        return self.trigger_mode and self.is_triggered_
    
    def data_callback(self, data):
         # Count triggers and ignore first one which is initial connection callback and not actual value change.
        self.trigger_count += 1
        if self.trigger_count <= 1:
            return

        self.trigger_value = data['value']

        if not self.parent.plotting_started:
            return

        if not self.trigger_data_done:
            return
        
        if self.data_behind:
            return

        if not self.is_triggered_func(data['value']):
            return

        self.is_triggered_ = True
        self.trigger_data_done = False

        if self.trigger_time_field is not None and self.trigger_time_field in data:
            ts = data[self.trigger_time_field]
            self.trigger_timestamp = ts['secondsPastEpoch'] + 1e-9*ts['nanoseconds']
        else:
            self.trigger_timestamp = None
        self.draw_data() # Draw data also when trigger PV is processed. It ensures that if plotted PV is not, display is updated.

    def __is_trigger_in_array(self, time_array):
        """
        Calculate if the trigger timestap is in the timestamp array.

        :param time_array: (numpy array) Time (SORTED!!!) array to be checked.
        :return: (Tuple -> (bool, integer)) True or False if timestamp is in the array.
                                            If True, second element hold index of the element, otherwise is None.
        """

        if self.trigger_timestamp is None:
            logging.getLogger().error(f'Trigger timestamp is not set. Check if {self.trigger_time_field} field exists')
            return -3
        
        if self.trigger_timestamp < time_array[0]:
            return -1

        if self.trigger_timestamp > time_array[-1]:
            return -2
        
        idx = np.searchsorted(time_array, self.trigger_timestamp)

        return idx

    def status(self):
        if not self.trigger_mode:
            return 'Off'
        if self.data_behind:
            return 'Waiting for new data'
        if self.missed_triggers > 0:
            return 'Trig off by %.1f s (Set buf=%.1e)' % (self.missed_time, self.missed_adjust_buffer_size)
        elif self.is_triggered_:
            return 'Collecting Data'
        else:
            return 'Waiting for trigger'

    def __trig_max_length(self):
        return self.parent.max_length
    
    def add_to_trig_data(self, k, v):
        # In trigger mode the minimum we must save is the whole last array (+ part of the old ones if max_length > vector_len)
        # We must store all the arrayes as the "Time" field determinate how much data do we really need, and the "Time" field can arrive last.
        required_data = self.__trig_max_length()
        self.trig_data[k] = np.append(self.trig_data.get(k, []), v)[-required_data:]
        self.data_behind = False # Allow to launch trigger mechanism again and see if data is no more behind rtigger time.

    def transfer(self) -> None :
        ''' Copy data from parent's cache and empty parent's cache. '''
        for k, v in self.parent.data.items():
            self.add_to_trig_data(k, v)
        self.parent.data = {}


    def draw_data(self):
        """
        If collected max_length/2 samples after the trigger mark, call signal to draw data
        """
        max_length = self.parent.max_length
        
        if not self.is_triggered():
            return
        
        if self.data_time_field not in self.trig_data.keys():
            if self.data_time_field is not None and not self.data_time_field_on_error: # If an error occurs for the first time...
                self.warning.emit('Data time field is absent in data. Ignoring it.') # ... warn the user ...
                self.data_time_field_on_error = True # ... and write down it had been down.
            for k, v in self.trig_data.items():
                if type(v) != np.ndarray:
                     continue

                self.parent.data[k] = self.trig_data[k][-self.parent.max_length:]
            self.display_start_index = 0
            self.plot_trigger_signal_emitter.emit()
            self.enable_trigger_marker = False
        else:
            self.data_time_field_on_error = False # Situation was fixed. Watch out for new errors.
            samples_after_trig = int(max_length / 2)

            # Check if we have trigger timestamp in buffer
            time_data = self.trig_data[self.data_time_field]
            idx = self.__is_trigger_in_array(time_data)
            self.enable_trigger_marker = True
            if idx >= 0:
                self.missed_triggers = 0                
                self.trigger_index = idx
                samples_after_trig_cnt = time_data.size - idx
                # Check if we have the requested number of samples, to trigger the plotting
                if samples_after_trig_cnt >= samples_after_trig:
                    self.display_start_index = max(idx - samples_after_trig, 0)
                    endindex = idx + samples_after_trig
                    for k, v in self.trig_data.items():
                        if type(v) != np.ndarray:
                            continue

                        if len(self.trig_data[k]) < time_data.size:
                            continue
                        
                        # `idx` holds the index in the stored waveforms where the trigger happened.
                        # Goal is to get the slice of the waveform so the sample when the trigger happened is in the middle.
                        # samples_after_trig determinate how much samples do we want to show after the trigger (idx + samples_after_trig),
                        # while max_length holds a maximum number of samples to show, for this reason we need `(self.max_length-self.samples_after_trig`
                        # samples before trigger/idx.
                        self.parent.data[k] = self.trig_data[k][self.display_start_index : endindex]
                    self.plot_trigger_signal_emitter.emit()
                else:
                    logging.getLogger().debug('Needs to acquire %i more samples before plotting' % (samples_after_trig - samples_after_trig_cnt))
            elif idx == -1:
                if len(time_data) >= self.__trig_max_length():
                    datatimediff = time_data[-1] - time_data[0]
                    timediff = time_data[0] - self.trigger_timestamp
                    increasesize = len(time_data) * timediff / datatimediff
                    self.missed_triggers += 1
                    self.missed_adjust_buffer_size = increasesize + self.parent.max_length
                    self.missed_time = timediff
                    self.is_triggered_ = False
                    self.trigger_data_done = True
                else:
                    self.is_triggered_ = False
                    self.trigger_data_done = True
                    self.missed_triggers = 0
            else:
                self.warning.emit('Data is %f seconds behind trigger time. Waiting for new data before starting triggering again.' % (self.trigger_timestamp - time_data[-1]))
                self.data_behind = True

    def display_trigger_index(self):
        """
        Returns the position of the trigger in the display buffer (i.e self.parent.data)
        """
        return self.trigger_index - self.display_start_index
    
    def set_data_time_field(self, data_time_field : str) -> None :
        '''
        Set trigger data time field and reset error flag.

        :param data_time_field: The new trigger data time field.
        '''
        self.data_time_field = data_time_field if data_time_field != 'None' else None
        self.data_time_field_on_error = False
        self.parent.setup_plot()
    
    def finish_drawing(self):
        # Trigger curves were drawn - Freeze the scope
        if self.trigger_mode and self.is_triggered_:
            self.is_triggered_ = False
            self.trigger_data_done = True

    def reset(self):
        self.trigger_count = 0
        self.is_triggered_ = False
        self.trigger_data_done = True
        self.data_behind = False
        self.trigger_value = None
        self.missed_triggers = 0
        
    def connect_to_callback(self):
        if self.trigger_mode:
            self.plot_trigger_signal_emitter.my_signal.connect(self.parent.update_drawing)

    def disconnect_to_callback(self):
        try:
            self.plot_trigger_signal_emitter.my_signal.disconnect()
        except Exception:
            pass

    def clear_waveform_data(self, pv_name : str) -> None :
        '''
        Removes all a specific PV related data.

        :param pv_name: The name of the PV of which the data should be removed.
        '''
        to_delete = [key for key in self.trig_data.keys() if pv_name in key]
        for key in to_delete:
            del self.trig_data[key]

class MouseOver:

    def __init__(self, widget):
        self.display_fields = []
        self.widget = widget
        self.textbox = None
        self.vline = None
        self.hline = None
        self.enabled = False
        self.display_location = None
        self.mouse_index = None
        self.highlight_points = [] 
        self.data_cache = {}
        
    def setup_plot(self):
        assert(self.widget.plot)
        self.textbox = pyqtgraph.LabelItem(color='w')
        self.textbox.setAttr('size', '12pt')
        self.vline = pyqtgraph.InfiniteLine(angle=90, movable=False)
        self.hline = pyqtgraph.InfiniteLine(angle=0, movable=False)

        # Clear any existing highlight points
        for point in self.highlight_points:
            self.widget.plot.removeItem(point)
        self.highlight_points = []

        # Create highlight point markers for each channel
        for ch in self.widget.channels:
            if ch.pvname != "None":
                highlight = pyqtgraph.ScatterPlotItem(size=10, pen=pyqtgraph.mkPen(None),
                                                     brush=pyqtgraph.mkBrush(ch.color))
                self.highlight_points.append(highlight)

        self.enable(self.enabled)
        
    def enable(self, flag):
        self.enabled = flag
        if flag:
            self.widget.plot.addItem(self.vline, ignoreBounds=True)
            self.widget.plot.addItem(self.hline, ignoreBounds=True)
            for highlight in self.highlight_points:
                self.widget.plot.addItem(highlight, ignoreBounds=True)
            self.textbox.setParentItem(self.widget.plot)
            self._apply_display_location()
            self.textbox.show()
            self.vline.show()
            self.hline.show()
            for highlight in self.highlight_points:
                highlight.show()
        else:
            self.widget.plot.removeItem(self.vline)
            self.widget.plot.removeItem(self.hline)
            for highlight in self.highlight_points:
                self.widget.plot.removeItem(highlight)
            self.textbox.setParentItem(None)

            self.textbox.hide()
            self.vline.hide()
            self.hline.hide()
            for highlight in self.highlight_points:
                highlight.hide()
            
    def set_display_fields(self, fields):
        self.display_fields = fields
        
    def _apply_display_location(self):
        if self.enabled:
            self.textbox.anchor(parentPos=(1,0.95), itemPos=(1,1))
            if self.display_location == 'top-right':
                 self.textbox.anchor(parentPos=(1, 0.00), itemPos=(1,0))
            elif self.display_location == 'bottom-right':
                 self.textbox.anchor(parentPos=(1, 0.95), itemPos=(1,1))
            elif self.display_location == 'bottom-left':
                 self.textbox.anchor(parentPos=(0.05, 0.95), itemPos=(0,1))
        
    def set_display_location(self, loc):
        self.display_location = loc
        self._apply_display_location()

    def populate_cache(self):
        for ch in self.widget.channels:
            if ch.pvname == 'None' or ch.pvname not in self.widget.data:
                continue
            field = ch.pvname
            self.data_cache[field] = self.widget.data.get(field)
    
    def update_textbox(self):
        if self.mouse_index is None or not self.enabled:
            return

        index = self.mouse_index
        channel_data = {}
        nsamples = 0

        if len(self.data_cache) == 0:
            self.populate_cache()
            
        for ch in self.widget.channels:
            if ch.pvname == 'None':
                continue
            if ch.pvname not in self.widget.data:
                continue

            channel_data[ch.pvname] = [self.data_cache.get(ch.pvname), ch.color]
            nsamples = max(nsamples, len(channel_data[ch.pvname][0]))

        for f in self.display_fields:
            if f in channel_data:
                continue
            
            channel_data[f] = [self.data_cache.get(f), '#FFFFFF']
            try:
                nsamples = max(nsamples, len(channel_data[f][0]))
            except:
                pass

        if len(channel_data) == 0:
            return

        xaxis = self.widget.current_xaxes
        xaxis_data = self.data_cache.get(xaxis) if xaxis != 'None' else None
        
        if index >= 0 and index < nsamples:
            text = []
            xvalue = index  # default x value
            if xaxis == 'None':
                text.append(f"x={index}")
            else:
                if xaxis_data is not None and index < len(xaxis_data):
                    xaxis_value = xaxis_data[index]
                else:
                    xaxis_value = 'N/A'
                
                if xaxis_data is not None and index < len(xaxis_data):
                    xvalue = xaxis_data[index]
                    

                text.append(f"{xaxis}={xaxis_value}")

            # Update highlight points for each channel
            highlight_idx = 0
            for ch in self.widget.channels:
                if ch.pvname == 'None':
                    continue
                if ch.pvname not in self.widget.data:
                    continue

                data = self.data_cache.get(ch.pvname)
                if data is not None and index < len(data) and highlight_idx < len(self.highlight_points):
                    yvalue = data[index] + ch.dc_offset
                    # For time-based x-axis, adjust x position
                    if xaxis != 'None' and xaxis in self.widget.data:
                        if xaxis_data is not None and len(xaxis_data) > 0:
                            xpos = xvalue - xaxis_data[0]
                        else:
                            xpos = index
                    else:
                        xpos = index
                    self.highlight_points[highlight_idx].setData([xpos], [yvalue])
                    highlight_idx += 1

            for k,v in channel_data.items():
                data = v[0]
                color = v[1]
                data_value = data[index] if data is not None and index <len(data) else 'N/A'
                text.append(f"<span style='color: {color}'>{k}={data_value}</span>")

            text = "<br>".join(text)
            self.textbox.setText(text)
        
    def on_mouse_move_event(self, event):
        if not self.enabled:
            return
        pos = event.pos()

        if not self.widget.plot.sceneBoundingRect().contains(pos):
            return

        mousePoint = self.widget.plot.vb.mapSceneToView(pos)
        mouse_x = mousePoint.x()

        # When xaxes is set, convert plot x-coordinate back to array index
        if self.widget.current_xaxes != "None" and self.widget.current_xaxes in self.widget.data:
            xaxis_data = self.widget.data.get(self.widget.current_xaxes)
            if xaxis_data is not None and len(xaxis_data) > 0:
                # Plot shows (time - time[0]), so add back the offset
                actual_x_value = mouse_x + xaxis_data[0]
                # Find the closest index in the xaxis data
                self.mouse_index = int(np.argmin(np.abs(xaxis_data - actual_x_value)))
            else:
                self.mouse_index = int(mouse_x)
        else:
            # No xaxes set, x-coordinate is the array index
            self.mouse_index = int(mouse_x)

        self.update_textbox()

        self.vline.setPos(mouse_x)
        self.hline.setPos(mousePoint.y())
            
class PlotWidget(pyqtgraph.GraphicsLayoutWidget):
    """
    Main class for plotting multiple sets of data.  Key functions:
    - setup_plot - sets up the channels to plot
    - data_process - pass in data to plot
    - update_drawing - plots data
    """
    def __init__(self, parent=None, **kargs):
        pyqtgraph.GraphicsLayoutWidget.__init__(self, parent=parent)
        self.setParent(parent)

        self.channels = []
        self.auto_scale = False
        self.first_data = True
        self.plotting_started = False
        
        self.sampling_mode = False        
        self.sample_data = {}
        
        self.mutex = pyqtgraph.QtCore.QMutex()

        self.max_length = None
        self.data_size = 0
        self.new_buffer = True
        self.data = {}
        self.new_plot = True
        
        # last id number of array received
        self.lastArrayId = None
        # count of lost arrays
        self.lostArrays = 0
        # count of array received
        self.arraysReceived = 0

        # EPICS7 field name for horizontal axis
        self.current_xaxes = "None"
        # EPICS7 field name for Array ID
        self.current_arrayid = "None"

        self.major_ticks = 0
        self.minor_ticks = 0
        
        self.fps = 0
        self.lastTime = time.time()

        self._max = None
        self._min = None

        self.bins = 100
        self.display_mode = DisplayMode.NORMAL
        self.fft_filter = FFTFilter.NONE
        self.histogram = False
        self.average = 1

        self.__fft_vgain = {
            'none' : 1,
            'hamming' : 1.853,
        }

        self.axis = []
        self.views = []
        self.curves = []

        self.error_callback = lambda x: None # Fonction to be called when an error occur to display information. Sould be set to ScopeControllerBase.notify_warning when Controller is instanciated.
        
        self.trigger = Trigger(self)
        self.mouse_over = MouseOver(self)
        
        # Setup plot variables
        self.single_axis = True
        self.plot = None
        self.setup_plot([])

        self.is_freeze = False

    def set_is_freeze(self, flag: bool):
        self.is_freeze = flag
        
    def trigger_mode(self):
        return self.trigger.trigger_mode

    def set_trigger_mode(self, flag):
        self.trigger.set_trigger_mode(flag)

    def enable_sampling_mode(self, val):
        """
        Set sampling mode.  If true, plot only the latest value at each refresh interval.
        Set this mode if plotting multiple data sources that have different data rates.
        """
        if self.sampling_mode != val:
            self.sampling_mode = val
            self.data.clear()
            self.setup_plot()
        
    def set_arrayid(self, value):
        """
        Set current field name for array id

        :param value:
        :return:
        """
        if value != self.current_arrayid:
            self.current_arrayid = value

    def set_xaxes(self, value):
        """
        Set current field name for x axes

        :param value:
        :return:
        """
        self.current_xaxes = value
        self.new_plot = True

        if self.current_xaxes == "None":
            self.plot.setLabel('bottom', '')
        else:
            # Capitalize the label for display purposes
            self.plot.setLabel('bottom', self.current_xaxes.capitalize())
        self.setup_plot()

    def set_enable_mouseover(self, value):
        self.mouse_over.enable(value)

    def set_mouseover_fields(self, fields):
        self.mouse_over.set_display_fields(fields)

    def set_mouseover_display_location(self, loc):
        self.mouse_over.set_display_location(loc)
        
    def mouseMoveEvent(self, event):
        pyqtgraph.GraphicsLayoutWidget.mouseMoveEvent(self, event)
        self.mouse_over.on_mouse_move_event(event)
        
    def set_major_ticks(self, value):
        self.major_ticks = value

    def set_minor_ticks(self, value):
        self.minor_ticks = value

    def _setup_ticks(self):
        if self.major_ticks <= 0 or self.current_xaxes != 'None':
            self.plot.getAxis('bottom').setTicks(None)
            return
        
        minVal = 0
        maxVal = self.max_length

        major_ticks = [ (i, str(i)) for i in range(0, maxVal + 1, int(self.major_ticks)) ]

        minor_ticks = None
        if self.minor_ticks > 0:
            tickMod = self.major_ticks / self.minor_ticks
            minor_ticks = [ (i, str(i) if (i/self.minor_ticks % tickMod) > 0 else '') for i in range(0, maxVal + 1, int(self.minor_ticks)) ]

        ticks = [major_ticks]
        if minor_ticks:
            ticks.append(minor_ticks)
            
        self.plot.getAxis('bottom').setTicks(ticks)
                                 
            
    def setup_plot(self, channels=None, single_axis=None):
        """
        Setup the channels to plot

        :param channels: list of PlotChannel objects
        :param single_axis: flag to share single axis, or have a axis for each figure. FFT and PSD support only single axis
        :return:
        """
        if single_axis is None:
            single_axis = self.single_axis

        # FFT and PSD support only single axis, PyQTGraph currently doesn't support log scale on the multiple axis setup
        if not single_axis and self.display_mode.is_fft():
            single_axis = True
            # Could Be replaced with logging if added in the future
            print(f"{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}: FFT or PSD selected in multi axis mode, which is not supported. Changed to one axis mode automatically.")

        # Delete existing plots
        self.delete_plots()

        self.xaxis_on_error = False

        # Set new list of signals
        if channels:
            self.channels = channels

        # Create plot item
        self.plot = pyqtgraph.PlotItem()
        self.plot.showGrid(x=True, y=True)
        if self.display_mode.is_fft():
            self.plot.setLogMode(x=True, y=True)

        # Generate plot items
        self.single_axis = single_axis
        if single_axis:
            self.setup_plot_single_axis()
        else:
            self.setup_plot_multi_axis()

        self.trigMarker = self.plot.plot()

        # Update plots
        self.plot.vb.sigResized.connect(self.update_views)
        self.update_views()

        #apply settings to new plot
        self.set_autoscale(self.auto_scale)
        
        self.new_plot = True
        self.data_size = 0
        self.mouse_over.setup_plot()
        
    def setup_plot_single_axis(self):
        """
        Setup items for single Y axis plot.

        :names: (list -> strings) List of channels to bi displayed. "None" should be used to ignore that channel.
        :return: (None)
        """
        if self.channels:
            self.plot.addLegend()
        for ch in self.channels:
            if not ch.should_be_drawn(self.current_xaxes, self.trigger.data_time_field):
                continue
            curve = self.plot.plot(pen=ch.color, name=ch.pvname)
            curve.plotdata_ave = None
            self.curves.append(curve)

        self.ci.addItem(self.plot, row=2)

    def setup_plot_multi_axis(self):
        """
        Setup items for multiple Y axis plot.

        :names: (list -> strings) List of channels to bi displayed. "None" should be used to ignore that channel.
        :return: (None)
        """
        # Workaround until pyqtgraph issue with multiple axis is resolved
        # (see https://git.aps.anl.gov/C2/conda/data-viewer/-/issues/48)
        # Pick up proper viewbox geometry from parent
        self.ci.addItem(self.plot, row=2)

        # We do not use default axis
        self.plot.hideAxis('left')

        # Create axis and views
        left_axis = []
        right_axis = []
        for i, ch in enumerate(self.channels):
            if not ch.should_be_drawn(self.current_xaxes, self.trigger.data_time_field):
                continue

            axis = pyqtgraph.AxisItem(ch.axis_location)
            axis.setLabel(f"Channel {i+1} [{ch.pvname}]", color=ch.color)
            if ch.axis_location == "left":
                left_axis.append(axis)
            else:
                right_axis.append(axis)
            self.axis.append(axis)
            # First view we take from plotItem
            if len(self.axis) == 1:
                self.views.append(self.plot.vb)
            else:
                self.views.append(pyqtgraph.ViewBox())

        # Add axis and plot to GraphicsLayout (self.ci)
        # Order how they are added is important, while it is also important
        # we hold correct order (the same as in the "names" variable) in self.axis
        # variable as other code depends on this.
        for a in left_axis:
            self.ci.addItem(a, row=2)
        self.ci.addItem(self.plot, row=2)
        for a in right_axis:
            self.ci.addItem(a, row=2)

        # Add Viewboxes to the layout
        for vb in self.views:
            if vb != self.plot.vb:
                self.ci.scene().addItem(vb)

        # Link axis to view boxes
        for i, view in enumerate(self.views):
            self.axis[i].linkToView(view)
            if view != self.plot.vb:
                view.setXLink(self.plot.vb)

        # Make curves
        count = 0

        for i, ch in enumerate(self.channels):
            if not ch.should_be_drawn(self.current_xaxes, self.trigger.data_time_field):
                continue
            
            curve = pyqtgraph.PlotCurveItem(pen=ch.color)
            curve.plotdata_ave = None
            left_curve = []
            right_curve = []
            if ch.axis_location == "left":
                left_curve.append(curve)
            else:
                right_curve.append(curve)
            self.curves.extend(left_curve)
            self.curves.extend(right_curve)
            self.views[count].addItem(curve)
            count += 1

    def delete_plots(self):
        """
        Delete all plots

        :return:
        """
        if self.single_axis:
            for curve in self.curves:
                self.plot.removeItem(curve)
        else:
            # Delete old plots if exists
            for i, view in enumerate(self.views):
                view.removeItem(self.curves[i])

            for a in self.axis:
                self.ci.removeItem(a)

        # Remove plotItem
        if self.plot is not None:
            self.ci.removeItem(self.plot)

        # Remove references to all chart items
        self.views = []
        self.axis = []
        self.curves = []

    def update_views(self):
        """
        Update the view so they scale properly.

        :return:
        """
        for view in self.views:
            if view == self.plot.vb:
                continue
            view.setGeometry(self.plot.vb.sceneBoundingRect())

    def set_autoscale(self, flag):
        """
        Enable or disable the autoscale.

        :param flag: (bool) True to enable the autoscale, False otherwise.
        :return:
        """
        self.auto_scale = flag

        if self.auto_scale:
            self.plot.enableAutoRange()
            for view in self.views:
                view.enableAutoRange()
        else:
            self.plot.disableAutoRange()
            for view in self.views:
                view.disableAutoRange()
                    


    def do_autoscale(self):
        """
        Auto-scale x/y range of the current plot
        """
        #Use autoRange instead enableAutoRange when autoscale not set so that 
        #it isn't persistant. This way we can use this function for one time 
        #auto-scale and for persistant autoscales
        if self.auto_scale:
            self.plot.enableAutoRange()
            for view in self.views:
                view.enableAutoRange()
        else:
            self.plot.autoRange()
            for view in self.views:
                view.autoRange()

                
    def reset_xrange(self):
        """
        Set x range of the current plot to maximum buffer size
        Not supported cases where the x values are not the buffer samples
        """

        #
        # Cases where x-values are not buffer samples
        #
        if self.current_xaxes != 'None' or self.display_mode.is_fft() or self.histogram:
            return
        
        xmin = 0;
        xmax = self.max_length
        self.plot.setXRange(xmin, xmax)
        for view in self.views:
            view.setXRange(xmin, xmax)
            
    def wait(self):
        """

        :return:
        """
        self.mutex.lock()

    def signal(self):
        """

        :return:
        """
        self.mutex.unlock()

    def update_buffer(self, value):
        """

        :param value:
        :return:
        """
        self.max_length = value
        self.new_buffer = True
        
    def set_range(self, **kwargs):
        """
        Set data range for data filtering.
        Any data out of range will be filtered out, and not plotted.

        :param kwargs:
        :return:
        """
        self._max = kwargs.get("max", None)
        self._min = kwargs.get("min", None)

    def filter(self, data, pair=None):
        """
        Filter data out of range

        :param data:
        :param pair:
        :return:
        """
        rd, rt = data, pair
        if self._max is not None:
            mask = rd <= self._max
            rd = rd[mask]
            if pair is not None:
                rt = rt[mask]
        if self._min is not None:
            mask = rd >= self._min
            rd = rd[mask]
            if pair is not None:
                rt = rt[mask]
        if pair is not None:
            return rd, rt
        return rd

    def set_display_mode(self, value):
        """

        :param value:
        :return:
        """
        try:
            self.display_mode = DisplayMode(value)    
        except ValueError:
            raise ValueError(f"{str(value)} is not valid display mode.")

        self.plot.autoScale = True

        # Mode changed, iterate over the curves and set moving average to None
        for curve in self.curves:
            curve.plotdata_ave = None

    def set_fft_filter(self, value):
        """
        Set fft filter to use. Valid values are None / "none" and "hamming".

        :param value: (None or string) Filter to be used on the data, before the fft.
        :return:
        """
        if value is None:
            value = "none"
        
        try:
            self.fft_filter = FFTFilter(value)
        except ValueError:
            raise ValueError(f"{str(value)} is not valid FFT filter type.")            

    def set_average(self, value):
        """
        Set average number

        :param value:
        :return:
        """
        self.average = value

    def set_histogram(self, flag):
        """
        Set flag to enable/disable histogram plotting

        :param flag:
        :return:
        """
        if flag != self.histogram:
            self.new_plot = True

        self.histogram = flag

    def set_binning(self, value):
        """
        Set number for binning

        :param value:
        :return:
        """
        self.bins = value
   
    def clear_sample_data(self, pvname):
        """
        Clear sample data for PV, usually when the connection is lost.  
        """
        if pvname in self.sample_data:
            self.sample_data[pvname] = 0

    def clear_waveform_data(self, pv_name : str) -> None :
        '''
        Empty cache and trigger cache of one specific PV's data.

        :param pv_name: The name of the PV. 
        '''
        to_delete = [key for key in self.data.keys() if pv_name in key]
        for key in to_delete:
            del self.data[key]
        self.trigger.clear_waveform_data(pv_name)

    def clear_all(self) -> None :
        ''' Reset plot with empty channel and empty channels, cache and trigger cache. '''
        self.setup_plot([])
        self.data = {}
        self.channels = []
        self.trigger.trig_data = {}

    def data_process(self, data_generator):
        """
        Process raw data off the wire

        :param data_generator: generator that yields pvaccess data from the wire as key/value pairs. 
        :return:
        """
        # Increment array count
        self.arraysReceived += 1

        # Check if scope is frozen
        if self.is_freeze:
            return

        self.wait()
        new_size = self.data_size
        vector_len = 0

        got_data = False
        
        for k, v in data_generator():
            if k == self.current_arrayid:
                if self.lastArrayId is not None:
                    if v - self.lastArrayId > 1:
                        self.lostArrays += 1
                self.lastArrayId = v
                if self.data_size == 0:
                    new_size += 4
            else:
                # Do the same job for all waveforms.
                for waveform in self.channels:
                    array_id = waveform.test_array_id
                    last_test_array = waveform.last_test_array
                    if (k == array_id):
                        if (last_test_array is not None) and (v - last_test_array > 1):
                            self.lostArrays += 1
                        waveform.last_test_array = v

            # If pvaccess modules was build without numpy, normal Python list is returned. Make conversion here.
            if type(v) is list:
                v = np.array(v)

            if np.isscalar(v):
                v = np.array([v])
                
            if type(v) is not np.ndarray:
                continue

            # At this point in program we found an nd array that may or may not have data. nd array is
            # not an EPICS7 NDArray, but a numpy ndarray.
            # If no data in a pv field, we just skip this whole loop iteration.
            if len(v) == 0:
                continue

            if not np.isscalar(v[0]):
                continue

            if self.data_size == 0:
                type_size = v[0].dtype.itemsize
                new_size += type_size * len(v)
                
            got_data = True

            if self.sampling_mode:
                self.sample_data[k] = v[-1]
            elif self.trigger.trigger_mode:
                self.trigger.add_to_trig_data(k, v)
            else:
                # We are in free running mode. Only last max_length of the data can be stored.
                arr = np.append(self.data.get(k, []), v)
                self.data[k] = arr[-self.max_length:]
        if got_data:
            self.trigger.draw_data()
                
        self.signal()
        if self.data_size == 0:
            self.data_size = new_size
            
        if self.first_data:
            self.first_data = False

    def calculate_fft(self, data, sample_period, mode, filter):
        """
        Calculate fft on the input array.

        :param data: (Numpy array) Data to be transformed.
        :param sample_period: (int) Sampling period of the data.
        :param mode: (DisplayMode) This could be either "fft" or "psd".
        :param filter: (FFTFilter) Filter to be applied on the data before transformation.

        :return: (Numpy array, Numpy array) xf and yf transformations of the data.
        """
        xf = yf = None

        # Perform transformation for X axis
        data_len = len(data)
        xf = np.fft.rfftfreq(data_len, d=sample_period)

        # Calculate window
        if filter == FFTFilter.HAMMING:
            window = np.hamming(data_len)
            data = data * window
        
        # Perform transformation for Y axis
        yf_raw = np.abs(np.fft.rfft(data))

        # Apply normalisation filter        
        vertical_gain = self.__fft_vgain[str(filter)]

        if mode == DisplayMode.FFT:
            yf = 2. * vertical_gain * yf_raw / data_len
            # DC bin has different scale factor
            yf[0] = yf[0] / 2.
        elif mode == DisplayMode.PSD:
            # Sample period in sec. Sample rate is 1/sample rate. Hz/bin=srage/nf
            sample_rate = 1. / sample_period
            yf = 2. * vertical_gain * vertical_gain * yf_raw * yf_raw / (sample_rate * sample_rate)
            # DC bin has different scale factor
            yf[0] = yf[0] / 4.
        else:
            raise ValueError(f"{str(mode)} is not valid mode for FFT.")

        return xf, yf

    def exponential_moving_average(self, data, data_ave):
        """
        Calculate exponential moving average on the data.

        :param data: (ndarray) Latest array data.
        :param data_ave: (ndarray) Data average until now.

        :return: (ndarray) Exponential moving average.
        """
        alpha = 2. / (self.average + 1.)

        if data_ave is None or len(data_ave) != len(data):
            data_ave=np.array([1e-10] * len(data))

        new_data_ave = data_ave + alpha * (data - data_ave)

        return new_data_ave

    def autocorrelation_fft(self, x, filter):
        # Zero-pad the data to twice its length
        n = len(x)

        if(filter == FFTFilter.HAMMING):
            # Apply Hamming window
            hamming_window = np.hamming(n)
            x_wind = hamming_window * x
        else:
            x_wind = x

        # Compute the FFT
        x = np.fft.fft(x_wind)

        # Compute the power spectrum
        p = x * np.conjugate(x)

        # Compute the inverse FFT to get the autocorrelation
        autocorr = np.fft.ifft(p).real

        # Normalize the result
        autocorr = autocorr[:n] / n
        return autocorr

    def draw_curve(self, count, data, channel, draw_trig_mark=False):
        """
        Draw a waveform curve

        :param index:  count of curve for plotting
        :param data:   curve data for plotting
        :param draw_trig_mark: flag whether drawing trigger mark
        :return:
        """

        data_len = len(data)
        if data_len == 0:
            return
        
        # in case on time reference in PV, we declare sample period to sec per sample.
        # 1 second per sample as initial
        sample_period = 1.0
        # time array
        time_array = None

        if self.current_xaxes != "None":
            if len(self.data.get(self.current_xaxes,[])) == data_len:
            # TODO later to support: frequency field & sample period as time reference
            # TODO need to handle multiple waveform plotting with different data length
            # Currently, support time only
                sample_period = np.diff(self.data[self.current_xaxes]).mean()
                time_array = self.data[self.current_xaxes]
            elif not self.xaxis_on_error:
                self.error_callback('Time axis does not fit data length, perhaps it is missing in data or not started. Ignoring it.') # error_callback should be set to ScopeControllerBase.notify_warning
                self.xaxis_on_error = True

        xf = yf = None
        if self.display_mode == DisplayMode.DIFF:
            data = np.diff(data)
        elif self.display_mode.is_fft():
            if data_len == 0:
                return            
            
            xf, yf = self.calculate_fft(data, sample_period, self.display_mode, self.fft_filter)
        elif self.display_mode == DisplayMode.AUTOCORFFT:
            data = self.autocorrelation_fft(data, self.fft_filter)
            
        if self.histogram and not self.display_mode.is_fft():
            self.curves[count].opts['stepMode'] = True
        else:
            self.curves[count].opts['stepMode'] = False

        # Exponential moving average
        if self.average > 1:
            if yf is not None:
                yf = self.exponential_moving_average(yf, self.curves[count].plotdata_ave)
                self.curves[count].plotdata_ave = yf
            else:
                data = self.exponential_moving_average(data, self.curves[count].plotdata_ave)
                self.curves[count].plotdata_ave = data

        # Exponential moving average
        if self.average > 1:
            if yf is not None:
                yf = self.exponential_moving_average(yf, self.curves[count].plotdata_ave)
                self.curves[count].plotdata_ave = yf
            else:
                data = self.exponential_moving_average(data, self.curves[count].plotdata_ave)
                self.curves[count].plotdata_ave = data

        # Draw curve for the fft or psd mode
        if self.display_mode.is_fft():
            self.curves[count].setData(xf, yf)

        # Calculate histogram bins and draw the curve
        elif self.histogram and not self.display_mode.is_fft():
            d = self.filter(data)
            y, x = np.histogram(d, bins=self.bins)
            self.curves[count].setData(x, y)

        # Draw waveform where X axis are indexes of data array which is drawn on Y axis
        elif time_array is None:
            data_to_plot = self.filter(data) + channel.dc_offset
            self.curves[count].setData(data_to_plot)
            self.__handle_trigger_marker__(draw_trig_mark, [data_to_plot.min(), data_to_plot.max()])

        # Draw time_array on the X axis and data on Y
        else:
            d, t = self.filter(data, time_array)
            data_to_plot = d + channel.dc_offset
            self.curves[count].setData(t - t[0], data_to_plot)
            self.__handle_trigger_marker__(draw_trig_mark, [data_to_plot.min(), data_to_plot.max()], time_array=time_array)

    def __handle_trigger_marker__(self, draw_trig_mark, mark_size, time_array=None):
        """
        Draw vertical line trigger mark at the specified marktime.

        :param draw_trig_mark: (bool) Flag if trigger line should be drawn.
        :param marktime: (int) Sample number at which the trigger mark happened.
        :param mark_size: (Array [int, int]) Y range for the trigger mark.
        :return:
        """
        if self.trigger.is_triggered() and self.trigger.enable_trigger_marker:
            if draw_trig_mark:
                if time_array is not None:
                    marktime = self.trigger.trigger_timestamp - time_array[0]
                else:
                    marktime = self.trigger.display_trigger_index()
                    
                # Add trigger marker on plotting
                pvnames = [c.pvname for c in self.channels if c.should_be_drawn(self.current_xaxes, self.trigger.data_time_field)] # Uses only effectively displayed channels to calculate the minimum and maximum.
                min_value = max_value = None
                if self.single_axis:
                    for field, value in self.data.items():
                        if field in pvnames:
                            a_min = np.amin(value).item()
                            a_max = np.amax(value).item()
                            min_value = a_min if min_value is None else min(min_value, a_min)
                            max_value = a_max if max_value is None else max(max_value, a_max)
                    mark_size = [min_value, max_value]
                else:
                    mark_size = mark_size
                # Create a new pen each plot to ensure line width is 1
                # Otherwise, line can disappear when increasing size of data to plot
                self.trigMarker.setPen(pyqtgraph.mkPen(color='r', width=1))
                self.trigMarker.setData(np.array([marktime, marktime]),
                                        np.array(mark_size))
        else:
            self.trigMarker.clear()
            
    def update_drawing(self):
        """
        Update display plotting

        :return:
        """

        if self.first_data or not self.plotting_started:
            # TODO this is to help to over come race condition. To be done in a better way later
            # self.signal()
            return

        # Do not update the drawing if image is frozen
        if self.is_freeze:
            return

        # Take ownership the self.data variable which holds all the waveforms
        self.wait()
        
        self.mouse_over.populate_cache()

        if self.sampling_mode:
            max_samples = min(max([0] + [len(v) for v in self.data.values()]) + 1, self.max_length)
            
            for k, v in self.sample_data.items():
                data = np.append(self.data.get(k, []), v)[-self.max_length:]
                #
                # If started collecting PV data after other PVs, pad any data points before collection
                # with zeros
                #
                if max_samples > len(data):
                    data = np.pad(data, (max_samples - len(data), 0), 'constant', constant_values=0)
                self.data[k] = data;
        # Iterate over the names (channels) selected on the GUI and draw a line for each
        count = 0
        draw_trig_mark = True
        for idx, ch in enumerate(self.channels):
            if ch.should_be_drawn(self.current_xaxes, self.trigger.data_time_field):
                data = self.data.get(ch.pvname)
                if data is not None:
                    self.draw_curve(count, data, ch, draw_trig_mark)
                    draw_trig_mark = False
                count = count + 1

        # Axis scaling
        if self.new_plot:
            self.do_autoscale()
            self.reset_xrange()
        elif self.new_buffer:
            self.reset_xrange()

        self._setup_ticks()
            
        self.new_plot = False
        self.new_buffer = False        

        self.trigger.finish_drawing()

        self.mouse_over.update_textbox()
        
        self.update_fps()

        # Release the ownership on the self.data
        self.signal()

    def update_fps(self):
        """
        Update fps statistics

        :return:
        """
        now = time.time()
        dt = now - self.lastTime
        self.lastTime = now
        if self.fps is None:
            self.fps = 1.0 / dt
        else:
            s = np.clip(dt * 3., 0, 1)
            self.fps = self.fps * (1 - s) + (1.0 / dt) * s

    def notify_plotting_started(self, val):
        self.plotting_started = val

    def start_trigger(self):
        self.trigger.connect_to_callback()
        self.trigger.transfer()

    def stop_trigger(self):
        self.trigger.reset()
        self.trigger.disconnect_to_callback()
