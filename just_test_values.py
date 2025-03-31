########################################################################
# ---------------------------------------------------------------------
# This code reads signals from the board and saves them to a file .csv
# ---------------------------------------------------------------------
########################################################################

from Fps import Fps
from open_bci_v3 import OpenBCIBoard
from test_openbci import stop_streaming

lowcut = 8.0
highcut = 12.0
fs = 250.0
ffps = Fps()
ffps.tic()

def handle_sample(sample):

    global repetitions

    ffps.steptoc()

    sample_value = sample.channel_data[2]  # Extraer el dato relevante
    fps_value = ffps.fps  # Calcular FPS estimado

    print(f"Estimated FPS: {fps_value:.2f} - Sample: {sample_value} ")


board = OpenBCIBoard()
board.print_register_settings()
board.get_radio_channel_number()
print(f'OpenBCI connected to radio channel {board.radio_channel_number}')

while(True):
    board.start_streaming(handle_sample)

board.disconnect()
exit()


