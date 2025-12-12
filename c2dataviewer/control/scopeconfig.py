# -*- coding: utf-8 -*-

from .scope_config_base import ScopeConfigureBase
import re
from .config import Scope
from typing import Any

"""
C2 DATA VIEWER is distributed subject to a Software License Agreement found
in the file LICENSE that is included with this distribution.
SPDX-License-Identifier: EPICS

Copyright 2018 UChicago Argonne LLC
 as operator of Argonne National Laboratory

PVA object viewer utilities

@author: Guobao Shen <gshen@anl.gov>
"""

DEFAULT_MINIMUM_CHANNELS_NUMBER : int = 4
DEFAULT_MINIMUM_WAVEFORMS_NUMBER : int = 4
DEFAULT_MAXIMUM_CHANNELS_NUMBER : int = 10
DEFAULT_MAXIMUM_WAVEFORM_NUMBER : int = 10

class Configure(ScopeConfigureBase):
    """
    Scope application configuration panel settings
    """
    def __init__(self, params, **kwargs):
        """

        :param params: parameters parsed from command line and configuration file
        :param pvs: pv name dictionary, format: {"alias": "PV:Name"}
        """
        super().__init__(params, **kwargs)
        self.pvs = kwargs.get("pv", None)
        self.pvs_ca = kwargs.get("pv_ca", None)

        self.default_color = ['#FFFF00', '#FF00FF', '#55FF55', '#00FFFF', '#5555FF',
                              '#5500FF', '#FF5555', '#0000FF', '#FFAA00', '#000000']
        
        self.default_arrayid = kwargs.get("arrayid", None)
        if not self.default_arrayid:
            self.default_arrayid = self.params.get(Scope.ARRAYID, 'None')
        self.default_xaxes = kwargs.get("xaxes", "None")
        if not self.default_xaxes:
            self.default_xaxes = self.params.get(Scope.XAXES, 'None')
        
    def new_channel(number : int, color : str, field : list[str], dc_offset : float) -> dict[str, Any] : 
        channel = {
            'name' : 'Channel %s' % number,
            'type' : 'group',
            'children': [
                {
                    'name' : 'Color',
                    'type' : 'color',
                    'value' : color,
                    'readonly' : True
                },
                {'name' : 'Field', 'type' : 'list', 'limits' : [field], 'value' : field},
                {'name' : 'DC offset', 'type' : 'float', 'value' : dc_offset},
                {
                    'name' : 'Axis location',
                    'type' : 'list',
                    'limits' :
                    {
                        'Left' : 'left',
                        'Right' : 'right',
                    },
                    'value' : 'Left'},
            ]
        }
        return channel

    def assemble_channel(self, section=None):
        """
        Assemble channel information for plotting

        :param section:
        :return:
        """
        # get channel counts to display, 4 by default
        self.counts = self.params.get(Scope.CHANNEL_COUNT, default = DEFAULT_MINIMUM_CHANNELS_NUMBER)
        channel = []

        #Read channel information.  Channel order is
        #determined by order in config
        chan_cfgs = self.params.get_channel_config()

        self.counts = max(self.counts, len(chan_cfgs))
        self.counts = min(self.counts, DEFAULT_MAXIMUM_CHANNELS_NUMBER)
        
        for i in range(self.counts):
            default_cfg = {
                'field' : 'None',
                'dcoffset': 0.0
            }
            
            chcfg = chan_cfgs[i] if len(chan_cfgs) > i else default_cfg
            field = chcfg.get('field', default_cfg['field'])
            dcoffset = float(chcfg.get('dcoffset', default_cfg['dcoffset']))

            channel.append(Configure.new_channel(number = i + 1, color = self.default_color[i], field = field, dc_offset = dcoffset))

        return channel
    
    def new_waveform(number : int, color : str, pv : str, dc_offset : float, array_id : str = 'None', array_id_limits : list[str] = ['None']) -> dict[str, Any] :
        waveform = {
            'name' : 'Waveform %s' % number,
            'type' : 'group',
            'children' : [
                {
                    'name' : 'Color',
                    'type' : 'color',
                    'value' : color,
                    'readonly' : True
                },
                {'name' : 'PV', 'type' : 'str', 'value' : pv},
                {'name' : 'PV status', 'type' : 'str', 'value' : '', 'readonly' : True},
                {'name' : 'ArrayId', 'type' : 'list', 'limits' : array_id_limits, 'value' : array_id},
                {'name' : 'DC offset', 'type' : 'float', 'value' : dc_offset},
                {
                    'name' : 'Axis location',
                    'type' : 'list',
                    'limits' :
                    {
                        'Left' : 'left',
                        'Right' : 'right',
                    },
                    'value' : 'Left'
                },
                {'name' : 'Start', 'type' : 'bool', 'value' : False}
            ]
        }
        return waveform
    
    def assemble_waveforms(self) -> list[dict[str, Any]] :
        '''
        Returns a list of dictionnaries to be passed to pyqtgraph.parametertree.Parameter object to create the parameters of the application.

        :return: The list of dictionnaries. Keys of each dictionnary are parameters (PV, DC offset, ...) as string and values, their corresponding value ('MY:PV', 5, ...).
        '''
        self.counts_waveforms = self.params.get(Scope.WAVEFORM_COUNT, default = DEFAULT_MINIMUM_WAVEFORMS_NUMBER)
        
        waveforms = []

        waveforms_configure_lookup_values = self.params.get_waveform_config()

        # self.pvs_ca contains dictionnaires PV names from command line as string as values.
        # Extract these names and put it in a list of dictionnaries under the 'pv' key of each dictionnary (see return description).
        waveforms_configurations = []
        if self.pvs_ca :
            for pv_name in self.pvs_ca.values() :
                    if not any(pv_name in parameters.values() for parameters in waveforms_configure_lookup_values) :
                        waveforms_configurations.append({'pv' : pv_name})
        # Put, after the command line PVs, the PVs from configuration file, given by Parser.get_waveform_config method.
        waveforms_configurations.extend(waveforms_configure_lookup_values)

        self.counts_waveforms = max(self.counts_waveforms, len(waveforms_configurations))
        self.counts_waveforms = min(self.counts_waveforms, DEFAULT_MAXIMUM_WAVEFORM_NUMBER)
        
        for i in range(self.counts_waveforms):
            default_configuration = {
                'pv' : '',
                'dcoffset': 0.0,
                'arrayid': 'None'
            }
            
            waveform_configuration = waveforms_configurations[i] if len(waveforms_configurations) > i else default_configuration
            pv = waveform_configuration.get('pv', default_configuration['pv'])
            dcoffset = float(waveform_configuration.get('dcoffset', default_configuration['dcoffset']))
            array_id = waveform_configuration.get('arrayid', default_configuration['arrayid'])
            array_id_limits = ['None']
            if array_id != 'None':
                array_id_limits.append(array_id)

            waveforms.append(Configure.new_waveform(number = i + 1, color = self.default_color[i], pv = pv, dc_offset = dcoffset, array_id = array_id, array_id_limits = array_id_limits))

        return waveforms

    def assemble_display(self, section=None):
        display = super().assemble_display(section=section, app_section_key="SCOPE", default_autoscale=False)
        #FIXME: move this to base class once get mouseover support in striptool
        children = display['children']
        mouse_over = self.params.get(Scope.MOUSE_OVER, default=False)
        newchildren = [
            { "name" : "Mouse Over", "type": "bool", "value": mouse_over }
            ]
        children.extend(newchildren)
        
        return display

    def assemble_acquisition(self, section=None):
        buffer_unit = self.params.get(Scope.BUFFER_UNIT, default='samples')
        buffer_unit = buffer_unit.title()

        acquisition = super().assemble_acquisition(section, buffer_unit=buffer_unit)
        children = acquisition['children']

        start = self.params.get(Scope.CONNECT_ON_START, False)
        ca_mode = self.params.get(Scope.CA_MODE, False)

        id_value = ["None"]
        if self.default_arrayid != "None":
            id_value.append(self.default_arrayid)

        if self.pvs is not None:
            pv = list(self.pvs.values())[0]
        else:
            # it means PV map is not specified from command line
            # get one from configuration
            pv = self.params.get(Scope.PV)
            # if PV is available by default
            self.pvs = {pv: pv}

        child_ca = {'name' : 'CA Mode', 'type' : 'bool', 'value' : ca_mode, 'default' : False}
        newchildren = [
            {"name": "Buffer Unit", "type": "list", "limits": ["Samples", "Objects"], "value": buffer_unit},
            {"name": "PV", "type": "str", "value": pv},
            {"name": "PV status", "type": "str", "value": "Disconnected", "readonly": True},
            {'name' : 'ArrayId', 'type' : 'list', 'limits' : id_value, 'value' : self.default_arrayid},
            {"name": "Start", "type": "bool", "value": start},
            {'name' : 'Start CA', 'type' : 'bool', 'value' : start},
            {'name' : 'Channels', 'type' : 'int', 'value' : self.counts, 'limits' : [1, 10]},
            {'name' : 'Waveforms', 'type' : 'int', 'value' : self.counts_waveforms, 'limits' : [1, 10]},
        ]

        children.insert(1, child_ca)
        children.extend(newchildren)
        
        return acquisition

    def assemble_statistics(self):
        stats = super().assemble_statistics()
        children = stats['children']
        children.append( {"name": "Avg Samples/Obj", "type": "float", "value": 0, "readonly":True, "decimals":20})
        return stats
    
    def assemble_config(self, section=None):
        # Assemble extra configuration information for plotting which x-axes.

        axes = ["None"]
        if self.default_xaxes != "None":
            axes.append(self.default_xaxes)

        self.default_major_tick = self.params.get(Scope.MAJORTICKS, 0)
        self.default_minor_tick = self.params.get(Scope.MINORTICKS, 0)

        # Load extra display fields from config
        extra_fields = self.params.get(Scope.EXTRA_DISPLAY_FIELDS, [])

        mo_display_loc = self.params.get(Scope.MOUSE_OVER_DISPLAY_LOCATION, 'bottom_right').replace('_', '-')

        cfg = {"name": "Config",
               "type": "group",
               "expanded": True,
               "children": [
                   {"name": "X Axes", "type": "list", "limits": axes, "value": self.default_xaxes},
                   {"name": "Major Ticks", "type": "int", "value": self.default_major_tick, 'decimals':20},
                   {"name": "Minor Ticks", "type": "int", "value": self.default_minor_tick, 'decimals':20},
                   {"name": "Extra Display Fields", "type": "checklist", "value": extra_fields, "limits": extra_fields, "expanded": False},
                   {"name": "MO Disp Location", "type": "list", "limits": ['top-right', 'bottom-right', 'bottom-left'], "value": mo_display_loc}

                   ]
               }
        return cfg

    def parse(self):
        """

        :return:
        """
        
        display = self.assemble_display()
        channel = self.assemble_channel()
        waveforms = self.assemble_waveforms()
        acquisition = self.assemble_acquisition()
        trigger = self.assemble_trigger()
        cfg = self.assemble_config()

        # line up in order
        paramcfg = [acquisition, trigger, display, cfg]
        for ch in channel:
            paramcfg.append(ch)
        for waveform in waveforms:
            paramcfg.append(waveform)
        statistics = self.assemble_statistics()
        
        paramcfg.append(statistics)

        return paramcfg
