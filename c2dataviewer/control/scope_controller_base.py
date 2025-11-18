"""
C2 DATA VIEWER is distributed subject to a Software License Agreement found
in the file LICENSE that is included with this distribution.
SPDX-License-Identifier: EPICS
"""

import numpy as np
import pyqtgraph
import pvaccess as pva
from ..model import ConnectionState
import math
from .config import Scope
from PyQt5 import QtWidgets

class ScopeControllerBase:
    def __init__(self, widget, model, parameters, warning, channels=[], **kwargs):
        self._win = widget
        self.model = model
        self.parameters = parameters
        self.data = None
        # refresh frequency: every 100 ms by default
        self.refresh = 100

        self.plotting_started = False

        self.timer = pyqtgraph.QtCore.QTimer()
        self.timer.timeout.connect(self._win.graphicsWidget.update_drawing)
        self._win.graphicsWidget.set_autoscale(parameters.child('Display', 'Autoscale').value())
        self._win.graphicsWidget.set_model(self.model)

        self._warning = warning
        self._warning.warningConfirmButton.clicked.connect(lambda: self.accept_warning())

        self.arrays = np.array([])
        self.lastArrays = 0

        self.default_trigger = None
        self.trigger_is_monitor = False
        self.trigger_auto_scale = False

        self._win.graphicsWidget.set_histogram(parameters.child('Display', 'Histogram').value())
        single_axis = parameters.child('Display', 'Single axis').value()
        self._win.graphicsWidget.setup_plot(channels=channels, single_axis=single_axis)

        display_mode = parameters.child('Display', 'Mode').value()
        if(display_mode != "normal"):
            self.set_display_mode(display_mode)
            
        # timer to update status with statistics data
        self.status_timer = pyqtgraph.QtCore.QTimer()
        self.status_timer.timeout.connect(self.update_status)
        self.status_timer.start(1000)

        # Setup save configuration button
        self._win.saveConfigButton.clicked.connect(self._on_save_config_action)


    def set_display_mode(self, val):
        self._win.graphicsWidget.set_display_mode(val)
        self._win.graphicsWidget.setup_plot()
        # Disable multiaxis for the FFT-type modes. As at the time of the
        # writing this code pyqtgraph does not support logarithmic scale in multiaxis configuration.
        if self._win.graphicsWidget.display_mode.is_fft():
            self.parameters.child("Display").child("Single axis").setReadonly()
        else:
            self.parameters.child("Display").child("Single axis").setWritable()

    def set_trigger_pv(self, pvname):
        if self._win.graphicsWidget.plotting_started:
            self.notify_warning("Stop plotting first before changing trigger PV")
            return
                
        pvname = pvname.strip()
        if pvname == '':
            return
        
        proto = 'ca'
        name = pvname
        
        if "://" in name:
            proto, name = pvname.split("://")

        try:
            pvfields = self.model.update_trigger(name, proto=proto.lower())
            child = self.parameters.child("Trigger").child("Time Field")
            if proto == 'ca':
                child.hide()
                self._win.graphicsWidget.trigger.trigger_time_field = 'timeStamp'
            else:
                self._win.graphicsWidget.trigger.trigger_time_field = None
                pvfields.insert(0, 'None')
                child.show()
                # Get current value before updating limits
                current_value = child.value()
                child.setLimits(pvfields)
                # Restore value if it's valid, otherwise set to None
                if current_value in pvfields:
                    child.setValue(current_value)
                else:
                    child.setValue('None')                                
                                
        except Exception as e:
            self.notify_warning("Channel {}://{} timed out. \n{}".format(proto, name, repr(e)))


    def default_config(self, **kwargs):
        buffer_unit = kwargs.get('buffer_unit', 'Samples')
            
        max_length = self.parameters.child("Acquisition").child("Buffer (%s)" % buffer_unit).value()
        if max_length and buffer_unit == 'Samples':
            self.update_buffer_samples(int(max_length))
            
        self._win.graphicsWidget.set_binning(self.parameters.child("Display").child("Num Bins").value())

        refresh = self.parameters.child("Display").child("Refresh").value()
        if refresh:
            self.set_freshrate(refresh)

        try:
            trigger_pv = self.parameters.child("Trigger").child("PV").value()
            self.set_trigger_pv(trigger_pv)

            trigger_mode = self.parameters.child("Trigger").child("Mode").value()
            self.set_trigger_mode(trigger_mode)
        
            self.trigger_auto_scale = self.parameters.child("Trigger").child("Autoscale Buffer").value()
        except:
            pass

        
    def update_buffer_samples(self, size):
        """
        Sets number of samples in buffer
        
        :param size  size of buffer in number of samples
        """
        self._win.graphicsWidget.update_buffer(size)
        self.parameters.child("Acquisition").child("Buffer (Samples)").setValue(self._win.graphicsWidget.max_length)
            
    def parameter_change(self, params, changes):
        """
        
        :param params:
        :param changes:
        :return:
        """
        for param, change, data in changes:
            if change == "value":
                path = self.parameters.childPath(param)
                if path is not None:
                    childName = '.'.join(path)
                else:
                    childName = param.name()

                if childName == "Trigger.PV":
                    if data is None:
                        return
                    self.set_trigger_pv(data)
                elif childName == "Trigger.Mode":
                    self.set_trigger_mode(data)
                elif childName == "Trigger.Threshold":
                    self._win.graphicsWidget.trigger.trigger_level = data
                elif childName == "Trigger.Data Time Field":
                    self._win.graphicsWidget.trigger.data_time_field = data
                elif childName == "Trigger.Time Field":
                    self._win.graphicsWidget.trigger.trigger_time_field = data
                elif childName == "Trigger.Autoscale Buffer":
                    self.trigger_auto_scale = data
                elif childName == "Acquisition.Buffer (Samples)":
                    self._win.graphicsWidget.update_buffer(data)
                elif childName == "Acquisition.Freeze":
                    self._win.graphicsWidget.set_is_freeze(data)
                elif childName == "Display.Mode":
                    self.set_display_mode(data)
                elif childName == "Display.FFT filter":
                    self._win.graphicsWidget.set_fft_filter(data)
                elif childName == "Display.Exp moving avg":
                    self._win.graphicsWidget.set_average(data)
                elif childName == "Display.Autoscale":
                    self._win.graphicsWidget.set_autoscale(data)
                elif childName == "Display.Single axis":
                    self._win.graphicsWidget.setup_plot(single_axis=data)
                elif childName == "Display.Histogram":
                    self._win.graphicsWidget.set_histogram(data)
                elif childName == "Display.Num Bins":
                    self._win.graphicsWidget.set_binning(data)
                elif childName == "Display.Refresh":
                    self.set_freshrate(data)

    def set_freshrate(self, value):
        """
        Set time to refresh
            
        :param value: time interval to plot, in second
        :return:
        """
        plotting_started = self._win.graphicsWidget.plotting_started
        self.stop_plotting()
        self.refresh = value*1000.0
        if plotting_started:
            self.start_plotting()


    def start_plotting(self):
        """
            
        :return:
        """

        try:
            self.timer.timeout.disconnect()
            self.timer.stop()
        except Exception:
            pass

        self.stop_trigger()
        
        # Setup free run plotting
        if not self._win.graphicsWidget.trigger_mode():
            self.timer.timeout.connect(self._win.graphicsWidget.update_drawing)
            self.timer.start(int(self.refresh))
        else:
            self.start_trigger()

        self._win.graphicsWidget.notify_plotting_started(True)
        
    def stop_plotting(self):
        """

        :return:
        """
        self._win.graphicsWidget.notify_plotting_started(False)

        self.timer.stop()
        self.stop_trigger()
                    
    def set_trigger_mode(self, value):
        """
        Set trigger mode.
    
        :param value:
        :return:
        """
        trigger_mode = value != 'none'
        if trigger_mode != self._win.graphicsWidget.trigger_mode():
            if self._win.graphicsWidget.plotting_started:
                action = 'on' if trigger_mode else 'off'
                self.notify_warning('Stop plotting first before turning trigger %s' % (action))
                return
            
        self._win.graphicsWidget.set_trigger_mode(trigger_mode)
            
        trigger_type = None
        if trigger_mode:
            self._win.graphicsWidget.trigger.set_trigger_type(value)
            
    def start_trigger(self):
        """
        Process to start DAQ in trigger mode
            
        :return:
        """
        if not self.trigger_is_monitor:
            if self.model.trigger is None:
                raise Exception('Trigger PV is not set or is invalid')
            

            
            self.model.start_trigger(self._win.graphicsWidget.trigger.data_callback)
            self.trigger_is_monitor = True

    def stop_trigger(self):
        """
        Stop trigger mode
        :return:
        """
        self.trigger_is_monitor = False
        self.model.stop_trigger()
        
    def accept_warning(self):
        """
            
        :return:
        """
        self._warning.close()

    def notify_warning(self, msg):
        #close previous warning
        self.accept_warning()
            
        self._warning.warningTextBrowse.setText(msg)
        self._warning.show()

        
    def update_status(self):
        """
        Update statistics status.
            
        :return:
        """
        # Update display
        single_axis_child = self.parameters.child("Display", "Single axis")
        if single_axis_child.value() != self._win.graphicsWidget.single_axis:
            single_axis_child.setValue(self._win.graphicsWidget.single_axis)

        # Update statistics
        with self._win._proc.oneshot():
            cpu = self._win._proc.cpu_percent(None)

        # TODO algorithm to calculate Array/sec
        arraysReceived = self._win.graphicsWidget.arraysReceived
        n = arraysReceived - self.lastArrays
        self.lastArrays = arraysReceived
        self.arrays = np.append(self.arrays, n)[-10:]

        for q in self.parameters.child("Statistics").children():
            if q.name() == 'CPU':
                q.setValue(cpu)
            elif q.name() == 'Lost Arrays':
                q.setValue(self._win.graphicsWidget.lostArrays)
            elif q.name() == 'Tot. Arrays':
                q.setValue(self._win.graphicsWidget.arraysReceived)
            elif q.name() == 'Arrays/Sec':
                q.setValue(self.arrays.mean())
            elif q.name() == 'Bytes/Sec':
                q.setValue(self.arrays.mean() * self._win.graphicsWidget.data_size)
            elif q.name() == 'Rate':
                q.setValue(self._win.graphicsWidget.fps)

        try:
            for q in self.parameters.child("Trigger").children():
                if q.name() == "Trig Status":
                    stat_str = 'Disconnected'
                    if self.trigger_is_monitor:
                        stat_str = self._win.graphicsWidget.trigger.status()
                    q.setValue(stat_str)
                elif q.name() == "Trig Value":
                    q.setValue(str(self._win.graphicsWidget.trigger.trigger_value))
        except:
            pass

        #handle any auto-adjustments
        if self.trigger_auto_scale and self._win.graphicsWidget.trigger_mode():
            if self._win.graphicsWidget.trigger.missed_triggers > 0:
                newsize = self._win.graphicsWidget.trigger.missed_adjust_buffer_size

                # Round up to 3 10's places
                # ex. 12345 would be rounded to 12400
                precision = 3
                exp = math.ceil(math.log10(newsize))
                roundunit = 10**max(exp - precision, 0)
                newsize = math.ceil(newsize / roundunit) * roundunit

                self.update_buffer_samples(newsize)

    def serialize_scope_config(self, serializer):
        """
        Serialize scope base configuration to a Serializer instance.
        This includes Display, Acquisition, and Trigger settings.

        :param serializer: config.Serializer instance to write to
        """
        # Serialize Display settings
        display_mode = self.parameters.child("Display", "Mode").value()
        serializer.set(Scope.DISPLAY_MODE, display_mode)

        fft_filter = self.parameters.child("Display", "FFT filter").value()
        serializer.set(Scope.FFT_FILTER, fft_filter)

        average = self.parameters.child("Display", "Exp moving avg").value()
        serializer.set(Scope.AVERAGE, int(average))

        autoscale = self.parameters.child("Display", "Autoscale").value()
        serializer.set(Scope.AUTOSCALE, autoscale)

        single_axis = self.parameters.child("Display", "Single axis").value()
        serializer.set(Scope.SINGLE_AXIS, single_axis)

        histogram = self.parameters.child("Display", "Histogram").value()
        serializer.set(Scope.HISTOGRAM, histogram)

        n_bin = self.parameters.child("Display", "Num Bins").value()
        serializer.set(Scope.NBIN, int(n_bin))

        refresh = self.parameters.child("Display", "Refresh").value()
        # Convert from seconds to milliseconds
        serializer.set(Scope.REFRESH, int(refresh * 1000))

        # Serialize Acquisition settings
        # Try to get buffer unit (scope-specific)
        try:
            buffer_unit = self.parameters.child("Acquisition", "Buffer Unit").value()
            if buffer_unit:
                serializer.set(Scope.BUFFER_UNIT, buffer_unit)
                # Get buffer size based on buffer unit
                buffer_size = self.parameters.child("Acquisition", f"Buffer ({buffer_unit})").value()
                if buffer_size:
                    serializer.set(Scope.BUFFER, int(buffer_size))
        except:
            # If Buffer Unit doesn't exist, fall back to Buffer (Samples)
            try:
                buffer_samples = self.parameters.child("Acquisition", "Buffer (Samples)").value()
                if buffer_samples:
                    serializer.set(Scope.BUFFER, int(buffer_samples))
            except:
                pass

        # freeze = self.parameters.child("Acquisition", "Freeze").value()
        # Freeze is not in schema, but we can document it if needed

        # Serialize Trigger settings
        try:
            trigger_pv = self.parameters.child("Trigger", "PV").value()
            if trigger_pv:
                serializer.set(Scope.TRIGGER, trigger_pv)

            trigger_mode = self.parameters.child("Trigger", "Mode").value()
            serializer.set(Scope.TRIGGER_MODE, trigger_mode)

            threshold = self.parameters.child("Trigger", "Threshold").value()
            serializer.set(Scope.TRIGGER_THRESHOLD, threshold)

            autoscale_buffer = self.parameters.child("Trigger", "Autoscale Buffer").value()
            serializer.set(Scope.TRIGGER_AUTOSCALE_BUFFER, autoscale_buffer)

            time_field = self.parameters.child("Trigger", "Time Field").value()
            if time_field and time_field != "None":
                serializer.set(Scope.TRIGGER_TIME_FIELD, time_field)

            data_time_field = self.parameters.child("Trigger", "Data Time Field").value()
            if data_time_field and data_time_field != "None":
                serializer.set(Scope.TRIGGER_DATA_TIME_FIELD, data_time_field)
        except:
            # Trigger section may not exist in all scope types
            pass


    def _on_save_config_action(self):
        """
        Handle the save configuration action from the File menu.
        Opens a file dialog and saves the current configuration.
        """

        # Open file dialog to get save location
        file_path, _ = QtWidgets.QFileDialog.getSaveFileName(
            self._win,
            "Save Configuration",
            "",
            "C2 Data Viewer Config (*.c2dv);;All Files (*)"
        )

        if file_path:
            try:
                # Ensure file has .c2dv extension
                if not file_path.endswith('.c2dv'):
                    file_path += '.c2dv'

                # Save configuration
                with open(file_path, 'w') as f:
                    self.serialize(f)

                # Show success message
                QtWidgets.QMessageBox.information(
                    self._win,
                    "Success",
                    f"Configuration saved to:\n{file_path}"
                )
            except Exception as e:
                # Show error message
                QtWidgets.QMessageBox.critical(
                    self._win,
                    "Error",
                    f"Failed to save configuration:\n{str(e)}"
                )
