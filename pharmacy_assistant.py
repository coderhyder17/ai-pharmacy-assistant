
import re

from medicine_catalog import search_medicine


# =========================================
# 1. CONFIGURATION
# =========================================

PHARMACY_NAME = "AI Pharmacy Assistant"


# =========================================
# 2. LANGUAGE DETECTION
# =========================================

def detect_language(message):

    if any("\u0600" <= char <= "\u06FF" for char in message):
        return "urdu"

    words = set(
        re.findall(r"\b\w+\b", message.lower())
    )

    roman_urdu_words = {
        "mujhe", "chahiye", "hai", "hain", "kya",
        "kitna", "kitni", "konsi", "kaunsi", "dawa",
        "batao", "milay", "jayegi", "ki", "ke",
        "mein", "mera", "meri", "ka", "karna",
        "milega", "milti", "aur"
    }

    if words.intersection(roman_urdu_words):
        return "roman_urdu"

    return "english"


# =========================================
# 3. MEDICAL SAFETY CHECK
# =========================================

def is_medical_advice_request(message):

    message = message.lower().strip()
    message = re.sub(r"[^\w\s]", " ", message)
    message = re.sub(r"\s+", " ", message).strip()

    medical_patterns = [

        # Medicine recommendations
        r"what medicine should i take",
        r"which medicine should i take",
        r"what should i take",
        r"which medicine is best",
        r"recommend.*medicine",
        r"suggest.*medicine",
        r"medicine for (fever|pain|cough|cold|headache)",

        # Strength and dosage recommendations
        r"which strength should i take",
        r"what strength should i take",
        r"which dose should i take",
        r"what dose should i take",
        r"how much should i take",
        r"how many tablets should i take",
        r"how often should i take",
        r"when should i take",
        r"how to take",
        r"\bdosage\b",
        r"dose batao",
        r"kitni dose",
        r"kitna lena chahiye",
        r"kitni tablets",
        r"kitne tablets",

        # Medical suitability and safety
        r"can i take",
        r"is it safe to take",
        r"side effects",
        r"contraindication",
        r"pregnant",
        r"pregnancy",
        r"for my child",
        r"for baby",
        r"for a child",

        # Roman Urdu
        r"kya lena chahiye",
        r"kya dawa loon",
        r"konsi dawa",
        r"kaunsi dawa",
        r"kitna istemal karun",
        r"kitni dafa",
        r"bachay ko kitna",
        r"bachay ke liye konsi dawa",

        # Urdu script
        r"کون سی دوا",
        r"کونسی دوا",
        r"کتنی خوراک",
        r"کتنا لینا",
        r"کیا لینا چاہیے"
    ]

    return any(
        re.search(pattern, message)
        for pattern in medical_patterns
    )


def get_safety_response(message):

    language = detect_language(message)

    if language == "roman_urdu":

        return (
            "Is bare mein hamare qualified pharmacist se mashwara karein "
            "ya apni prescription follow karein. "
            "Main sirf medicine ki availability aur price check kar sakta hoon."
        )

    if language == "urdu":

        return (
            "براہ کرم اس بارے میں ہمارے مستند فارماسسٹ سے مشورہ کریں "
            "یا اپنے ڈاکٹر کے نسخے پر عمل کریں۔ "
            "میں صرف دوا کی دستیابی اور قیمت بتا سکتا ہوں۔"
        )

    return (
        "Please follow your prescription or consult our qualified pharmacist. "
        "I can only help check medicine availability and prices."
    )


# =========================================
# 4. EXTRACT STRENGTH AND DOSAGE FORM
# =========================================

def extract_explicit_strength(message):

    pattern = (
        r"\b\d+(?:\.\d+)?\s*(?:mg|mcg|g|ml)"
        r"(?:\s*/\s*\d+(?:\.\d+)?\s*(?:mg|mcg|g|ml))?"
        r"(?:\s*\+\s*\d+(?:\.\d+)?\s*(?:mg|mcg|g|ml))*"
    )

    match = re.search(
        pattern,
        message,
        re.IGNORECASE
    )

    if match:

        return re.sub(
            r"\s+",
            " ",
            match.group(0)
        ).strip()

    return None


def extract_explicit_form(message):

    forms = {
        "syrup": r"\bsyrup\b",
        "tablet": r"\btablets?\b",
        "capsule": r"\bcapsules?\b",
        "injection": r"\binjections?\b",
        "cream": r"\bcream\b",
        "ointment": r"\bointment\b",
        "drops": r"\bdrops?\b"
    }

    for form, pattern in forms.items():

        if re.search(pattern, message, re.IGNORECASE):
            return form

    return None


# =========================================
# 5. EXTRACT QUANTITY
# =========================================

def extract_quantity(message, default_unit=None):

    message = str(message).lower().strip()

    number_words = {
        "one": "1", "two": "2", "three": "3", "four": "4",
        "five": "5", "six": "6", "seven": "7", "eight": "8",
        "nine": "9", "ten": "10", "eleven": "11", "twelve": "12",
        "thirteen": "13", "fourteen": "14", "fifteen": "15",
        "sixteen": "16", "seventeen": "17", "eighteen": "18",
        "nineteen": "19", "twenty": "20"
    }

    message = re.sub(
        r"\b(" + "|".join(number_words) + r")\b",
        lambda match: number_words[match.group(1)],
        message,
        flags=re.IGNORECASE
    )

    match = re.search(
        r"\b(\d+)\s*(bottles?|packs?|packets?)\b",
        message,
        flags=re.IGNORECASE
    )

    if match:
        quantity = int(match.group(1))
        requested_unit = match.group(2).lower()
        unit = "bottles" if requested_unit.startswith("bottle") else "packs"

        return {"quantity": quantity, "unit": unit}

    if default_unit:
        number_pattern = (
            r"\b(?:i need|i want|need|want|give me|get me|"
            r"please give me|mujhe chahiye|chahiye)\s+(\d+)\b"
        )

        match = re.search(number_pattern, message)

        if not match:
            match = re.fullmatch(r"\s*(\d+)\s*", message)

        if match:
            return {"quantity": int(match.group(1)), "unit": default_unit}

    return None


# =========================================
# 6. EXTRACT MEDICINE SEARCH TERM
# =========================================

STOP_WORDS = {
    # English
    "i", "is", "the", "a", "an",
    "available", "availability",
    "do", "does", "you", "have", "has", "any",
    "price", "cost", "tell", "me", "please",
    "how", "much", "what", "check", "find",
    "medicine", "product", "need", "want",
    "buy", "get", "order", "of", "for", "to", "do", "other", "show", "list", "all", "products", "products",
    "and", "in", "stock", "there", "currently",
    "hear", "here", "got", "it", "that", "same",
    "also", "thanks", "thank", "only", "said", "just", "that", "its",
    "yes", "yeah", "yep", "okay", "ok", "sure",
    "hey", "hello", "hi", "please",
    "give", "me", "get", "packet", "packets", "pack", "packs",
    "bottle", "bottles",
    "one", "two", "three", "four", "five", "six", "seven",
    "eight", "nine", "ten", "eleven", "twelve", "thirteen",
    "fourteen", "fifteen", "sixteen", "seventeen", "eighteen",
    "nineteen", "twenty",
    "haan", "han", "jee", "ji",

    # Roman Urdu
    "mujhe", "chahiye", "hai", "hain", "kya",
    "ki", "ka", "ke", "batao", "karo",
    "milega", "milti", "mil", "sakta", "sakti",
    "konsi", "kaunsi", "dawa", "meri", "mera",
    "kitna", "kitni", "aur",
    "mujhay", "chahye", "batayein",
    "chahiyen", "chaiye", "chaheye", "chahie",
    "chahiyein", "chahyein"
}


def extract_search_term(message):

    term = message.lower()
    term = re.sub(r"\b([a-z]+)[’']s\b", r"\1", term)
    term = re.sub(r"\bit\s+is\b|\bit’s\b|\bit's\b", " ", term)

    # Remove strength
    term = re.sub(
        r"\b\d+(?:\.\d+)?\s*(?:mg|mcg|g|ml)"
        r"(?:\s*/\s*\d+(?:\.\d+)?\s*(?:mg|mcg|g|ml))?"
        r"(?:\s*\+\s*\d+(?:\.\d+)?\s*(?:mg|mcg|g|ml))*",
        " ",
        term,
        flags=re.IGNORECASE
    )

    # Remove quantities with numeric or spoken numbers and their units.
    number_words_pattern = (
        r"one|two|three|four|five|six|seven|eight|nine|ten|"
        r"eleven|twelve|thirteen|fourteen|fifteen|sixteen|"
        r"seventeen|eighteen|nineteen|twenty"
    )
    term = re.sub(
        rf"\b(?:\d+|{number_words_pattern})\s*(?:bottles?|packs?|packets?)\b",
        " ",
        term,
        flags=re.IGNORECASE
    )

    term = re.sub(
        rf"\b(?:{number_words_pattern})\b",
        " ",
        term,
        flags=re.IGNORECASE
    )

    # Remove dosage forms
    term = re.sub(
        r"\b(syrup|tablets?|capsules?|injections?|cream|ointment|drops?)\b",
        " ",
        term
    )

    # Remove standalone numbers
    term = re.sub(
        r"\b\d+\b",
        " ",
        term
    )

    # Keep meaningful medicine-name words
    words = re.findall(
        r"[a-zA-Z]+",
        term
    )

    medicine_words = [
        word for word in words
        if word not in STOP_WORDS
    ]

    # Remove duplicates while preserving word order
    medicine_words = list(
        dict.fromkeys(medicine_words)
    )

    return " ".join(medicine_words).strip()


# =========================================
# 7.1. INTENT AND CLARIFICATION HELPERS
# =========================================

def is_catalogue_browse_request(message):
    text = re.sub(r"[^\w\s]", " ", str(message).lower())
    text = re.sub(r"\s+", " ", text).strip()

    patterns = (
        r"\bwhat (?:other )?(?:products|medicines)\b",
        r"\bshow (?:me )?(?:all )?(?:products|medicines)\b",
        r"\blist (?:all )?(?:products|medicines)\b",
        r"\bwhat do you have\b",
        r"\bwhat else do you have\b",
        r"\bavailable (?:products|medicines)\b",
        r"\bshow me everything\b",
        r"\b(?:show me )?(?:the )?(?:full )?catalog(?:ue)?\b",
        r"\bshow me that catalog(?:ue)?\b",
        r"\bcatalog(?:ue)? please\b",
        r"\bpoori list\b",
        r"\bsari dawa(?:ein)?\b",
    )
    return any(re.search(pattern, text) for pattern in patterns)


def extract_unlabelled_number(message):
    """
    Find a number that may be an unclear medicine strength, rather than
    silently treating it as a strength. Ignore numbers attached to units,
    dosage forms, or inventory quantities.
    """
    text = str(message).lower()

    # Remove valid strengths first.
    text = re.sub(
        r"\b\d+(?:\.\d+)?\s*(?:mg|mcg|g|ml)"
        r"(?:\s*/\s*\d+(?:\.\d+)?\s*(?:mg|mcg|g|ml))?"
        r"(?:\s*\+\s*\d+(?:\.\d+)?\s*(?:mg|mcg|g|ml))*",
        " ",
        text,
        flags=re.IGNORECASE
    )

    # Remove ordinary quantities and pack/form counts.
    text = re.sub(
        r"\b\d+\s*(?:packs?|packets?|bottles?|tablets?|capsules?)\b",
        " ",
        text,
        flags=re.IGNORECASE
    )

    match = re.search(r"\b\d+(?:\.\d+)?\b", text)
    return match.group(0) if match else None


def get_form_mismatch_response(results, requested_form, language):
    actual_forms = []
    for medicine in results:
        form = str(medicine.get("dosage_form", "")).strip()
        if form and form.lower() not in [item.lower() for item in actual_forms]:
            actual_forms.append(form)

    if not actual_forms:
        return None

    forms_text = ", ".join(actual_forms)
    return get_message(
        language,
        f"I found this medicine in our catalogue, but not as {requested_form}. "
        f"The catalogue lists: {forms_text}. Would you like information about "
        "the listed product?",
        f"Yeh medicine catalogue mein mili hai, lekin {requested_form} ki form mein nahi. "
        f"Catalogue mein yeh form available hai: {forms_text}. Kya aap listed product "
        "ki details chahte hain?",
        f"یہ دوا کیٹلاگ میں موجود ہے، لیکن {requested_form} کی شکل میں نہیں۔ "
        f"کیٹلاگ میں یہ شکل موجود ہے: {forms_text}۔ کیا آپ درج شدہ پروڈکٹ کی تفصیل چاہتے ہیں؟"
    )


def get_catalogue_browse_response(language):
    try:
        # search_medicine uses a substring search; an empty term returns
        # the catalogue rows when its SQL LIKE pattern is built as %%.
        results = search_medicine(search_term="", strength=None, dosage_form=None)
    except Exception as error:
        print("Catalogue browse error:", error)
        results = []

    # Only display available products in a customer-facing availability list.
    available = [
        medicine for medicine in results
        if int(medicine.get("stock_quantity", 0) or 0) > 0
    ]

    if not available:
        return get_message(
            language,
            "I couldn't retrieve any currently available products from the catalogue. "
            "Please ask the pharmacist for assistance.",
            "Catalogue mein filhal koi available product retrieve nahi ho saka. "
            "Pharmacist se madad lein.",
            "کیٹلاگ سے فی الحال کوئی دستیاب پروڈکٹ نہیں مل سکی۔ براہ کرم فارماسسٹ سے رابطہ کریں۔"
        )

    available = available[:12]
    lines = [
        get_message(
            language,
            "Here are the products currently marked as available:",
            "Yeh products catalogue mein filhal available hain:",
            "یہ پروڈکٹس فی الحال کیٹلاگ میں دستیاب ہیں:"
        )
    ]

    for index, medicine in enumerate(available, start=1):
        lines.append(
            f"{index}. {medicine['brand_name']} - {medicine['strength']} "
            f"{medicine['dosage_form']} - PKR {float(medicine['price_pkr']):.2f}"
        )

    lines.append(
        get_message(
            language,
            "Which product would you like me to check?",
            "Aap kis product ki details check karwana chahte hain?",
            "آپ کس پروڈکٹ کی تفصیل چیک کروانا چاہتے ہیں؟"
        )
    )
    return "\n".join(lines)


# =========================================
# 7. DATABASE SEARCH
# =========================================

def normalize_strength_components(value):
    """
    Convert strength text into comparable numeric-unit components.
    Examples:
      "500 mg" -> ["500mg"]
      "500 mg + 65 mg" -> ["500mg", "65mg"]
      "120 mg/5 ml" -> ["120mg", "5ml"]
    """
    if not value:
        return []

    matches = re.findall(
        r"(\d+(?:\.\d+)?)\s*(mg|mcg|g|ml)",
        str(value).lower().replace(",", ""),
        flags=re.IGNORECASE
    )

    return [
        f"{float(number):g}{unit.lower()}"
        for number, unit in matches
    ]


def strength_matches(requested_strength, catalogue_strength):
    requested = normalize_strength_components(requested_strength)
    available = normalize_strength_components(catalogue_strength)

    if not requested or not available:
        return False

    # A request for "500 mg" can identify a combination product
    # whose first active ingredient is 500 mg. Brand matching
    # distinguishes Panadol from Panadol Extra.
    if len(requested) == 1:
        return available[0] == requested[0]

    return available == requested


def normalize_name(value):
    return " ".join(re.findall(r"[a-z0-9]+", str(value).lower()))


def filter_by_requested_brand(results, search_term):
    """
    Prefer the longest exact brand phrase present in the request.
    Thus 'Panadol' does not accidentally select 'Panadol Extra',
    while 'Panadol Extra' selects the latter.
    """
    query = normalize_name(search_term).split()
    if not query:
        return results

    matched_brands = []

    for medicine in results:
        brand_words = normalize_name(medicine.get("brand_name", "")).split()
        if not brand_words or len(brand_words) > len(query):
            continue

        for index in range(len(query) - len(brand_words) + 1):
            if query[index:index + len(brand_words)] == brand_words:
                matched_brands.append((len(brand_words), " ".join(brand_words)))
                break

    if not matched_brands:
        return results

    longest_brand = max(matched_brands, key=lambda item: item[0])[1]

    return [
        medicine for medicine in results
        if normalize_name(medicine.get("brand_name", "")) == longest_brand
    ]


def search_catalogue(customer_message):

    search_term = extract_search_term(customer_message)

    if not search_term:
        return []

    # Search broadly first. Strength/form are normalized and filtered
    # below because SQL exact matching can confuse "500mg" with "500 mg".
    results = search_medicine(
        search_term=search_term,
        strength=None,
        dosage_form=None
    )

    if not results:
        return []

    results = filter_by_requested_brand(results, search_term)

    strength = extract_explicit_strength(customer_message)
    if strength:
        results = [
            medicine for medicine in results
            if strength_matches(strength, medicine.get("strength", ""))
        ]

    dosage_form = extract_explicit_form(customer_message)
    if dosage_form:
        results = [
            medicine for medicine in results
            if str(medicine.get("dosage_form", "")).lower() == dosage_form.lower()
        ]

    return results


# =========================================
# 8. RESPONSE LANGUAGE HELPERS
# =========================================

def get_message(language, english, roman_urdu, urdu):

    if language == "roman_urdu":
        return roman_urdu

    if language == "urdu":
        return urdu

    return english


# =========================================
# 9. FORMAT PRODUCT LIST
# =========================================

def format_product_list(results, language):

    if language == "roman_urdu":

        lines = [
            "Yeh products hamare catalogue mein mile hain:"
        ]

    elif language == "urdu":

        lines = [
            "یہ مصنوعات ہمارے کیٹلاگ میں موجود ہیں:"
        ]

    else:

        lines = [
            "Here are the matching products:"
        ]

    for index, medicine in enumerate(results, start=1):

        lines.append(
            f"{index}. {medicine['brand_name']} "
            f"({medicine['generic_name']}) - "
            f"{medicine['strength']} "
            f"{medicine['dosage_form']}"
        )

    lines.append(
        get_message(
            language,
            "Which one would you like?",
            "Aap ko in mein se konsa product chahiye?",
            "براہ کرم بتائیں آپ کو کون سی دوا چاہیے؟"
        )
    )

    return "\n".join(lines)


# =========================================
# 10. FORMAT SINGLE PRODUCT
# =========================================

def format_single_product(
    medicine,
    language,
    requested_quantity=None
):

    brand = medicine["brand_name"]
    generic = medicine["generic_name"]
    strength = medicine["strength"]
    dosage_form = medicine["dosage_form"]

    pack_size = medicine["pack_size"]
    price = float(medicine["price_pkr"])

    stock_quantity = int(
        medicine["stock_quantity"]
    )

    stock_unit = medicine["stock_unit"]

    unit_singular = {
        "packs": "pack",
        "bottles": "bottle"
    }.get(
        stock_unit,
        stock_unit.rstrip("s")
    )

    product_name = (
        f"{brand} ({generic}), {strength} {dosage_form}"
    )

    is_available = stock_quantity > 0

    # Product unavailable
    if not is_available:

        return get_message(
            language,
            f"Sorry, {product_name} is currently OUT OF STOCK.",
            f"Maazrat, {product_name} filhal out of stock hai.",
            f"معذرت، {product_name} فی الحال اسٹاک میں موجود نہیں ہے۔"
        )

    # Base product information
    if language == "roman_urdu":

        lines = [
            f"Ji, {product_name} available hai.",
            f"Stock: {stock_quantity} {stock_unit}",
            f"Pack size: {pack_size}",
            f"Price per {unit_singular}: PKR {price:.2f}"
        ]

    elif language == "urdu":

        lines = [
            f"{product_name} دستیاب ہے۔",
            f"اسٹاک: {stock_quantity} {stock_unit}",
            f"پیک سائز: {pack_size}",
            f"قیمت فی {unit_singular}: PKR {price:.2f}"
        ]

    else:

        lines = [
            f"Yes, {product_name} is available.",
            f"Stock: {stock_quantity} {stock_unit}",
            f"Pack size: {pack_size}",
            f"Price per {unit_singular}: PKR {price:.2f}"
        ]

    # Quantity and estimated bill
    if requested_quantity:

        quantity = requested_quantity["quantity"]
        requested_unit = requested_quantity["unit"]

        if quantity <= 0:

            return get_message(
                language,
                "Please provide a valid quantity.",
                "Barah-e-karam sahi quantity batayein.",
                "براہ کرم درست مقدار بتائیں۔"
            )

        if requested_unit != stock_unit:

            return get_message(
                language,
                f"This product is sold by {unit_singular}. "
                f"Please provide the quantity in {stock_unit}.",
                f"Yeh product {unit_singular} ke hisaab se sell hota hai. "
                f"Please quantity {stock_unit} mein batayein.",
                f"یہ پروڈکٹ {unit_singular} کے حساب سے فروخت ہوتا ہے۔ "
                f"براہ کرم مقدار {stock_unit} میں بتائیں۔"
            )

        if quantity > stock_quantity:

            return get_message(
                language,
                f"Only {stock_quantity} {stock_unit} are currently available. "
                "Please choose a smaller quantity.",
                f"Is waqt sirf {stock_quantity} {stock_unit} available hain. "
                "Please kam quantity select karein.",
                f"اس وقت صرف {stock_quantity} {stock_unit} دستیاب ہیں۔ "
                f"براہ کرم کم مقدار منتخب کریں۔"
            )

        total = quantity * price

        if language == "roman_urdu":

            lines.extend([
                f"Requested quantity: {quantity} {stock_unit}",
                f"Estimated total: PKR {total:.2f}",
                "Yeh sirf estimated bill hai. Sale complete nahi hui."
            ])

        elif language == "urdu":

            lines.extend([
                f"مطلوبہ مقدار: {quantity} {stock_unit}",
                f"متوقع بل: PKR {total:.2f}",
                "یہ صرف تخمینہ ہے۔ فروخت مکمل نہیں ہوئی۔"
            ])

        else:

            lines.extend([
                f"Requested quantity: {quantity} {stock_unit}",
                f"Estimated total: PKR {total:.2f}",
                "This is an estimate only. No sale has been completed."
            ])

    return "\n".join(lines)


# =========================================
# 11. PRODUCT SELECTION
# =========================================

def resolve_product_selection(message, state):

    pending = state["pending_medicines"]

    if not pending:
        return None

    text = message.lower().strip()
    language = state["pending_language"]

    def finish_selection(selected, requested_quantity=None):
        state["pending_medicines"] = []
        state["last_medicine"] = selected
        state["last_language"] = language

        if requested_quantity is None:
            requested_quantity = extract_quantity(
                message,
                default_unit=selected["stock_unit"]
            )

        if requested_quantity is None:
            requested_quantity = state.get("pending_quantity")

        state["pending_quantity"] = None

        response = format_single_product(selected, language, requested_quantity)
        if requested_quantity and requested_quantity.get("unit") == selected.get("stock_unit") and int(requested_quantity["quantity"]) <= int(selected["stock_quantity"]):
            add_cart_item(state, selected, int(requested_quantity["quantity"]), requested_quantity["unit"])
            response += "\n\n" + format_cart(state, language)
        return response

    # A. Selection by list number
    if re.fullmatch(r"\d+", text):
        index = int(text) - 1

        if 0 <= index < len(pending):
            return finish_selection(pending[index])

        return get_message(
            language,
            "Invalid selection. Please choose a valid product number.",
            "Yeh number list mein nahi hai. Please sahi number select karein.",
            "یہ نمبر فہرست میں موجود نہیں۔ براہ کرم درست نمبر منتخب کریں۔"
        )

    search_term = extract_search_term(message)
    candidates = list(pending)

    # B. Prefer an exact/longest brand phrase in the customer's words.
    if search_term:
        candidates = filter_by_requested_brand(candidates, search_term)

    # C. Filter by normalized strength components.
    strength = extract_explicit_strength(message)
    if strength:
        candidates = [
            medicine for medicine in candidates
            if strength_matches(strength, medicine.get("strength", ""))
        ]

    # D. Filter by dosage form.
    form = extract_explicit_form(message)
    if form:
        candidates = [
            medicine for medicine in candidates
            if str(medicine.get("dosage_form", "")).lower() == form.lower()
        ]

    if len(candidates) == 1:
        return finish_selection(candidates[0])

    if len(candidates) > 1 and (search_term or strength or form):
        state["pending_medicines"] = candidates
        return format_product_list(candidates, language)

    # E. Selection by stock unit, e.g. packs or bottles.
    quantity = extract_quantity(message)
    requested_unit = quantity["unit"] if quantity else None

    if not requested_unit and re.fullmatch(
        r"\s*(packs?|packets?|bottles?)\s*", text
    ):
        requested_unit = "bottles" if "bottle" in text else "packs"

    if requested_unit:
        unit_candidates = [
            medicine for medicine in pending
            if medicine["stock_unit"] == requested_unit
        ]

        if len(unit_candidates) == 1:
            return finish_selection(unit_candidates[0], quantity)

        if len(unit_candidates) > 1:
            state["pending_medicines"] = unit_candidates
            return format_product_list(unit_candidates, language)

    return None


# =========================================
# 12. HANDLE QUANTITY FOLLOW-UP
# =========================================

def handle_quantity_followup(message, state):

    medicine = state["last_medicine"]

    if not medicine:
        return None

    quantity = extract_quantity(
        message,
        default_unit=medicine["stock_unit"]
    )

    if not quantity:
        return None

    language = detect_language(message)

    if language == "english" and state["last_language"]:
        language = state["last_language"]

    response = format_single_product(medicine, language, quantity)
    if quantity and quantity.get("unit") == medicine.get("stock_unit") and int(quantity["quantity"]) <= int(medicine["stock_quantity"]):
        add_cart_item(state, medicine, int(quantity["quantity"]), quantity["unit"])
        response += "\n\n" + format_cart(state, language)
    return response



# =========================================
# 12. CART AND MULTI-PRODUCT ORDER HELPERS
# =========================================

NUMBER_WORDS_FOR_CART = {
    "one": 1, "two": 2, "three": 3, "four": 4, "five": 5,
    "six": 6, "seven": 7, "eight": 8, "nine": 9, "ten": 10,
    "eleven": 11, "twelve": 12, "thirteen": 13, "fourteen": 14,
    "fifteen": 15, "sixteen": 16, "seventeen": 17,
    "eighteen": 18, "nineteen": 19, "twenty": 20
}


def _cart_unit(unit_text):
    unit_text = unit_text.lower()
    if unit_text.startswith("bottle"):
        return "bottles"
    return "packs"


def _cart_quantity(value):
    value = value.lower()
    return int(value) if value.isdigit() else NUMBER_WORDS_FOR_CART.get(value)


def _cart_item_key(medicine):
    return str(medicine.get("sku") or medicine.get("id") or (
        medicine.get("brand_name", "") + "|" + medicine.get("strength", "") + "|" + medicine.get("dosage_form", "")
    )).lower()


def add_cart_item(state, medicine, quantity, unit):
    state.setdefault("cart_items", [])
    key = _cart_item_key(medicine)
    for item in state["cart_items"]:
        if _cart_item_key(item["medicine"]) == key:
            item["quantity"] = quantity
            item["unit"] = unit
            return
    state["cart_items"].append({"medicine": medicine, "quantity": quantity, "unit": unit})


def format_cart(state, language="english"):
    items = state.get("cart_items", [])
    if not items:
        return "Your cart is empty. Tell me which medicines and quantities you need."

    lines = ["Your current order estimate:"]
    grand_total = 0.0
    for item in items:
        medicine = item["medicine"]
        quantity = int(item["quantity"])
        unit = item["unit"]
        price = float(medicine["price_pkr"])
        line_total = quantity * price
        grand_total += line_total
        lines.append(
            f"- {medicine['brand_name']} {medicine['strength']} {medicine['dosage_form']}: "
            f"{quantity} {unit} x PKR {price:.2f} = PKR {line_total:.2f}"
        )
    lines.append(f"Estimated cart total: PKR {grand_total:.2f}")
    lines.append("This is an estimate only. No sale has been completed and stock has not been deducted.")
    return "\n".join(lines)


def parse_multi_product_order(message):
    """Return quantity-led order segments; never infer a missing quantity or unit."""
    normalized = str(message).strip()
    number_pattern = r"(?:\d+|" + "|".join(NUMBER_WORDS_FOR_CART) + r")"
    unit_pattern = r"packs?|packets?|bottles?|pairs?"
    pattern = re.compile(rf"\b({number_pattern})\s+({unit_pattern})\b", re.IGNORECASE)
    matches = list(pattern.finditer(normalized))
    if len(matches) < 2:
        return None

    segments = []
    for index, match in enumerate(matches):
        start = match.start()
        end = matches[index + 1].start() if index + 1 < len(matches) else len(normalized)
        chunk = normalized[start:end].strip(" ,.;")
        quantity = _cart_quantity(match.group(1))
        unit = _cart_unit(match.group(2))
        if not quantity or quantity <= 0:
            return {"error": "Please provide a valid quantity for each medicine."}
        # 'pairs' is only treated as packs in a quantity-led pharmacy order.
        segments.append({"text": chunk, "quantity": quantity, "unit": unit})
    return segments


def handle_multi_product_order(message, state, language):
    segments = parse_multi_product_order(message)
    if not segments:
        return None
    if isinstance(segments, dict):
        return segments["error"]

    resolved = []
    problems = []
    for segment in segments:
        chunk = re.sub(r"\b(?:and|also)\s*$", "", segment["text"], flags=re.IGNORECASE).strip()
        # Convert the recognized spoken inventory unit into the catalogue unit.
        chunk = re.sub(r"\bpairs?\b", "packs", chunk, flags=re.IGNORECASE)
        results = search_catalogue(chunk)
        if len(results) != 1:
            if not results:
                problems.append(f"I couldn't identify the medicine in: '{chunk}'.")
            else:
                names = ", ".join(
                    f"{m['brand_name']} {m['strength']} {m['dosage_form']}" for m in results
                )
                problems.append(f"Please clarify which product you mean in '{chunk}': {names}.")
            continue
        medicine = results[0]
        if medicine.get("stock_unit") != segment["unit"]:
            problems.append(
                f"{medicine['brand_name']} is sold in {medicine['stock_unit']}, not {segment['unit']}."
            )
        elif int(medicine["stock_quantity"]) <= 0:
            problems.append(f"{medicine['brand_name']} {medicine['strength']} is out of stock.")
        elif segment["quantity"] > int(medicine["stock_quantity"]):
            problems.append(
                f"Only {medicine['stock_quantity']} {medicine['stock_unit']} of {medicine['brand_name']} are available."
            )
        else:
            resolved.append((medicine, segment["quantity"], segment["unit"]))

    if problems:
        return "\n".join(problems + ["Please repeat or clarify the order. I have not changed your cart."])

    # Add all lines only after every requested item has passed validation.
    for medicine, quantity, unit in resolved:
        add_cart_item(state, medicine, quantity, unit)
        state["last_medicine"] = medicine
        state["last_language"] = language
    return format_cart(state, language)


def handle_cart_command(message, state):
    text = re.sub(r"[^a-z0-9\s]", " ", message.lower())
    text = re.sub(r"\s+", " ", text).strip()
    if re.fullmatch(r"(?:show|view|check) (?:my )?cart|cart|my order", text):
        return format_cart(state)
    if text in {"clear cart", "clear my cart", "empty cart", "cancel order"}:
        state["cart_items"] = []
        return "Your cart has been cleared. No sale was completed."

    remove_match = re.match(r"^(?:remove|delete)\s+(.+?)\s+(?:from )?(?:my )?cart$", text)
    if not remove_match:
        remove_match = re.match(r"^(?:remove|delete)\s+(.+)$", text)
    if remove_match:
        target = remove_match.group(1).strip()
        items = state.get("cart_items", [])
        kept = [item for item in items if normalize_name(target) not in normalize_name(item["medicine"].get("brand_name", ""))]
        if len(kept) == len(items):
            return f"I couldn't find {target} in your cart. Say 'show cart' to review it."
        state["cart_items"] = kept
        return format_cart(state)

    change_match = re.match(
        rf"^(?:change|update)\s+(.+?)\s+(?:to|into)\s+({r'\d+|one|two|three|four|five|six|seven|eight|nine|ten|eleven|twelve|thirteen|fourteen|fifteen|sixteen|seventeen|eighteen|nineteen|twenty'})\s+(packs?|packets?|bottles?)$",
        text
    )
    if change_match:
        target, qty_text, unit_text = change_match.groups()
        quantity = _cart_quantity(qty_text)
        unit = _cart_unit(unit_text)
        for item in state.get("cart_items", []):
            if normalize_name(target) in normalize_name(item["medicine"].get("brand_name", "")):
                medicine = item["medicine"]
                if unit != medicine.get("stock_unit"):
                    return f"{medicine['brand_name']} is sold in {medicine['stock_unit']}."
                if quantity > int(medicine["stock_quantity"]):
                    return f"Only {medicine['stock_quantity']} {unit} are available for {medicine['brand_name']}."
                item["quantity"] = quantity
                item["unit"] = unit
                return format_cart(state)
        return f"I couldn't find {target} in your cart."
    return None


# =========================================
# 13. MAIN CONVERSATION MANAGER
# =========================================

def get_ai_response(customer_message, state):

    state.setdefault("pending_quantity", None)
    state.setdefault("cart_items", [])

    message = customer_message.strip()

    if not message:
        return ""

    language = detect_language(message)

    cart_response = handle_cart_command(message, state)
    if cart_response is not None:
        return cart_response

    multi_response = handle_multi_product_order(message, state, language)
    if multi_response is not None:
        return multi_response

    # -------------------------------------
    # A. Medical safety check
    # -------------------------------------

    if is_medical_advice_request(message):

        return get_safety_response(message)

    # -------------------------------------
    # B. Catalogue browsing
    # -------------------------------------

    if is_catalogue_browse_request(message):
        state["pending_medicines"] = []
        state["pending_quantity"] = None
        state["pending_language"] = language
        state["last_language"] = language
        return get_catalogue_browse_response(language)

    # -------------------------------------
    # C. Resolve an existing product list
    # -------------------------------------

    if state["pending_medicines"]:

        selection_response = resolve_product_selection(
            message,
            state
        )

        if selection_response is not None:
            return selection_response

        new_search_term = extract_search_term(message)

        # If this is not a new medicine name,
        # ask the customer to select from the list.
        if not new_search_term:

            options = "; ".join(
                f"{index}. {item['brand_name']} {item['strength']} {item['dosage_form']}"
                for index, item in enumerate(state["pending_medicines"], start=1)
            )
            return get_message(
                state["pending_language"],
                f"I didn't catch which product you mean. Please say a product number "
                f"or its name/strength. Your options are: {options}.",
                f"Mujhe samajh nahi aaya aap ko kaunsa product chahiye. "
                f"Product ka number ya naam/strength batayein: {options}.",
                f"مجھے واضح نہیں ہوا کہ آپ کون سی دوا چاہتے ہیں۔ براہ کرم فہرست میں سے نمبر "
                f"یا دوا کا نام/طاقت بتائیں: {options}۔"
            )

        # Otherwise, continue and search for the new medicine.
        state["pending_quantity"] = None

    # -------------------------------------
    # C. Check for quantity follow-up
    # -------------------------------------

    search_term = extract_search_term(message)

    if not search_term:

        quantity_response = handle_quantity_followup(
            message,
            state
        )

        if quantity_response is not None:
            return quantity_response

        if extract_quantity(message):

            return get_message(
                language,
                "Please tell me which medicine you need.",
                "Please batayein aap ko konsi medicine chahiye.",
                "براہ کرم بتائیں آپ کو کون سی دوا چاہیے۔"
            )

        return get_message(
            language,
            "Please tell me the medicine name you want to check.",
            "Please medicine ka naam batayein.",
            "براہ کرم دوا کا نام بتائیں جس کی دستیابی چیک کرنی ہے۔"
        )

    # -------------------------------------
    # D. Start a new medicine search
    # -------------------------------------

    state["pending_medicines"] = []
    state["pending_quantity"] = None
    state["pending_language"] = language
    state["last_medicine"] = None
    state["last_language"] = language

    # -------------------------------------
    # E. Search SQLite catalogue
    # -------------------------------------

    try:

        results = search_catalogue(message)

    except Exception as error:

        print("Database error:", error)

        return get_message(
            language,
            "Sorry, I couldn't access the medicine catalogue.",
            "Maazrat, medicine catalogue access nahi ho saka.",
            "معذرت، دوا کا کیٹلاگ دستیاب نہیں ہے۔"
        )

    # If a number has no unit, accept it only when it exactly matches
    # the numeric strength of a uniquely matched catalogue product and
    # the remaining search term is just that product's brand. This lets
    # "Brufen 200" match the catalogue's Brufen 200 mg, but rejects
    # unclear phrases such as "Panadol 500 Henry" and "Panadol 510".
    unclear_number = extract_unlabelled_number(message)
    if unclear_number and results:
        brand_only = len(results) == 1 and normalize_name(search_term) == normalize_name(results[0].get("brand_name", ""))
        strength_numbers = re.findall(r"\d+(?:\.\d+)?", str(results[0].get("strength", ""))) if len(results) == 1 else []
        if brand_only and unclear_number in strength_numbers:
            pass
        else:
            return get_message(
                language,
                f"I heard the number {unclear_number}, but not a clear strength unit. Please repeat the strength with its unit, such as mg or ml. I won't guess the medicine strength.",
                f"Maine number {unclear_number} suna hai, lekin strength ki unit clear nahi. Barah-e-karam mg ya ml ke sath strength dobara batayein. Main strength ka andaza nahi lagaunga.",
                f"میں نے نمبر {unclear_number} سنا ہے، لیکن طاقت کی اکائی واضح نہیں۔ براہ کرم mg یا ml کے ساتھ دوبارہ بتائیں۔ میں طاقت کا اندازہ نہیں لگاؤں گا۔"
            )

    # -------------------------------------
    # F. No matching product
    # -------------------------------------

    if not results:

        # If speech included a number but the unit/remaining words were unclear,
        # check whether a recognizable catalogue brand was still spoken. This
        # catches cases such as "Panadol 500 Henry" without guessing the unit.
        unclear_number = extract_unlabelled_number(message)
        if unclear_number:
            for word in extract_search_term(message).split():
                try:
                    possible = search_medicine(
                        search_term=word,
                        strength=None,
                        dosage_form=None
                    )
                    possible = filter_by_requested_brand(possible, word)
                except Exception:
                    possible = []
                if possible:
                    return get_message(
                        language,
                        f"I heard {possible[0].get('brand_name', 'the medicine')} and the number {unclear_number}, but the strength unit or remaining words were unclear. Please repeat the strength with its unit, such as mg or ml. I won't guess.",
                        f"Maine {possible[0].get('brand_name', 'medicine')} aur number {unclear_number} suna hai, lekin strength ki unit clear nahi. Barah-e-karam mg ya ml ke sath dobara batayein. Main andaza nahi lagaunga.",
                        f"میں نے {possible[0].get('brand_name', 'دوا')} اور نمبر {unclear_number} سنا ہے، لیکن طاقت کی اکائی واضح نہیں۔ براہ کرم mg یا ml کے ساتھ دوبارہ بتائیں۔ میں اندازہ نہیں لگاؤں گا۔"
                    )

        # If the brand exists but the requested dosage form does not,
        # explain the catalogue's actual form rather than saying the brand
        # itself is missing.
        requested_form = extract_explicit_form(message)
        if requested_form:
            base_term = extract_search_term(message)
            try:
                broad_results = search_medicine(
                    search_term=base_term,
                    strength=None,
                    dosage_form=None
                ) if base_term else []
                broad_results = filter_by_requested_brand(broad_results, base_term)
                requested_strength = extract_explicit_strength(message)
                if requested_strength:
                    broad_results = [
                        item for item in broad_results
                        if strength_matches(requested_strength, item.get("strength", ""))
                    ]
            except Exception:
                broad_results = []

            if broad_results:
                mismatch_response = get_form_mismatch_response(
                    broad_results, requested_form, language
                )
                if mismatch_response:
                    state["pending_medicines"] = broad_results
                    return mismatch_response

        return get_message(
            language,
            "Sorry, I couldn't find that product in our catalogue. "
            "Please check the medicine name.",
            "Maazrat, yeh product catalogue mein nahi mila. "
            "Please medicine ka naam check karein.",
            "معذرت، یہ دوا ہمارے کیٹلاگ میں نہیں ملی۔ "
            "براہ کرم دوا کا نام چیک کریں۔"
        )

    # -------------------------------------
    # G. Multiple matching products
    # -------------------------------------

    if len(results) > 1:

        state["pending_medicines"] = results
        state["pending_quantity"] = extract_quantity(message)

        return format_product_list(
            results,
            language
        )

    # -------------------------------------
    # H. Exactly one matching product
    # -------------------------------------

    medicine = results[0]

    state["last_medicine"] = medicine

    # Extract requested quantity
    quantity = extract_quantity(
        message,
        default_unit=medicine["stock_unit"]
    )

    response = format_single_product(medicine, language, quantity)
    if quantity and quantity.get("unit") == medicine.get("stock_unit") and int(quantity["quantity"]) <= int(medicine["stock_quantity"]):
        add_cart_item(state, medicine, int(quantity["quantity"]), quantity["unit"])
        response += "\n\n" + format_cart(state, language)
    return response


# =========================================
# 14. RUN TEXT-BASED ASSISTANT
# =========================================

def main():

    state = {
        "pending_medicines": [],
        "pending_language": "english",
        "pending_quantity": None,
        "last_medicine": None,
        "last_language": "english",
        "cart_items": []
    }

    print("\n===================================")
    print(f"       {PHARMACY_NAME.upper()}")
    print("===================================")

    print("Type 'exit' to stop.\n")

    while True:

        customer_message = input("Customer: ").strip()

        if customer_message.lower() in ["exit", "quit"]:

            print("\nAssistant: Allah Hafiz!")
            break

        if not customer_message:
            continue

        if customer_message.lower() in [
            "hi",
            "hello",
            "salam",
            "assalam o alaikum"
        ]:

            language = detect_language(customer_message)

            print(
                "\nAssistant: "
                + get_message(
                    language,
                    "Hello! How can I help you today?",
                    "Assalam o alaikum! Main aap ki kya madad kar sakta hoon?",
                    "السلام علیکم! میں آپ کی کیا مدد کر سکتا ہوں؟"
                )
                + "\n"
            )

            continue

        try:

            answer = get_ai_response(
                customer_message,
                state
            )

            print(f"\nAssistant: {answer}\n")

        except Exception as error:

            print("\nError:", error)
            print("Please check your database and catalogue code.\n")


if __name__ == "__main__":
    main()
