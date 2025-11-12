"""
C2 DATA VIEWER is distributed subject to a Software License Agreement found
in the file LICENSE that is included with this distribution.
SPDX-License-Identifier: EPICS
"""

import unittest
from configparser import ConfigParser
from c2dataviewer.control.striptoolconfig import StripToolConfigure
from c2dataviewer.control.pvconfig import PvConfig
from c2dataviewer.model import make_protocol

# Global protocol constants for testing
PROTO_CA = make_protocol('ca')
PROTO_PVA = make_protocol('pva')


class TestStriptoolConfig(unittest.TestCase):
    def setUp(self):
        """Reset color index before each test."""
        PvConfig.color_index = 0

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
    # Display configuration tests
    # ------------------------------------------------------------------
    def test_display_configuration(self):
        """
        Comprehensive test for display configuration including:
        - Autoscale precedence (STRIPTOOL section overrides DISPLAY section)
        - All settings with valid values
        - Default values when settings absent (StripTool default autoscale is True)
        - Bad/invalid input handling with fallback to defaults
        """
        # Test 1: Autoscale precedence - STRIPTOOL section overrides DISPLAY
        raw1 = """
        [STRIPTOOL]
        DefaultProtocol = ca
        AUTOSCALE=True

        [DISPLAY]
        AUTOSCALE=False
        """
        parser = ConfigParser()
        parser.read_string(raw1)
        configure = StripToolConfigure(parser)
        section = parser["DISPLAY"]
        display = configure.assemble_display(section=section)
        self.assertTrue(self.get_display_val(data=display, val='Autoscale'))

        # Test 2: Autoscale from DISPLAY section when not in STRIPTOOL
        raw2 = """
        [STRIPTOOL]
        DefaultProtocol = ca

        [DISPLAY]
        AUTOSCALE=False
        """
        parser = ConfigParser()
        parser.read_string(raw2)
        configure = StripToolConfigure(parser)
        section = parser["DISPLAY"]
        display = configure.assemble_display(section=section)
        self.assertFalse(self.get_display_val(data=display, val='Autoscale'))

        # Test 3: Default autoscale (True for StripTool)
        raw3 = """
        [STRIPTOOL]
        DefaultProtocol = ca

        [DISPLAY]
        AVERAGE=1
        """
        parser = ConfigParser()
        parser.read_string(raw3)
        configure = StripToolConfigure(parser)
        section = parser["DISPLAY"]
        display = configure.assemble_display(section=section)
        self.assertTrue(self.get_display_val(data=display, val='Autoscale'))

        # Test 4: All settings with valid values
        raw4 = """
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
        """
        parser = ConfigParser()
        parser.read_string(raw4)
        configure = StripToolConfigure(parser)
        section = parser["DISPLAY"]
        display = configure.assemble_display(section=section)
        self.assertEqual(self.get_display_val(display, 'Mode'), 'psd')
        self.assertEqual(self.get_display_val(display, 'FFT filter'), 'hamming')
        self.assertEqual(self.get_display_val(display, 'Exp moving avg'), 15)
        self.assertFalse(self.get_display_val(display, 'Autoscale'))  # STRIPTOOL precedence
        self.assertFalse(self.get_display_val(display, 'Single axis'))
        self.assertTrue(self.get_display_val(display, 'Histogram'))
        self.assertEqual(self.get_display_val(display, 'Num Bins'), 512)
        self.assertEqual(self.get_display_val(display, 'Refresh'), 0.25)  # 250ms -> 0.25s

        # Test 5: Default values when no DISPLAY section
        raw5 = """
        [STRIPTOOL]
        DefaultProtocol = ca
        """
        parser = ConfigParser()
        parser.read_string(raw5)
        configure = StripToolConfigure(parser)
        display = configure.assemble_display(section=None)
        self.assertEqual(self.get_display_val(display, 'Mode'), 'normal')
        self.assertEqual(self.get_display_val(display, 'FFT filter'), 'none')
        self.assertEqual(self.get_display_val(display, 'Exp moving avg'), 1)
        self.assertTrue(self.get_display_val(display, 'Autoscale'))
        self.assertTrue(self.get_display_val(display, 'Single axis'))
        self.assertFalse(self.get_display_val(display, 'Histogram'))
        self.assertEqual(self.get_display_val(display, 'Num Bins'), 100)
        self.assertEqual(self.get_display_val(display, 'Refresh'), 0.1)

        # Test 6: Bad/invalid input falls back to defaults
        raw6 = """
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
        parser.read_string(raw6)
        configure = StripToolConfigure(parser)
        section = parser["DISPLAY"]
        display = configure.assemble_display(section=section)
        self.assertEqual(self.get_display_val(display, 'Mode'), 'normal')
        self.assertEqual(self.get_display_val(display, 'FFT filter'), 'none')
        self.assertEqual(self.get_display_val(display, 'Exp moving avg'), 1)
        self.assertTrue(self.get_display_val(display, 'Single axis'))
        self.assertFalse(self.get_display_val(display, 'Histogram'))
        self.assertEqual(self.get_display_val(display, 'Num Bins'), 100)
        self.assertEqual(self.get_display_val(display, 'Refresh'), 0.1)
        self.assertTrue(self.get_display_val(display, 'Autoscale'))

    # ------------------------------------------------------------------
    # Channel/PV configuration tests
    # ------------------------------------------------------------------
    def test_channel_configuration(self):
        """
        Comprehensive test for channel/PV configuration including:
        - Basic PV names and colors
        - Protocol specification and defaults
        - Default color assignment
        - Case-insensitive channel names
        - Multiple channels
        - Special characters in PV names
        """
        # Test 1: Basic channel configuration
        raw1 = """
        [STRIPTOOL]
        DefaultProtocol = ca
        Chan1.PV = TEST:PV1
        Chan1.Color = #FF0000
        Chan2.PV = TEST:PV2
        Chan2.Color = #00FF00
        """
        parser = ConfigParser()
        parser.read_string(raw1)
        cfg = StripToolConfigure(parser)
        self.assertEqual(len(cfg.pvs), 2)
        self.assertIn('TEST:PV1', cfg.pvs)
        self.assertIn('TEST:PV2', cfg.pvs)
        pv1 = cfg.pvs['TEST:PV1']
        self.assertEqual(pv1.pvname, 'TEST:PV1')
        self.assertEqual(pv1.color, '#FF0000')
        self.assertEqual(pv1.proto, PROTO_CA)
        pv2 = cfg.pvs['TEST:PV2']
        self.assertEqual(pv2.pvname, 'TEST:PV2')
        self.assertEqual(pv2.color, '#00FF00')
        self.assertEqual(pv2.proto, PROTO_CA)

        # Test 2: Protocol override in PV string
        raw2 = """
        [STRIPTOOL]
        DefaultProtocol = ca
        Chan1.PV = ca://TEST:PV1
        Chan2.PV = pva://TEST:PV2
        Chan3.PV = TEST:PV3
        """
        parser = ConfigParser()
        parser.read_string(raw2)
        cfg = StripToolConfigure(parser)
        self.assertEqual(len(cfg.pvs), 3)
        self.assertEqual(cfg.pvs['TEST:PV1'].proto, PROTO_CA)
        self.assertEqual(cfg.pvs['TEST:PV2'].proto, PROTO_PVA)
        self.assertEqual(cfg.pvs['TEST:PV3'].proto, PROTO_CA)

        # Test 3: Default protocol pva
        raw3 = """
        [STRIPTOOL]
        DefaultProtocol = pva
        Chan1.PV = TEST:PV1
        Chan2.PV = ca://TEST:PV2
        """
        parser = ConfigParser()
        parser.read_string(raw3)
        cfg = StripToolConfigure(parser)
        self.assertEqual(cfg.pvs['TEST:PV1'].proto, PROTO_PVA)
        self.assertEqual(cfg.pvs['TEST:PV2'].proto, PROTO_CA)

        # Test 4: Default color assignment
        PvConfig.color_index = 0  # Reset color index
        raw4 = """
        [STRIPTOOL]
        DefaultProtocol = ca
        Chan1.PV = TEST:PV1
        Chan2.PV = TEST:PV2
        Chan2.Color = #FFFFFF
        """
        parser = ConfigParser()
        parser.read_string(raw4)
        cfg = StripToolConfigure(parser)
        self.assertEqual(cfg.pvs['TEST:PV1'].color, '#FFFF00')  # Default color
        self.assertEqual(cfg.pvs['TEST:PV2'].color, '#FFFFFF')  # Explicit color

        # Test 5: Case-insensitive channel names
        raw5 = """
        [STRIPTOOL]
        DefaultProtocol = ca
        CHAN1.PV = TEST:PV1
        Chan2.pv = TEST:PV2
        chan3.PV = TEST:PV3
        """
        parser = ConfigParser()
        parser.read_string(raw5)
        cfg = StripToolConfigure(parser)
        self.assertEqual(len(cfg.pvs), 3)
        self.assertIn('TEST:PV1', cfg.pvs)
        self.assertIn('TEST:PV2', cfg.pvs)
        self.assertIn('TEST:PV3', cfg.pvs)

        # Test 6: Multiple properties
        raw6 = """
        [STRIPTOOL]
        DefaultProtocol = ca
        Chan1.PV = pva://TEST:MOTOR1
        Chan1.Color = #123456
        """
        parser = ConfigParser()
        parser.read_string(raw6)
        cfg = StripToolConfigure(parser)
        pv = cfg.pvs['TEST:MOTOR1']
        self.assertEqual(pv.pvname, 'TEST:MOTOR1')
        self.assertEqual(pv.color, '#123456')
        self.assertEqual(pv.proto, PROTO_PVA)

        # Test 7: Empty section
        raw7 = """
        [STRIPTOOL]
        DefaultProtocol = ca
        """
        parser = ConfigParser()
        parser.read_string(raw7)
        cfg = StripToolConfigure(parser)
        self.assertEqual(len(cfg.pvs), 0)
        self.assertEqual(cfg.default_proto, 'ca')

        # Test 8: Many channels
        raw8 = """
        [STRIPTOOL]
        DefaultProtocol = ca
        Chan1.PV = TEST:PV1
        Chan2.PV = TEST:PV2
        Chan3.PV = TEST:PV3
        Chan4.PV = TEST:PV4
        Chan5.PV = TEST:PV5
        Chan6.PV = TEST:PV6
        Chan7.PV = TEST:PV7
        Chan8.PV = TEST:PV8
        """
        parser = ConfigParser()
        parser.read_string(raw8)
        cfg = StripToolConfigure(parser)
        self.assertEqual(len(cfg.pvs), 8)
        for i in range(1, 9):
            self.assertIn(f'TEST:PV{i}', cfg.pvs)

        # Test 9: Duplicate PVs (last one wins)
        raw9 = """
        [STRIPTOOL]
        DefaultProtocol = ca
        Chan1.PV = TEST:SAME
        Chan1.Color = #FF0000
        Chan2.PV = TEST:SAME
        Chan2.Color = #00FF00
        """
        parser = ConfigParser()
        parser.read_string(raw9)
        cfg = StripToolConfigure(parser)
        self.assertEqual(len(cfg.pvs), 1)
        pv = cfg.pvs['TEST:SAME']
        self.assertEqual(pv.color, '#00FF00')

        # Test 10: Special characters in PV names
        raw10 = """
        [STRIPTOOL]
        DefaultProtocol = ca
        Chan1.PV = TEST:PV-WITH-DASHES
        Chan2.PV = TEST:PV_WITH_UNDERSCORES
        Chan3.PV = TEST:PV.WITH.DOTS
        Chan4.PV = TEST:PV:COLONS:HERE
        """
        parser = ConfigParser()
        parser.read_string(raw10)
        cfg = StripToolConfigure(parser)
        self.assertEqual(len(cfg.pvs), 4)
        self.assertIn('TEST:PV-WITH-DASHES', cfg.pvs)
        self.assertIn('TEST:PV_WITH_UNDERSCORES', cfg.pvs)
        self.assertIn('TEST:PV.WITH.DOTS', cfg.pvs)
        self.assertIn('TEST:PV:COLONS:HERE', cfg.pvs)

    # ------------------------------------------------------------------
    # Error handling and edge cases
    # ------------------------------------------------------------------
    def test_error_handling(self):
        """
        Comprehensive test for error handling and edge cases including:
        - Missing STRIPTOOL section
        - Missing DefaultProtocol
        - Invalid color formats
        - Channel with only color but no PV
        - Protocol string format variations
        """
        # Test 1: Missing STRIPTOOL section
        raw1 = """
        [DISPLAY]
        MODE=normal
        """
        parser = ConfigParser()
        parser.read_string(raw1)
        cfg = StripToolConfigure(parser)
        self.assertEqual(len(cfg.pvs), 0)
        self.assertIsNone(cfg.default_proto)

        # Test 2: Missing DefaultProtocol (should default to 'ca')
        raw2 = """
        [STRIPTOOL]
        Chan1.PV = TEST:PV1
        """
        parser = ConfigParser()
        parser.read_string(raw2)
        cfg = StripToolConfigure(parser)
        self.assertEqual(cfg.default_proto, 'ca')
        self.assertEqual(cfg.pvs['TEST:PV1'].proto, PROTO_CA)

        # Test 3: Invalid color formats (stored as-is)
        raw3 = """
        [STRIPTOOL]
        DefaultProtocol = ca
        Chan1.PV = TEST:PV1
        Chan1.Color = red
        Chan2.PV = TEST:PV2
        Chan2.Color = 12345
        """
        parser = ConfigParser()
        parser.read_string(raw3)
        cfg = StripToolConfigure(parser)
        self.assertEqual(cfg.pvs['TEST:PV1'].color, 'red')
        self.assertEqual(cfg.pvs['TEST:PV2'].color, '12345')

        # Test 4: Channel with only color but no PV (ignored)
        raw4 = """
        [STRIPTOOL]
        DefaultProtocol = ca
        Chan1.Color = #FF0000
        Chan2.PV = TEST:PV2
        """
        parser = ConfigParser()
        parser.read_string(raw4)
        cfg = StripToolConfigure(parser)
        self.assertEqual(len(cfg.pvs), 1)
        self.assertIn('TEST:PV2', cfg.pvs)

        # Test 5: Protocol string case variations
        raw5 = """
        [STRIPTOOL]
        DefaultProtocol = ca
        Chan1.PV = CA://TEST:PV1
        Chan2.PV = PVA://TEST:PV2
        Chan3.PV = pva://TEST:PV3
        """
        parser = ConfigParser()
        parser.read_string(raw5)
        cfg = StripToolConfigure(parser)
        self.assertIn('TEST:PV1', cfg.pvs)
        self.assertIn('TEST:PV2', cfg.pvs)
        self.assertIn('TEST:PV3', cfg.pvs)

    def test_acquisition_sample_mode(self):
        """
        Test that acquisition includes Sample Mode for striptool.
        """
        raw = """
        [STRIPTOOL]
        DefaultProtocol = ca
        """
        parser = ConfigParser()
        parser.read_string(raw)
        cfg = StripToolConfigure(parser)

        acquisition = cfg.assemble_acquisition()

        # Check that Sample Mode is present
        sample_mode = None
        for child in acquisition['children']:
            if child['name'] == 'Sample Mode':
                sample_mode = child
                break

        self.assertIsNotNone(sample_mode)
        self.assertEqual(sample_mode['type'], 'bool')
        self.assertTrue(sample_mode['value'])


if __name__ == '__main__':
    unittest.main()
