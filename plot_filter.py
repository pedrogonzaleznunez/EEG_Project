########################################################################
# ---------------------------------------------------------------------
# This code plot signals from a .csv file
# ---------------------------------------------------------------------
########################################################################

import csv
import sys

from scipy.signal import butter, iirnotch, filtfilt, lfilter
import numpy as np
import matplotlib.pyplot as plt

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
    #y = filtfilt(b, a, data)
    return y

def notch_filter(series, fs):
    f0 = 50.0
    Q = 30.0
    b, a = iirnotch(f0, Q, fs)
    series = filtfilt( b, a, series)
    return series
############################################################################################################

def plot_filtered_signal(muestras, tiempos):
    plt.figure(figsize=(16, 8))
    plt.plot(tiempos, muestras, color='b', label="Señal (mV)")
    plt.xlabel("Tiempo (s)")
    plt.ylabel("Amplitud (mV)")
    plt.title("Señal Filtrada en el tiempo")
    plt.legend()
    plt.grid()
    plt.show()

# def plot_filtered_signal(muestras, tiempos):
#     plt.figure(figsize=(16, 8))
#     plt.plot(tiempos, muestras, 'b-', linewidth=0.5, label="Señal (mV)")
#     plt.xlabel("Tiempo (s)")
#     plt.ylabel("Amplitud (mV)")
#     plt.title("Señal EEG en el tiempo (usa los botones de zoom/pan)")
#     plt.grid()
#     plt.tight_layout()  # Mejor ajuste de los elementos
#     plt.show(block=True)  # Mantiene la figura abierta

def plot_fourier(muestras, tiempos):
    N = len(muestras) #- 375  # Número de muestras
    print(f"N: {N}")
    # muestras = muestras - np.mean(muestras) --> Quitar DC
    # muestras -= np.mean(muestras)
    # muestras = muestras / np.max(np.abs(muestras))
    # print("Primeros valores de la señal:", muestras[:10])
    # print("Media de la señal:", np.mean(muestras))
    yf = np.fft.rfft(muestras)
    #yf = np.abs(yf) / len(muestras)
    xf = np.fft.rfftfreq(N, dt)

    plt.figure(figsize=(16, 8))
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

    with (open(csv_filename) as csvfile):
        reader = csv.reader(csvfile, delimiter=',')
        next(reader)  # Ignorar encabezados

        # Leer columnas
        repetitions = []
        sample_values = []
        tiempos = []
        fps_values = []

        for row in reader:
            if int(row[0]) < 0:
                continue
            repetitions.append(int(row[0]))  # ID o índice, puede seguir siendo int
            sample_values.append(float(row[1]))  # Valores de señal EEG, deben ser float
            fps_values.append(float(row[2]))  # Si esta columna también tiene decimales
            tiempos.append(float(row[0]) * dt)  # Asegurar que sea float

        # Aplicar filtros
        bandpass_filtered = butter_bandpass_filter(sample_values, 8, 12, 250, order=5)
        # bandpass_filtered = butter_bandpass_filter(sample_values, 0.5, 20, 250, order=5)
        #bandpass_filtered = notch_filter(bandpass_filtered, 250)

        # Plotear resultados
        plot_filtered_signal(bandpass_filtered, tiempos)
        plot_fourier(bandpass_filtered, tiempos)


    print("DONE")

except Exception as e:
    print(f"Error: {e}")

finally:
    sys.exit


