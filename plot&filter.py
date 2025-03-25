import csv
import sys

from django.contrib.admin.checks import must_be
from scipy.signal import butter, iirnotch, filtfilt, lfilter
from scipy.fft import rfft, rfftfreq
import numpy as np
import matplotlib.pyplot as plt
from readsignal import csv_filename

fs = 250
dt = 1 / fs

############################################################################################################
def butter_bandpass(lowcut, highcut, fs, order=5):
    nyq = 0.5 * fs
    low = lowcut / nyq
    high = highcut / nyq
    b, a = butter(order, [low, high], btype='band')
    return b, a

def butter_bandpass_filter(data, lowcut, highcut, fs, order=5):
    b, a = butter_bandpass(lowcut, highcut, fs, order=order)
    y = lfilter(b, a, data)
    return y

def notch_filter(series, fs):
    f0 = 50.0
    Q = 30.0
    b, a = iirnotch(f0, Q, fs)
    series = filtfilt( b, a, series)
    return series
############################################################################################################

def plot_filtered_signal(muestras, tiempos):
    plt.figure(figsize=(12, 6))
    plt.plot(tiempos, muestras, color='b', label="Señal (mV)")
    plt.xlabel("Tiempo (s)")
    plt.ylabel("Amplitud (mV)")
    plt.title("Señal EEG en el tiempo")
    plt.legend()
    plt.grid()
    plt.show()

def plot_fourier(muestras, tiempos):
    N = len(muestras)  # Número de muestras
    yf = np.fft.rfft(muestras)
    xf = np.fft.rfftfreq(N, dt)

    plt.figure(figsize=(12, 6))
    plt.title('Señal transformada y filtrada')
    plt.plot(xf, np.abs(yf), color='r', label='Transformada de Fourier')
    plt.xlabel('Frecuencia (Hz)')
    plt.ylabel('Amplitud')
    plt.grid()
    plt.show()

try:
    csv_filename = sys.argv[1]
    print(f"Opening file {csv_filename}")
    # Leer archivo CSV

    with open(csv_filename) as csvfile:
        reader = csv.reader(csvfile, delimiter=',')
        next(reader)  # Ignorar encabezados

        # Leer columnas
        repetitions = sample_values = tiempos = fps_values = []

        for row in reader:
            repetitions.append(int(row[0]))
            sample_values.append(int(row[1]))
            fps_values.append(int(row[2]))
            tiempos.append(int(row[0]) * dt)

            # Aplicar filtros
            bandpass_filtered = butter_bandpass_filter(sample_values, 8, 12, 250, order=5)
            #notch_filtered = notch_filter(bandpass_filtered, 250)

            plot_filtered_signal(sample_values, tiempos)
            plot_fourier(sample_values, tiempos)

except Exception as e:
    print(f"Error initializing {e}:")

finally:
    print("DONE")

