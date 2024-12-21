"""
Core OpenBCI object for handling connections and samples from the board.
EXAMPLE USE:
def handle_sample(sample):
  print(sample.channels)
board = OpenBCIBoard()
board.print_register_settings()
board.start(handle_sample)
@NOTE: If daisy modules is enabled, the callback will occur every two samples, hence "packet_id" will only contain even numbers. As a side effect, the sampling rate will be divided by 2.
@FIXME: at the moment we can just force daisy mode, do not check that the module is detected.

"""
import serial
import struct
import numpy as np
import time
import timeit
import atexit
import logging
import threading
import sys
#import pdb
import glob

# @NOTE: This is not ENFORCED in the board !!! The board uses whatever sampling frequency it has been previously configured.
SAMPLE_RATE = 250.0  # Hz
START_BYTE = 0xA0  # start of data packet
END_BYTE = 0xC0  # end of data packet
ADS1299_Vref = 4.5  # reference voltage for ADC in ADS1299.  set by its hardware
ADS1299_gain = 24.0  # assumed gain setting for ADS1299.  set by its Arduino code
scale_fac_uVolts_per_count = ADS1299_Vref / float((pow(2, 23) - 1)) / ADS1299_gain * 1000000.
scale_fac_accel_G_per_count = 0.002 / (pow(2, 4))  # assume set to +/4G, so 2 mG
'''
#Commands for in SDK http://docs.openbci.com/software/01-Open BCI_SDK:
command_stop = "s";
command_startText = "x";
command_startBinary = "b";
command_startBinary_wAux = "n";
command_startBinary_4chan = "v";
command_activateFilters = "F";
command_deactivateFilters = "g";
command_deactivate_channel = {"1", "2", "3", "4", "5", "6", "7", "8"};
command_activate_channel = {"q", "w", "e", "r", "t", "y", "u", "i"};
command_activate_leadoffP_channel = {"!", "@", "#", "$", "%", "^", "&", "*"};  //shift + 1-8
command_deactivate_leadoffP_channel = {"Q", "W", "E", "R", "T", "Y", "U", "I"};   //letters (plus shift) right below 1-8
command_activate_leadoffN_channel = {"A", "S", "D", "F", "G", "H", "J", "K"}; //letters (plus shift) below the letters below 1-8
command_deactivate_leadoffN_channel = {"Z", "X", "C", "V", "B", "N", "M", "<"};   //letters (plus shift) below the letters below the letters below 1-8
command_biasAuto = "`";
command_biasFixed = "~";
'''


class OpenBCIBoard(object):
    """
    Handle a connection to an OpenBCI board.
    Args:
      port: The port to connect to.
      baud: The baud of the serial connection.
      daisy: Enable or disable daisy module and 16 chans readings
    """

    def __init__(self, port=None, baud=115200, filter_data=True,
                 scaled_output=True, daisy=False, log=True, timeout=10,sendDeviceStopAfterSerialStop=True):
        # @FIXME: Watch out --> changed the default timeout to 10 seconds.
        self.log = log  # print_incoming_text needs log
        self.streaming = False
        self.baudrate = baud
        self.baudrate_default = 115200
        self.timeout = timeout
        self.sendDeviceStopAfterSerialStop = sendDeviceStopAfterSerialStop
        self.log_packet_count = 0
        self.initSendBoardByteString = b''
        self.callback = None
        self.radio_channel_number = 0
        self.checktimer = None
        self.audio = False

        if not port:
            port = self.find_port()
        self.port = port
        print("Connecting to V3 at port %s" % (port))

        self.baudrate_serial_code = b'\xF0\x05'.decode("cp1250")
        if baud == 115200:
            self.baudrate_serial_code = b'\xF0\x05'.decode("cp1250")
        elif baud == 230400:
            self.baudrate_serial_code = b'\xF0\x06'.decode("cp1250")
        elif baud == 921600:
            self.baudrate_serial_code = b'\xF0\x0A'.decode("cp1250")
        else:
            print("baudrate_serial of " + str(self.baudrate_serial) + " not handled")
            # sys.exit(0)

        time.sleep(2)
        self.ser = serial.Serial(port=port, baudrate=self.baudrate_default, timeout=timeout)
        print("Serial with baud rate of " + str(self.baudrate_default) + " established to port " + port)

        # Initialize 32-bit board, doesn't affect 8bit board
        self.ser.write(b'v')
        time.sleep(1)

        temp_line_read = ""
        self.openBCIFirmwareVersion = "v1"
        while temp_line_read != "No Message":
            temp_line_read = self.print_incoming_text()
            if "Rainbow V1" in temp_line_read:
                self.openBCIFirmwareVersion = "v3"              # The Rainbow board V1 is equivalent to OpenBCI v3
                self.audio = True
                print("Rainbow Board detected!")
            if "Firmware: v2." in temp_line_read:
                self.openBCIFirmwareVersion = "v2"
            if "Firmware: v3" in temp_line_read:
                self.openBCIFirmwareVersion = "v3"
            if "Firmware: v4" in temp_line_read:
                self.openBCIFirmwareVersion = "v4"
        
        print("OpenBCI Firmware " + self.openBCIFirmwareVersion + " detected")

        #print('Setting OpenBCI Radio Channel to: 7')
        getchannel = b'\xF0\x01\x07'.decode("cp1250")
        #self.ser.write(getchannel.encode("utf-8"))

        self.get_radio_channel_number()


        if  self.openBCIFirmwareVersion != "v1":
            self.ser.write(self.baudrate_serial_code.encode("utf-8"))
            self.ser.baudrate = self.baudrate

            print("Serial reconfigured to baud rate of " + str(baud) + " on port " + port)

            # @FIXME: This is insane
            s = serial.Serial(port=port, baudrate=self.baudrate_default, timeout=self.timeout)
            print("Connected, asking id")
            time.sleep(2)
            s.write(b'v')
            openbci_serial_connected = self.openbci_id(s)
            s.close()

            print(self.ser)

        else:
            print("Serial baud rate of " + str(baud) + " on port " + port + " NOT supported by " + self.openBCIFirmwareVersion + " switching to default baud rate of " + str(baud) )

        # wait for device to be ready

        self.streaming = False
        self.filtering_data = filter_data
        self.scaling_output = scaled_output
        self.eeg_channels_per_sample = 8  # number of EEG channels per sample *from the board*
        self.aux_channels_per_sample = 3  # number of AUX channels per sample *from the board*
        self.read_state = 0
        self.daisy = daisy
        self.last_odd_sample = OpenBCISample(-1, [], [])  # used for daisy
        self.attempt_reconnect = False
        self.last_reconnect = 0
        self.reconnect_freq = 5
        self.packets_dropped = 0


        


        # Disconnects from board when terminated
        atexit.register(self.disconnect)

    def getSampleRate(self):
        if self.daisy:
            return SAMPLE_RATE / 2
        else:
            return SAMPLE_RATE

    def getNbEEGChannels(self):
        if self.daisy:
            return self.eeg_channels_per_sample * 2
        else:
            return self.eeg_channels_per_sample

    def getNbAUXChannels(self):
        return self.aux_channels_per_sample
    

    def start_streaming(self, callback, lapse=-1):
        """
        Start handling streaming data from the board. Call a provided callback
        for every single sample that is processed (every two samples with daisy module).
        Args:
          callback: A callback function -- or a list of functions -- that will receive a single argument of the
              OpenBCISample object captured.
        """
        if not self.streaming:
            self.ser.write(b'b')
            self.streaming = True

        start_time = timeit.default_timer()

        # Enclose callback funtion in a list if it comes alone
        if not isinstance(callback, list):
            callback = [callback]

        self.callback = callback


        # Initialize check connection
        self.check_connection()

        self.stream(lapse,start_time)

    def stream(self,lapse, start_time):
        while self.streaming:

            # read current sample
            sample = self._read_serial_binary()
            # if a daisy module is attached, wait to concatenate two samples (main board + daisy) before passing it to callback
            if self.daisy:
                # odd sample: daisy sample, save for later
                if ~sample.id % 2:
                    self.last_odd_sample = sample
                # even sample: concatenate and send if last sample was the fist part, otherwise drop the packet
                elif sample.id - 1 == self.last_odd_sample.id:
                    # the aux data will be the average between the two samples, as the channel samples themselves have been averaged by the board
                    avg_aux_data = list((np.array(sample.aux_data) + np.array(self.last_odd_sample.aux_data)) / 2)

                    whole_sample = OpenBCISample(sample.id, sample.channel_data + self.last_odd_sample.channel_data,
                                                 avg_aux_data)
                    for call in self.callback:
                        call(whole_sample)
            else:
                for call in self.callback:
                    call(sample)
            if (lapse > 0 and timeit.default_timer() - start_time > lapse):
                self.stop()
            if self.log:
                self.log_packet_count = self.log_packet_count + 1

    def restream(self,lapse=-1):
        if not self.streaming:
            self.ser.write(b'b')
            self.streaming = True

        start_time = timeit.default_timer()
        self.stream(lapse,start_time)



    """
      PARSER:
      Parses incoming data packet into OpenBCISample.
      Incoming Packet Structure:
      Start Byte(1)|Sample ID(1)|Channel Data(24)|Aux Data(6)|End Byte(1)
      0xA0|0-255|8, 3-byte signed ints|3 2-byte signed ints|0xC0
      33 bytes
    """

    def _read_serial_binary(self, max_bytes_to_skip=5000):
        def read(n):
            bb = self.ser.read(n)
            if not bb:
                self.warn('Device appears to be stalled. Quitting...')
                sys.exit()
                raise Exception('Device Stalled')
                sys.exit(0)
                return '\xFF'
            else:
                return bb

        for rep in range(max_bytes_to_skip):

            # ---------Start Byte & ID---------
            if self.read_state == 0:

                b = read(1)

                if struct.unpack('B', b)[0] == START_BYTE:
                    if (rep != 0):
                        self.warn('Skipped %d bytes before start found' % (rep))
                        rep = 0;
                    packet_id = struct.unpack('B', read(1))[0]  # packet id goes from 0-255
                    log_bytes_in = str(packet_id);

                    self.read_state = 1

            # ---------Channel Data---------
            elif self.read_state == 1:
                channel_data = []
                for c in range(self.eeg_channels_per_sample):

                    # 3 byte ints
                    literal_read = read(3)

                    unpacked = struct.unpack('3B', literal_read)
                    log_bytes_in = log_bytes_in + '|' + str(literal_read);

                    # 3byte int in 2s compliment
                    if (unpacked[0] >= 127):
                        pre_fix = bytes(bytearray.fromhex('FF'))
                    else:
                        pre_fix = bytes(bytearray.fromhex('00'))

                    literal_read = pre_fix + literal_read;

                    # unpack little endian(>) signed integer(i) (makes unpacking platform independent)
                    myInt = struct.unpack('>i', literal_read)[0]

                    if self.scaling_output:
                        channel_data.append(myInt * scale_fac_uVolts_per_count)
                    else:
                        channel_data.append(myInt)

                self.read_state = 2;

            # ---------Accelerometer Data---------
            elif self.read_state == 2:
                aux_data = []
                for a in range(self.aux_channels_per_sample):

                    # short = h
                    acc = struct.unpack('>h', read(2))[0]
                    log_bytes_in = log_bytes_in + '|' + str(acc);

                    if self.scaling_output:
                        aux_data.append(acc * scale_fac_accel_G_per_count)
                    else:
                        aux_data.append(acc)

                self.read_state = 3;
            # ---------End Byte---------
            elif self.read_state == 3:
                val = struct.unpack('B', read(1))[0]
                log_bytes_in = log_bytes_in + '|' + str(val);
                self.read_state = 0  # read next packet
                if (val == END_BYTE):
                    sample = OpenBCISample(packet_id, channel_data, aux_data)
                    self.packets_dropped = 0
                    sample.marker = ''                              # @NOTE Added for LSL compatibility
                    sample.markertimestamp = timeit.default_timer() # @NOTE Added for LSL compatibility
                    sample.filtered = 0
                    return sample
                else:
                    self.warn("ID:<%d> <Unexpected END_BYTE found <%s> instead of <%s>"
                              % (packet_id, val, END_BYTE))
                    logging.debug(log_bytes_in);
                    self.packets_dropped = self.packets_dropped + 1



    """
    Flush from the board whatever data is being sent
    @FIXME: Check how many times is reading data and call stop after a counter is reached.
    """
    def flush(self):
        self.ser.timeout = 1
        self.ser.write(b's')
        time.sleep(1)
        fencecounter = 0
        if self.ser.inWaiting():
            timeouted = False
            while (not timeouted):
                c = self.ser.read()
                if c == b'' or len(c)==0:
                    timeouted = True
                #print (c)
                fencecounter += 1
                if fencecounter > 1000:
                    self.ser.write(b's')
                    fencecounter = 0
        self.ser.timeout = self.timeout


    """
    Clean Up (atexit)
    """
    def stop(self,sendDeviceStopAfterSerialStop=False):
        print("Stopping streaming...\nWait for buffer to flush...")
        self.streaming = False
        if self.sendDeviceStopAfterSerialStop or sendDeviceStopAfterSerialStop:
            self.ser.write(b's')
            if self.log:
                logging.warning('sent <s>: stopped streaming')

    def disconnect(self):
        if (self.streaming == True):
            self.stop(True)
        if (self.ser.isOpen()):
            print("Closing Serial...")
            self.ser.close()
            logging.warning('serial closed')

    """
        SETTINGS AND HELPERS
    """

    def warn(self, text):
        if self.log:
            # log how many packets where sent succesfully in between warnings
            if self.log_packet_count:
                logging.info('Data packets received:' + str(self.log_packet_count))
                self.log_packet_count = 0;
            logging.warning(text)
        print("Warning: %s" % text)

    def print_incoming_text(self):
        """
        When starting the connection, print all the debug data until
        we get to a line with the end sequence '$$$'.
        """
        if self.openBCIFirmwareVersion == 'v1':
            self.ser.timeout = 1.0 #wait for 1 s for each character in read
        line = ''
        # Wait for device to send data
        if self.openBCIFirmwareVersion == 'v1':
            time.sleep(2)
        else:
            time.sleep(0.2)

        ctr = 0
        if self.ser.inWaiting():
            #while self.ser.inWaiting():
            # Look for end sequence $$$
            c = ''
            timeouted = False
            while ('$$$' not in line) and not timeouted:
                c = self.ser.read()
                if c == '' or len(c) == 0:
                    #timeouted = True
                    ctr = ctr + 1
                    if (ctr >= 10): raise Exception("Connection issues: is the board really turned on?")
                line += c.decode('utf-8')
            print(line)
        else:
            self.warn("No Message")
            line = "No Message"

        if self.openBCIFirmwareVersion == 'v1':
            self.ser.timeout = self.timeout #reset timeout to default
        return line




    def openbci_id(self, serial):
        """
        When automatically detecting port, parse the serial return for the "OpenBCI" ID.
        """
        line = ''
        data = b''
        # # Wait for device to send data
        # if self.openBCIFirmwareVersion == 'v1':
        #     serial.timeout = 1.0 #wait for 1 s for each character in read

        time.sleep(2)

        res = False

        if serial.inWaiting():
            line = ''
            c = ''
            # Look for end sequence $$$
            timeouted = False
            while ('$$$' not in line) and not timeouted:
                c = serial.read()
                if c == '':
                    timeouted = True
                print(c)
                line += c.decode("utf-8")
                
            if ("OpenBCI" in line):
                res = True
            if (line.find("Rainbow")>=0):
                print("Detected Rainbow Board")
                res = True
         

        # OpenBCI V3 8-16 channel
        # On Board ADS1299 Device ID: 0x3E
        # LIS3DH Device ID: 0x33
        # Firmware: v3.1.2
        # $$$

        # if self.openBCIFirmwareVersion == 'v1':
        #     serial.timeout = self.timeout  # reset timeout to default
        print (line)
        return res

    def print_register_settings(self):
        self.ser.write(b'?')
        time.sleep(0.5)
        self.print_incoming_text(); 
    

    def impeadance_measurment(self, channel, p, n):
        command = 'z' + str(channel) + str(p) + str(n) + 'Z'
        #self.ser.write(b'z101Z')
        self.ser.write(bytes(command,'cp1250'))
        time.sleep(0.5)
        self.print_incoming_text(); 

    def set_radio_channel_number(self):
        data = [0xF0,0x01,0x02]    
        self.ser.write(bytes(data))
        time.sleep(1.5)   
        self.print_incoming_text(); 
    

    # @NOTE: add radio_channel as a parameter in set_radio_channel_number function 
    def config_radio_channel_number(self, radio_channel):
        self.ser.write(bytes([0xF0, 0x01, radio_channel]))
        time.sleep(1.5)   
        self.print_incoming_text(); 

    # @NOTE: added this new function to change the host's radio channel 
    def set_radio_channel_override(self, radio_channel):
        self.ser.write(bytes([0xF0, 0x02, radio_channel]))
        time.sleep(0.1)   

    # @NOTE: added this new function to scan through channels until a success message has been found    
    def scan_channels(self):
        success = False 
        for channel_number in range(1, 26):

            # Host channel override
            self.set_radio_channel_override(channel_number)

            # Discards override data
            while self.ser.in_waiting > 0:
                self.ser.read()

            # Channel Status
            self.ser.write(bytes([0xF0, 0x07]))
            time.sleep(0.1)

            mes = []
            while self.ser.in_waiting > 0:
                mes.append(chr(self.ser.read(1)[0]))
            received_string = "".join(mes)

            if received_string == "Success: System is Up$$$":
                print(f"Successfully connected to channel: {channel_number}")
                success = True
                return channel_number 

        if not success:
            print("Could not connect, is your board powered on?")
            return None
            
    def get_radio_channel_number(self):
        data = [0xF0,0x00]
        self.ser.write(bytes(data))
        time.sleep(1.5)

        line = ''
        data = b''
        channelnumber = 0

        res = False

        print('Reading Radio Channel.')

        try:
            line = ''
            c = ''
            # Look for end sequence $$$
            timeouted = False
            while ('$$$' not in line) and not timeouted:
                c = self.ser.read()
                if c == '':
                    timeouted = True
                print(c)
                line += c.decode("utf-8")
            if "Channel" in line:
                res = True
            channelnumber = int(line.split(':')[2][:-4])
        except:
            self.warn('Cannot identify Radio Channel Number.')
            
        print (line)

        self.radio_channel_number = channelnumber

        return channelnumber

    # DEBBUGING: Prints individual incoming bytes
    def print_bytes_in(self):
        if not self.streaming:
            self.ser.write(b'b')
            self.streaming = True
        while self.streaming:
            print(struct.unpack('B', self.ser.read())[0]);

            '''Incoming Packet Structure:
          Start Byte(1)|Sample ID(1)|Channel Data(24)|Aux Data(6)|End Byte(1)
          0xA0|0-255|8, 3-byte signed ints|3 2-byte signed ints|0xC0'''

    def print_packets_in(self):
        while self.streaming:
            b = struct.unpack('B', self.ser.read())[0];

            if b == START_BYTE:
                self.attempt_reconnect = False
                if skipped_str:
                    logging.debug('SKIPPED\n' + skipped_str + '\nSKIPPED')
                    skipped_str = ''

                packet_str = "%03d" % (b) + '|';
                b = struct.unpack('B', self.ser.read())[0];
                packet_str = packet_str + "%03d" % (b) + '|';

                # data channels
                for i in range(24 - 1):
                    b = struct.unpack('B', self.ser.read())[0];
                    packet_str = packet_str + '.' + "%03d" % (b);

                b = struct.unpack('B', self.ser.read())[0];
                packet_str = packet_str + '.' + "%03d" % (b) + '|';

                # aux channels
                for i in range(6 - 1):
                    b = struct.unpack('B', self.ser.read())[0];
                    packet_str = packet_str + '.' + "%03d" % (b);

                b = struct.unpack('B', self.ser.read())[0];
                packet_str = packet_str + '.' + "%03d" % (b) + '|';

                # end byte
                b = struct.unpack('B', self.ser.read())[0];

                # Valid Packet
                if b == END_BYTE:
                    packet_str = packet_str + '.' + "%03d" % (b) + '|VAL';
                    print(packet_str)
                    # logging.debug(packet_str)

                # Invalid Packet
                else:
                    packet_str = packet_str + '.' + "%03d" % (b) + '|INV';
                    # Reset
                    self.attempt_reconnect = True


            else:
                print(b)
                if b == END_BYTE:
                    skipped_str = skipped_str + '|END|'
                else:
                    skipped_str = skipped_str + "%03d" % (b) + '.'

            if self.attempt_reconnect and (timeit.default_timer() - self.last_reconnect) > self.reconnect_freq:
                self.last_reconnect = timeit.default_timer()
                self.warn('Reconnecting')
                self.reconnect()

    
    def check_connection(self, interval=2, max_packets_to_skip=10):
        # check number of dropped packages and establish connection problem if too large
        if self.packets_dropped > max_packets_to_skip:
            # if error, attempt to reconect
            self.reconnect()
        # check again again in 2 seconds
        self.checktimer = threading.Timer(interval, self.check_connection)
        self.checktimer.start()

    def reconnect(self):
        # This is a soft disconnect, disconnects and reconnects the streaming.
        self.packets_dropped = 0
        self.warn('Reconnecting')
        self.stop(sendDeviceStopAfterSerialStop=True)  # try if you can to send stop
        time.sleep(0.5)
        self.ser.baudrate = self.baudrate_default
        self.ser.write(b'v')
        time.sleep(0.5)
        self.ser.write(self.baudrate_serial_code.encode("utf-8"))
        self.ser.baudrate = self.baudrate
        time.sleep(0.5)
        self.ser.write(b'v')
        time.sleep(0.5)
        self.ser.write(self.initSendBoardByteString)
        time.sleep(0.5)

        self.get_radio_channel_number()




 #       hasSerialMessage = True
 #       while hasSerialMessage:
 #           hasSerialMessage = self.print_incoming_text()
        self.restream()
        # self.attempt_reconnect = False

    # Adds a filter at 60hz to cancel out ambient electrical noise
    def enable_filters(self):
        self.ser.write(b'f')
        self.filtering_data = True;

    def disable_filters(self):
        self.ser.write(b'g')
        self.filtering_data = False;

    def test_signal(self, signal):
        if signal == 0:
            self.ser.write(b'0')
            self.warn("Connecting all pins to ground")
        elif signal == 1:
            self.ser.write(b'p')
            self.warn("Connecting all pins to Vcc")
        elif signal == 2:
            self.ser.write(b'-')
            self.warn("Connecting pins to low frequency 1x amp signal")
        elif signal == 3:
            self.ser.write(b'=')
            self.warn("Connecting pins to high frequency 1x amp signal")
        elif signal == 4:
            self.ser.write(b'[')
            self.warn("Connecting pins to low frequency 2x amp signal")
        elif signal == 5:
            self.ser.write(b']')
            self.warn("Connecting pins to high frequency 2x amp signal")
        else:
            self.warn("%s is not a known test signal. Valid signals go from 0-5" % (signal))

    def set_channel(self, channel, toggle_position):
        # Commands to set toggle to on position
        if toggle_position == 1:
            if channel == 1:
                self.ser.write(b'!')
            if channel == 2:
                self.ser.write(b'@')
            if channel == 3:
                self.ser.write(b'#')
            if channel == 4:
                self.ser.write(b'$')
            if channel == 5:
                self.ser.write(b'%')
            if channel == 6:
                self.ser.write(b'^')
            if channel == 7:
                self.ser.write(b'&')
            if channel == 8:
                self.ser.write(b'*')
            if channel == 9 and self.daisy:
                self.ser.write(b'Q')
            if channel == 10 and self.daisy:
                self.ser.write(b'W')
            if channel == 11 and self.daisy:
                self.ser.write(b'E')
            if channel == 12 and self.daisy:
                self.ser.write(b'R')
            if channel == 13 and self.daisy:
                self.ser.write(b'T')
            if channel == 14 and self.daisy:
                self.ser.write(b'Y')
            if channel == 15 and self.daisy:
                self.ser.write(b'U')
            if channel == 16 and self.daisy:
                self.ser.write(b'I')
        # Commands to set toggle to off position
        elif toggle_position == 0:
            if channel == 1:
                self.ser.write(b'1')
            if channel == 2:
                self.ser.write(b'2')
            if channel == 3:
                self.ser.write(b'3')
            if channel == 4:
                self.ser.write(b'4')
            if channel == 5:
                self.ser.write(b'5')
            if channel == 6:
                self.ser.write(b'6')
            if channel == 7:
                self.ser.write(b'7')
            if channel == 8:
                self.ser.write(b'8')
            if channel == 9 and self.daisy:
                self.ser.write(b'q')
            if channel == 10 and self.daisy:
                self.ser.write(b'w')
            if channel == 11 and self.daisy:
                self.ser.write(b'e')
            if channel == 12 and self.daisy:
                self.ser.write(b'r')
            if channel == 13 and self.daisy:
                self.ser.write(b't')
            if channel == 14 and self.daisy:
                self.ser.write(b'y')
            if channel == 15 and self.daisy:
                self.ser.write(b'u')
            if channel == 16 and self.daisy:
                self.ser.write(b'i')

    def find_port(self):
        # Finds the serial port names
        if sys.platform.startswith('win'):
            print("detected windows system")
            ports = ['COM%s' % (i + 1) for i in range(256)]
        elif sys.platform.startswith('linux') or sys.platform.startswith('cygwin'):
            print("detected unix system")
            ports = glob.glob('/dev/ttyUSB*')
        elif sys.platform.startswith('darwin'):
            print("detected darwin system")
            ports = glob.glob('/dev/tty.usbserial*')
        else:
            print('Error finding ports on your operating system')
            raise EnvironmentError('Error finding ports on your operating system')
        openbci_port = ''
        print("Available ports")
        print(ports)
        for port in ports:
            try:
                s = serial.Serial(port=port, baudrate=self.baudrate_default, timeout=self.timeout)
                print("Connected, asking id")
                time.sleep(2)
                s.write(b'v')
                openbci_serial_connected = self.openbci_id(s)
                s.close()
                if openbci_serial_connected:
                    openbci_port = port;
            except (OSError,serial.SerialException) as o:
                print("Exception while opening serial port:" % o)
                raise OSError("Cannot find OpenBCI port")
        if openbci_port == '':
            print('Cannot find identify OpenBCI board on port.')
            raise OSError('Cannot find identify OpenBCI board on port.')
        else:
            return openbci_port


class OpenBCISample(object):
    """Object encapulsating a single sample from the OpenBCI board."""

    def __init__(self, packet_id, channel_data, aux_data, time=None):
        self.time = time
        if time is None:
            self.time = timeit.default_timer()
        self.id = packet_id
        self.channel_data = channel_data
        self.aux_data = aux_data

    def __copy__(self):
        return type(self)(self.id, self.channel_data, self.aux_data, self.time)

    def __deepcopy__(self, memo):
        id_self = id(self)
        acopy = memo.get(id_self)
        if acopy is None:
            acopy = type(self)(
                deepcopy(self.id, memo),
                deepcopy(self.channel_data, memo),
                deepcopy(self.aux_data, memo),
                deepcopy(self.time, memo))
            memo[id_self] = acopy
        return acopy
