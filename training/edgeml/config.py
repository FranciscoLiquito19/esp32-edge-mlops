"""Constants shared across the pipeline. The firmware has the same numbers in
firmware/components/capture/include/capture.h; the model package carries the
input size and labels, so the firmware never hard-codes those."""

# Camera frame as captured by the device.
CAPTURE_WIDTH = 1024
CAPTURE_HEIGHT = 768

# Model input: the capture decoded at 1/8 scale, greyscale.
INPUT_WIDTH = CAPTURE_WIDTH // 8
INPUT_HEIGHT = CAPTURE_HEIGHT // 8
INPUT_CHANNELS = 1

# Class order is the order of the model outputs.
LABELS = ("nothing", "person", "animal")

# Folder under data/raw/ for captures that have not been labelled yet.
UNLABELED_DIR = "unlabeled"
