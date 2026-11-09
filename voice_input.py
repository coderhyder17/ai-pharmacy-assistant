
import sounddevice as sd
import numpy as np
from scipy.io.wavfile import write
from faster_whisper import WhisperModel


# =========================================
# 1. CONFIGURATION
# =========================================

SAMPLE_RATE = 16000
DURATION = 6
MICROPHONE_DEVICE = 1

AUDIO_FILE = "recording.wav"


# =========================================
# 2. LOAD WHISPER MODEL
# =========================================

print("Loading Whisper model...")

model = WhisperModel(
    "base",
    device="cpu",
    compute_type="int8"
)

print("Whisper model loaded successfully!")


# =========================================
# 3. RECORD MICROPHONE AUDIO
# =========================================

def record_audio():

    print("\nSpeak now...")
    print(f"Recording for {DURATION} seconds...\n")

    audio = sd.rec(
        int(DURATION * SAMPLE_RATE),
        samplerate=SAMPLE_RATE,
        channels=1,
        dtype="float32",
        device=MICROPHONE_DEVICE
    )

    sd.wait()

    # Convert float audio into 16-bit PCM
    audio_int16 = np.int16(
        np.clip(audio, -1, 1) * 32767
    )

    write(
        AUDIO_FILE,
        SAMPLE_RATE,
        audio_int16
    )

    print("Recording completed!")


# =========================================
# 4. CONVERT SPEECH INTO TEXT
# =========================================

def transcribe_audio():

    print("Recognizing speech...")

    segments, info = model.transcribe(
        AUDIO_FILE,
        beam_size=5,
        language=None,
        vad_filter=True,
        initial_prompt=(
            "Pharmacy conversation. "
            "Medicine names: Panadol, Panadol Extra, "
            "Brufen, Augmentin, Paracetamol."
        )
    )
    
    recognized_text = " ".join(
        segment.text.strip()
        for segment in segments
    ).strip()

    print("\nDetected language:", info.language)
    print("Recognized text:", recognized_text)

    return recognized_text


# =========================================
# 5. MAIN
# =========================================

if __name__ == "__main__":

    try:

        record_audio()
        transcribe_audio()

    except Exception as error:

        print("\nAn error occurred:")
        print(error)
