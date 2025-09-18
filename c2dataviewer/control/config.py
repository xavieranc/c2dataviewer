from collections import namedtuple
from enum import Enum, auto
from configparser import ConfigParser
import re
import logging

class Scope(Enum):
    BUFFER = auto()
    BUFFER_UNIT = auto()
    DISPLAY_MODE = auto()
    FFT_FILTER = auto()
    AVERAGE = auto()
    AUTOSCALE = auto()
    SINGLE_AXIS = auto()
    HISTOGRAM = auto()
    NBIN = auto()
    REFRESH = auto()
    TRIGGER = auto()
    TRIGGER_MODE = auto()
    CHANNEL_COUNT = auto()
    MOUSE_OVER = auto()
    CONNECT_ON_START = auto()
    PV = auto()
    ARRAYID = auto()
    XAXES = auto()
    MAJORTICKS = auto()
    MINORTICKS = auto()
    EXTRA_DISPLAY_FIELDS = auto()
    MOUSE_OVER_DISPLAY_LOCATION = auto()

class Striptool(Enum):
    DEFAULT_PROTOCOL = auto()
    
    
Field = namedtuple('Field', ['loc', 'type'])


_schema = {
    Scope.BUFFER : Field(loc=('ACQUISITION', 'BUFFER'),type=int),
    Scope.BUFFER_UNIT: Field(loc=('ACQUISITION', 'BUFFERUNIT'),type=['samples', 'objects']),
    Scope.AUTOSCALE: Field(loc=[ ('STRIPTOOL', 'AUTOSCALE'),('SCOPE', 'AUTOSCALE'), ('DISPLAY', 'AUTOSCALE')], type=bool),
    Scope.DISPLAY_MODE: Field(loc=('DISPLAY', 'MODE'), type=['normal', 'fft', 'psd', 'diff', 'autocorrelate_fft']),
    Scope.FFT_FILTER: Field(loc=('DISPLAY', 'FFT_FILTER'), type=['none', 'hamming']),
    Scope.AVERAGE: Field(loc=('DISPLAY', 'AVERAGE'), type=int),
    Scope.SINGLE_AXIS: Field(loc=('DISPLAY', 'SINGLE_AXIS'), type=bool),
    Scope.HISTOGRAM: Field(loc=('DISPLAY', 'HISTOGRAM'), type=bool),
    Scope.NBIN: Field(loc=('DISPLAY', 'N_BIN'), type=int),
    Scope.REFRESH: Field(loc=('DISPLAY', 'REFRESH'), type=int),
    Scope.TRIGGER: Field(loc=('TRIGGER', 'TRIGGER'), type=str),
    Scope.TRIGGER_MODE: Field(loc=('TRIGGER', 'TRIGGER_MODE'),
                              type=['none', 'onchange', 'gtthreshold', 'ltthreshold']),
    Scope.CHANNEL_COUNT: Field(loc=('CHANNELS', 'COUNT'), type=int),
    Scope.MOUSE_OVER: Field(loc=('DISPLAY', 'MOUSEOVER'), type=bool),
    Scope.CONNECT_ON_START: Field(loc=('ACQUISITION', 'CONNECTONSTART'), type=bool),
    Scope.PV: Field(loc=('ACQUISITION', 'PV'), type=str),
    Scope.ARRAYID: Field(loc=('CONFIG', 'ARRAYID'), type=str),
    Scope.XAXES: Field(loc=('CONFIG', 'XAXES'), type=str),
    Scope.MAJORTICKS: Field(loc=('CONFIG', 'MAJORTICKS'), type=int),
    Scope.MINORTICKS: Field(loc=('CONFIG', 'MINORTICKS'), type=int),
    Scope.EXTRA_DISPLAY_FIELDS: Field(loc=('CONFIG', 'EXTRADISPLAYFIELDS'), type=list),
    Scope.MOUSE_OVER_DISPLAY_LOCATION: Field(loc=('CONFIG', 'EXTRADISPLAYLOCATION'), type=['top_right', 'bottom_right', 'bottom_left']),
    Striptool.DEFAULT_PROTOCOL: Field(loc=('STRIPTOOL', 'DEFAULTPROTOCOL'), type=str)
}

class Parser:
    def __init__(self, cfg):
        self.cfg = cfg
        self.logger = logging.getLogger()
        
    def get_sections_list(self):
        appname = self.get_appname()
        try:
            sections = self.cfg[appname]['SECTIONS']
        except:
            raise ValueError(f'"SECTIONS" setting not found in {appname}')
        return sections.split()

    def get_channel_config(self, is_striptool=False):
        section = None
        try:
            if is_striptool:
                section=self.cfg['STRIPTOOL']
            else:
                section=self.cfg['CHANNELS']               
        except:
            section = None
            
        #Read channel information.  Channel order is
        #determined by order in config
        chan_cfg_lookup = {}
        
        if section:
            for k, v in section.items():
                if bool(re.match('chan', k, re.I)):
                    ch, param = k.lower().split('.')
                    chan_cfg_lookup[ch] = chan_cfg_lookup.get(ch, {})
                    chan_cfg_lookup[ch][param] = v

        chan_cfgs = list(chan_cfg_lookup.values())
        return chan_cfgs
    
    def get_appname(self):
        return self.cfg.get('DEFAULT', 'APP')        
        
    def get(self, key, default=None):
        try:
            fielddef = _schema[key]
        except Exception as e:
            raise KeyError('Invalid configuration key') from e            

        loc=fielddef.loc
        
        if isinstance(loc, list):
            for l in loc:
                val = self.__get(l, fielddef, None)
                if val is not None:
                    return val
            return default
        else:
            val =  self.__get(loc, fielddef, default)
            return val
        
    def __get(self, loc, fielddef, default):
        try:
            if fielddef.type == int:
                val = self.cfg.getint(loc[0], loc[1], fallback=default)
            elif fielddef.type == float:
                val = self.cfg.getfloat(loc[0], loc[1], fallback=default)
            elif fielddef.type == bool:
                val = self.cfg.getboolean(loc[0], loc[1], fallback=default)
            elif fielddef.type == str:
                val = self.cfg.get(loc[0], loc[1], fallback=default)
            elif fielddef.type == list:
                val = self.cfg.get(loc[0], loc[1], fallback=default)
                val = val.lower().strip().split(',') if val else []            
            elif isinstance(fielddef.type, list):
                val = self.cfg.get(loc[0], loc[1], fallback=default)
                val = val.lower().strip() if val else val
                if val is not None and val not in fielddef.type:                
                    raise ValueError(f'Invalid for key {loc[1]}: value {val}')
            else:
                raise ValueError(f'Invalid type: {fielddef.type}')
        except Exception as e:
            self.logger.error(f'Failed to get {loc}:{e}')
            val = default
        return val
    
class Serializer:
    def __init__(self):
        self.cfg = ConfigParser()

    def set(self, key, value):
        try:
            fielddef = _schema[key]
        except Exception as e:
            raise KeyError('Invalid configuration key') from e

        loc=fielddef.loc        
        self.cfg.set(loc[0], loc[1], value)

    
    def write(self, cfile):
        self.cfg.write(cfile)
