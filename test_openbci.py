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
import csv
import time

from matplotlib import pyplot as plt

from Plotter import Plotter
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

def create_csv():
    """Crea el archivo CSV con los encabezados adecuados."""
    with open(csv_filename, mode='w', newline='') as f:
        writer = csv.writer(f)
        writer.writerow(["Repetition", "Sample Value", "FPS"])  # Encabezados

def handle_sample(sample):
    ffps.steptoc()

    sample_value = sample.channel_data[2]  # Extraer el dato relevante
    fps_value = ffps.fps  # Calcular FPS estimado

    global repetitions
    #print( f"Estimated frames per second: {ffps.fps} - Sample: {sample.channel_data[2]} ")

    print(f"Estimated FPS: {fps_value:.2f} - Sample: {sample_value}")

    # Guardar en CSV
    with open(csv_filename, mode='a', newline='') as f:
        writer = csv.writer(f)
        writer.writerow([repetitions, sample_value, fps_value])

    repetitions += 1
    if repetitions >= 2500:
        print("Se alcanzó el límite de muestras, cerrando...")
        #plot the file 'sample.csv'
        plot_from_csv(csv_filename)
        exit()


def plot_from_csv(filename):
    tiempos = []
    muestras = []

    fs = 250  # Frecuencia de muestreo (250 muestras por segundo)
    dt = 1 / fs  # Intervalo de tiempo entre muestras

    # Leer el archivo CSV
    with open(filename, newline='') as csvfile:
        reader = csv.reader(csvfile)
        next(reader)  # Saltar el encabezado

        for row in reader:
            repetition = int(row[0])
            sample_value = float(row[1])

            # Convertir la repetición a tiempo (segundos)
            time_sec = repetition * dt

            tiempos.append(time_sec)
            muestras.append(sample_value)

    # Graficar
    plt.figure(figsize=(12, 6))
    plt.plot(tiempos, muestras, color='b', label="Señal EEG (mV)")
    plt.xlabel("Tiempo (s)")
    plt.ylabel("Amplitud (mV)")
    plt.title("Señal EEG en el tiempo")
    plt.legend()
    plt.grid()
    plt.show()

if __name__ == '__main__':

    repetitions = 0
    fs = 250.0
    csv_filename = 'sample.csv'

    create_csv()

    board = OpenBCIBoard()
    board.print_register_settings()
    board.get_radio_channel_number()
    print(f'OpenBCI connected to radio channel {board.radio_channel_number}')


    board.start_streaming(handle_sample)

    #print('Closing up everything....')
    board.checktimer.cancel()

    board.disconnect()

    print('Done!')
