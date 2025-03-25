########################################################################
# ---------------------------------------------------------------------
# This code reads signals from the board and saves them to a file .csv
# ---------------------------------------------------------------------
########################################################################

import csv
import time
import subprocess
from Fps import Fps
from open_bci_v3 import OpenBCIBoard
from test_openbci import stop_streaming

global repetitions # =0

lowcut = 8.0
highcut = 12.0
fs = 250.0
ffps = Fps()
ffps.tic()

def play_sound():
    subprocess.run(["afplay", "./note.mp3"])
    return

def handle_sample(sample):

    ffps.steptoc()

    sample_value = sample.channel_data[2]  # Extraer el dato relevante
    fps_value = ffps.fps  # Calcular FPS estimado

    print(f"Estimated FPS: {fps_value:.2f} - Sample: {sample_value} ")

    with open(csv_filename, mode='a', newline='') as f:
        writer = csv.writer(f)
        writer.writerow([repetitions, sample_value,fps_value])

    repetitions += 1
    if repetitions >= 2500:
        print("Se alcanzó el límite de muestras [10segs], cerrando...")
        stop_streaming()
        exit()

try:
    patientname = input("Enter the name of the patient:")
    typeofexp = input("Enter the type of experiment: EC or EO (eyes closed or eyes open):")
    numexp = input("Enter the number of the patients experiment: ")
    csv_filename = numexp + "_" +  patientname + "_raw.csv"
    # ie: 02_Pedro_raw.csv
    #time_to_record = int(input("Enter the time to wait for the signal in seconds: "))
    time_to_record = 6 * 30

    with open('signal.csv', mode='w') as f:
        writer = csv.writer(f)
        writer.writerow(["Repetition", "Sample Value", "FPS"])

    # board = OpenBCIBoard()
    # board.print_register_settings()
    # board.get_radio_channel_number()
    #print(f'OpenBCI connected to radio channel {board.radio_channel_number}')

    print("Waiting for the signal to stabilize")
    for i in range(time_to_record):
        print(f"stabilizing... {time_to_record-i}")
        time.sleep(1)

    play_sound()
    print("Recording signal...")
    #board.start_streaming(handle_sample)

except Exception as e:
    print(f"Error initializing {e}:")

finally:
    #board.disconnect()
    print(f"saved as {csv_filename}")
    exit()


