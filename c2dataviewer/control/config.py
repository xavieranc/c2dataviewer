from collections import namedtuple
from enum import Enum, auto
from configparser import ConfigParser
import re
import logging


class AppType(Enum):
    SCOPE = "scope"
    IMAGE = "image"
    STRIPTOOL = "striptool"

    def __str__(self):
        return self.value

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
    TRIGGER_THRESHOLD = auto()
    TRIGGER_AUTOSCALE_BUFFER = auto()
    TRIGGER_TIME_FIELD = auto()
    TRIGGER_DATA_TIME_FIELD = auto()
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
    SAMPLEMODE = auto()
    
Field = namedtuple('Field', ['loc', 'type'])
MultiLoc = namedtuple('MultiLoc', ['sections', 'write_section', 'field'])

_schema = {
    Scope.BUFFER : Field(loc=('ACQUISITION', 'BUFFER'),type=int),
    Scope.BUFFER_UNIT: Field(loc=('ACQUISITION', 'BUFFERUNIT'),type=['samples', 'objects']),
    Scope.AUTOSCALE: Field(loc=MultiLoc(['STRIPTOOL', 'SCOPE', 'DISPLAY'], 'DISPLAY', 'AUTOSCALE'), type=bool),
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
    Scope.TRIGGER_THRESHOLD: Field(loc=('TRIGGER', 'THRESHOLD'), type=float),
    Scope.TRIGGER_AUTOSCALE_BUFFER: Field(loc=('TRIGGER', 'AUTOSCALE_BUFFER'), type=bool),
    Scope.TRIGGER_TIME_FIELD: Field(loc=('TRIGGER', 'TIME_FIELD'), type=str),
    Scope.TRIGGER_DATA_TIME_FIELD: Field(loc=('TRIGGER', 'DATA_TIME_FIELD'), type=str),
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
    Striptool.DEFAULT_PROTOCOL: Field(loc=('STRIPTOOL', 'DEFAULTPROTOCOL'), type=str),
    Striptool.SAMPLEMODE: Field(loc=('ACQUISITION', 'SAMPLEMODE'), type=str)
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
        
        if isinstance(loc, MultiLoc):
            for s in loc.sections:
                l = (s, loc.field)
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
        if isinstance(loc, MultiLoc):
            section = loc.write_section
            option = loc.field
        else:
            section, option = loc[0], loc[1]

        # Ensure section exists
        if not self.cfg.has_section(section):
            self.cfg.add_section(section)

        self.cfg.set(section, option, str(value))

    def set_app(self, app: AppType):
        self.__set_raw('DEFAULT', 'APP', str(app).upper())

    def __set_raw(self, section, option, value):
        '''
        Set a configuration value directly without schema validation.
        Useful for app-specific or channel-specific settings.
        '''
        # DEFAULT section is special in ConfigParser and cannot be added
        if section != 'DEFAULT' and not self.cfg.has_section(section):
            self.cfg.add_section(section)
        self.cfg.set(section, option, str(value))

    def write_channels(self, section: str, chan_cfgs: list[dict]):
        '''
        Write channel configurations to a specific section.

        section: Section name to write channels to (e.g., 'STRIPTOOL', 'CHANNELS')
        chan_cfgs: List of channel configs, where a channel config
                   is a dictionary of channel fields
        '''
        if not self.cfg.has_section(section):
            self.cfg.add_section(section)

        i = 1
        for cfg in chan_cfgs:
            prefix = f'chan{i}.'
            for k, v in cfg.items():
                key = f'{prefix}{k.lower()}'
                self.cfg.set(section, key, str(v))
            i += 1

    def write(self, cfile):
        self.cfg.write(cfile)
