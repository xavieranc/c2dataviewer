"""
C2 DATA VIEWER is distributed subject to a Software License Agreement found
in the file LICENSE that is included with this distribution.
SPDX-License-Identifier: EPICS
"""

import unittest
from configparser import ConfigParser
from c2dataviewer.control.scopeconfig import Configure


class TestScopeConfig(unittest.TestCase):
    def get_display_val(self, data, val):
        """
        Helper method to extract the value for a given entry (by name) from
        the children list returned by Configure helper methods.
        """
        for child in data['children']:
            if child['name'] == val:
                return child['value']

    # ------------------------------------------------------------------
    # Existing tests
    # ------------------------------------------------------------------
    def test_trigger(self):
        raw1 = """
        [TRIGGER]
        TRIGGER=pv1
        TRIGGER_MODE=onchange
        """
        parser = ConfigParser()
        parser.read_string(raw1)
        configure = Configure(parser)
        section = parser["TRIGGER"]
        self.assertIsNotNone(section)
        trigger = configure.assemble_trigger(section=section)
        self.assertEqual(self.get_display_val(data=trigger, val='PV'), 'pv1')
        self.assertEqual(self.get_display_val(data=trigger, val='Mode'), 'onchange')

    def test_autoscale(self):
        # Does autoscale setting in app specific section take precedence?
        raw1 = """
        [SCOPE]
        DefaultProtocol = ca
        AUTOSCALE=False

        [DISPLAY]
        AUTOSCALE=True
        AVERAGE=1
        HISTOGRAM=False
        N_BIN=100
        REFRESH=100
        """
        parser = ConfigParser()
        parser.read_string(raw1)
        configure = Configure(parser)
        section = parser["DISPLAY"]
        display = configure.assemble_display(section=section)

        # 'SCOPE' section has AUTOSCALE=False, so Autoscale should be False
        self.assertFalse(self.get_display_val(data=display, val='Autoscale'))

        # When autoscale setting absent in app specific section, but present in DISPLAY
        raw2 = """
        [SCOPE]
        DefaultProtocol = ca

        [DISPLAY]
        AUTOSCALE=True
        AVERAGE=1
        HISTOGRAM=False
        N_BIN=100
        REFRESH=100
        """
        parser = ConfigParser()
        parser.read_string(raw2)
        configure = Configure(parser)
        section = parser["DISPLAY"]
        display = configure.assemble_display(section=section)
        self.assertTrue(self.get_display_val(data=display, val='Autoscale'))

        # When autoscale setting absent in both app specific and DISPLAY sections,
        # default (False) is selected
        raw3 = """
        [SCOPE]
        DefaultProtocol = ca

        [DISPLAY]
        AVERAGE=1
        HISTOGRAM=False
        N_BIN=100
        REFRESH=100
        """
        parser = ConfigParser()
        parser.read_string(raw3)
        configure = Configure(parser)
        section = parser["DISPLAY"]
        display = configure.assemble_display(section=section)
        self.assertFalse(self.get_display_val(data=display, val='Autoscale'))

    # ------------------------------------------------------------------
    # New tests
    # ------------------------------------------------------------------
    def test_display_all_settings(self):
        """
        Provide every DISPLAY setting and verify that each is picked up
        correctly by assemble_display.
        """
        raw = """
        [SCOPE]
        DefaultProtocol = ca
        AUTOSCALE=True

        [DISPLAY]
        MODE=fft
        FFT_FILTER=hamming
        AVERAGE=10
        SINGLE_AXIS=False
        HISTOGRAM=True
        N_BIN=256
        REFRESH=500
        AUTOSCALE=False
        """
        parser = ConfigParser()
        parser.read_string(raw)
        configure = Configure(parser)
        section = parser["DISPLAY"]
        display = configure.assemble_display(section=section)

        # Mode
        self.assertEqual(self.get_display_val(display, 'Mode'), 'fft')
        # FFT filter (capitalized by implementation)
        self.assertEqual(self.get_display_val(display, 'FFT filter'), 'Hamming')
        # Exp moving avg
        self.assertEqual(self.get_display_val(display, 'Exp moving avg'), 10)
        # Autoscale -> 'SCOPE' section takes precedence (True)
        self.assertTrue(self.get_display_val(display, 'Autoscale'))
        # Single axis
        self.assertFalse(self.get_display_val(display, 'Single axis'))
        # Histogram
        self.assertTrue(self.get_display_val(display, 'Histogram'))
        # Num bins
        self.assertEqual(self.get_display_val(display, 'Num Bins'), 256)
        # Refresh is converted from ms to seconds (500 ms → 0.5 s)
        self.assertEqual(self.get_display_val(display, 'Refresh'), 0.5)

    def test_display_defaults(self):
        """
        Verify defaults when the DISPLAY section (or individual keys)
        are not provided.
        """
        raw = """
        [SCOPE]
        DefaultProtocol = ca
        """
        parser = ConfigParser()
        parser.read_string(raw)
        configure = Configure(parser)

        # Passing section=None simulates absence of DISPLAY
        display = configure.assemble_display(section=None)

        self.assertEqual(self.get_display_val(display, 'Mode'), 'Normal')
        self.assertEqual(self.get_display_val(display, 'FFT filter'), 'None')
        self.assertEqual(self.get_display_val(display, 'Exp moving avg'), 1)
        self.assertFalse(self.get_display_val(display, 'Autoscale'))
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
        [DISPLAY]
        MODE=invalidmode
        FFT_FILTER=bogusfilter
        AVERAGE=-5
        SINGLE_AXIS=maybe
        HISTOGRAM=maybe
        N_BIN=badint
        REFRESH=badfloat
        """
        parser = ConfigParser()
        parser.read_string(raw)
        configure = Configure(parser)
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
