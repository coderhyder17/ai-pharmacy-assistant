
import re
import sounddevice as sd
import numpy as np

from scipy.io.wavfile import write
from faster_whisper import WhisperModel

from pharmacy_assistant import (
    get_ai_response,
    detect_language,
    get_message
)


# =========================================
# 1. CONFIGURATION
# =========================================

SAMPLE_RATE = 16000
DURATION = 8

MICROPHONE_DEVICE = 1
AUDIO_FILE = "recording.wav"

MIN_AUDIO_LEVEL = 0.002

MIN_AVG_LOG_PROB = -1.0
MAX_NO_SPEECH_PROB = 0.65

EXIT_COMMANDS = {
    "exit", "quit", "stop",
    "band karo", "bas karo"
}

SHORT_VALID_UTTERANCES = {
    "panadol", "brufen", "augmentin",
    "tablet", "tablets", "syrup",
    "capsule", "capsules", "pack", "packet", "bottle",
    "one", "two", "three", "four", "five",
    "six", "seven", "eight", "nine", "ten"
}

MEDICINE_HOTWORDS = (
    "Panadol, Panadol Extra, Brufen, Augmentin, "
    "Paracetamol, Ibuprofen"
)


# =========================================
# 2. LOAD WHISPER MODEL
# =========================================

print("\nLoading Whisper model...")

whisper_model = WhisperModel(
    "base",
    device="cpu",
    compute_type="int8"
)

print("Whisper loaded successfully!")


# =========================================
# 3. CONVERSATION STATE
# =========================================

state = {
    "pending_medicines": [],
    "pending_language": "english",
    "last_medicine": None,
    "last_language": "english",
    "pending_quantity": None,
    "cart_items": [],

    # Pending tablet-to-pack confirmation
    "pending_quantity_confirmation": None,
    "pending_unit_clarification": None
}


# =========================================
# 4. RECORD AUDIO
# =========================================

def record_audio():

    print("\nListening... Speak now.")

    audio = sd.rec(
        int(DURATION * SAMPLE_RATE),
        samplerate=SAMPLE_RATE,
        channels=1,
        dtype="float32",
        device=MICROPHONE_DEVICE
    )

    sd.wait()

    audio_level = float(np.sqrt(np.mean(audio ** 2)))

    if audio_level < MIN_AUDIO_LEVEL:
        print("No clear audio detected.")
        return False

    audio_int16 = np.int16(
        np.clip(audio, -1, 1) * 32767
    )

    write(
        AUDIO_FILE,
        SAMPLE_RATE,
        audio_int16
    )

    return True


# =========================================
# 5. CORRECT COMMON MEDICINE TRANSCRIPTIONS
# =========================================

def correct_medicine_transcription(message):

    pharmacy_context = re.search(
        r"\b(have|hear|need|want|give|price|available|"
        r"tablet|tablets|template|syrup|medicine|packs?|pets?|facts?|"
        r"panadol|brufen|profen|augmentin|augment)\b",
        message,
        re.IGNORECASE
    )

    if not pharmacy_context:
        return message

    corrections = {
        r"\bpen and all\b": "Panadol",
        r"\bpan and all\b": "Panadol",
        r"\ban argument\b": "Augmentin",
        r"\bargument\b": "Augmentin",
        # Common Whisper substitutions for "packs" in a quantity request.
        r"(\b\d+)\s+pets?\b": r"\1 packs",
        r"(\b\d+)\s+facts?\s+(?=of\s+it\b)": r"\1 packs ",
        # 'pairs' is corrected only in a quantity-led pharmacy order.
        r"(\b\d+)\s+pairs?\s+(?=of\s+(?:it|panadol|brufen|profen|augmentin))": r"\1 packs ",
        # Common phonetic substitutions, gated by a pharmacy context.
        r"\bprofen\b": "Brufen",
        r"\btemplate\b": "tablet",
        r"\baugment\s+and\s+tablet\b": "Augmentin tablet",
        r"\baugment\s+and\s+table\s+it\b": "Augmentin tablet"
    }

    for wrong, correct in corrections.items():

        message = re.sub(
            wrong,
            correct,
            message,
            flags=re.IGNORECASE
        )

    message = re.sub(
        r"\bdo you hear (Augmentin)\b",
        r"do you have \1",
        message,
        flags=re.IGNORECASE
    )

    return message


# =========================================
# 6. SPEECH TO TEXT
# =========================================

def transcribe_audio():

    print("Recognizing speech...")

    segments, info = whisper_model.transcribe(
        AUDIO_FILE,
        beam_size=5,
        language=None,
        vad_filter=True,

        vad_parameters={
            "min_silence_duration_ms": 500,
            "speech_pad_ms": 300
        },

        no_speech_threshold=0.6,
        log_prob_threshold=-1.0,

        condition_on_previous_text=False,
        hotwords=MEDICINE_HOTWORDS,
        initial_prompt=(
            "Pharmacy conversation in English, Urdu, and Roman Urdu. "
            "Medicine names may include Panadol, Panadol Extra, Brufen, "
            "Augmentin, Paracetamol, and Ibuprofen. Listen carefully to "
            "medicine strengths and units such as mg, mcg, g, and ml. "
            "Do not assume unclear numbers."
        )
    )

    segments = list(segments)

    if not segments:
        print("No speech recognized.")
        return ""

    recognized_text = " ".join(
        segment.text.strip()
        for segment in segments
    ).strip()

    if not recognized_text:
        print("No speech recognized.")
        return ""

    recognized_text = re.sub(
        r"\s+",
        " ",
        recognized_text
    ).strip()

    suspicious_phrases = [
        "the customer may speak english",
        "the customer may speak",
        "medicine names include"
    ]

    if any(
        phrase in recognized_text.lower()
        for phrase in suspicious_phrases
    ):
        print("Unreliable transcription. Please try again.")
        return ""

    # Whisper can occasionally echo words from its pharmacy prompt during
    # silence. Reject this characteristic non-request rather than searching.
    lower_text = recognized_text.lower()
    medicine_terms = sum(
        term in lower_text
        for term in ("panadol", "brufen", "augmentin", "ibuprofen", "paracetamol")
    )
    request_words = ("need", "want", "have", "price", "available", "give", "chahiye", "mujhe")
    if "urdu" in lower_text and medicine_terms >= 2 and not any(word in lower_text for word in request_words):
        print("Unreliable transcription. Please speak again.")
        return ""

    average_log_probability = np.mean([
        segment.avg_logprob
        for segment in segments
    ])

    average_no_speech_probability = np.mean([
        segment.no_speech_prob
        for segment in segments
    ])

    if average_log_probability < MIN_AVG_LOG_PROB:
        print("Speech was unclear. Please try again.")
        return ""

    if average_no_speech_probability > MAX_NO_SPEECH_PROB:
        print("No reliable speech detected.")
        return ""

    if len(recognized_text.split()) == 1:

        if recognized_text.lower() not in SHORT_VALID_UTTERANCES:
            print("Speech was too short. Please try again.")
            return ""

    recognized_text = correct_medicine_transcription(
        recognized_text
    )

    print("\nDetected language:", info.language)
    print("You said:", recognized_text)

    return recognized_text


# =========================================
# 7. CLEAN CUSTOMER MESSAGE
# =========================================

def clean_customer_message(message):

    message = message.strip()

    # Remove greetings only when they appear at the beginning.
    # Example: "Hello, I want Panadol"
    # becomes: "I want Panadol"

    message = re.sub(
        r"^(?:hello|hi|hey|salam|assalam\s+o\s+alaikum)"
        r"[\s,!.]+",
        "",
        message,
        flags=re.IGNORECASE
    )

    return message.strip()


# =========================================
# 8. EXIT COMMAND
# =========================================

def is_exit_command(message):

    return message.lower().strip() in EXIT_COMMANDS


# =========================================
# 9. CONVERT SPOKEN NUMBERS
# =========================================

NUMBER_WORDS = {
    "one": "1",
    "two": "2",
    "three": "3",
    "four": "4",
    "five": "5",
    "six": "6",
    "seven": "7",
    "eight": "8",
    "nine": "9",
    "ten": "10",
    "eleven": "11",
    "twelve": "12",
    "thirteen": "13",
    "fourteen": "14",
    "fifteen": "15",
    "sixteen": "16",
    "seventeen": "17",
    "eighteen": "18",
    "nineteen": "19",
    "twenty": "20"
}


def convert_number_words(message):

    words = message.split()
    converted_words = []

    for word in words:

        clean_word = word.strip(".,!?;:").lower()

        if clean_word in NUMBER_WORDS:
            converted_words.append(NUMBER_WORDS[clean_word])
        else:
            converted_words.append(word)

    return " ".join(converted_words)


# =========================================
# 10. NORMALIZE QUANTITY FOLLOW-UPS
# =========================================

def normalize_quantity_followup(message):

    # Preserve medicine names and natural phrasing. The pharmacy
    # conversation manager parses quantities, units, and pronouns.
    return convert_number_words(message.strip())


# =========================================
# 11. TABLET COUNT TO PACK CONVERSION
# =========================================

def get_tablets_per_pack(medicine):

    pack_size = str(medicine.get("pack_size", ""))

    match = re.search(
        r"(\d+)\s*tablets?",
        pack_size,
        re.IGNORECASE
    )

    if match:
        return int(match.group(1))

    return None


def check_quantity_clarification(message):

    medicine = state.get("last_medicine")

    if not medicine or state["pending_medicines"]:
        return None

    message = convert_number_words(
        message.lower().strip()
    )

    # Handle tablet quantities for medicines sold in packs.

    tablet_match = re.search(
        r"\b(\d+)\s+tablets?\b",
        message
    )

    if (
        tablet_match
        and medicine.get("stock_unit") == "packs"
    ):

        requested_tablets = int(tablet_match.group(1))

        tablets_per_pack = get_tablets_per_pack(
            medicine
        )

        if not tablets_per_pack:
            return (
                "This medicine is sold in packs. "
                "Please tell me how many packs you need."
            )

        # Convert only when the tablet count is an exact
        # multiple of the catalogue pack size.

        if requested_tablets % tablets_per_pack == 0:

            required_packs = (
                requested_tablets // tablets_per_pack
            )

            state["pending_quantity_confirmation"] = {
                "packs": required_packs,
                "medicine": medicine
            }

            pack_word = (
                "pack" if required_packs == 1 else "packs"
            )

            return (
                f"Each pack contains {tablets_per_pack} tablets. "
                f"{requested_tablets} tablets means "
                f"{required_packs} {pack_word}. "
                f"Would you like me to add "
                f"{required_packs} {pack_word}?"
            )

        return (
            f"This medicine is sold in packs of "
            f"{tablets_per_pack} tablets. "
            "Please tell me how many packs you need."
        )

    # Bags are not a recognized inventory unit.

    bag_match = re.search(r"\b(\d+)\s+bags?\b", message)
    if bag_match:
        state["pending_unit_clarification"] = {
            "medicine": medicine,
            "quantity": int(bag_match.group(1))
        }
        return (
            "Do you mean packs or bottles? I will keep the medicine and quantity you requested. "
            "Please confirm the correct unit."
        )

    return None


def handle_unit_clarification(message):
    pending = state.get("pending_unit_clarification")
    if not pending:
        return None

    normalized = convert_number_words(message.lower().strip())
    normalized = re.sub(r"[^a-z0-9\s]", " ", normalized)
    normalized = re.sub(r"\s+", " ", normalized).strip()

    unit = None
    if re.search(r"\b(bottles?|bottle)\b", normalized):
        unit = "bottles"
    elif re.search(r"\b(packs?|packets?|pack)\b", normalized):
        unit = "packs"

    if unit is None:
        return "Please confirm whether you mean packs or bottles."

    medicine = pending["medicine"]
    quantity = pending["quantity"]
    state["pending_unit_clarification"] = None

    if unit != medicine.get("stock_unit"):
        correct_unit = medicine.get("stock_unit", "packs")
        return f"This product is sold by {correct_unit}. Please confirm the quantity in {correct_unit}."

    request = (
        f"I need {quantity} {unit} of {medicine.get('brand_name', '')} "
        f"{medicine.get('strength', '')} {medicine.get('dosage_form', '')}"
    )
    return get_ai_response(request, state)


# =========================================
# 12. HANDLE YES / NO CONFIRMATION
# =========================================

YES_WORDS = {
    "yes", "yeah", "yep", "yes please",
    "okay", "ok", "sure",
    "haan", "han", "jee", "ji",
    "ہاں", "جی"
}

NO_WORDS = {
    "no", "no thanks", "no thank you",
    "nope", "nah",
    "nahi", "nahin", "nhi",
    "نہیں"
}



def handle_quantity_confirmation(message):

    pending = state.get("pending_quantity_confirmation")
    if not pending:
        return None

    normalized = convert_number_words(message.lower().strip())
    normalized = re.sub(r"[^a-z0-9\s]", " ", normalized)
    normalized = re.sub(r"\s+", " ", normalized).strip()

    proposed_quantity = int(pending["packs"])
    medicine = pending.get("medicine") or state.get("last_medicine")

    # A clear refusal cancels only this pending conversion.
    if re.fullmatch(r"(?:no|nope|nah|nahi|nahin|nhi)(?:\s+(?:thanks|thank you))?", normalized):
        state["pending_quantity_confirmation"] = None
        return "No problem. I have not added that quantity. Please tell me how many packs you would like."

    # Do not let unrelated chatter become a confirmation.
    if re.fullmatch(r"(?:thank you|thanks|thanks a lot|thank you very much|shukriya)", normalized):
        state["pending_quantity_confirmation"] = None
        return "You're welcome! I haven't added the pending quantity. Is there anything else I can help you with?"

    affirmative = bool(re.match(
        r"^(?:yes|yeah|yep|okay|ok|sure|haan|han|jee|ji)\b", normalized
    ))

    # Understand a complete spoken instruction, not just a bare yes/no.
    quantity_match = re.search(
        r"\b(\d+)\s*(packs?|packets?|tablets?)\b", normalized
    )

    # Also accept a plain affirmative (the proposed quantity was already stated).
    if quantity_match:
        stated_quantity = int(quantity_match.group(1))
        unit_word = quantity_match.group(2)
        if unit_word.startswith("tablet"):
            return (
                "Please confirm the quantity in packs. "
                "The catalogue sells this medicine by the pack."
            )
        quantity = stated_quantity

        # If a different medicine is spoken, do not silently attach it to this order.
        if medicine:
            brand = str(medicine.get("brand_name", "")).lower()
            known_brands = ("panadol", "panadol extra", "brufen", "augmentin")
            mentioned = [name for name in known_brands if re.search(rf"\b{re.escape(name)}\b", normalized)]
            if mentioned and brand not in normalized:
                return (
                    f"I was asking about {medicine.get('brand_name', 'the previous medicine')}. "
                    "Please finish that confirmation first, or say no to cancel it."
                )
    elif affirmative:
        quantity = proposed_quantity
    else:
        return (
            f"I was asking whether to add {proposed_quantity} packs. "
            "You can say 'yes', 'okay, one pack', or 'give me one pack of Brufen'."
        )

    if quantity <= 0:
        return "Please provide a valid quantity."

    if medicine is None:
        state["pending_quantity_confirmation"] = None
        return "Please tell me the medicine name again so I can add the correct product."

    if quantity > int(medicine.get("stock_quantity", 0)):
        return (
            f"Only {medicine.get('stock_quantity', 0)} packs of "
            f"{medicine.get('brand_name', 'this medicine')} are available. "
            "Please choose a smaller quantity."
        )

    state["pending_quantity_confirmation"] = None
    brand = medicine.get("brand_name", "")
    strength = medicine.get("strength", "")
    dosage_form = medicine.get("dosage_form", "")
    pack_word = "pack" if quantity == 1 else "packs"
    request = f"I need {quantity} {pack_word} of {brand} {strength} {dosage_form}"
    return get_ai_response(request, state)


# =========================================
# 13. HANDLE GREETINGS
# =========================================

def handle_greeting(message):

    message = message.lower().strip()

    greetings = [
        "hi",
        "hello",
        "hey",
        "salam",
        "assalam o alaikum"
    ]

    if message not in greetings:
        return None

    language = detect_language(message)

    return get_message(
        language,
        "Hello! How can I help you today?",
        "Assalam o alaikum! Main aap ki kya madad kar sakta hoon?",
        "السلام علیکم! میں آپ کی کیا مدد کر سکتا ہوں؟"
    )


# =========================================
# 14. HANDLE THANK YOU
# =========================================

def handle_thank_you(message):

    message = message.lower().strip()

    message = re.sub(
        r"[.!?,]",
        "",
        message
    )

    message = re.sub(
        r"\s+",
        " ",
        message
    ).strip()

    thank_you_phrases = {
        "thank you",
        "thanks",
        "thank you very much",
        "thanks a lot",
        "ok thank you",
        "okay thank you",
        "shukriya",
        "bohat shukriya"
    }

    if message not in thank_you_phrases and not re.fullmatch(
        r"(?:(?:ok|okay|thanks|thank you|please|shukriya)\s*)+",
        message
    ):
        return None

    language = detect_language(message)

    return get_message(
        language,
        "You're welcome! Is there anything else I can help you with?",
        "Koi baat nahi! Kya main aap ki aur madad kar sakta hoon?",
        "کوئی بات نہیں! کیا میں آپ کی مزید مدد کر سکتا ہوں؟"
    )


# =========================================
# 15. PROCESS CUSTOMER REQUEST
# =========================================

def process_voice_request(customer_message):

    if not customer_message:
        return

    if is_exit_command(customer_message):
        return

    # Resolve a previously requested packs/bottles clarification first.
    unit_response = handle_unit_clarification(customer_message)
    if unit_response is not None:
        print("\nAssistant:", unit_response)
        return

    # Handle pending quantity confirmation first.

    confirmation_response = handle_quantity_confirmation(
        customer_message
    )

    if confirmation_response is not None:

        print("\nAssistant:", confirmation_response)
        return

    # Handle greetings.

    greeting_response = handle_greeting(
        customer_message
    )

    if greeting_response:

        print("\nAssistant:", greeting_response)
        return

    # Handle thank-you messages.

    thank_you_response = handle_thank_you(
        customer_message
    )

    if thank_you_response:

        print("\nAssistant:", thank_you_response)
        return

    # Ignore unrelated speech instead of turning it into a medicine search.
    lower_message = customer_message.lower().strip()
    pharmacy_intent = re.search(
        r"\b(have|need|want|give|price|cost|available|availability|"
        r"medicine|tablet|tablets|syrup|capsule|pack|packs|packet|packets|"
        r"bottle|bottles|cart|order|chahiye|mujhe|milta|milti)\b",
        lower_message
    )
    known_medicine = re.search(
        r"\b(panadol|brufen|profen|augmentin|paracetamol|ibuprofen)\b",
        lower_message
    )
    quantity_only = re.fullmatch(
        r"(?:i need |i want |need |want )?\d+\s*(?:packs?|packets?|bottles?)?",
        lower_message
    )
    if not (pharmacy_intent or known_medicine or quantity_only):
        print("\nAssistant: Sorry, I didn't catch a pharmacy request. Please tell me the medicine name or what you would like to check.")
        return

    # Remove greeting words from the beginning of requests.

    customer_message = clean_customer_message(
        customer_message
    )

    if not customer_message:
        return

    # Check tablet counts and unsupported quantity units.

    clarification = check_quantity_clarification(
        customer_message
    )

    if clarification:

        print("\nAssistant:", clarification)
        return

    # Normalize quantity follow-ups.

    processed_message = normalize_quantity_followup(
        customer_message
    )

    # Send request to existing pharmacy logic.

    answer = get_ai_response(
        processed_message,
        state
    )

    print("\nAssistant:", answer)


# =========================================
# 16. MAIN VOICE LOOP
# =========================================

def main():

    print("\n===================================")
    print("       AI VOICE PHARMACY ASSISTANT")
    print("===================================")

    print("\nSpeak to the assistant.")
    print("Say 'exit' to stop.")

    print("\nExample requests:")
    print("- Hello, do you have Panadol?")
    print("- I want Panadol tablet.")
    print("- Mujhe Brufen chahiye.")
    print("- I need 3 packs.")
    print("- Three packs of it.")
    print("- I need 10 tablets of it.")

    while True:

        try:

            audio_recorded = record_audio()

            if not audio_recorded:
                continue

            customer_message = transcribe_audio()

            if not customer_message:
                continue

            if is_exit_command(customer_message):

                print("\nAssistant: Allah Hafiz!")
                break

            process_voice_request(
                customer_message
            )

        except KeyboardInterrupt:

            print("\n\nAssistant stopped.")
            break

        except Exception as error:

            print("\nAn error occurred:")
            print(error)

            print("\nPlease try again.")


# =========================================
# 17. RUN APPLICATION
# =========================================

if __name__ == "__main__":
    main()
