import numpy as np
import pandas as pd
import matplotlib.pyplot as plt
from scipy.fft import rfft, rfftfreq

# Cargar datos desde el archivo CSV
archivo_csv = '/Users/agustinaperini/Documents/GitHub/EEG_Signals/sample_signal.csv'  # Reemplazar con la ruta correcta
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