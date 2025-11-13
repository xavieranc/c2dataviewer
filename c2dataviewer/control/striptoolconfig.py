"""
C2 DATA VIEWER is distributed subject to a Software License Agreement found
in the file LICENSE that is included with this distribution.
SPDX-License-Identifier: EPICS
"""
from .pvconfig import PvConfig
import re
from .scope_config_base import ScopeConfigureBase
from .config import Striptool
import logging

def parse_pv(val):
    pvname = None
    if "://" in val:
        proto, pvname = val.split('://')
        return pvname, proto
    else:
        pvname = val
        return pvname, None

class StripToolConfigure(ScopeConfigureBase):
    def __init__(self, params, **kwargs):
        super().__init__(params, **kwargs)
        self.default_proto = None
        self.pvs = {}

        try:
            cfg = self.params.cfg['STRIPTOOL']
        except:
            return

        self.default_proto = self.params.get(Striptool.DEFAULT_PROTOCOL, default='ca')

        cfgpvs = self.params.get_channel_config(is_striptool=True)
        for cfg in cfgpvs:
            chcfg = PvConfig()
            for k, v in cfg.items():
                if k == 'pv':
                    pvname, proto = parse_pv(v)
                    chcfg.pvname = pvname
                    if proto is None:
                        proto = self.default_proto
                    chcfg.set_proto(proto)
                elif k == 'color':
                    chcfg.color = str(v)
            
            if chcfg.pvname:
                self.pvs[chcfg.pvname] = chcfg
            
        pvs = kwargs.get('pv')
        if pvs:
            for pv in pvs.values():
                chcfg = None
                pvname, proto = parse_pv(pv)
                if pvname in self.pvs:
                    chcfg = self.pvs[pvname]
                else:
                    chcfg = PvConfig()
                    chcfg.set_proto(self.default_proto)
                    
                chcfg.pvname = pvname
                if proto:
                    chcfg.set_proto(proto)
                self.pvs[pvname] = chcfg                

    def assemble_acquisition(self, section=None):
        acquisition = super().assemble_acquisition(section)
        children = acquisition['children']

        # Load Sample Mode from config
        sample_mode = self.params.get(Striptool.SAMPLEMODE, default=True)
        # Handle string values from config file
        if isinstance(sample_mode, str):
            sample_mode = sample_mode.lower() in ('true', '1', 'yes')

        children.append({"name": "Sample Mode", "type":"bool", "value": sample_mode})

        return acquisition
    
    def assemble_display(self, section=None):
        display = super().assemble_display(section=section, app_section_key="STRIPTOOL", default_autoscale=True)

        return display
    
    def parse(self):
        acquisition = self.assemble_acquisition()
        display = self.assemble_display()            
        statistics = self.assemble_statistics()
        # line up in order
        paramcfg = [acquisition, display, statistics]

        return paramcfg


