import numpy as np
import pandas as pd

# Parámetros de la señal
Fs = 250  # Frecuencia de muestreo en Hz
T = 1 / Fs  # Periodo de muestreo
N = 1000  # Número de muestras
t = np.linspace(0, (N - 1) * T, N)  # Vector de tiempo

# Crear una señal de prueba: combinación de dos senoidales (10 Hz y 40 Hz)
signal = 1.5 * np.sin(2 * np.pi * 10 * t) + 0.5 * np.sin(2 * np.pi * 40 * t)

# Crear un DataFrame
df = pd.DataFrame({
    "Repetition": np.arange(N),
    "Sample Value": signal,
    "FPS": [Fs] * N
})

# Guardar como archivo CSV
csv_filename = "/Users/agustinaperini/Documents/GitHub/EEG_Signals/sample_signal.csv"
df.to_csv(csv_filename, index=False)

csv_filename