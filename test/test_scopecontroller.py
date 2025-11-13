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
        self.parameters = Parameter.create(
            name="params", type="group", children=configure.parse())
        self.window.parameterPane.setParameters(self.parameters, showTop=False)

        # Model to be used
        self.model = DataReceiver()

        # Build GUI elements
        self.warning = WarningDialog(None)

        self.scope_controller = ScopeController(
            widget=self.window, model=self.model, parameters=self.parameters, WARNING=self.warning)

    def tearDown(self):
        """
        Tear down the environment after each test case.
        This method is called after each test.

        :return:
        """
        # Clean up the window to prevent Qt object deletion issues
        if hasattr(self, 'window'):
            self.window.close()
            self.window.deleteLater()
        if hasattr(self, 'scope_controller'):
            del self.scope_controller
        # Process pending Qt events to ensure cleanup
        QtWidgets.QApplication.processEvents()

    def create_controller(self, configure):
        """
        Helper method to create a controller with the given Configure object.

        :param configure: Configure object with parsed configuration
        :return: ScopeController instance
        """
        parameters = Parameter.create(
            name="params", type="group", children=configure.parse())
        self.window.parameterPane.setParameters(parameters, showTop=False)

        controller = ScopeController(
            widget=self.window, model=self.model, parameters=parameters, WARNING=self.warning)

        return controller

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

    def test_config_file_settings(self):
        """
        Test that settings from config file are properly loaded into controller.
        """
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

        configure = Configure(parser)
        controller = self.create_controller(configure)

        # Verify config settings are loaded
        self.assertTrue(controller.parameters.child("Display").child("Autoscale").value())
        self.assertEqual(controller.parameters.child("Display").child("Mode").value(), 'fft')
        self.assertEqual(controller.parameters.child("Display").child("Exp moving avg").value(), 5)
        self.assertEqual(controller.parameters.child("Display").child("Refresh").value(), 0.2)
        self.assertEqual(controller.parameters.child("Acquisition").child("Buffer (Samples)").value(), 500)

    def test_kwarg_settings(self):
        """
        Test that keyword arguments are properly used in controller setup.
        """
        parser = configparser.ConfigParser()
        parser.read_string("[SCOPE]\nDefaultProtocol = ca")

        configure = Configure(parser, arrayid='TestArray', xaxes='TestXAxis')
        controller = self.create_controller(configure)

        # Verify kwarg settings are used
        self.assertEqual(controller.parameters.child("Config").child("ArrayId").value(), 'TestArray')
        self.assertEqual(controller.parameters.child("Config").child("X Axes").value(), 'TestXAxis')

    def test_kwarg_overrides_config(self):
        """
        Test that keyword arguments override config file settings.
        """
        config_str = """
        [SCOPE]
        DefaultProtocol = ca

        [CONFIG]
        ARRAYID = ConfigArrayId
        XAXES = ConfigXAxis
        """
        parser = configparser.ConfigParser()
        parser.read_string(config_str)

        configure = Configure(parser, arrayid='KwargArrayId', xaxes='KwargXAxis')
        controller = self.create_controller(configure)

        # Verify kwargs override config file values
        self.assertEqual(controller.parameters.child("Config").child("ArrayId").value(), 'KwargArrayId')
        self.assertEqual(controller.parameters.child("Config").child("X Axes").value(), 'KwargXAxis')

    def test_pv_kwarg(self):
        """
        Test that PV can be set via keyword argument.
        """
        parser = configparser.ConfigParser()
        parser.read_string("[SCOPE]\nDefaultProtocol = ca")

        configure = Configure(parser, pv={'test': 'TEST:PV:NAME'})
        controller = self.create_controller(configure)

        # Verify PV kwarg is used
        self.assertEqual(controller.parameters.child("Acquisition").child("PV").value(), 'TEST:PV:NAME')

    def test_serialize_full_config(self):
        """
        Test that serialize function writes proper configuration to file with channels.
        """
        from io import StringIO
        from configparser import ConfigParser

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

        configure = Configure(parser)
        controller = self.create_controller(configure)

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

    def test_serialize_minimal_config(self):
        """
        Test serialize with minimal configuration (default settings).
        """
        from io import StringIO
        from configparser import ConfigParser

        parser = ConfigParser()
        parser.read_string("[SCOPE]\nDefaultProtocol = ca")

        configure = Configure(parser)
        controller = self.create_controller(configure)

        # Serialize to StringIO
        output = StringIO()
        controller.serialize(output)

        # Read back the serialized config
        output.seek(0)
        result_cfg = ConfigParser()
        result_cfg.read_file(output)

        # Verify app type
        self.assertEqual(result_cfg.get('DEFAULT', 'APP'), 'SCOPE')

        # Verify Display section exists (should have default values)
        self.assertTrue(result_cfg.has_section('DISPLAY'))

        # Verify Acquisition section exists
        self.assertTrue(result_cfg.has_section('ACQUISITION'))

    def test_serialize_buffer_objects(self):
        """
        Test serialize with buffer unit set to Objects.
        """
        from io import StringIO
        from configparser import ConfigParser

        config_str = """
        [SCOPE]
        DefaultProtocol = pva

        [ACQUISITION]
        BUFFERUNIT = Objects
        BUFFER = 50
        """
        parser = ConfigParser()
        parser.read_string(config_str)

        configure = Configure(parser)
        controller = self.create_controller(configure)

        # Serialize to StringIO
        output = StringIO()
        controller.serialize(output)

        # Read back the serialized config
        output.seek(0)
        result_cfg = ConfigParser()
        result_cfg.read_file(output)

        # Verify buffer unit and size
        self.assertEqual(result_cfg.get('ACQUISITION', 'bufferunit'), 'Objects')
        self.assertEqual(result_cfg.get('ACQUISITION', 'buffer'), '50')

