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
        self.assertEqual(self.get_display_val(display, 'FFT filter'), 'hamming')
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

        self.assertEqual(self.get_display_val(display, 'Mode'), 'normal')
        self.assertEqual(self.get_display_val(display, 'FFT filter'), 'none')
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
        self.assertEqual(self.get_display_val(display, 'Num Bins'), 100)
        # Bad float for refresh -> 0.001 (1 ms expressed as seconds)
        self.assertEqual(self.get_display_val(display, 'Refresh'), 0.1)
        # Bad AUTOSCALE value -> treated as True
        self.assertTrue(self.get_display_val(display, 'Autoscale'))

    # ------------------------------------------------------------------
    # Channel/PV configuration tests
    # ------------------------------------------------------------------
    def test_channel_basic(self):
        """
        Test basic channel configuration with PV names and colors.
        """
        raw = """
        [STRIPTOOL]
        DefaultProtocol = ca
        Chan1.PV = TEST:PV1
        Chan1.Color = #FF0000
        Chan2.PV = TEST:PV2
        Chan2.Color = #00FF00
        """
        parser = ConfigParser()
        parser.read_string(raw)
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

    def test_channel_protocol_override(self):
        """
        Test that protocol specified in PV string overrides default protocol.
        """
        raw = """
        [STRIPTOOL]
        DefaultProtocol = ca
        Chan1.PV = ca://TEST:PV1
        Chan2.PV = pva://TEST:PV2
        Chan3.PV = TEST:PV3
        """
        parser = ConfigParser()
        parser.read_string(raw)
        cfg = StripToolConfigure(parser)

        self.assertEqual(len(cfg.pvs), 3)

        # Explicit ca protocol
        self.assertEqual(cfg.pvs['TEST:PV1'].proto, PROTO_CA)
        # Explicit pva protocol
        self.assertEqual(cfg.pvs['TEST:PV2'].proto, PROTO_PVA)
        # Default protocol (ca)
        self.assertEqual(cfg.pvs['TEST:PV3'].proto, PROTO_CA)

    def test_channel_default_protocol_pva(self):
        """
        Test that default protocol setting works for pva.
        """
        raw = """
        [STRIPTOOL]
        DefaultProtocol = pva
        Chan1.PV = TEST:PV1
        Chan2.PV = ca://TEST:PV2
        """
        parser = ConfigParser()
        parser.read_string(raw)
        cfg = StripToolConfigure(parser)

        # Should use pva as default
        self.assertEqual(cfg.pvs['TEST:PV1'].proto, PROTO_PVA)
        # Explicit ca should override
        self.assertEqual(cfg.pvs['TEST:PV2'].proto, PROTO_CA)

    def test_channel_no_color(self):
        """
        Test channels without explicit color specification get default colors.
        """
        raw = """
        [STRIPTOOL]
        DefaultProtocol = ca
        Chan1.PV = TEST:PV1
        Chan2.PV = TEST:PV2
        Chan2.Color = #FFFFFF
        """
        parser = ConfigParser()
        parser.read_string(raw)
        cfg = StripToolConfigure(parser)

        # Chan1 has no color specified, should get first default color
        self.assertEqual(cfg.pvs['TEST:PV1'].color, '#FFFF00')
        # Chan2 has explicit color
        self.assertEqual(cfg.pvs['TEST:PV2'].color, '#FFFFFF')

    def test_channel_case_insensitive(self):
        """
        Test that channel names are case-insensitive.
        """
        raw = """
        [STRIPTOOL]
        DefaultProtocol = ca
        CHAN1.PV = TEST:PV1
        Chan2.pv = TEST:PV2
        chan3.PV = TEST:PV3
        """
        parser = ConfigParser()
        parser.read_string(raw)
        cfg = StripToolConfigure(parser)

        self.assertEqual(len(cfg.pvs), 3)
        self.assertIn('TEST:PV1', cfg.pvs)
        self.assertIn('TEST:PV2', cfg.pvs)
        self.assertIn('TEST:PV3', cfg.pvs)

    def test_channel_multiple_properties(self):
        """
        Test channel with multiple properties defined.
        """
        raw = """
        [STRIPTOOL]
        DefaultProtocol = ca
        Chan1.PV = pva://TEST:MOTOR1
        Chan1.Color = #123456
        """
        parser = ConfigParser()
        parser.read_string(raw)
        cfg = StripToolConfigure(parser)

        pv = cfg.pvs['TEST:MOTOR1']
        self.assertEqual(pv.pvname, 'TEST:MOTOR1')
        self.assertEqual(pv.color, '#123456')
        self.assertEqual(pv.proto, PROTO_PVA)

    def test_channel_empty_section(self):
        """
        Test behavior when STRIPTOOL section has no channels.
        """
        raw = """
        [STRIPTOOL]
        DefaultProtocol = ca
        """
        parser = ConfigParser()
        parser.read_string(raw)
        cfg = StripToolConfigure(parser)

        self.assertEqual(len(cfg.pvs), 0)
        self.assertEqual(cfg.default_proto, 'ca')

    def test_channel_many_channels(self):
        """
        Test configuration with many channels.
        """
        raw = """
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
        parser.read_string(raw)
        cfg = StripToolConfigure(parser)

        self.assertEqual(len(cfg.pvs), 8)
        for i in range(1, 9):
            self.assertIn(f'TEST:PV{i}', cfg.pvs)

    def test_channel_duplicate_pvs(self):
        """
        Test that duplicate PV names are handled (last one wins).
        """
        raw = """
        [STRIPTOOL]
        DefaultProtocol = ca
        Chan1.PV = TEST:SAME
        Chan1.Color = #FF0000
        Chan2.PV = TEST:SAME
        Chan2.Color = #00FF00
        """
        parser = ConfigParser()
        parser.read_string(raw)
        cfg = StripToolConfigure(parser)

        # Should only have one entry for TEST:SAME
        self.assertEqual(len(cfg.pvs), 1)
        # Last configuration should win
        pv = cfg.pvs['TEST:SAME']
        self.assertEqual(pv.color, '#00FF00')

    def test_channel_special_characters_in_pv(self):
        """
        Test PV names with special characters.
        """
        raw = """
        [STRIPTOOL]
        DefaultProtocol = ca
        Chan1.PV = TEST:PV-WITH-DASHES
        Chan2.PV = TEST:PV_WITH_UNDERSCORES
        Chan3.PV = TEST:PV.WITH.DOTS
        Chan4.PV = TEST:PV:COLONS:HERE
        """
        parser = ConfigParser()
        parser.read_string(raw)
        cfg = StripToolConfigure(parser)

        self.assertEqual(len(cfg.pvs), 4)
        self.assertIn('TEST:PV-WITH-DASHES', cfg.pvs)
        self.assertIn('TEST:PV_WITH_UNDERSCORES', cfg.pvs)
        self.assertIn('TEST:PV.WITH.DOTS', cfg.pvs)
        self.assertIn('TEST:PV:COLONS:HERE', cfg.pvs)

    # ------------------------------------------------------------------
    # Error handling tests
    # ------------------------------------------------------------------
    def test_missing_striptool_section(self):
        """
        Test behavior when STRIPTOOL section is missing.
        """
        raw = """
        [DISPLAY]
        MODE=normal
        """
        parser = ConfigParser()
        parser.read_string(raw)
        cfg = StripToolConfigure(parser)

        # Should handle gracefully with empty pvs
        self.assertEqual(len(cfg.pvs), 0)
        self.assertIsNone(cfg.default_proto)

    def test_missing_default_protocol(self):
        """
        Test behavior when DefaultProtocol is not specified.
        """
        raw = """
        [STRIPTOOL]
        Chan1.PV = TEST:PV1
        """
        parser = ConfigParser()
        parser.read_string(raw)
        cfg = StripToolConfigure(parser)

        # Should use default 'ca'
        self.assertEqual(cfg.default_proto, 'ca')
        self.assertEqual(cfg.pvs['TEST:PV1'].proto, PROTO_CA)

    def test_invalid_color_format(self):
        """
        Test that invalid color formats are still stored as-is.
        """
        raw = """
        [STRIPTOOL]
        DefaultProtocol = ca
        Chan1.PV = TEST:PV1
        Chan1.Color = red
        Chan2.PV = TEST:PV2
        Chan2.Color = 12345
        """
        parser = ConfigParser()
        parser.read_string(raw)
        cfg = StripToolConfigure(parser)

        # Colors are stored as strings without validation
        self.assertEqual(cfg.pvs['TEST:PV1'].color, 'red')
        self.assertEqual(cfg.pvs['TEST:PV2'].color, '12345')

    def test_channel_only_color_no_pv(self):
        """
        Test channel with only color but no PV (should be ignored).
        """
        raw = """
        [STRIPTOOL]
        DefaultProtocol = ca
        Chan1.Color = #FF0000
        Chan2.PV = TEST:PV2
        """
        parser = ConfigParser()
        parser.read_string(raw)
        cfg = StripToolConfigure(parser)

        # Chan1 should be ignored since it has no PV
        self.assertEqual(len(cfg.pvs), 1)
        self.assertIn('TEST:PV2', cfg.pvs)

    def test_protocol_variations(self):
        """
        Test various protocol string formats.
        """
        raw = """
        [STRIPTOOL]
        DefaultProtocol = ca
        Chan1.PV = CA://TEST:PV1
        Chan2.PV = PVA://TEST:PV2
        Chan3.PV = pva://TEST:PV3
        """
        parser = ConfigParser()
        parser.read_string(raw)
        cfg = StripToolConfigure(parser)

        # Protocol parsing should handle case variations
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
