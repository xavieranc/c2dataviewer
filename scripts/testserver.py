"""
C2 DATA VIEWER is distributed subject to a Software License Agreement found
in the file LICENSE that is included with this distribution.
SPDX-License-Identifier: EPICS
"""

import pvaccess as pva
import argparse
import multiprocessing as mp
import random
import time
import enum
import numpy as np
from datetime import datetime as dt

class WaveformType(enum.Enum):
    RANDOM = 'random'
    LINEAR = 'linear'

    def __str__(self):
        return self.value

# Image color modes (from c2dataviewer.view.image_definitions)
COLOR_MODE_MONO = 0  # [NX, NY]
COLOR_MODE_RGB1 = 2  # [3, NX, NY]
COLOR_MODE_RGB2 = 3  # [NX, 3, NY]
COLOR_MODE_RGB3 = 4  # [NX, NY, 3]

class LinearGenerator:
    def __init__(self, offset, size):
        self.offset = offset
        self.x = -1
        self.size = size
    def calc(self):
        self.x += 1                
        self.x = self.x % self.size
        return self.x + self.offset

class RandomGenerator:
    def __init__(self, min=0, max=100):
        self.min = min
        self.max = max

    def calc(self):
        return random.uniform(self.min, self.max)

def get_time_stamp(time_stamp=None):
    """
    Transform seconds to PVA timestamp (or generate for the current time if time_stamp=None)

    :param time_stamp: (int) Timestamp in nano seconds or None to take current time.
    :return: (PvTimeStamp) Timestamp value.
    """
    NANOSECONDS_IN_SECOND = 1000000000
    if time_stamp is None:
        time_stamp = np.datetime64(dt.now(), 'ns')
    else:
        time_stamp = np.datetime64(time_stamp, 'ns')
    t = (time_stamp-np.datetime64(0,'ns'))/np.timedelta64(1, 's')
    s = int(t)
    ns = int((t - s)*NANOSECONDS_IN_SECOND)
    return pva.PvTimeStamp(s,ns,0)

def create_image(id, image=None, data_type='ubyteValue', nx=None, ny=None, nz=None, color_mode=None, time_stamp=None):
    """
    Generate image as NtNdArray.

    :param id: (int) Array index.
    :param image: (np.array) Image data. If None, random data is generated.
    :param data_type: (string) Datatype of the image. Default value is 'ubyteValue'.
    :param nx: (int) Dimension of the image in X direction.
    :param ny: (int) Dimension of the image in Y direction.
    :param nz: (int) Dimension of the image in Z direction. Should be None (default) or 3.
    :param color_mode: (int) Color mode the image. Possible values are 0, 2, 3, 4.
    :param time_stamp: (int) EPICS timestamp in seconds. Can be None in which case the current time is used.
    """
    # Generate timestamp and the image
    time_stamp = get_time_stamp(time_stamp)
    if image is None:
        image = np.random.randint(0, 256, size=nx*ny*(nz if nz is not None else 1), dtype=np.uint8)

    # Build the NtNdArray
    nda = pva.NtNdArray()
    nda['uniqueId'] = id
    dims = [pva.PvDimension(nx, 0, nx, 1, False), pva.PvDimension(ny, 0, ny, 1, False)]
    if nz is not None:
        if color_mode == COLOR_MODE_RGB1:
            dims.insert(0, pva.PvDimension(nz, 0, nz, 1, False))
        elif color_mode == COLOR_MODE_RGB2:
            dims.insert(1, pva.PvDimension(nz, 0, nz, 1, False))
        elif color_mode == COLOR_MODE_RGB3:
            dims.append(pva.PvDimension(nz, 0, nz, 1, False))
    nda['dimension'] = dims
    nda['descriptor'] = 'Test Server Simulated Image'
    nda['compressedSize'] = nx*ny*(nz if nz is not None else 1)
    nda['uncompressedSize'] = nx*ny*(nz if nz is not None else 1)
    nda['timeStamp'] = time_stamp
    nda['dataTimeStamp'] = time_stamp

    # Set codec to empty string for uncompressed data
    nda['codec'] = {'name': ''}

    # Set color mode attribute (always set it, default to MONO if not specified)
    if color_mode is None:
        color_mode = COLOR_MODE_MONO
    attrs = [pva.NtAttribute('ColorMode', pva.PvInt(color_mode))]
    nda['attribute'] = attrs

    # Set image value
    nda['value'] = {data_type : image}

    return nda

class Trigger:
    def __init__(self, args):
        self.pvname = args.triggerpv
        self.schema = {'value': pva.FLOAT,
                       'timeStamp' : {
                           'secondsPastEpoch' : pva.UINT,
                           'nanoseconds' : pva.UINT
                       }
                       }
        self.server = pva.PvaServer(self.pvname, pva.PvObject(self.schema))
        self.delay = args.trigger_interval
        self.gen = LinearGenerator(-10, 20)

    def fire(self, trigger_time):
        value = self.gen.calc()
        ts = int(trigger_time)
        tns = (trigger_time - ts)*1e9
        pv = pva.PvObject(self.schema, {'value':value,
                                        'timeStamp' :
                                        { 'secondsPastEpoch' : ts, 'nanoseconds' : int(tns) } })
        self.server.update(pv)

    
def run_striptool_pvserver(arg):
    pvid = arg[0]
    args = arg[1]    
    pvname = args.pvprefix + str(pvid)
    maxdelay = 1 / args.minrate
    make_struct = args.num_structs and pvid < args.num_structs
    if make_struct:
        print('creating %s as a struct PV' % pvname)
        schema = { 'obj1' : {'x': pva.FLOAT, 'y': pva.FLOAT}, 'z': pva.FLOAT}
    else:
        schema = {'value':pva.FLOAT}
    server = pva.PvaServer(pvname, pva.PvObject(schema))
    delay = random.uniform(0.1, maxdelay)
    print('starting %s at %f Hz' % (pvname, 1/delay))
    wftype = arg[1].wftype
    if wftype == WaveformType.LINEAR:
        offset = random.uniform(0, 100)
        size = random.uniform(100, 5000);
        gen = LinearGenerator(offset, size)
    else:
        gen = RandomGenerator()
        
    while(True):
        value = gen.calc()

        if make_struct:
            pvval = {'obj1': {'x': value, 'y': -value }, 'z': value + 10 }
        else:
            pvval = {'value': value}
            
        pv = pva.PvObject(schema, pvval)
        server.update(pv)
        time.sleep(delay)

    
def run_striptool(args):
    with mp.Pool(args.numpvs) as p:
        arglist = [ (c, args) for c in range(args.numpvs) ]
        p.map(run_striptool_pvserver, arglist)

def trigger_process(args):
    pvname = args.triggerpv
    trigger = Trigger(args)
    print('trigger %s started' % (pvname))
    while(True):
        trigger.fire(time.time())
        time.sleep(args.trigger_interval)
    
def run_scope(args):
    if args.triggerpv:
        p = mp.Process(target=trigger_process, args=(args,))
        p.start()

    pvname = args.pvname
    schema = { 'obj1' : {'x': [pva.FLOAT], 'y': [pva.FLOAT]}, 'obj2' : {'x': [pva.FLOAT], 'y': [pva.FLOAT]}, 'time': [pva.DOUBLE], 'objectTime': pva.DOUBLE, 'names': [pva.STRING]}
    server = pva.PvaServer(pvname, pva.PvObject(schema))
    print('starting', pvname)
    delay = 1/args.pvrate
    nsamples = args.wflen
    sample_time_interval = delay / nsamples

    # Set up waveform generators
    wftype = args.wftype
    if wftype == WaveformType.LINEAR:
        gen_x = LinearGenerator(0, nsamples)
        gen_y = LinearGenerator(10, nsamples)
    else:
        gen_x = RandomGenerator()
        gen_y = RandomGenerator()

    while(True):
        objectTime = float(time.time())
        time.sleep(delay)
        times = [ i*sample_time_interval + objectTime for i in range(0, nsamples) ]

        x = [ gen_x.calc() for _ in range(nsamples) ]
        y = [ gen_y.calc() for _ in range(nsamples) ]

        names = [ 'val'+str(i) for i in range(0, nsamples) ]
        pv = pva.PvObject(schema, {'obj1':{'x':x, 'y':y}, 'obj2': {'x':x, 'y':y},
                                   'objectTime': objectTime, 'time' : times, 'names': names})
        server.update(pv)

def run_image(args):
    pvname = args.pvname

    # Create initial NtNdArray to establish the PV structure
    initial_nda = create_image(
        0,
        nx=args.width,
        ny=args.height,
        nz=3 if args.color else None,
        color_mode=args.color_mode if args.color else COLOR_MODE_MONO,
        data_type=args.data_type
    )

    server = pva.PvaServer(pvname, initial_nda)
    print(f'starting image server: {pvname}')
    print(f'  Image size: {args.width}x{args.height}')
    print(f'  Color mode: {"RGB" if args.color else "MONO"} ({args.color_mode if args.color else COLOR_MODE_MONO})')
    print(f'  Data type: {args.data_type}')
    print(f'  Update rate: {args.rate} Hz')

    delay = 1.0 / args.rate
    frame_id = 0

    while(True):
        time.sleep(delay)

        # Create new image data
        nda = create_image(
            frame_id,
            nx=args.width,
            ny=args.height,
            nz=3 if args.color else None,
            color_mode=args.color_mode if args.color else COLOR_MODE_MONO,
            data_type=args.data_type
        )

        server.update(nda)
        frame_id += 1
    
if __name__ == "__main__":
    parser = argparse.ArgumentParser('Test server')
    subparsers = parser.add_subparsers(dest='command')
    striptool = subparsers.add_parser('striptool', help='Test server for striptool app')
    striptool.add_argument('pvprefix',  help='prefix to generated pv names')
    striptool.add_argument('numpvs',  help='number of pvs to generate', type=int)
    striptool.add_argument('--min-rate', dest='minrate', default=0.5, type=int)
    striptool.add_argument('--waveform-type', dest='wftype', default=WaveformType.RANDOM, type=WaveformType, choices=list(WaveformType))
    striptool.add_argument('--add-struct', dest='num_structs', type=int, help='If set, number of pvs to be struct instead of scalar')
    scope = subparsers.add_parser('scope', help='Test server for scope app')
    scope.add_argument('pvname', help='structure pv to host')
    scope.add_argument('--trigger-pv', help='Adds a trigger PV.  PV values will range between -10 and 10', dest='triggerpv')
    scope.add_argument('--trigger-interval', help='Fires at given interval in seconds', dest='trigger_interval', default=1, type=float)
    scope.add_argument('--pv-rate', help='PV update rate', dest='pvrate', default=2, type=float)
    scope.add_argument('--waveform-length', help='Waveform length', dest='wflen', default=100, type=int)
    scope.add_argument('--waveform-type', dest='wftype', default=WaveformType.RANDOM, type=WaveformType, choices=list(WaveformType))
    image = subparsers.add_parser('image', help='Test server for image app')
    image.add_argument('pvname', help='PV name for image channel')
    image.add_argument('--width', help='Image width in pixels', default=512, type=int)
    image.add_argument('--height', help='Image height in pixels', default=512, type=int)
    image.add_argument('--rate', help='Image update rate in Hz', default=2.0, type=float)
    image.add_argument('--color', help='Generate RGB color images', action='store_true')
    image.add_argument('--color-mode', help='Color mode for RGB images: 2=RGB1, 3=RGB2, 4=RGB3', dest='color_mode', default=COLOR_MODE_RGB3, type=int, choices=[COLOR_MODE_RGB1, COLOR_MODE_RGB2, COLOR_MODE_RGB3])
    image.add_argument('--data-type', help='Data type for image values', dest='data_type', default='ubyteValue', choices=['ubyteValue', 'byteValue', 'ushortValue', 'shortValue', 'uintValue', 'intValue', 'ulongValue', 'longValue', 'floatValue', 'doubleValue'])
    args = parser.parse_args()
    if args.command == 'striptool':
        run_striptool(args)
    elif args.command == 'scope':
        run_scope(args)
    elif args.command == 'image':
        run_image(args)
