# import sys
# import time
# sys.path.append('/Users/pedrogonzaleznunez/Documents/GitHub/EEG_Signals')
# from python_scientific.signalfeatures import butter_bandpass
# import numpy as np
# import matplotlib.pyplot as plt
# from scipy.fft import rfft, rfftfreq
#from RealTimeFilter import butter_bandpass
#from Plotter import Plotter
#import serial
#import time

from open_bci_v3 import OpenBCIBoard
from scipy.signal import butter, lfilter, iirnotch, filtfilt

from Fps import Fps

############################################################################################################
# imported method from python_scientific.signalfeatures
def butter_bandpass(lowcut, highcut, fs, order=5):
    nyq = 0.5 * fs
    low = lowcut / nyq
    high = highcut / nyq
    b, a = butter(order, [low, high], btype='band')
    return b, a

############################################################################################################

repetitions = 0

# def plot_spectrum(N, series, fs):
#     yf = rfft(series)
#     xf = rfftfreq(N, 1/fs)
#
#     plt.figure(figsize=(14,7))
#     plt.title('Frequency Spectrum')
#     plt.plot(xf, np.abs(yf), color='green')
#     plt.ylabel('Amplitude')
#     plt.xlabel('Freq Hz')
#     plt.show()

def notch_filter(series, fs):
    f0 = 50.0
    Q = 30.0
    b, a = iirnotch(f0, Q, fs)
    series = filtfilt( b, a, series)

    return series

def butter_bandpass_filter(data, lowcut, highcut, fs, order=5):
    b,a = butter_bandpass(lowcut, highcut, fs, order=order)
    y = lfilter(b,a,data)
    return y

ffps = Fps()
ffps.tic()

def handle_sample(sample):
    ffps.steptoc()
    print( f"Estimated frames per second: {ffps.fps} - Sample: {sample.channel_data[0]} ")

if __name__ == '__main__':

    fs = 250.0

    board = OpenBCIBoard()
    board.print_register_settings()
    board.get_radio_channel_number()
    print(f'OpenBCI connected to radio channel {board.radio_channel_number}')

    board.start_streaming(handle_sample)

    #print('Closing up everything....')
    board.checktimer.cancel()

    board.disconnect()

    print('Done!')
