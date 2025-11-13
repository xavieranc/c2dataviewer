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
    @classmethod
    def setUpClass(cls):
        """Set up logging capture once for all tests."""
        cls.log_stream = StringIO()
        cls.log_handler = logging.StreamHandler(cls.log_stream)
        cls.log_handler.setLevel(logging.DEBUG)
        formatter = logging.Formatter('%(levelname)s:%(name)s:%(message)s')
        cls.log_handler.setFormatter(formatter)
        logger.addHandler(cls.log_handler)

    @classmethod
    def tearDownClass(cls):
        """Clean up logging after all tests."""
        logger.removeHandler(cls.log_handler)
        cls.log_stream.close()

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

    def test_display_configuration(self):
        """
        Comprehensive test for display configuration including:
        - Autoscale precedence (SCOPE section overrides DISPLAY section)
        - All settings with valid values
        - Default values when settings absent
        - Bad/invalid input handling with fallback to defaults
        """
        # Test 1: Autoscale precedence - SCOPE section overrides DISPLAY
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
        logger.debug("Assembled display (autoscale precedence):\n%s", pformat(display))
        # SCOPE section has AUTOSCALE=False, so it takes precedence
        self.assertFalse(self.get_display_val(data=display, val='Autoscale'))

        # Test 2: Autoscale from DISPLAY section when not in SCOPE
        raw2 = """
        [SCOPE]
        DefaultProtocol = ca

        [DISPLAY]
        AUTOSCALE=True
        """
        parser = ConfigParser()
        parser.read_string(raw2)
        configure = Configure(parser)
        section = parser["DISPLAY"]
        display = configure.assemble_display(section=section)
        logger.debug("Assembled display (autoscale from display):\n%s", pformat(display))
        self.assertTrue(self.get_display_val(data=display, val='Autoscale'))

        # Test 3: All settings with valid values
        raw3 = """
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
        """
        parser = ConfigParser()
        parser.read_string(raw3)
        configure = Configure(parser)
        section = parser["DISPLAY"]
        display = configure.assemble_display(section=section)
        logger.debug("Assembled display (all settings):\n%s", pformat(display))
        self.assertEqual(self.get_display_val(display, 'Mode'), 'fft')
        self.assertEqual(self.get_display_val(display, 'FFT filter'), 'hamming')
        self.assertEqual(self.get_display_val(display, 'Exp moving avg'), 10)
        self.assertTrue(self.get_display_val(display, 'Autoscale'))  # SCOPE precedence
        self.assertFalse(self.get_display_val(display, 'Single axis'))
        self.assertTrue(self.get_display_val(display, 'Histogram'))
        self.assertEqual(self.get_display_val(display, 'Num Bins'), 256)
        self.assertEqual(self.get_display_val(display, 'Refresh'), 0.5)  # 500ms -> 0.5s

        # Test 4: Default values when no DISPLAY section
        raw4 = """
        [SCOPE]
        DefaultProtocol = ca
        """
        parser = ConfigParser()
        parser.read_string(raw4)
        configure = Configure(parser)
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

        # Test 5: Bad/invalid input falls back to defaults
        raw5 = """
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
        parser.read_string(raw5)
        configure = Configure(parser)
        section = parser["DISPLAY"]
        display = configure.assemble_display(section=section)
        logger.debug("Assembled display (bad input):\n%s", pformat(display))
        self.assertEqual(self.get_display_val(display, 'Mode'), 'normal')
        self.assertEqual(self.get_display_val(display, 'FFT filter'), 'none')
        self.assertEqual(self.get_display_val(display, 'Exp moving avg'), 1)
        self.assertTrue(self.get_display_val(display, 'Single axis'))
        self.assertFalse(self.get_display_val(display, 'Histogram'))
        self.assertEqual(self.get_display_val(display, 'Num Bins'), 100)
        self.assertEqual(self.get_display_val(display, 'Refresh'), 0.1)

    # ------------------------------------------------------------------
    # Channel configuration tests
    # ------------------------------------------------------------------
    def test_channel_configuration(self):
        """
        Comprehensive test for channel configuration including:
        - Basic channel definitions with fields and offsets
        - Default values when no channels specified
        - Channel count override when more channels defined than COUNT
        - Maximum channel limit (10 channels)
        - Partial configuration with mixed defined/default channels
        """
        # Test 1: Basic channel configuration
        raw1 = """
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
        parser.read_string(raw1)
        configure = Configure(parser)
        channels = configure.assemble_channel()
        logger.debug("Assembled channels (basic):\n%s", pformat(channels))
        self.assertEqual(len(channels), 2)
        self.assertEqual(channels[0]['name'], 'Channel 1')
        self.assertEqual(self.get_display_val(channels[0], 'Field'), 'field1')
        self.assertEqual(self.get_display_val(channels[0], 'DC offset'), 1.5)
        self.assertEqual(self.get_display_val(channels[0], 'Color'), '#FFFF00')
        self.assertEqual(channels[1]['name'], 'Channel 2')
        self.assertEqual(self.get_display_val(channels[1], 'Field'), 'field2')
        self.assertEqual(self.get_display_val(channels[1], 'DC offset'), -2.0)
        self.assertEqual(self.get_display_val(channels[1], 'Color'), '#FF00FF')

        # Test 2: Default values when no channels specified
        raw2 = """
        [SCOPE]
        DefaultProtocol = ca
        """
        parser = ConfigParser()
        parser.read_string(raw2)
        configure = Configure(parser)
        channels = configure.assemble_channel()
        logger.debug("Assembled channels (defaults):\n%s", pformat(channels))
        self.assertEqual(len(channels), 4)  # 4 channels by default
        for i, ch in enumerate(channels):
            self.assertEqual(ch['name'], f'Channel {i+1}')
            self.assertEqual(self.get_display_val(ch, 'Field'), 'None')
            self.assertEqual(self.get_display_val(ch, 'DC offset'), 0.0)

        # Test 3: Channel count override when more channels defined
        raw3 = """
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
        parser.read_string(raw3)
        configure = Configure(parser)
        channels = configure.assemble_channel()
        logger.debug("Assembled channels (count override):\n%s", pformat(channels))
        self.assertEqual(len(channels), 5)  # Overrides COUNT=2
        self.assertEqual(self.get_display_val(channels[0], 'Field'), 'field1')
        self.assertEqual(self.get_display_val(channels[4], 'Field'), 'field5')

        # Test 4: Maximum channel limit
        raw4 = """
        [SCOPE]
        DefaultProtocol = ca

        [CHANNELS]
        COUNT=15
        """
        parser = ConfigParser()
        parser.read_string(raw4)
        configure = Configure(parser)
        channels = configure.assemble_channel()
        logger.debug("Assembled channels (max limit):\n%s", pformat(channels))
        self.assertEqual(len(channels), 10)  # Limited to 10 channels

        # Test 5: Partial channel configuration
        raw5 = """
        [SCOPE]
        DefaultProtocol = ca

        [CHANNELS]
        COUNT=4
        chan0.field=field1
        chan0.dcoffset=5.0
        chan2.field=field3
        """
        parser = ConfigParser()
        parser.read_string(raw5)
        configure = Configure(parser)
        channels = configure.assemble_channel()
        logger.debug("Assembled channels (partial config):\n%s", pformat(channels))
        self.assertEqual(len(channels), 4)
        # Channels from config appear first in order defined
        self.assertEqual(self.get_display_val(channels[0], 'Field'), 'field1')
        self.assertEqual(self.get_display_val(channels[0], 'DC offset'), 5.0)
        self.assertEqual(self.get_display_val(channels[1], 'Field'), 'field3')
        self.assertEqual(self.get_display_val(channels[1], 'DC offset'), 0.0)
        # Remaining channels use defaults
        self.assertEqual(self.get_display_val(channels[2], 'Field'), 'None')
        self.assertEqual(self.get_display_val(channels[3], 'Field'), 'None')

    def test_channel_properties(self):
        """
        Test specific channel properties including:
        - Color assignment from palette
        - DC offset with various numeric formats
        - Axis location defaults
        """
        # Test 1: Color assignment
        raw1 = """
        [SCOPE]
        DefaultProtocol = ca

        [CHANNELS]
        COUNT=5
        """
        parser = ConfigParser()
        parser.read_string(raw1)
        configure = Configure(parser)
        channels = configure.assemble_channel()
        logger.debug("Assembled channels (colors):\n%s", pformat(channels))
        expected_colors = ['#FFFF00', '#FF00FF', '#55FF55', '#00FFFF', '#5555FF']
        for i, (ch, expected_color) in enumerate(zip(channels, expected_colors)):
            color = self.get_display_val(ch, 'Color')
            self.assertEqual(color, expected_color,
                           f"Channel {i} color mismatch: expected {expected_color}, got {color}")

        # Test 2: DC offset with different numeric formats
        raw2 = """
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
        parser.read_string(raw2)
        configure = Configure(parser)
        channels = configure.assemble_channel()
        logger.debug("Assembled channels (dcoffset types):\n%s", pformat(channels))
        self.assertEqual(self.get_display_val(channels[0], 'DC offset'), 0.0)
        self.assertEqual(self.get_display_val(channels[1], 'DC offset'), 10.5)
        self.assertEqual(self.get_display_val(channels[2], 'DC offset'), -5.25)
        self.assertAlmostEqual(self.get_display_val(channels[3], 'DC offset'), 0.001)

        # Test 3: Axis location defaults
        raw3 = """
        [SCOPE]
        DefaultProtocol = ca

        [CHANNELS]
        COUNT=2
        chan0.field=field1
        chan1.field=field2
        """
        parser = ConfigParser()
        parser.read_string(raw3)
        configure = Configure(parser)
        channels = configure.assemble_channel()
        logger.debug("Assembled channels (axis location):\n%s", pformat(channels))
        for i, ch in enumerate(channels):
            axis_loc = self.get_display_val(ch, 'Axis location')
            self.assertEqual(axis_loc, 'Left',
                           f"Channel {i} should have default axis location 'Left'")


if __name__ == '__main__':
    unittest.main()
