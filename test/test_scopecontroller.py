# -*- coding: utf-8 -*-

"""
C2 DATA VIEWER is distributed subject to a Software License Agreement found
in the file LICENSE that is included with this distribution.
SPDX-License-Identifier: EPICS

Copyright 2021 UChicago Argonne LLC
 as operator of Argonne National Laboratory

Unit tests for Scope controller

@author: Matic Pogacnik <mpogacnik@anl.gov>
"""
import os
import sys
import unittest
import configparser
import pvaccess as pva

from pyqtgraph.Qt import QtWidgets
from pyqtgraph.parametertree import Parameter

from c2dataviewer.model import DataSource as DataReceiver
from c2dataviewer.control.scopeconfig import Configure
from c2dataviewer.scope import ScopeWindow, WarningDialog
from c2dataviewer.control import ScopeController


os.environ["QT_QPA_PLATFORM"] = "offscreen"


class TestImageDisplay(unittest.TestCase):
    """
    Units tests for the scope controllers.
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
        """
        Build the environment for each unit test case.
        This method is called before each test.

        :return:
        """

        # Create ImageWindow and get the imageWidget instance
        self.window = ScopeWindow()

        # Build parameter tree
        configure = Configure(configparser.ConfigParser())
        parameters = Parameter.create(
            name="params", type="group", children=configure.parse())
        self.window.parameterPane.setParameters(parameters, showTop=False)

        # Model to be used
        model = DataReceiver()

        # Build GUI elements
        warning = WarningDialog(None)

        self.scope_controller = ScopeController(
            widget=self.window, model=model, parameters=parameters, WARNING=warning)

    def tearDown(self):
        """
        Tear down the environment after each test case.
        This mentod is called after each test.

        :return:
        """
        pass

    def test_update_status(self):
        """
        Test update statistics
        """
        #make sure that update_status runs without errors
        self.scope_controller.update_status()


    def test_get_fdr(self):
        """
        Test if the PV structure is properly parsed and correct fields are
        extracted to be used as a drop down items on the GUI. This are pva.ScalarType
        and arrays of pva.ScalarType.
        """
        # Mock get for the receiver
        def mock_get(*_):

            test_struct = {
                "anInt": pva.INT,
                "aStruct": {
                    "aStruct_aFloat": pva.FLOAT,
                    "aStruct_aDoubleArray": [pva.DOUBLE],
                },
                "aFloatArray": [pva.FLOAT],
                "aStringArray": [pva.STRING],
                "aStructArray": [
                    {
                        "aStructArray_aFloat": pva.FLOAT,
                        "aStructArray_aDoubleArray": [pva.DOUBLE],
                    }
                ],
                "aString": pva.STRING,
                "aDoubleArray": [pva.DOUBLE],
                "aVariant": (),
                "aBooleanArray": [pva.BOOLEAN],
            }
            return pva.PvObject(test_struct)
        self.scope_controller.model.get = mock_get

        fdr, fdr_scalar, fdr_nonnumeric = self.scope_controller.get_fdr()

        self.assertListEqual(fdr, ['aBooleanArray', 'aDoubleArray',
                             'aFloatArray', 'aStruct.aStruct_aDoubleArray'])
        self.assertListEqual(
            fdr_scalar, ['aString', 'aStruct.aStruct_aFloat', 'anInt'])

        self.assertListEqual(fdr_nonnumeric, ['aStringArray'])
        
    def test_buffer_size(self):
        #pass in data
        self.scope_controller.monitor_callback({ 'x' : [10]*100})
        bufval = self.scope_controller.parameters.child("Acquisition").child("Buffer (Samples)").value()
        self.assertEqual(bufval, 100)

        #set to object unit
        self.scope_controller.set_buffer_unit('Objects')
        bufval = self.scope_controller.parameters.child("Acquisition").child("Buffer (Objects)").value()
        self.assertEqual(bufval, 1)

    def test_configuration_and_kwargs(self):
        """
        Test config file settings, keyword arguments, and kwarg override behavior.
        Tests that settings from config file are properly loaded, kwargs work,
        and kwargs override config file values when both are present.
        """
        # Test 1: Config file settings
        config_str = """
        [SCOPE]
        DefaultProtocol = ca
        AUTOSCALE = True

        [DISPLAY]
        MODE = fft
        AVERAGE = 5
        REFRESH = 200

        [ACQUISITION]
        BUFFER = 500
        """
        parser = configparser.ConfigParser()
        parser.read_string(config_str)

        window = ScopeWindow()
        configure = Configure(parser)
        parameters = Parameter.create(
            name="params", type="group", children=configure.parse())
        window.parameterPane.setParameters(parameters, showTop=False)

        model = DataReceiver()
        warning = WarningDialog(None)
        controller = ScopeController(
            widget=window, model=model, parameters=parameters, WARNING=warning)

        # Verify config settings are loaded
        self.assertTrue(parameters.child("Display").child("Autoscale").value())
        self.assertEqual(parameters.child("Display").child("Mode").value(), 'fft')
        self.assertEqual(parameters.child("Display").child("Exp moving avg").value(), 5)
        self.assertEqual(parameters.child("Display").child("Refresh").value(), 0.2)
        self.assertEqual(parameters.child("Acquisition").child("Buffer (Samples)").value(), 500)

        # Test 2: Kwarg settings
        parser2 = configparser.ConfigParser()
        parser2.read_string("[SCOPE]\nDefaultProtocol = ca")

        window2 = ScopeWindow()
        configure2 = Configure(parser2, arrayid='TestArray', xaxes='TestXAxis')
        parameters2 = Parameter.create(
            name="params", type="group", children=configure2.parse())
        window2.parameterPane.setParameters(parameters2, showTop=False)

        model2 = DataReceiver()
        warning2 = WarningDialog(None)
        controller2 = ScopeController(
            widget=window2, model=model2, parameters=parameters2, WARNING=warning2)

        # Verify kwarg settings are used
        self.assertEqual(parameters2.child("Config").child("ArrayId").value(), 'TestArray')
        self.assertEqual(parameters2.child("Config").child("X Axes").value(), 'TestXAxis')

        # Test 3: Kwarg overrides config
        config_str3 = """
        [SCOPE]
        DefaultProtocol = ca

        [CONFIG]
        ARRAYID = ConfigArrayId
        XAXES = ConfigXAxis
        """
        parser3 = configparser.ConfigParser()
        parser3.read_string(config_str3)

        window3 = ScopeWindow()
        configure3 = Configure(parser3, arrayid='KwargArrayId', xaxes='KwargXAxis')
        parameters3 = Parameter.create(
            name="params", type="group", children=configure3.parse())
        window3.parameterPane.setParameters(parameters3, showTop=False)

        model3 = DataReceiver()
        warning3 = WarningDialog(None)
        controller3 = ScopeController(
            widget=window3, model=model3, parameters=parameters3, WARNING=warning3)

        # Verify kwargs override config file values
        self.assertEqual(parameters3.child("Config").child("ArrayId").value(), 'KwargArrayId')
        self.assertEqual(parameters3.child("Config").child("X Axes").value(), 'KwargXAxis')

        # Test 4: PV kwarg
        parser4 = configparser.ConfigParser()
        parser4.read_string("[SCOPE]\nDefaultProtocol = ca")

        window4 = ScopeWindow()
        configure4 = Configure(parser4, pv={'test': 'TEST:PV:NAME'})
        parameters4 = Parameter.create(
            name="params", type="group", children=configure4.parse())
        window4.parameterPane.setParameters(parameters4, showTop=False)

        model4 = DataReceiver()
        warning4 = WarningDialog(None)
        controller4 = ScopeController(
            widget=window4, model=model4, parameters=parameters4, WARNING=warning4)

        # Verify PV kwarg is used
        self.assertEqual(parameters4.child("Acquisition").child("PV").value(), 'TEST:PV:NAME')

    def test_serialize(self):
        """
        Test serialize function with full config, minimal config, and buffer units.
        Verifies that serialization works properly for all configuration scenarios.
        """
        from io import StringIO
        from configparser import ConfigParser

        # Test 1: Full configuration with channels
        config_str = """
        [SCOPE]
        DefaultProtocol = pva

        [DISPLAY]
        MODE = fft
        AVERAGE = 10
        AUTOSCALE = True
        REFRESH = 500

        [ACQUISITION]
        PV = TEST:SCOPE:PV
        BUFFER = 1000
        BUFFERUNIT = Samples

        [CONFIG]
        ARRAYID = myArrayId
        XAXES = myXAxis
        MAJORTICKS = 5
        MINORTICKS = 2
        """
        parser = ConfigParser()
        parser.read_string(config_str)

        window = ScopeWindow()
        configure = Configure(parser)
        parameters = Parameter.create(
            name="params", type="group", children=configure.parse())
        window.parameterPane.setParameters(parameters, showTop=False)

        model = DataReceiver()
        warning = WarningDialog(None)
        controller = ScopeController(
            widget=window, model=model, parameters=parameters, WARNING=warning)

        # Set limits for Field parameters so they can accept custom values
        field_limits = ["None", "field1", "field2"]
        controller.parameters.child("Channel 1", "Field").setLimits(field_limits)
        controller.parameters.child("Channel 2", "Field").setLimits(field_limits)

        # Set some channel fields in parameters (serialize reads from parameters)
        controller.parameters.child("Channel 1", "Field").setValue("field1")
        controller.parameters.child("Channel 1", "DC offset").setValue(5.0)
        controller.parameters.child("Channel 2", "Field").setValue("field2")

        # Serialize to StringIO
        output = StringIO()
        controller.serialize(output)

        # Read back the serialized config
        output.seek(0)
        result_cfg = ConfigParser()
        result_cfg.read_file(output)

        # Verify app type
        self.assertEqual(result_cfg.get('DEFAULT', 'APP'), 'SCOPE')

        # Verify Display settings
        self.assertEqual(result_cfg.get('DISPLAY', 'mode'), 'fft')
        self.assertEqual(result_cfg.get('DISPLAY', 'average'), '10')
        self.assertEqual(result_cfg.get('DISPLAY', 'autoscale'), 'True')
        self.assertEqual(result_cfg.get('DISPLAY', 'refresh'), '500')

        # Verify Acquisition settings
        self.assertEqual(result_cfg.get('ACQUISITION', 'pv'), 'TEST:SCOPE:PV')
        self.assertEqual(result_cfg.get('ACQUISITION', 'buffer'), '1000')
        self.assertEqual(result_cfg.get('ACQUISITION', 'bufferunit'), 'Samples')

        # Verify Config settings
        self.assertTrue(result_cfg.has_section('CONFIG'))
        self.assertEqual(result_cfg.get('CONFIG', 'majorticks'), '5')
        self.assertEqual(result_cfg.get('CONFIG', 'minorticks'), '2')

        # Verify channel configurations
        self.assertTrue(result_cfg.has_section('CHANNELS'))
        self.assertEqual(result_cfg.get('CHANNELS', 'chan1.field'), 'field1')
        self.assertEqual(result_cfg.get('CHANNELS', 'chan1.dcoffset'), '5.0')
        self.assertEqual(result_cfg.get('CHANNELS', 'chan2.field'), 'field2')

        # Test 2: Minimal configuration (default settings)
        parser2 = ConfigParser()
        parser2.read_string("[SCOPE]\nDefaultProtocol = ca")

        window2 = ScopeWindow()
        configure2 = Configure(parser2)
        parameters2 = Parameter.create(
            name="params", type="group", children=configure2.parse())
        window2.parameterPane.setParameters(parameters2, showTop=False)

        model2 = DataReceiver()
        warning2 = WarningDialog(None)
        controller2 = ScopeController(
            widget=window2, model=model2, parameters=parameters2, WARNING=warning2)

        # Serialize to StringIO
        output2 = StringIO()
        controller2.serialize(output2)

        # Read back the serialized config
        output2.seek(0)
        result_cfg2 = ConfigParser()
        result_cfg2.read_file(output2)

        # Verify app type
        self.assertEqual(result_cfg2.get('DEFAULT', 'APP'), 'SCOPE')

        # Verify Display section exists (should have default values)
        self.assertTrue(result_cfg2.has_section('DISPLAY'))

        # Verify Acquisition section exists
        self.assertTrue(result_cfg2.has_section('ACQUISITION'))

        # Test 3: Buffer unit set to Objects
        config_str3 = """
        [SCOPE]
        DefaultProtocol = pva

        [ACQUISITION]
        BUFFERUNIT = Objects
        BUFFER = 50
        """
        parser3 = ConfigParser()
        parser3.read_string(config_str3)

        window3 = ScopeWindow()
        configure3 = Configure(parser3)
        parameters3 = Parameter.create(
            name="params", type="group", children=configure3.parse())
        window3.parameterPane.setParameters(parameters3, showTop=False)

        model3 = DataReceiver()
        warning3 = WarningDialog(None)
        controller3 = ScopeController(
            widget=window3, model=model3, parameters=parameters3, WARNING=warning3)

        # Serialize to StringIO
        output3 = StringIO()
        controller3.serialize(output3)

        # Read back the serialized config
        output3.seek(0)
        result_cfg3 = ConfigParser()
        result_cfg3.read_file(output3)

        # Verify buffer unit and size
        self.assertEqual(result_cfg3.get('ACQUISITION', 'bufferunit'), 'Objects')
        self.assertEqual(result_cfg3.get('ACQUISITION', 'buffer'), '50')

