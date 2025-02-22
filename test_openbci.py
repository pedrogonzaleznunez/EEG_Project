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
import numpy as np
import pandas as pd
from scipy.fft import rfft, rfftfreq
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

def create_csv(csv_filename='sample.csv'):
    """Crea el archivo CSV con los encabezados adecuados."""
    with open(csv_filename, mode='w', newline='') as f:
        if f.tell() == 0:  # Solo escribe el encabezado si el archivo está vacío
            writer = csv.writer(f)
            writer.writerow(["Repetition", "Sample Value", "FPS"])


def handle_sample(sample):
    ffps.steptoc()
    csv_filename = 'sample.csv'

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
        transformada_fourier(csv_filename)
        stop_streaming()
        exit()


def plot_from_csv(filename):
    print("Plotting from CSV file...")
    tiempos = []
    muestras = []

    csv_filename = 'sample.csv'

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

def transformada_fourier(filename):
    print("Applying Fourier Transform...")
    # Cargar datos desde el archivo CSV
    archivo_csv = '/Users/pedrogonzaleznunez/Documents/GitHub/EEG_Signals/sample.csv'  # Reemplazar con la ruta correcta
    # datos = pd.read_csv(archivo_csv, delimiter=',', names=['Repetition','Sample Value','FPS'])
    datos = pd.read_csv(archivo_csv, delimiter=',', header=0)

    # Extraer la señal EEG
    # eeg_signal = datos['Sample Value'].values
    eeg_signal = pd.to_numeric(datos['Sample Value'], errors='coerce')
    eeg_signal = eeg_signal.dropna().values  # Elimina filas con valores NaN

    Fs = 250.0  # Frecuencia de muestreo en Hz
    N = len(eeg_signal)  # Número de muestras

    # Aplicar Transformada de Fourier
    yf = rfft(eeg_signal)
    xf = rfftfreq(N, 1 / Fs)

    # Graficar el espectro de frecuencia
    plt.figure(figsize=(12, 6))
    plt.title('Espectro de Frecuencia de la Señal EEG')
    plt.plot(xf, np.abs(yf), color='blue')
    plt.xlabel('Frecuencia (Hz)')
    plt.ylabel('Amplitud')
    plt.grid()
    plt.show()

def stop_streaming():
    board.checktimer.cancel()
    board.disconnect()

if __name__ == '__main__':

    repetitions = 0
    fs = 250.0
    csv_filename = 'sample.csv'

    create_csv(csv_filename)
    board = OpenBCIBoard()
    board.print_register_settings()
    board.get_radio_channel_number()
    print(f'OpenBCI connected to radio channel {board.radio_channel_number}')

    board.start_streaming(handle_sample)


    print('Done!')
