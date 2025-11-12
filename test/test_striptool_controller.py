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

    def create_controller(self, cfgtext=None):
        if not cfgtext:
            cfgtext = self.DEFAULT_CFG
        cfg = ConfigParser()
        cfg.read_string(cfgtext)
        self.cfg = StripToolConfigure(cfg)
        
        self.striptool_controller = StripToolController(
            self.window,  self.model, self.pvedit_dialog, self.warning, self.parameters, self.cfg)
        
    def test_pv_operations(self):
        """
        Test PV list creation, editing, and callback operations.
        Tests both initial PV loading and runtime PV edit operations.
        """
        # Test 1: PV list loading and callback editing
        raw = """
[STRIPTOOL]
Chan1.PV = pva://Bar:Baz
Chan2.PV = pva://Bar:Baz2
Chan1.Color = #000000
Chan2.Color = #FFFFFF
        """

        self.create_controller(raw)

        expected = {
            'Bar:Baz' : PvConfig('Bar:Baz', '#000000', 'pva'),
            'Bar:Baz2' : PvConfig('Bar:Baz2', '#FFFFFF', 'pva'),
            }
        pvdict = self.striptool_controller.pvdict
        self.assertEqual(len(expected), len(pvdict))
        for k, v in expected.items():
            self.assertTrue(k in pvdict)
            p = pvdict[k].make_pvconfig()
            self.assertEqual(p.pvname, v.pvname)
            self.assertEqual(p.color, v.color)
            self.assertEqual(p.proto, v.proto)

        # Test editing via callback
        newpvlist = [ PvConfig('Foo:bar', '#444444', 'ca'), PvConfig('Foo:bar2', '#555555', 'ca') ]
        self.striptool_controller.pv_edit_callback(newpvlist)
        self.assertEqual(len(newpvlist), len(pvdict))
        pvdict = self.striptool_controller.pvdict
        for v in newpvlist:
            self.assertTrue(v.pvname in pvdict)
            p = pvdict[v.pvname].make_pvconfig()
            self.assertEqual(p.pvname, v.pvname)
            self.assertEqual(p.color, v.color)
            self.assertEqual(p.proto, v.proto)

        # Test 2: PV edit dialog operations
        raw2 = """
[STRIPTOOL]
DefaultProtocol = pva
Chan0.PV = Ch0
Chan1.PV = Ch1
Chan2.PV = Ch2
"""

        pvcount = 3
        self.create_controller(raw2)

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
        self.create_controller()

        #make sure that update_status runs without errors
        self.striptool_controller.update_status()

    # ------------------------------------------------------------------
    # Config file vs keyword arguments tests
    # ------------------------------------------------------------------
    def test_configuration_and_kwargs(self):
        """
        Test display settings, PV loading, default protocols, kwargs, and mixed configs.
        Verifies that config file settings are properly loaded, kwargs work correctly,
        and PVs from both sources are integrated into the controller.
        """
        from c2dataviewer.model import make_protocol

        # Test 1: Display settings from config file
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

        window = StripToolWindow()
        parameters = Parameter.create(
            name="params", type="group", children=configure.parse())
        window.parameterPane.setParameters(parameters, showTop=False)

        model = DataReceiver()
        warning = WarningDialog(None)
        pvedit_dialog = PvEditDialog()

        controller = StripToolController(
            window, model, pvedit_dialog, warning, parameters, configure)

        # Verify settings are loaded via parameters
        self.assertFalse(parameters.child("Display").child("Autoscale").value())
        self.assertEqual(parameters.child("Display").child("Mode").value(), 'psd')
        self.assertEqual(parameters.child("Display").child("Exp moving avg").value(), 10)
        self.assertEqual(parameters.child("Display").child("Refresh").value(), 0.3)
        self.assertTrue(parameters.child("Display").child("Histogram").value())

        # Test 2: PVs from config loaded into controller
        config_str2 = """
        [STRIPTOOL]
        DefaultProtocol = ca
        Chan1.PV = TEST:PV:ONE
        Chan1.Color = #FF0000
        Chan2.PV = pva://TEST:PV:TWO
        Chan2.Color = #00FF00
        """
        cfg2 = ConfigParser()
        cfg2.read_string(config_str2)
        configure2 = StripToolConfigure(cfg2)

        window2 = StripToolWindow()
        parameters2 = Parameter.create(
            name="params", type="group", children=configure2.parse())
        window2.parameterPane.setParameters(parameters2, showTop=False)

        model2 = DataReceiver()
        warning2 = WarningDialog(None)
        pvedit_dialog2 = PvEditDialog()

        controller2 = StripToolController(
            window2, model2, pvedit_dialog2, warning2, parameters2, configure2)

        # Verify PVs are loaded into controller
        self.assertEqual(len(controller2.pvdict), 2)
        self.assertIn('TEST:PV:ONE', controller2.pvdict)
        self.assertIn('TEST:PV:TWO', controller2.pvdict)

        # Verify PV details
        pv1_config = controller2.pvdict['TEST:PV:ONE'].make_pvconfig()
        self.assertEqual(pv1_config.color, '#FF0000')

        pv2_config = controller2.pvdict['TEST:PV:TWO'].make_pvconfig()
        self.assertEqual(pv2_config.color, '#00FF00')

        # Test 3: Default protocol is used
        config_str3 = """
        [STRIPTOOL]
        DefaultProtocol = pva
        Chan1.PV = TEST:PV:DEFAULT
        """
        cfg3 = ConfigParser()
        cfg3.read_string(config_str3)
        configure3 = StripToolConfigure(cfg3)

        window3 = StripToolWindow()
        parameters3 = Parameter.create(
            name="params", type="group", children=configure3.parse())
        window3.parameterPane.setParameters(parameters3, showTop=False)

        model3 = DataReceiver()
        warning3 = WarningDialog(None)
        pvedit_dialog3 = PvEditDialog()

        controller3 = StripToolController(
            window3, model3, pvedit_dialog3, warning3, parameters3, configure3)

        # Verify default protocol is used
        self.assertEqual(configure3.default_proto, 'pva')
        pv_config = controller3.pvdict['TEST:PV:DEFAULT'].make_pvconfig()
        self.assertEqual(pv_config.proto, make_protocol('pva'))

        # Test 4: PV kwarg integration
        cfg4 = ConfigParser()
        cfg4.read_string("[STRIPTOOL]\nDefaultProtocol = ca")

        # Pass PV via kwarg
        configure4 = StripToolConfigure(cfg4, pv={'kwarg_pv': 'KWARG:TEST:PV'})

        window4 = StripToolWindow()
        parameters4 = Parameter.create(
            name="params", type="group", children=configure4.parse())
        window4.parameterPane.setParameters(parameters4, showTop=False)

        model4 = DataReceiver()
        warning4 = WarningDialog(None)
        pvedit_dialog4 = PvEditDialog()

        controller4 = StripToolController(
            window4, model4, pvedit_dialog4, warning4, parameters4, configure4)

        # Verify kwarg PV is in controller
        self.assertIn('KWARG:TEST:PV', controller4.pvdict)

        # Test 5: Mixed config and kwarg PVs
        config_str5 = """
        [STRIPTOOL]
        DefaultProtocol = ca
        Chan1.PV = CONFIG:PV
        Chan1.Color = #0000FF
        """
        cfg5 = ConfigParser()
        cfg5.read_string(config_str5)

        # Add kwarg PV
        configure5 = StripToolConfigure(cfg5, pv={'kwarg': 'KWARG:PV'})

        window5 = StripToolWindow()
        parameters5 = Parameter.create(
            name="params", type="group", children=configure5.parse())
        window5.parameterPane.setParameters(parameters5, showTop=False)

        model5 = DataReceiver()
        warning5 = WarningDialog(None)
        pvedit_dialog5 = PvEditDialog()

        controller5 = StripToolController(
            window5, model5, pvedit_dialog5, warning5, parameters5, configure5)

        # Both PVs should be in controller
        self.assertIn('CONFIG:PV', controller5.pvdict)
        self.assertIn('KWARG:PV', controller5.pvdict)
        self.assertEqual(len(controller5.pvdict), 2)

        # Verify config PV retains its color
        config_pv = controller5.pvdict['CONFIG:PV'].make_pvconfig()
        self.assertEqual(config_pv.color, '#0000FF')

    def test_controller_pv_edit_updates(self):
        """
        Test that controller properly handles PV edits after initialization.
        This tests runtime behavior, not just config loading.
        """
        config_str = """
        [STRIPTOOL]
        DefaultProtocol = ca
        Chan1.PV = INITIAL:PV
        """
        cfg = ConfigParser()
        cfg.read_string(config_str)
        configure = StripToolConfigure(cfg)

        window = StripToolWindow()
        parameters = Parameter.create(
            name="params", type="group", children=configure.parse())
        window.parameterPane.setParameters(parameters, showTop=False)

        model = DataReceiver()
        warning = WarningDialog(None)
        pvedit_dialog = PvEditDialog()

        controller = StripToolController(
            window, model, pvedit_dialog, warning, parameters, configure)

        # Initial state
        self.assertEqual(len(controller.pvdict), 1)
        self.assertIn('INITIAL:PV', controller.pvdict)

        # Add new PV via controller callback (simulates user edit)
        new_pvlist = [
            PvConfig('NEW:PV:ONE', '#AA0000', 'ca'),
            PvConfig('NEW:PV:TWO', '#00AA00', 'pva')
        ]
        controller.pv_edit_callback(new_pvlist)

        # Verify controller updated
        self.assertEqual(len(controller.pvdict), 2)
        self.assertIn('NEW:PV:ONE', controller.pvdict)
        self.assertIn('NEW:PV:TWO', controller.pvdict)
        self.assertNotIn('INITIAL:PV', controller.pvdict)

    def test_serialize(self):
        """
        Test serialize function with full configuration and minimal configuration.
        Verifies that serialization works properly for all configuration scenarios.
        """
        from io import StringIO

        # Test 1: Full configuration with PVs
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

        window = StripToolWindow()
        parameters = Parameter.create(
            name="params", type="group", children=configure.parse())
        window.parameterPane.setParameters(parameters, showTop=False)

        model = DataReceiver()
        warning = WarningDialog(None)
        pvedit_dialog = PvEditDialog()

        controller = StripToolController(
            window, model, pvedit_dialog, warning, parameters, configure)

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

        # Test 2: Minimal configuration (no PVs)
        config_str2 = """
        [STRIPTOOL]
        DefaultProtocol = ca
        """
        cfg2 = ConfigParser()
        cfg2.read_string(config_str2)
        configure2 = StripToolConfigure(cfg2)

        window2 = StripToolWindow()
        parameters2 = Parameter.create(
            name="params", type="group", children=configure2.parse())
        window2.parameterPane.setParameters(parameters2, showTop=False)

        model2 = DataReceiver()
        warning2 = WarningDialog(None)
        pvedit_dialog2 = PvEditDialog()

        controller2 = StripToolController(
            window2, model2, pvedit_dialog2, warning2, parameters2, configure2)

        # Serialize to StringIO
        output2 = StringIO()
        controller2.serialize(output2)

        # Read back the serialized config
        output2.seek(0)
        result_cfg2 = ConfigParser()
        result_cfg2.read_file(output2)

        # Verify app type
        self.assertEqual(result_cfg2.get('DEFAULT', 'APP'), 'STRIPTOOL')

        # Verify STRIPTOOL section exists even with no PVs
        self.assertTrue(result_cfg2.has_section('STRIPTOOL'))


if __name__ == '__main__':
    unittest.main()

