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

TIME_TO_STABILIZE = 6 * 30 # 3min
TIME_TO_START_RECORDING = 0
TIME_TO_RECORD = 10 * 250 # 10 segs

csv_filename = ""
repetitions = 0

lowcut = 8.0
highcut = 12.0
fs = 250.0
ffps = Fps()
ffps.tic()

def play_sound():
    subprocess.run(["afplay", "./note.mp3"])
    return

# def just_print(sample):
#     ffps.steptoc()
#
#     sample_value = sample.channel_data[2]  # Extraer el dato relevante
#     fps_value = ffps.fps  # Calcular FPS estimado
#
#     print(f"Estimated FPS: {fps_value:.2f} - Sample: {sample_value} ")

def handle_sample(sample):

    global repetitions

    repetitions += 1
    if repetitions < 0:
        return

    if repetitions == 0:
        print("Signal stabilized, starting recording...")
        play_sound()

    ffps.steptoc()

    sample_value = sample.channel_data[2]  # Extraer el dato relevante
    fps_value = ffps.fps  # Calcular FPS estimado

    print(f"Estimated FPS: {fps_value:.2f} - Sample: {sample_value} ")

    with open(csv_filename, mode='a', newline='') as f:
        writer = csv.writer(f)
        writer.writerow([repetitions, sample_value,fps_value])

    if repetitions >= 3750: # 10 segs
        print("Se alcanzó el límite de muestras [10segs], cerrando...")
        play_sound()
        stop_streaming()
        board.disconnect()
        exit()

try:
    patientname = input("Enter the name of the patient:")
    typeofexp = input("Enter the type of experiment: EC or EO (eyes closed or eyes open):")
    numexp = input("Enter the number of the patients experiment: ")
    csv_filename = numexp + "_" + typeofexp + "_" +  patientname + "_raw.csv"
    # ie: 02_Pedro_raw.csv
    #time_to_record = int(input("Enter the time to wait for the signal in seconds: "))
    time_to_record = TIME_TO_STABILIZE

    with open('signal.csv', mode='w') as f:
        writer = csv.writer(f)
        writer.writerow(["Repetition", "Sample Value", "FPS"])

    board = OpenBCIBoard()
    board.print_register_settings()
    board.get_radio_channel_number()
    print(f'OpenBCI connected to radio channel {board.radio_channel_number}')

    print("Waiting for the signal to stabilize")
    for i in range(time_to_record):
        print(f"stabilizing... {time_to_record-i}")
        time.sleep(1)

    board.start_streaming(handle_sample)
    print("Signal stabilized, starting recording...")


except Exception as e:
    print(f"Error initializing {e}:")

finally:
    print(f"saved as {csv_filename}")
    exit()


