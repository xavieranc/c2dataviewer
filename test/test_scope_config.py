"""
C2 DATA VIEWER is distributed subject to a Software License Agreement found
in the file LICENSE that is included with this distribution.
SPDX-License-Identifier: EPICS
"""

import unittest
import logging
from configparser import ConfigParser
from pprint import pformat
from io import StringIO

from c2dataviewer.control.scopeconfig import Configure

# ----------------------------------------------------------------------
# Configure logging to capture debug messages in a buffer. The messages
# will only be printed if a test fails, making the output cleaner for
# successful test runs.
# ----------------------------------------------------------------------
logger = logging.getLogger(__name__)
logger.setLevel(logging.DEBUG)


class TestScopeConfig(unittest.TestCase):
    def setUp(self):
        """Set up logging capture for each test."""
        self.log_stream = StringIO()
        self.log_handler = logging.StreamHandler(self.log_stream)
        self.log_handler.setLevel(logging.DEBUG)
        formatter = logging.Formatter('%(levelname)s:%(name)s:%(message)s')
        self.log_handler.setFormatter(formatter)
        logger.addHandler(self.log_handler)

    def tearDown(self):
        """Print captured logs only if test failed."""
        logger.removeHandler(self.log_handler)
        # Check if test failed
        if hasattr(self, '_outcome'):
            result = self._outcome.result
            if result.failures or result.errors:
                # Test failed, print the logs
                log_output = self.log_stream.getvalue()
                if log_output:
                    print(f"\n--- Debug output for {self.id()} ---")
                    print(log_output)
                    print("--- End debug output ---\n")
        self.log_stream.close()

    def get_display_val(self, data, val):
        """
        Helper method to extract the value for a given entry (by name) from
        the children list returned by Configure helper methods.

        Emits debug information whenever a value is looked-up so that the
        test output clearly indicates what is being searched and (when
        found) what value is returned.
        """
        logger.debug("Looking for key '%s' in data:\n%s", val, pformat(data))
        for child in data['children']:
            if child['name'] == val:
                logger.debug("Key '%s' found with value: %s", val, child['value'])
                return child['value']
        logger.debug("Key '%s' not found!", val)
        return None

    def dump_config(self, config_parser):
        """
        Dumps content from a ConfigParser object.
        
        Args:
        config_parser: A ConfigParser instance
        
        Returns:
        str: String representation of the config
        """
        result = []
        for section in config_parser.sections():
            result.append(f"[{section}]")
            for key, value in config_parser.items(section):
                result.append(f"{key} = {value}")
            result.append("")
            
        return "\n".join(result)

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

        logger.debug("Assembled trigger structure:\n%s", pformat(trigger))

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
        logger.debug('CONFIG:\n%s', self.dump_config(parser))
        display = configure.assemble_display()

        logger.debug("Assembled display (raw1):\n%s", pformat(display))

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

        logger.debug("Assembled display (raw2):\n%s", pformat(display))

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

        logger.debug("Assembled display (raw3):\n%s", pformat(display))

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

        logger.debug("Assembled display (all settings):\n%s", pformat(display))

        # Mode
        self.assertEqual(self.get_display_val(display, 'Mode'), 'fft')
        # FFT filter (capitalized by implementation)
        self.assertEqual(self.get_display_val(display, 'FFT filter'), 'hamming')
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

        logger.debug("Assembled display (defaults):\n%s", pformat(display))

        self.assertEqual(self.get_display_val(display, 'Mode'), 'normal')
        self.assertEqual(self.get_display_val(display, 'FFT filter'), 'none')
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

        logger.debug("Assembled display (bad input):\n%s", pformat(display))

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

    # ------------------------------------------------------------------
    # Channel configuration tests
    # ------------------------------------------------------------------
    def test_channel_basic(self):
        """
        Test basic channel configuration with explicit channel definitions.
        """
        raw = """
        [SCOPE]
        DefaultProtocol = ca

        [CHANNELS]
        COUNT=2
        chan0.field=field1
        chan0.dcoffset=1.5
        chan1.field=field2
        chan1.dcoffset=-2.0
        """
        parser = ConfigParser()
        parser.read_string(raw)
        configure = Configure(parser)
        channels = configure.assemble_channel()

        logger.debug("Assembled channels (basic):\n%s", pformat(channels))

        # Should have 2 channels
        self.assertEqual(len(channels), 2)

        # Check first channel
        ch0 = channels[0]
        self.assertEqual(ch0['name'], 'Channel 1')
        self.assertEqual(self.get_display_val(ch0, 'Field'), 'field1')
        self.assertEqual(self.get_display_val(ch0, 'DC offset'), 1.5)
        self.assertEqual(self.get_display_val(ch0, 'Color'), '#FFFF00')

        # Check second channel
        ch1 = channels[1]
        self.assertEqual(ch1['name'], 'Channel 2')
        self.assertEqual(self.get_display_val(ch1, 'Field'), 'field2')
        self.assertEqual(self.get_display_val(ch1, 'DC offset'), -2.0)
        self.assertEqual(self.get_display_val(ch1, 'Color'), '#FF00FF')

    def test_channel_defaults(self):
        """
        Test channel configuration with default values when no channels specified.
        """
        raw = """
        [SCOPE]
        DefaultProtocol = ca
        """
        parser = ConfigParser()
        parser.read_string(raw)
        configure = Configure(parser)
        channels = configure.assemble_channel()

        logger.debug("Assembled channels (defaults):\n%s", pformat(channels))

        # Should have 4 channels by default
        self.assertEqual(len(channels), 4)

        # All channels should have default values
        for i, ch in enumerate(channels):
            self.assertEqual(ch['name'], f'Channel {i+1}')
            self.assertEqual(self.get_display_val(ch, 'Field'), 'None')
            self.assertEqual(self.get_display_val(ch, 'DC offset'), 0.0)

    def test_channel_count_override(self):
        """
        Test that channel count is overridden when more channels are defined
        than specified in COUNT.
        """
        raw = """
        [SCOPE]
        DefaultProtocol = ca

        [CHANNELS]
        COUNT=2
        chan0.field=field1
        chan1.field=field2
        chan2.field=field3
        chan3.field=field4
        chan4.field=field5
        """
        parser = ConfigParser()
        parser.read_string(raw)
        configure = Configure(parser)
        channels = configure.assemble_channel()

        logger.debug("Assembled channels (count override):\n%s", pformat(channels))

        # Should have 5 channels (overriding COUNT=2)
        self.assertEqual(len(channels), 5)

        # Verify all defined channels are present
        self.assertEqual(self.get_display_val(channels[0], 'Field'), 'field1')
        self.assertEqual(self.get_display_val(channels[4], 'Field'), 'field5')

    def test_channel_max_limit(self):
        """
        Test that channel count is limited to maximum of 10.
        """
        raw = """
        [SCOPE]
        DefaultProtocol = ca

        [CHANNELS]
        COUNT=15
        """
        parser = ConfigParser()
        parser.read_string(raw)
        configure = Configure(parser)
        channels = configure.assemble_channel()

        logger.debug("Assembled channels (max limit):\n%s", pformat(channels))

        # Should be limited to 10 channels
        self.assertEqual(len(channels), 10)

    def test_channel_partial_config(self):
        """
        Test channel configuration with only some channels defined.
        Remaining channels should use defaults.

        Note: Channels from config file are returned in the order they appear,
        not by channel number. Missing channel indices are filled with defaults.
        """
        raw = """
        [SCOPE]
        DefaultProtocol = ca

        [CHANNELS]
        COUNT=4
        chan0.field=field1
        chan0.dcoffset=5.0
        chan2.field=field3
        """
        parser = ConfigParser()
        parser.read_string(raw)
        configure = Configure(parser)
        channels = configure.assemble_channel()

        logger.debug("Assembled channels (partial config):\n%s", pformat(channels))

        # Should have 4 channels
        self.assertEqual(len(channels), 4)

        # First two channels are from config (chan0 and chan2 in order they appear)
        # Channel 0 should have custom config
        self.assertEqual(self.get_display_val(channels[0], 'Field'), 'field1')
        self.assertEqual(self.get_display_val(channels[0], 'DC offset'), 5.0)

        # Channel 1 is chan2 from config (second channel defined)
        self.assertEqual(self.get_display_val(channels[1], 'Field'), 'field3')
        self.assertEqual(self.get_display_val(channels[1], 'DC offset'), 0.0)

        # Remaining channels (2 and 3) should have defaults
        self.assertEqual(self.get_display_val(channels[2], 'Field'), 'None')
        self.assertEqual(self.get_display_val(channels[2], 'DC offset'), 0.0)

        self.assertEqual(self.get_display_val(channels[3], 'Field'), 'None')
        self.assertEqual(self.get_display_val(channels[3], 'DC offset'), 0.0)

    def test_channel_colors(self):
        """
        Test that channels are assigned unique colors from the color palette.
        """
        raw = """
        [SCOPE]
        DefaultProtocol = ca

        [CHANNELS]
        COUNT=5
        """
        parser = ConfigParser()
        parser.read_string(raw)
        configure = Configure(parser)
        channels = configure.assemble_channel()

        logger.debug("Assembled channels (colors):\n%s", pformat(channels))

        expected_colors = ['#FFFF00', '#FF00FF', '#55FF55', '#00FFFF', '#5555FF']

        for i, (ch, expected_color) in enumerate(zip(channels, expected_colors)):
            color = self.get_display_val(ch, 'Color')
            self.assertEqual(color, expected_color,
                           f"Channel {i} color mismatch: expected {expected_color}, got {color}")

    def test_channel_dcoffset_types(self):
        """
        Test that DC offset handles different numeric formats correctly.
        """
        raw = """
        [SCOPE]
        DefaultProtocol = ca

        [CHANNELS]
        COUNT=4
        chan0.dcoffset=0
        chan1.dcoffset=10.5
        chan2.dcoffset=-5.25
        chan3.dcoffset=1e-3
        """
        parser = ConfigParser()
        parser.read_string(raw)
        configure = Configure(parser)
        channels = configure.assemble_channel()

        logger.debug("Assembled channels (dcoffset types):\n%s", pformat(channels))

        self.assertEqual(self.get_display_val(channels[0], 'DC offset'), 0.0)
        self.assertEqual(self.get_display_val(channels[1], 'DC offset'), 10.5)
        self.assertEqual(self.get_display_val(channels[2], 'DC offset'), -5.25)
        self.assertAlmostEqual(self.get_display_val(channels[3], 'DC offset'), 0.001)

    def test_channel_axis_location_defaults(self):
        """
        Test that all channels have axis location with correct default value.
        """
        raw = """
        [SCOPE]
        DefaultProtocol = ca

        [CHANNELS]
        COUNT=2
        chan0.field=field1
        chan1.field=field2
        """
        parser = ConfigParser()
        parser.read_string(raw)
        configure = Configure(parser)
        channels = configure.assemble_channel()

        logger.debug("Assembled channels (axis location):\n%s", pformat(channels))

        # Both channels should have axis location set to 'Left' by default
        for i, ch in enumerate(channels):
            axis_loc = self.get_display_val(ch, 'Axis location')
            self.assertEqual(axis_loc, 'Left',
                           f"Channel {i} should have default axis location 'Left'")


if __name__ == '__main__':
    unittest.main()
