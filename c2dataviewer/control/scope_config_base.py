from .config import Parser, Scope

"""
C2 DATA VIEWER is distributed subject to a Software License Agreement found
in the file LICENSE that is included with this distribution.
SPDX-License-Identifier: EPICS
"""

class ScopeConfigureBase:
    def __init__(self, params, **kwargs):
        self.params = Parser(params)
        self.default_trigger = kwargs.get("trigger", None)

    def add_source_aquisition_props(self, children, section):
        """
        Add acquisition information specific to the application data source.  This
        should be implemented by the child class
        """
        return children

    def assemble_acquisition(self, section=None, buffer_unit='Samples'):
        """
        Assemble acquisition information

        :param section:
        :return:
        """

        children = []

        buffer_size = self.params.get(Scope.BUFFER)
        
        children += [
            {"name": "Freeze", "type": "bool", "value": False},
            {"name": "Buffer (%s)" % buffer_unit, "type": "int", "value": buffer_size, "siPrefix": False, 'decimals': 20}
        ]

        acquisition = {"name": "Acquisition", "type":"group", "children": children}
        
        return acquisition

    
    def assemble_display(self, section=None, app_section_key=None, default_autoscale=None):
        """
        Assemble display information

        :param section: DISPLAY section in config file
        :param app_section_key: type of app
        :param default_autoscale: default autoscale values for each app
        :return:
        """
        # If AUTOSCALE set in the app specific sections in the config file
        autoscale = self.params.get(Scope.AUTOSCALE, default=default_autoscale)
        display_mode = self.params.get(Scope.DISPLAY_MODE, default='normal')
        fft_filter = self.params.get(Scope.FFT_FILTER, default='none')
        n_average = self.params.get(Scope.AVERAGE, default=1)
        n_average = n_average if n_average > 0 else 1
        single_axis = self.params.get(Scope.SINGLE_AXIS, default=True)
        histogram = self.params.get(Scope.HISTOGRAM, default=False)
        n_binning = self.params.get(Scope.NBIN, default=100)
        refresh = self.params.get(Scope.REFRESH, default=100)

        display = {"name": "Display", "type": "group", "expanded": True,
                   "children": [
                       {"name": "Mode", "type": "list", "limits": {
                           "Normal": "normal",
                           "FFT": "fft",
                           "PSD": "psd",
                           "Diff": "diff",    
                           "Autocorrelation FFT": "autocorrelate_fft",               
                       }, "value": display_mode},
                       {"name": "FFT filter", "type": "list", "limits": {
                           "None" : "none",
                           "Hamming" : "hamming"
                       }, "value": fft_filter},
                       {"name": "Exp moving avg", "type": "int", "value": n_average, "limits" : (1, 1e+10)},
                       {"name": "Autoscale", "type": "bool", "value": autoscale},
                       {"name": "Single axis", "type": "bool", "value": single_axis},
                       {"name": "Histogram", "type": "bool", "value": histogram},
                       {"name": "Num Bins", "type": "int", "value": n_binning},
                       {"name": "Refresh", "type": "float", "value": refresh / 1000., "siPrefix": True, "suffix": "s"},
                   ]}
        
        return display
    

    def assemble_trigger(self, section=None):
        trigger_pv = self.params.get(Scope.TRIGGER, self.default_trigger)
        if trigger_pv is not None and trigger_pv.upper().strip() == "NONE":
            # set trigger PV value to None if a "None" string comes from configuration
            trigger_pv = None

        trigger_mode = self.params.get(Scope.TRIGGER_MODE, 'none')
        if trigger_mode == 'off':
            trigger_mode = 'none'

        config_expanded = True if trigger_mode != "none" else False

        # Load trigger settings from config
        time_field = self.params.get(Scope.TRIGGER_TIME_FIELD, None)
        if time_field is None:
            time_field = "None"

        data_time_field = self.params.get(Scope.TRIGGER_DATA_TIME_FIELD, None)
        if data_time_field is None:
            data_time_field = "None"

        autoscale_buffer = self.params.get(Scope.TRIGGER_AUTOSCALE_BUFFER, True)
        threshold = self.params.get(Scope.TRIGGER_THRESHOLD, 0.0)

        cfg ={"name": "Trigger",
              "type": "group",
              "expanded": config_expanded,
              "children" : [
                  { "name" :  "Mode", "type": "list", "limits": {
                    "Off" : "none",
                    "On change" : "onchange",
                    "Greater than threshold" : "gtthreshold",
                    "Lesser than threshold" : "ltthreshold"
                    },
                  "value" : trigger_mode
                 },
                  {"name": "PV", "type": "str", "value": trigger_pv},
                  {"name": "Trig Status", "type": "str", "value": "", "readonly": True},
                  {"name": "Trig Value", "type": "str", "value": "", "readonly": True},
                  {"name": "Time Field", "type": "list", "limits" : [time_field],
                   "value": time_field, "default" : "None", "visible" : False},
                  {"name": "Data Time Field", "type": "list", "limits" : [data_time_field],
                   "value": data_time_field, "default" : "None" },
                  {"name": "Autoscale Buffer", "type": "bool", "value" : autoscale_buffer},
                  {"name": "Threshold", "type": "float", "value": threshold},
              ]}
        return cfg
    
    def assemble_statistics(self):
        statistics = {"name": "Statistics", "type": "group",
                      "expanded":False,
                      "children": [
            {"name": "CPU", "type": "float", "value": 0, "readonly": True, "suffix": "%"},
            {"name": "Lost Arrays", "type": "int", "value": 0, "readonly": True},
            {"name": "Tot. Arrays", "type": "int", "value": 0, "readonly": True, "siPrefix": True},
            {"name": "Arrays/Sec", "type": "float", "value": 0., "readonly": True, "siPrefix": True,
             "suffix": "/sec"},
            {"name": "Bytes/Sec", "type": "float", "value": 0., "readonly": True, "siPrefix": True,
             "suffix": "/sec"},
            {"name": "Rate", "type": "float", "value": 0., "readonly": True, "siPrefix": True,
             "suffix": "Frames/sec"},
        ]}
        return statistics
