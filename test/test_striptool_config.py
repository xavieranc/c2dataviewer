"""
C2 DATA VIEWER is distributed subject to a Software License Agreement found
in the file LICENSE that is included with this distribution.
SPDX-License-Identifier: EPICS
"""

import unittest
from configparser import ConfigParser
from c2dataviewer.control.striptoolconfig import StripToolConfigure
from c2dataviewer.control.pvconfig import PvConfig


class TestStriptoolConfig(unittest.TestCase):
    def test_config(self):
        raw = """
[STRIPTOOL]
DefaultProtocol = ca
Chan1.PV = Foo:Bar
Chan2.PV = pva://Bar:Baz
Chan1.Color = #000000
Chan2.Color = #0000FF
"""
        parser = ConfigParser()
        parser.read_string(raw)
        cfg = StripToolConfigure(parser)
        expected = {
            'Foo:Bar': PvConfig('Foo:Bar', '#000000', 'ca'),
            'Bar:Baz': PvConfig('Bar:Baz', '#0000FF', 'pva')
        }

        self.assertEqual(len(cfg.pvs), len(expected))

        for pv in cfg.pvs.values():
            self.assertTrue(pv.pvname in expected)
            e = expected[pv.pvname]
            self.assertEqual(e.pvname, pv.pvname)
            self.assertEqual(e.color, pv.color)
            self.assertEqual(e.proto, pv.proto)
            del expected[pv.pvname]

    def get_display_val(self, data, val):
        for child in data['children']:
            if child['name'] == val:
                ret_val = child['value']
                return ret_val

    # ------------------------------------------------------------------
    # Autoscale precedence tests  (existing)
    # ------------------------------------------------------------------
    def test_autoscale(self):
        # Does autoscale setting in app specific section take precedence?
        raw1 = """
        [STRIPTOOL]
        DefaultProtocol = ca
        AUTOSCALE=True

        [DISPLAY]
        AUTOSCALE=False
        AVERAGE=1
        HISTOGRAM=False
        N_BIN=100
        REFRESH=100
        """
        parser = ConfigParser()
        parser.read_string(raw1)
        configure = StripToolConfigure(parser)
        section = parser["DISPLAY"]
        display = configure.assemble_display(section=section)

        self.assertTrue(self.get_display_val(data=display, val='Autoscale'))

        # When autoscale setting absent in app specific section, but present in DISPLAY
        raw2 = """
        [STRIPTOOL]
        DefaultProtocol = ca

        [DISPLAY]
        AUTOSCALE=False
        AVERAGE=1
        HISTOGRAM=False
        N_BIN=100
        REFRESH=100
        """
        parser = ConfigParser()
        parser.read_string(raw2)
        configure = StripToolConfigure(parser)
        section = parser["DISPLAY"]
        display = configure.assemble_display(section=section)

        self.assertFalse(self.get_display_val(data=display, val='Autoscale'))

        # When autoscale setting absent in both app specific and in DISPLAY sections,
        # default (True for StripTool) is selected
        raw3 = """
        [STRIPTOOL]
        DefaultProtocol = ca

        [DISPLAY]
        AVERAGE=1
        HISTOGRAM=False
        N_BIN=100
        REFRESH=100
        """
        parser = ConfigParser()
        parser.read_string(raw3)
        configure = StripToolConfigure(parser)
        section = parser["DISPLAY"]
        display = configure.assemble_display(section=section)

        self.assertTrue(self.get_display_val(data=display, val='Autoscale'))

    # ------------------------------------------------------------------
    # New tests
    # ------------------------------------------------------------------
    def test_display_all_settings(self):
        """
        Provide every DISPLAY setting and verify that each is picked up
        correctly by assemble_display.
        """
        raw = """
        [STRIPTOOL]
        DefaultProtocol = ca
        AUTOSCALE=False

        [DISPLAY]
        MODE=psd
        FFT_FILTER=hamming
        AVERAGE=15
        SINGLE_AXIS=False
        HISTOGRAM=True
        N_BIN=512
        REFRESH=250
        AUTOSCALE=True
        """
        parser = ConfigParser()
        parser.read_string(raw)
        configure = StripToolConfigure(parser)
        section = parser["DISPLAY"]
        display = configure.assemble_display(section=section)

        # Mode
        self.assertEqual(self.get_display_val(display, 'Mode'), 'psd')
        # FFT filter
        self.assertEqual(self.get_display_val(display, 'FFT filter'), 'Hamming')
        # Exp moving avg
        self.assertEqual(self.get_display_val(display, 'Exp moving avg'), 15)
        # Autoscale -> STRIPTOOL section takes precedence (False)
        self.assertFalse(self.get_display_val(display, 'Autoscale'))
        # Single axis
        self.assertFalse(self.get_display_val(display, 'Single axis'))
        # Histogram
        self.assertTrue(self.get_display_val(display, 'Histogram'))
        # Num bins
        self.assertEqual(self.get_display_val(display, 'Num Bins'), 512)
        # Refresh conversion (250 ms → 0.25 s)
        self.assertEqual(self.get_display_val(display, 'Refresh'), 0.25)

    def test_display_defaults(self):
        """
        Verify defaults when the DISPLAY section (or individual keys)
        are not provided.  StripTool's default AUTOSCALE is True.
        """
        raw = """
        [STRIPTOOL]
        DefaultProtocol = ca
        """
        parser = ConfigParser()
        parser.read_string(raw)
        configure = StripToolConfigure(parser)

        # Passing section=None simulates absence of DISPLAY
        display = configure.assemble_display(section=None)

        self.assertEqual(self.get_display_val(display, 'Mode'), 'Normal')
        self.assertEqual(self.get_display_val(display, 'FFT filter'), 'None')
        self.assertEqual(self.get_display_val(display, 'Exp moving avg'), 1)
        self.assertTrue(self.get_display_val(display, 'Autoscale'))
        self.assertTrue(self.get_display_val(display, 'Single axis'))
        self.assertFalse(self.get_display_val(display, 'Histogram'))
        self.assertEqual(self.get_display_val(display, 'Num Bins'), 100)
        self.assertEqual(self.get_display_val(display, 'Refresh'), 0.1)

    def test_display_bad_input(self):
        """
        Feed bad/unsupported values and verify that assemble_display
        gracefully falls back to safe defaults.
        """
        raw = """
        [STRIPTOOL]
        DefaultProtocol = ca

        [DISPLAY]
        MODE=invalidmode
        FFT_FILTER=bogusfilter
        AVERAGE=-10
        SINGLE_AXIS=maybe
        HISTOGRAM=maybe
        N_BIN=badint
        REFRESH=badfloat
        AUTOSCALE=maybe
        """
        parser = ConfigParser()
        parser.read_string(raw)
        configure = StripToolConfigure(parser)
        section = parser["DISPLAY"]
        display = configure.assemble_display(section=section)

        # Invalid mode -> "normal"
        self.assertEqual(self.get_display_val(display, 'Mode'), 'normal')
        # Invalid filter -> 'none'
        self.assertEqual(self.get_display_val(display, 'FFT filter'), 'none')
        # Negative average -> reset to 1
        self.assertEqual(self.get_display_val(display, 'Exp moving avg'), 1)
        # Bad single axis value -> default True
        self.assertTrue(self.get_display_val(display, 'Single axis'))
        # Bad histogram value -> default False
        self.assertFalse(self.get_display_val(display, 'Histogram'))
        # Bad int for N_BIN -> 1
        self.assertEqual(self.get_display_val(display, 'Num Bins'), 1)
        # Bad float for refresh -> 0.001 (1 ms expressed as seconds)
        self.assertEqual(self.get_display_val(display, 'Refresh'), 0.001)
        # Bad AUTOSCALE value -> treated as False
        self.assertFalse(self.get_display_val(display, 'Autoscale'))
