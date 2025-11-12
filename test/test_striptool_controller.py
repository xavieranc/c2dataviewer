"""
C2 DATA VIEWER is distributed subject to a Software License Agreement found
in the file LICENSE that is included with this distribution.
SPDX-License-Identifier: EPICS
"""

import unittest
import os
import sys

from configparser import ConfigParser
from pyqtgraph.Qt import QtWidgets
from pyqtgraph.parametertree import Parameter

from c2dataviewer.model import DataSource as DataReceiver
from c2dataviewer.control.striptoolconfig import StripToolConfigure
from c2dataviewer.striptool import StripToolWindow, WarningDialog, PvEditDialog

from c2dataviewer.control.striptoolconfig import StripToolConfigure
from c2dataviewer.control.striptool_controller import StripToolController
from c2dataviewer.control.pvconfig import PvConfig

os.environ["QT_QPA_PLATFORM"] = "offscreen"

class TestStriptoolController(unittest.TestCase):
    DEFAULT_CFG = """
[STRIPTOOL]
"""

    @classmethod
    def setUpClass(cls):
        """
        Set up QApplication for all tests in this class.
        """
        cls.app = QtWidgets.QApplication.instance()
        if cls.app is None:
            cls.app = QtWidgets.QApplication(sys.argv)

    def setUp(self):
        # Create ImageWindow and get the imageWidget instance
        self.window = StripToolWindow()

        # Build parameter tree
        cf = ConfigParser()
        configure = StripToolConfigure(cf)
        self.parameters = Parameter.create(
            name="params", type="group", children=configure.parse())
        self.window.parameterPane.setParameters(self.parameters, showTop=False)

        # Model to be used
        self.model = DataReceiver()

        # Build GUI elements
        self.warning = WarningDialog(None)
        self.pvedit_dialog = PvEditDialog()

    def tearDown(self):
        """
        Tear down the environment after each test case.
        """
        # Clean up the window to prevent Qt object deletion issues
        if hasattr(self, 'window'):
            self.window.close()
            self.window.deleteLater()
        if hasattr(self, 'striptool_controller'):
            del self.striptool_controller
        # Process pending Qt events to ensure cleanup
        QtWidgets.QApplication.processEvents()

    def create_controller(self, configure):
        """
        Helper method to create a controller with the given StripToolConfigure object.

        :param configure: StripToolConfigure object with parsed configuration
        :return: StripToolController instance
        """
        parameters = Parameter.create(
            name="params", type="group", children=configure.parse())
        self.window.parameterPane.setParameters(parameters, showTop=False)

        controller = StripToolController(
            self.window, self.model, self.pvedit_dialog, self.warning, parameters, configure)

        return controller
        

    def test_pv_edit_dialog(self):
        """
        Test PV edit dialog operations.
        """
        raw = """
[STRIPTOOL]
DefaultProtocol = pva
Chan0.PV = Ch0
Chan1.PV = Ch1
Chan2.PV = Ch2
"""
        cfg = ConfigParser()
        cfg.read_string(raw)
        configure = StripToolConfigure(cfg)

        pvcount = 3
        self.striptool_controller = self.create_controller(configure)

        self.assertEqual(len(self.striptool_controller.pvdict), pvcount)
        pvlist = []
        for p in self.striptool_controller.pvdict.values():
            cfg = p.make_pvconfig()
            pvlist.append(cfg)

        pvedit = self.striptool_controller._pvedit_dialog
        pvedit._set_pvlist(pvlist)
        pvedit._add_pv('Ch3', '#000000', 'pva')
        pvedit._on_ok()

        self.assertEqual(len(self.striptool_controller.pvdict), pvcount + 1)
        self.assertTrue('Ch3' in self.striptool_controller.pvdict)

    def test_update_status(self):
        """
        Test update statistics
        """
        cfg = ConfigParser()
        cfg.read_string(self.DEFAULT_CFG)
        configure = StripToolConfigure(cfg)
        self.striptool_controller = self.create_controller(configure)

        #make sure that update_status runs without errors
        self.striptool_controller.update_status()

    # ------------------------------------------------------------------
    # Config file vs keyword arguments tests
    # ------------------------------------------------------------------
    def test_config_display_settings(self):
        """
        Test that display settings from config file are loaded into controller.
        """
        config_str = """
        [STRIPTOOL]
        DefaultProtocol = ca
        AUTOSCALE = False

        [DISPLAY]
        MODE = psd
        AVERAGE = 10
        REFRESH = 300
        HISTOGRAM = True
        """
        cfg = ConfigParser()
        cfg.read_string(config_str)
        configure = StripToolConfigure(cfg)

        controller = self.create_controller(configure)

        # Verify settings are loaded via parameters
        self.assertFalse(controller.parameters.child("Display").child("Autoscale").value())
        self.assertEqual(controller.parameters.child("Display").child("Mode").value(), 'psd')
        self.assertEqual(controller.parameters.child("Display").child("Exp moving avg").value(), 10)
        self.assertEqual(controller.parameters.child("Display").child("Refresh").value(), 0.3)
        self.assertTrue(controller.parameters.child("Display").child("Histogram").value())

    def test_config_pvs_loaded(self):
        """
        Test that PVs from config are properly loaded into controller's pvdict.
        """
        config_str = """
        [STRIPTOOL]
        DefaultProtocol = ca
        Chan1.PV = TEST:PV:ONE
        Chan1.Color = #FF0000
        Chan2.PV = pva://TEST:PV:TWO
        Chan2.Color = #00FF00
        """
        cfg = ConfigParser()
        cfg.read_string(config_str)
        configure = StripToolConfigure(cfg)

        controller = self.create_controller(configure)

        # Verify PVs are loaded into controller
        self.assertEqual(len(controller.pvdict), 2)
        self.assertIn('TEST:PV:ONE', controller.pvdict)
        self.assertIn('TEST:PV:TWO', controller.pvdict)

        # Verify PV details
        pv1_config = controller.pvdict['TEST:PV:ONE'].make_pvconfig()
        self.assertEqual(pv1_config.color, '#FF0000')

        pv2_config = controller.pvdict['TEST:PV:TWO'].make_pvconfig()
        self.assertEqual(pv2_config.color, '#00FF00')

    def test_default_protocol(self):
        """
        Test that default protocol from config is used by controller.
        """
        from c2dataviewer.model import make_protocol

        config_str = """
        [STRIPTOOL]
        DefaultProtocol = pva
        Chan1.PV = TEST:PV:DEFAULT
        """
        cfg = ConfigParser()
        cfg.read_string(config_str)
        configure = StripToolConfigure(cfg)

        controller = self.create_controller(configure)

        # Verify default protocol is used
        self.assertEqual(configure.default_proto, 'pva')
        pv_config = controller.pvdict['TEST:PV:DEFAULT'].make_pvconfig()
        self.assertEqual(pv_config.proto, make_protocol('pva'))

    def test_pv_kwarg_integration(self):
        """
        Test that PVs passed via kwargs are integrated into controller.
        """
        cfg = ConfigParser()
        cfg.read_string("[STRIPTOOL]\nDefaultProtocol = ca")

        # Pass PV via kwarg
        configure = StripToolConfigure(cfg, pv={'kwarg_pv': 'KWARG:TEST:PV'})

        controller = self.create_controller(configure)

        # Verify kwarg PV is in controller
        self.assertIn('KWARG:TEST:PV', controller.pvdict)

    def test_mixed_config_and_kwarg_pvs(self):
        """
        Test controller with both config file PVs and kwarg PVs.
        """
        config_str = """
        [STRIPTOOL]
        DefaultProtocol = ca
        Chan1.PV = CONFIG:PV
        Chan1.Color = #0000FF
        """
        cfg = ConfigParser()
        cfg.read_string(config_str)

        # Add kwarg PV
        configure = StripToolConfigure(cfg, pv={'kwarg': 'KWARG:PV'})

        controller = self.create_controller(configure)

        # Both PVs should be in controller
        self.assertIn('CONFIG:PV', controller.pvdict)
        self.assertIn('KWARG:PV', controller.pvdict)
        self.assertEqual(len(controller.pvdict), 2)

        # Verify config PV retains its color
        config_pv = controller.pvdict['CONFIG:PV'].make_pvconfig()
        self.assertEqual(config_pv.color, '#0000FF')
        
    def test_serialize_full_config(self):
        """
        Test that serialize function writes proper configuration to file with PVs.
        """
        from io import StringIO

        config_str = """
        [STRIPTOOL]
        DefaultProtocol = pva
        Chan1.PV = TEST:PV:ONE
        Chan1.Color = #FF0000
        Chan2.PV = ca://TEST:PV:TWO
        Chan2.Color = #00FF00
        Chan3.PV = TEST:PV:THREE
        Chan3.Color = #0000FF
        """
        cfg = ConfigParser()
        cfg.read_string(config_str)
        configure = StripToolConfigure(cfg)

        controller = self.create_controller(configure)

        # Serialize to StringIO
        output = StringIO()
        controller.serialize(output)

        # Read back the serialized config
        output.seek(0)
        result_cfg = ConfigParser()
        result_cfg.read_file(output)

        # Verify app type
        self.assertEqual(result_cfg.get('DEFAULT', 'APP'), 'STRIPTOOL')

        # Verify PVs are serialized with protocol prefixes
        self.assertEqual(result_cfg.get('STRIPTOOL', 'chan1.pv'), 'pva://TEST:PV:ONE')
        self.assertEqual(result_cfg.get('STRIPTOOL', 'chan1.color'), '#FF0000')

        # Chan2 already has ca:// prefix in config, should keep it
        self.assertEqual(result_cfg.get('STRIPTOOL', 'chan2.pv'), 'ca://TEST:PV:TWO')
        self.assertEqual(result_cfg.get('STRIPTOOL', 'chan2.color'), '#00FF00')

        self.assertEqual(result_cfg.get('STRIPTOOL', 'chan3.pv'), 'pva://TEST:PV:THREE')
        self.assertEqual(result_cfg.get('STRIPTOOL', 'chan3.color'), '#0000FF')

        # Verify scope config is serialized
        self.assertTrue(result_cfg.has_section('DISPLAY'))
        self.assertTrue(result_cfg.has_section('ACQUISITION'))

        # Verify sample mode is serialized
        self.assertTrue(result_cfg.has_option('ACQUISITION', 'SAMPLEMODE'))

    def test_serialize_minimal_config(self):
        """
        Test serialize with minimal configuration (no PVs).
        """
        from io import StringIO

        config_str = """
        [STRIPTOOL]
        DefaultProtocol = ca
        """
        cfg = ConfigParser()
        cfg.read_string(config_str)
        configure = StripToolConfigure(cfg)

        controller = self.create_controller(configure)

        # Serialize to StringIO
        output = StringIO()
        controller.serialize(output)

        # Read back the serialized config
        output.seek(0)
        result_cfg = ConfigParser()
        result_cfg.read_file(output)

        # Verify app type
        self.assertEqual(result_cfg.get('DEFAULT', 'APP'), 'STRIPTOOL')

        # Verify STRIPTOOL section exists even with no PVs
        self.assertTrue(result_cfg.has_section('STRIPTOOL'))


if __name__ == '__main__':
    unittest.main()

