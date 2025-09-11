"""
C2 DATA VIEWER is distributed subject to a Software License Agreement found
in the file LICENSE that is included with this distribution.
SPDX-License-Identifier: EPICS
"""
from .pvconfig import PvConfig
import re
from ..model import *
from .scope_config_base import ScopeConfigureBase

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
            cfg = params['STRIPTOOL']
        except:
            return
        
        self.default_proto = make_protocol(cfg.get('DefaultProtocol', 'ca'))

        cfgpvs = {}
        for k, v in cfg.items():
            if bool(re.match('chan', k, re.I)):
                ch, param = k.split('.')
                chcfg = cfgpvs.get(ch, PvConfig())

                if param == 'pv':
                    pvname, proto = parse_pv(v)
                    chcfg.pvname = pvname
                    if proto is None:
                        proto = self.default_proto
                    chcfg.set_proto(proto)
                    
                elif param == 'color':
                    chcfg.color = str(v)
                    
                cfgpvs[ch] = chcfg

        for p in cfgpvs.values():
            self.pvs[p.pvname] = p
            
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

        children.append({"name": "Sample Mode", "type":"bool", "value": True})

        return acquisition
    
    def assemble_display(self, section=None):
        display = super().assemble_display(section=section, app_section_key="STRIPTOOL", default_autoscale=True)

        return display
    
    def parse(self):
        try:
            acquisition = self.assemble_acquisition(self.params["ACQUISITION"])
        except KeyError:
            acquisition = self.assemble_acquisition()

        try:
            display = self.assemble_display(self.params["DISPLAY"])
        except KeyError:
            display = self.assemble_display()
            
        statistics = self.assemble_statistics()
        # line up in order
        paramcfg = [acquisition, display, statistics]

        return paramcfg


