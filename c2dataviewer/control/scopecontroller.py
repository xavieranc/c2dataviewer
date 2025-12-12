# -*- coding: utf-8 -*-

"""
C2 DATA VIEWER is distributed subject to a Software License Agreement found
in the file LICENSE that is included with this distribution.
SPDX-License-Identifier: EPICS

Copyright 2018 UChicago Argonne LLC
 as operator of Argonne National Laboratory

PVA object viewer utilities

@author: Guobao Shen <gshen@anl.gov>
"""

import numpy as np
import pyqtgraph
import pvaccess as pva
from ..model import ConnectionState
from .scope_controller_base import ScopeControllerBase
from .scopeconfig import Configure
from ..view.scope_display import PlotChannel as ScopePlotChannel
from ..model.pvapy_plugins import Channel
from pyqtgraph.Qt import QtCore
import math
import statistics
from typing import Callable

class Waveform:
    '''
    Sub-controller for waveform channel.
    No parameters (PV name, color, ...) are stored here. Instead, refers to Parameter object to know these, to avoid duplication of data (and possibly synchronisation problems).
    '''
    def __init__(self, index : int, controller) :
        '''
        :param index: The number of the waveform in parent's list of waveform (from one).
        :param controller: The main controller of Scope application.
        '''
        self.index = index
        self.parent_controller = controller
        self.channel = None
        self.update_channel()

    def update_channel(self, delete_previous : bool = False) -> None :
        '''
        Try to create connection with current name. If it fails or PV name is empty, reset.
        Should be called when PV name is changed.

        :param delete_previous: If so, deletes previous associated Channel. Else deactivates it.
        '''
        pv_name = self.get_pv_name()
        if pv_name != '':
            self.set_channel(channel = self.parent_controller.model.create_connection(pv_name, pva.CA, status_callback = self.connection_changed_callback, error_callback = self.parent_controller.notify_warning), delete_previous = delete_previous)
            if not self.channel:
                self.reset()
        else:
            self.reset()

    def set_channel(self, channel : Channel, delete_previous : bool = False) -> None :
        '''
        Set channel attribute to new Channel object.

        :param channel: The new Channel object.
        :param delete_previous: If so, deletes previous associated Channel. Else deactivates it.
        '''
        if self.channel :
            self.channel.delete() if delete_previous else self.channel.deactivate()
        self.channel = channel

    def reset(self) -> None :
        self.stop()
        self.set_channel(channel = None, delete_previous = False)
        self.parent_controller.muted(lambda : self.get_parameters().child('PV').setValue(''))
        self.connection_changed_callback(ConnectionState.EMPTY, '')

    def start(self) -> None :
        '''
        Tries to start the Waveform's Channel. Resets Waveform if channel is None or already running.
        Called by self.start_stop. 
        '''
        if self.channel and not self.channel.is_running():
            self.parent_controller.reset_object()
            self.channel.start(routine = self.monitor_callback)
            parameters = self.get_parameters()
            self.parent_controller.muted(lambda : parameters.child('Start').setValue(1))
            self.parent_controller.muted(lambda : parameters.child('PV').setReadonly(True))
        elif self.get_pv_name() == '':
            self.parent_controller.notify_warning('Can not start empty PV.')
            self.parent_controller.muted(lambda : self.get_parameters().child('Start').setValue(0))
        else:
            self.parent_controller.notify_warning('Waveform channel object is None or already running.')
            self.reset()
            
    def stop(self) -> None :
        '''
        Stop Waveform's Channel.
        Called either by self.start_stop or by parent_controller.stop_plotting_ca.
        '''
        if self.channel:
            self.channel.stop()
            parameters = self.get_parameters()
            pv_name = parameters.child('PV').value()
            self.parent_controller._win.graphicsWidget.clear_waveform_data(pv_name = pv_name)
            self.parent_controller.muted(lambda : parameters.child('Start').setValue(0))
            self.parent_controller.muted(lambda : parameters.child('PV').setReadonly(False))

    def start_stop(self) -> None :
        '''
        Either start or stop Waveform's Channel, based on the parameter tree.
        Called by parent_controller.set_waveform_data after user changed Start parameter.
        '''
        self.start() if self.get_parameters().child('Start').value() else self.stop()
            
    def connection_changed_callback(self, state : ConnectionState, msg) -> None :
        '''
        Change Parameter based on waveform's new state.
        '''
        ScopeController.execute_later(lambda : self.parent_controller.muted(lambda : self.get_parameters().child('PV status').setValue(state)))
        
    def monitor_callback(self, data : pva.pvaccess.PvObject) -> None :
        '''
        Callback passed to Waveform's Channel.
        Aims to refactor the data so each field is prefixed by the PV name and a separator so data do not mix up when registered by PlotWidget.
        For instance, 'value' field of 'MY:PV' PV becomes 'MY:PV.value'.
        '''
        data_dict = dict(data)
        pv_name = self.parent_controller.parameters.child('Waveform %s' % self.index, 'PV').value()
        for key in data_dict.keys():
            data_dict[pv_name + self.SEPARATOR + key] = data_dict.pop(key)
        self.parent_controller.monitor_callback(data_dict)

    def get_parameters(self) -> pyqtgraph.parametertree.Parameter :
        return self.parent_controller.parameters.child('Waveform %s' % self.index)

    def get_pv_name(self) -> str :
        return self.get_parameters().child('PV').value()

    def get_color(self) -> pyqtgraph.QtGui.QColor :
        return self.get_parameters().child('Color').value()

    def get_dc_offset(self) -> int :
        return self.get_parameters().child('DC offset').value()

    def get_axis_location(self) -> str :
        return self.get_parameters().child('Axis location').value()

    def is_started(self) -> bool :
        return self.get_parameters().child('Start').value()

    def get_array_id(self) -> str :
        return self.get_parameters().child('ArrayId').value()

    def create_plot_object(self) -> ScopePlotChannel :
        '''
        Generates PlotChannel object for PlotWidget.
        Called by parent_controller.update_waveforms_plot.

        :return: PlotChannel object corresponding to Waveform's parameters.
        '''
        return ScopePlotChannel(pvname = self.get_pv_name() + self.SEPARATOR + 'value', color = self.get_color().name(), dc_offset = self.get_dc_offset(), axis_location = self.get_axis_location(), started = self.is_started(), array_id = self.get_pv_name() + self.SEPARATOR + self.get_array_id())

    def delete(self) -> None :
        self.reset()

    SEPARATOR = '.'
    
class ScopeController(ScopeControllerBase):

    def __init__(self, widget, model, parameters, warning, **kwargs):
        
        """

        :param model:
        :param parameters:
        :param channels:
        """
        
        self.color_pattern = ['#FFFF00', '#FF00FF', '#55FF55', '#00FFFF', '#5555FF', '#5500FF', '#FF5555', '#0000FF', '#FFAA00', '#000000']

        nchannels = parameters.child('Acquisition', 'Channels').value()
        self.channels = []
        for i in range(nchannels):
            self.channels.append(ScopePlotChannel('None', self.color_pattern[i]))
        super().__init__(widget, model, parameters, warning, channels = self.channels)

        number_waveforms = parameters.child('Acquisition', 'Waveforms').value()
        self.waveforms = [Waveform(index = i + 1, controller = self) for i in range(number_waveforms)]

        self.default_arrayid = "None"
        self.default_xaxes = "None"
        self.current_arrayid = "None"
        self.current_xaxes = "None"

        #auto-set buffer size to waveform length.  This will be
        #disabled if buffer is set manually
        self.auto_buffer_size = True
        self.model.status_callback = self.connection_changed
        self._win.graphicsWidget.error_callback = self.notify_warning
        self._win.graphicsWidget.trigger.warning.signal.connect(self.notify_warning)
        self.connection_timer = pyqtgraph.QtCore.QTimer()
        self.connection_timer.timeout.connect(self.__check_connection)
        class FlagSignal(QtCore.QObject):
            sig = QtCore.pyqtSignal(bool)
            def __init__(self):
                QtCore.QObject.__init__(self)

        self.connection_timer_signal = FlagSignal()
        self.connection_timer_signal.sig.connect(self.__failed_connection_callback)
        self.buffer_unit = 'Samples'
        self.object_size = None
        self.object_size_tally = []

        if kwargs.get('default_configuration', False) :
            self.default_config(**kwargs)
        
    def default_config(self, **kwargs):
        """
        Update configuration based on commmand-line arguments
        Called in the top-level function and passes in the command-line arguments
        for scope as key-word arguments.
        Any options not set should be set in kwargs as None
        """
        default_pv = self.parameters.child('Acquisition', 'PV').value()
        self.model.update_device(name = default_pv, error_callback = self.connection_changed)

        ca_mode = self.parameters.child('Acquisition', 'CA Mode').value()
        if kwargs['ca_mode']:
            ca_mode = True
            
        start = self.parameters.child("Acquisition").child("Start").value()
        if kwargs['connect_on_start']:
            start = True

        bunit = self.parameters.child("Acquisition").child("Buffer Unit").value().strip()
        if bunit != "":
            self.buffer_unit = bunit
        
        super().default_config(**kwargs, buffer_unit=self.buffer_unit)
        self.auto_buffer_size = not self.parameters.child("Acquisition").child("Buffer (%s)" % self.buffer_unit).value()

        # Apply arrayid from command-line or config file
        arrayid = kwargs.get('arrayid') or self.parameters.child("Acquisition").child("ArrayId").value()
        if arrayid and arrayid != "None":
            self.set_arrayid(arrayid)

        # Apply xaxes from command-line or config file
        xaxes = kwargs.get('xaxes') or self.parameters.child("Config").child("X Axes").value()
        if xaxes and xaxes != "None":
            self.set_xaxes(xaxes)
            
        self._win.graphicsWidget.set_range(**kwargs)

        if kwargs['fields']:
            fields = kwargs['fields'].split(',')
            total_fields = len(fields)
            if total_fields > len(self.channels) :
                self.parameters.child('Acquisition', 'Channels').setValue(total_fields)
                self.set_channels_number(number = total_fields)
            for i, f in enumerate(fields):
                chan_name = "Channel %s" % (i + 1)
                child = self.parameters.child(chan_name)
                c = child.child("Field")
                c.setValue(f)
                self.set_channel_data(chan_name, 'Field', c.value())

        #Update other channel information
        for idx in range(len(self.channels)):
            chan_name = "Channel %s" % (idx + 1)
            child = self.parameters.child(chan_name)
            c = child.child("DC offset")
            if c.value() != 0:
                self.set_channel_data(chan_name, 'DC offset', c.value())
                
        child = self.parameters.child("Config").child("MO Disp Location")
        self._win.graphicsWidget.set_mouseover_display_location(child.value())
        
        # Apply Mouse Over setting from config
        mouse_over = self.parameters.child("Display").child("Mouse Over").value()
        self._win.graphicsWidget.set_enable_mouseover(mouse_over)

        # Apply Extra Display Fields from config
        extra_fields = self.parameters.child("Config").child("Extra Display Fields").value()
        if extra_fields:
            self._win.graphicsWidget.set_mouseover_fields(extra_fields)

        if ca_mode:
            self.parameters.child('Acquisition', 'CA Mode').setValue(1)
        self.set_CA_mode(mode = self.parameters.child('Acquisition', 'CA Mode').value())  

        if start:
            if ca_mode:
                self.start_plotting_ca()
            else:
                self.start_plotting()
            
    def __flatten_dict(dobj, kprefixs=[]):
        """
        Genenerator that can traverse through nested dictionaries and return
        key/value pairs

        For example given {'a':{'b':1}, 'c': 2}, it would yield
        ('a.b', 1) and ('c', 2)

        :param dobj dictionary object
        :param kprefixs  list of key of the directary and it's predecessors
        :yields key, value
        """
        sep = '.'
        for k, v in dobj.items():
            if type(v) == dict:
                yield from ScopeController.__flatten_dict(v, kprefixs + [k])
            else:
                yield sep.join(kprefixs + [k]), v

    def execute_later(instruction : Callable[[], None]) -> None :
        '''
        Executes instruction after event pile is emptied, avoiding SegFaults. See QtCore's documentation.

        :param instruction: The function to be executed.
        '''
        QtCore.QTimer.singleShot(0, instruction)

    def muted(self, instruction : Callable[[], None]) -> None :
        '''
        Disconnects then reconnects signal emited on parameter change, avoiding recursive calls and SegFaults.
        Should be used each time code modifies a parameter.
        
        :param: instruction: The function to be executed.
        '''
        # Try to disconnect signal. If already disconnected, TypeError is raised, then execute instruction as it is.
        try:
            self.parameters.sigTreeStateChanged.disconnect(self.parameter_change)
            instruction()
            self.parameters.sigTreeStateChanged.connect(self.parameter_change)
        except TypeError:
            instruction()

    def set_channels_number(self, number : int) -> None :
        '''
        Changes the number of channel input sections.
        
        :param number: The new number of sections that should be displayed.
        '''
        if number > 10 or number < 1 or type(number) is not int:
            raise ValueError(f'Invalid channel number: {number}. Must be integer between 1 and 10.')
        previous_number = len(self.channels)
        if previous_number > number:
            self.channels = self.channels[: number]
            while previous_number > number:
                self.muted(lambda : self.parameters.child('Channel %s' % previous_number).remove())
                previous_number -= 1
        else:
            while previous_number < number:
                self.muted(lambda : self.parameters.insertChild(self.parameters.child('Statistics'), Configure.new_channel(previous_number + 1, self.color_pattern[previous_number], ['None'], 0)))
                self.channels.append(ScopePlotChannel('None', self.color_pattern[previous_number]))
                previous_number = len(self.channels)
        self._win.parameterPane.setParameters(self.parameters, showTop = False)
        self.update_fdr()
        self._win.graphicsWidget.setup_plot(channels = self.channels)

    def set_waveforms_number(self, number : int) -> None :
        '''
        Changes the number of waveform input sections.
        
        :param number: The new number of sections that should be displayed.
        '''
        if number > 10 or number < 1:
            raise ValueError(f'Invalid waveform number: {number}.. Must be integer between 1 and 10.')
        previous_number = len(self.waveforms)
        if previous_number > number:
            parameters_to_delete = []
            while previous_number > number:
                self.waveforms.pop().delete()
                parameters_to_delete.append(self.parameters.child('Waveform %s' % previous_number))
                previous_number -= 1
            ScopeController.execute_later(lambda : self.delete_parameters(parameters_to_delete))
        else:
            while previous_number < number:
                self.muted(lambda : self.parameters.insertChild(self.parameters.child('Statistics'), Configure.new_waveform(previous_number + 1, self.color_pattern[previous_number], '', 0)))
                self.waveforms.append(Waveform(index = previous_number + 1, controller = self))
                previous_number = len(self.waveforms)
        self._win.parameterPane.setParameters(self.parameters, showTop = False)
        self.update_fdr()
        self.update_waveforms_plot()

    def delete_parameters(self, parameters : list[pyqtgraph.parametertree.Parameter]) -> None :
        for parameter in parameters :
            self.muted(lambda : parameter.remove())

    def get_fdr(self):
        """
        Get EPICS7 PV field description back as a list

        :return: list of field description
        :raise PvaException: raise pvaccess exception when channel cannot be connected.
        """
        fdr = []
        fdr_scalar = []
        fdr_nonnumeric = []
        
        if not self.parameters.child('Acquisition', 'CA Mode').value():
            pv = self.model.get()
            if pv is None:
                return fdr, fdr_scalar, fdr_nonnumeric
            pv_structure = pv.getStructureDict()
        else:
            pv_structure = {}
            got_data = False
            for waveform in self.waveforms:
                pv_name = waveform.get_pv_name()
                if pv_name != '':
                    pv = waveform.channel.get()
                    pv_structure[pv_name] = pv.getStructureDict()
                    got_data = True
            if not got_data:
                return fdr, fdr_scalar, fdr_nonnumeric

        pv_dictionary = {k:v for k,v in ScopeController.__flatten_dict(pv_structure)}
        for k, v in pv_dictionary.items():
            if type(v) == list and all(type(e) == pva.ScalarType for e in v):
                if v[0] is pva.ScalarType.STRING:
                    fdr_nonnumeric.append(k)
                else:
                    fdr.append(k)
            elif type(v) == pva.ScalarType:
                fdr_scalar.append(k)
            if type(v) != np.ndarray:
                continue
            if len(v) == 0:
                continue

        fdr.sort()
        fdr_scalar.sort()
        return fdr, fdr_scalar, fdr_nonnumeric

    def update_fdr(self, empty=False):
        """
        Update EPICS7 PV field description

        :return:
        """
        if empty:
            fdr = []
            fdr_scalar = []
        else:
            try:
                fdr, fdr_scalar, fdr_nonnumeric = self.get_fdr()
            except pva.PvaException as e:
                self.notify_warning('Failed to get PV field description: ' + (str(e)))
                return

        fdr_all = fdr + fdr_nonnumeric
        fdr.insert(0, "None")
        fdr_scalar.insert(0, "None")

        # fill up the selectable pull down menu for array ID
        if not self.parameters.child('Acquisition', 'CA Mode').value():
            child = self.parameters.child("Acquisition").child("ArrayId")
            self.muted(lambda : child.setLimits(fdr_scalar))
            if child.value() != 'None':
                self.set_arrayid(child.value())
        else:
            for waveform in self.waveforms:
                pv_name = waveform.get_pv_name()
                index = waveform.index
                waveform_limits = [element.replace(pv_name + Waveform.SEPARATOR, '') for element in fdr_scalar if pv_name in element]
                waveform_limits.insert(0, 'None')
                child = self.parameters.child('Waveform %s' % index, 'ArrayId')
                self.muted(lambda : child.setLimits(waveform_limits))
                if child.value() != 'None':
                    self.set_arrayid(child.value(), index)
        
        # fill up the selectable pull down menu for x axes
        child = self.parameters.child("Config").child("X Axes")
        self.muted(lambda : child.setLimits(fdr))
        if child.value() != 'None':
            self.set_xaxes(child.value())
                
        child = self.parameters.child("Trigger").child("Data Time Field")
        # Preserve current value before updating limits
        current_value = child.value()
        self.muted(lambda : child.setLimits(fdr))
        # Restore value if it's still valid
        if current_value != 'None' and current_value in fdr:
            self.muted(lambda : child.setValue(current_value))
        if child.value() != 'None':
            self._win.graphicsWidget.trigger.set_data_time_field(data_time_field = child.value())
        
        for idx in range(len(self.channels)):
            chan_name = "Channel %s" % (idx + 1)
            child = self.parameters.child(chan_name)
            c = child.child("Field")
            self.muted(lambda : c.setLimits(fdr))
            if c.value() != 'None':
                self.set_channel_data(chan_name, 'Field', c.value())

        child = self.parameters.child('Config').child('Extra Display Fields')
        # Preserve current values before updating limits
        current_values = child.value()
        self.muted(lambda : child.setLimits(fdr_all))
        # Restore values that are still valid
        if current_values:
            valid_values = [v for v in current_values if v in fdr_all]
            if valid_values:
                self.muted(lambda : child.setValue(valid_values))
            
    def __failed_connection_callback(self, flag):
        """
        Called initially with flag=False if failed to connect to PV
        Will start periodically checking the connection.
        Once able to connect successfully, this function is called
        again with flag=True
        """
        if not flag:
            # Start periodically checking connection
            self.connection_timer.start(5000)
        else:
            # Got a connection, so turn off timer
            # and reload the fdr
            restart = self._win.graphicsWidget.plotting_started
            self.connection_timer.stop()
            self.stop_plotting()
            self.update_fdr()
            if restart:
                self.start_plotting()                
            
    def connection_changed(self, state, msg):
        self.muted(lambda : self.parameters.child("Acquisition", 'PV status').setValue(state))

        if state == 'Failed to connect':
            self.connection_timer_signal.sig.emit(False)

    def __check_connection(self):
        def success_callback(data):
            self.connection_timer_signal.sig.emit(True)

        self.model.async_get(success_callback=success_callback)

    def set_arrayid(self, value : str, index : int = None) -> None:
        """
        Set current field name for array id.
        If index is provided, then consider it for the index-th Waveform. Simply pass as Parameter object stores Waveforms data.
            
        :param value: The new value.
        """
        if not index:
            if value != self.current_arrayid:
                self.current_arrayid = value
                self._win.graphicsWidget.current_arrayid = value
        else:
            pass

    def set_xaxes(self, value):
        """
        Set current field name for x axes
            
        :param value:
        :return:
        """
        if value != self.current_xaxes:
            self.current_xaxes = value
            self._win.graphicsWidget.set_xaxes(value)

    def set_major_ticks(self, value):
        self._win.graphicsWidget.set_major_ticks(value)

    def set_minor_ticks(self, value):
        self._win.graphicsWidget.set_minor_ticks(value)


    def set_channel_data(self, channel_name, field, value):
        # avoid changes caused by Statistic updating
        for i, chan in enumerate(self.channels):
            if channel_name != 'Channel %i' % (i + 1):
                continue

            if field == 'Field':
                chan.pvname = value
            elif field == 'DC offset':
                chan.dc_offset = value
            elif field == 'Axis location':
                chan.axis_location = value
            
        self._win.graphicsWidget.setup_plot(channels=self.channels)

    def set_waveform(self, waveform_name : str, parameter_name : str) -> None :
        '''
        Called by self.parameter_change when user changes waveforms parameters.
        Deals with the parameter name to know what to do.

        :param waveform_name: The Waveform's field Parameter's name (ex: 'Waveform 2').
        :param parameter_name: The field Parameter's name (ex: 'PV status').
        '''
        i = int(waveform_name[-1]) # Get index from the name.
        waveform = self.waveforms[i - 1] # Remind that there is a shift between parameters and list (Waveform 1 (index 1) <-> position in list 0).
        if parameter_name == 'PV':
            waveform.update_channel()
            self.update_fdr()
        elif parameter_name == 'PV status':
            return # Noting to do. PV status is just information for user.
        elif parameter_name == 'DC offset':
            pass
        elif parameter_name == 'Axis location':
            pass
        elif parameter_name == 'ArrayId':
            pass
        elif parameter_name == 'Start':
            waveform.start_stop()
        else:
            raise Exception('parameter_name is invalid.')
        # Now that Waveform parameters have changed, update View.
        self.update_waveforms_plot()

    def update_waveforms_plot(self) -> None :
        '''
        Generates PlotChannels corresponding to each Waveform and setup the View with these new objets.
        '''
        self._win.graphicsWidget.setup_plot(channels = [waveform.create_plot_object() for waveform in self.waveforms if waveform.get_pv_name() != ''])

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
                if childName == "Acquisition.Freeze":
                    self.freeze(mode = data)
                elif childName == "Acquisition.CA Mode":
                    self.set_CA_mode(mode = data)
                elif childName == "Acquisition.PV":
                    # stop DAQ and update pv info
                    self.stop_plotting()
                    self.model.update_device(name = data, restart = False, error_callback = self.connection_changed)
                    if data != "":
                        self.update_fdr()
                    else:
                        self.update_fdr(empty=True)   
                    self.reset_object()
                elif childName == "Acquisition.Start":
                    if data:
                        self.start_plotting()
                    else:
                        self.stop_plotting()
                elif childName == 'Acquisition.Start CA':
                    self.start_stop_ca()
                elif 'Channel ' in childName:
                    chan, field = childName.split('.')
                    self.set_channel_data(chan, field, data)
                elif 'Waveform ' in childName and not 'PV status' in childName:
                    self.set_waveform(*childName.split('.')) # First arugment : Waveform name; second : Waveform parameter.
                elif childName == "Acquisition.ArrayId":
                    self.set_arrayid(data)
                elif childName == 'Acquisition.Channels':
                    self.set_channels_number(number = data)
                elif childName == 'Acquisition.Waveforms':
                    self.set_waveforms_number(number = data)
                elif childName == "Config.X Axes":
                    self.set_xaxes(data)
                elif childName == "Config.Major Ticks":
                    self.set_major_ticks(data)
                elif childName == "Config.Minor Ticks":
                    self.set_minor_ticks(data)
                elif childName == "Acquisition.Buffer Unit":
                    self.set_buffer_unit(data)
                elif 'Acquisition.Buffer' in childName:
                    self.auto_buffer_size = False
                    self.__calc_buffer_size()
                elif "Config.Extra Display Field" in childName:
                    self._win.graphicsWidget.set_mouseover_fields(data);
                elif "Config.MO Disp Location" in childName:
                    self._win.graphicsWidget.set_mouseover_display_location(data);
                elif childName == "Display.Mouse Over":
                    self._win.graphicsWidget.set_enable_mouseover(data)
        super().parameter_change(params, changes)
        
    def __calc_buffer_size(self):
        #
        # This function will adjust the number of samples to plot
        # based on buffer size, buffer unit, and object size
        # Called whenever one of these settings has changed
        #
        
        if self.buffer_unit == "Objects":
            if self.object_size:
                nobj = self.parameters.child("Acquisition").child("Buffer (Objects)").value()
                nsamples = nobj * self.object_size
                self._win.graphicsWidget.update_buffer(nsamples)
            
    def update_buffer_samples(self, size):
        """
        Sets number of samples in buffer

        :param size  number of samples
        """
        if self.buffer_unit == 'Samples':
            super().update_buffer_samples(size)
            return

        if self.buffer_unit == 'Objects':
            if self.object_size:
                nobj = math.ceil(size / self.object_size)
                self.muted(lambda : self.parameters.child("Acquisition").child("Buffer (Objects)").setValue(nobj))
                self.__calc_buffer_size()
            else:
                self._win.graphicsWidget.update_buffer(size)
        else:
            raise Exception('Unknown buffer unit %s' % (self.buffer_unit))

    def set_buffer_unit(self, name):
        """
        Set units for buffer size.

        :param name buffer unit.  
        """
        if self.buffer_unit == name:
            return

        param = self.parameters.child("Acquisition").child("Buffer (%s)" % (self.buffer_unit))
        newname = "Buffer (%s)" % (name)
        self.muted(lambda : param.setName(newname))
        self.buffer_unit = name

        #Update buffer size based on current number of samples
        if self._win.graphicsWidget.max_length:
            self.update_buffer_samples(self._win.graphicsWidget.max_length)
        else:
            if self.buffer_unit == "Objects":
                nobj = self.parameters.child("Acquisition").child("Buffer (Objects)").value()
                if nobj == 0:
                    #default to 1 object
                    self.muted(lambda : self.parameters.child("Acquisition").child("Buffer (Objects)").setValue(1))
                self.__calc_buffer_size()

    def set_object_size(self, size):
        """
        Set number of samples per object

        :param size number of samples per object
        """
        if size == self.object_size:
            return
        
        self.object_size = size
        self.__calc_buffer_size()

    def reset_object(self) -> None :
        self.auto_buffer_size = True
        self.object_size = None
        self.object_size_tally = []
        
    def monitor_callback(self, data):
        # Calculate object size
        objlen = 0
        for k, v in ScopeController.__flatten_dict(dict(data)):
            try:
                objlen = max(len(v), objlen)
            except:
                pass

        if objlen > 0:
            self.set_object_size(objlen)

            #Default buffer size to number of samples in an object
            #if buffer size was not explicitly set
            if self.auto_buffer_size:
                self.update_buffer_samples(self.object_size)

        self.object_size_tally.append(objlen)
        self.object_size_tally = self.object_size_tally[-5:]
        
        if not self._win.graphicsWidget.max_length:
            return
            
        def generator():
            yield from ScopeController.__flatten_dict(dict(data))
        self._win.graphicsWidget.data_process(generator)

    def start_plotting(self):
        """

        :return:
        """

        # stop a model first anyway to ensure it is clean
        self.model.stop()
        
        # start a new monitor
        self.model.start(self.monitor_callback)
        
        try:                
            super().start_plotting()
            self.muted(lambda : self.parameters.child("Acquisition").child("Start").setValue(1))
        except Exception as e:
            self.parameters.child("Acquisition").child("Start").setValue(0)
            self.notify_warning('Failed to start plotting: ' + str(e))
            
    def stop_plotting(self):
        """

        :return:
        """
        super().stop_plotting()
        self.muted(lambda : self.parameters.child("Acquisition").child("Start").setValue(0))
        # Stop data source
        self.model.stop()

    def start_plotting_ca(self) -> None :
        super().start_plotting()
    
    def stop_plotting_ca(self) -> None :
        for waveform in self.waveforms:
            waveform.stop()
        self.update_waveforms_plot()
        super().stop_plotting()

    def start_stop_ca(self) -> None :
        '''
        Starts or stops CA acquisition based on the value of the corresponding parameter.
        Called when user changed the latter.
        '''
        self.start_plotting_ca() if self.parameters.child('Acquisition', 'Start CA').value() else self.stop_plotting_ca()

    def start_trigger(self) -> None :
        '''
        Make the trigger's parameters on read only before starting trigger.
        '''
        if not self.trigger_is_monitor and not self.model.trigger is None:
            self.muted(lambda : self.set_trigger_parameters_readonly(True))    
        super().start_trigger()

    def stop_trigger(self) -> None :
        '''
        Make the trigger's parameters writable after having stopped trigger.
        '''
        super().stop_trigger()
        self.muted(lambda : self.set_trigger_parameters_readonly(False))

    def set_trigger_parameters_readonly(self, mode : bool) -> None :
        '''
        Make the trigger parameters either writable or read only.

        :param mode: True for setting read only, False for writable.
        '''
        self.parameters.child('Trigger', 'PV').setReadonly(mode)
        self.parameters.child('Trigger', 'Mode').setReadonly(mode)
        self.parameters.child('Trigger', 'Data Time Field').setReadonly(mode)
        self.parameters.child('Trigger', 'Time Field').setReadonly(mode)

    def update_status(self):
        super().update_status()

        if len(self.object_size_tally) > 0:
            avg_obj_size = statistics.mean(self.object_size_tally)
            self.parameters.child("Statistics").child('Avg Samples/Obj').setValue(avg_obj_size)
            self.set_object_size(math.ceil(avg_obj_size))

    def set_CA_mode(self, mode : bool = True) -> None :
        '''
        Hide or show parameters in function of the mode, stop the previous acquisition and update field description to match new fields/waveforms.

        :param mode: True for setting CA mode, False for standard mode.
        '''
        toggles = [
            (True, ('Acquisition', 'PV')),
            (True, ('Acquisition', 'PV status')),
            (True, ('Acquisition', 'ArrayId')),
            (True, ('Acquisition', 'Start')),
            (False, ('Acquisition', 'Start CA')),
            (True, ('Acquisition', 'Channels')),
            (False, ('Acquisition', 'Waveforms')),
        ]
        toggles.extend(
            (True, ('Channel %s' % (i + 1), )) for i in range(len(self.channels))
        )
        toggles.extend(
            (False, ('Waveform %s' % (i + 1), )) for i in range(len(self.waveforms))
        )
        for boolean, parameter in toggles :
            self.muted(lambda : self.parameters.child(*parameter).setOpts(visible = boolean ^ mode))

        if mode:
            self.stop_plotting()
        else:
            self.stop_plotting_ca()
        self.update_fdr()

    def serialize(self, cfile):
        """
        Serialize the current scope configuration to an IO object.

        :param cfile: IO object (file-like) to write configuration to
        """
        from .config import Serializer, AppType, Scope

        serializer = Serializer()

        # Write app identifier
        serializer.set_app(AppType.SCOPE)

        # Serialize base scope configuration (Display, Acquisition, Trigger)
        # This includes buffer unit and buffer size
        self.serialize_scope_config(serializer)

        # Serialize scope-specific settings
        pv = self.parameters.child("Acquisition", "PV").value()
        if pv:
            serializer.set(Scope.PV, pv)

        start = self.parameters.child("Acquisition", "Start").value() or self.parameters.child("Acquisition", "Start CA").value()
        serializer.set(Scope.CONNECT_ON_START, start)

        ca_mode = self.parameters.child('Acquisition', 'CA Mode').value()
        serializer.set(Scope.CA_MODE, ca_mode)

        # Serialize Display settings
        mouse_over = self.parameters.child("Display", "Mouse Over").value()
        serializer.set(Scope.MOUSE_OVER, mouse_over)

        # Serialize Config settings
        arrayid = self.parameters.child("Acquisition", "ArrayId").value()
        if arrayid and arrayid != "None":
            serializer.set(Scope.ARRAYID, arrayid)

        xaxes = self.parameters.child("Config", "X Axes").value()
        if xaxes and xaxes != "None":
            serializer.set(Scope.XAXES, xaxes)

        major_ticks = self.parameters.child("Config", "Major Ticks").value()
        if major_ticks:
            serializer.set(Scope.MAJORTICKS, major_ticks)

        minor_ticks = self.parameters.child("Config", "Minor Ticks").value()
        if minor_ticks:
            serializer.set(Scope.MINORTICKS, minor_ticks)

        extra_fields = self.parameters.child("Config", "Extra Display Fields").value()
        if extra_fields:
            serializer.set(Scope.EXTRA_DISPLAY_FIELDS, ','.join(extra_fields))

        mo_location = self.parameters.child("Config", "MO Disp Location").value()
        if mo_location:
            serializer.set(Scope.MOUSE_OVER_DISPLAY_LOCATION, mo_location)

        # Serialize channel configurations
        chan_cfgs = []
        for idx, channel in enumerate(self.channels):
            chan_num = idx + 1
            chan_param = self.parameters.child(f"Channel {chan_num}")

            field = chan_param.child("Field").value()
            if field and field != "None":
                chan_cfg = {
                    'field': field,
                    'color': channel.color
                }

                dc_offset = chan_param.child("DC offset").value()
                if dc_offset != 0:
                    chan_cfg['dcoffset'] = dc_offset

                axis_location = chan_param.child("Axis location").value()
                if axis_location:
                    chan_cfg['axislocation'] = axis_location

                chan_cfgs.append(chan_cfg)

        if chan_cfgs:
            serializer.write_channels('CHANNELS', chan_cfgs)

        waveforms_configurations = []
        for waveform in self.waveforms:
            pv_name = waveform.get_pv_name()
            if pv_name != '':
                waveform_configuration = {'pv' : pv_name}

                dc_offset = waveform.get_dc_offset()
                if dc_offset != 0:
                    waveform_configuration['dcoffset'] = dc_offset
                
                array_id = waveform.get_array_id()
                if array_id != 'None':
                    waveform_configuration['arrayid'] = array_id
                
                waveforms_configurations.append(waveform_configuration)
                
        if waveforms_configurations:
            serializer.write_waveforms(waveforms_configurations = waveforms_configurations)

        # Write to file
        serializer.write(cfile)

    def freeze(self, mode : bool) -> None :
        '''
        Prevents user to change waveforms' parameters while screen is frozen.

        :param mode: True for freezing, else False.
        '''
        for i in range(len(self.waveforms)):
            for child in self.parameters.child('Waveform %s' % (i + 1)).children():
                if child.name() in ['PV', 'ArrayId', 'DC offset', 'Axis location', 'Start']:
                    self.muted(lambda : child.setReadonly(mode))