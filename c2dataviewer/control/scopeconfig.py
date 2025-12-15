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

        if self.pvs is not None:
            pv = list(self.pvs.values())[0]
        else:
            # it means PV map is not specified from command line
            # get one from configuration
            pv = self.params.get(Scope.PV)
            # if PV is available by default
            self.pvs = {pv: pv}

        newchildren = [
            {"name": "Buffer Unit", "type": "list", "limits": ["Samples", "Objects"],
             "value": buffer_unit},
            {"name": "PV", "type": "str", "value": pv},
            {"name": "PV status", "type": "str", "value": "Disconnected", "readonly": True},
            {"name": "Start", "type": "bool", "value": start},
            {'name' : 'Channels', 'type' : 'int', 'value' : self.counts, 'limits' : [1, 10]},
        ]

        children.extend(newchildren)
        
        return acquisition

    def assemble_statistics(self):
        stats = super().assemble_statistics()
        children = stats['children']
        children.append( {"name": "Avg Samples/Obj", "type": "float", "value": 0, "readonly":True, "decimals":20})
        return stats
    
    def assemble_config(self, section=None):
        # Assemble extra configuration information for plotting
        # which is ArrayId selection, and x axes
        id_value = ["None"]
        if self.default_arrayid != "None":
            id_value.append(self.default_arrayid)

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
                   {"name": "ArrayId", "type": "list", "limits": id_value, "value": self.default_arrayid},
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
        acquisition = self.assemble_acquisition()
        trigger = self.assemble_trigger()
        cfg = self.assemble_config()

        # line up in order
        paramcfg = [acquisition, trigger, display, cfg]
        for ch in channel:
            paramcfg.append(ch)
        statistics = self.assemble_statistics()
        
        paramcfg.append(statistics)

        return paramcfg
