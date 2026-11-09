
import os
import json
from dotenv import load_dotenv
from openai import OpenAI

# --------------------------------------------------
# 1. Configuration
# --------------------------------------------------

load_dotenv()

client = OpenAI(api_key=os.getenv("OPENAI_API_KEY"))
MODEL = os.getenv("OPENAI_MODEL", "gpt-6-astra")


# --------------------------------------------------
# 2. Demo medicine catalogue
# Replace these sample records with real store data.
# These prices and stock figures are fictional.
# --------------------------------------------------

MEDICINES = [
    {
        "name": "Panadol",
        "generic_name": "Paracetamol",
        "strength": "500 mg",
        "form": "tablet",
        "stock": 120,
        "price": 30,
        "location": "Shelf A1"
    },
    {
        "name": "Panadol",
        "generic_name": "Paracetamol",
        "strength": "120 mg/5 ml",
        "form": "syrup",
        "stock": 25,
        "price": 180,
        "location": "Shelf B2"
    },
    {
        "name": "Brufen",
        "generic_name": "Ibuprofen",
        "strength": "200 mg",
        "form": "tablet",
        "stock": 45,
        "price": 55,
        "location": "Shelf A3"
    },
    {
        "name": "Augmentin",
        "generic_name": "Amoxicillin + Clavulanic Acid",
        "strength": "625 mg",
        "form": "tablet",
        "stock": 0,
        "price": 450,
        "location": "Shelf C1"
    }
]


# --------------------------------------------------
# 3. Python function: Search the medicine catalogue
# --------------------------------------------------

def search_medicine_catalog(
    medicine_name,
    strength,
    dosage_form
):
    """Search catalogue records; never invent inventory data."""

    search_name = medicine_name.lower().strip()

    matches = []

    for medicine in MEDICINES:

        names = [
            medicine["name"].lower(),
            medicine["generic_name"].lower()
        ]

        # Match the requested medicine or generic name
        if not any(
            search_name in name or name in search_name
            for name in names
        ):
            continue

        # Apply strength filter if customer specified it
        if strength and strength.lower() not in medicine["strength"].lower():
            continue

        # Apply dosage-form filter if customer specified it
        if dosage_form and dosage_form.lower() != medicine["form"].lower():
            continue

        matches.append(medicine)

    return {
        "results_found": len(matches),
        "medicines": matches
    }


# --------------------------------------------------
# 4. Give the AI permission to call our search function
# --------------------------------------------------

TOOLS = [
    {
        "type": "function",
        "name": "search_medicine_catalog",
        "description": (
            "Search the pharmacy's catalogue for a medicine and return "
            "verified product details, stock, price and shelf location. "
            "Use this only when the customer asks about a medicine. "
            "Never invent or assume catalogue information."
        ),
        "strict": True,
        "parameters": {
            "type": "object",
            "properties": {
                "medicine_name": {
                    "type": "string",
                    "description": "Medicine brand or generic name."
                },
                "strength": {
                    "type": ["string", "null"],
                    "description": "Requested strength, e.g. 500 mg, or null if unspecified."
                },
                "dosage_form": {
                    "type": ["string", "null"],
                    "description": "Tablet, syrup, capsule, etc., or null if unspecified."
                }
            },
            "required": [
                "medicine_name",
                "strength",
                "dosage_form"
            ],
            "additionalProperties": False
        }
    }
]


# --------------------------------------------------
# 5. Assistant behaviour and safety instructions
# --------------------------------------------------

INSTRUCTIONS = """
You are a friendly AI voice assistant for a pharmacy.

LANGUAGE:
- Understand Urdu, English and mixed Urdu-English (Roman Urdu included).
- Reply in the customer's language and style.
- Keep replies short and natural because they will be spoken aloud.
- Do not force the customer to speak only one language.

YOUR TASK:
1. Understand which medicine the customer is asking about.
2. Identify the brand/generic name, strength and dosage form when provided.
3. Ask a short follow-up question when important details are missing.
4. Search the catalogue when appropriate.
5. Report only the stock, price and location returned by the catalogue.
6. If multiple variants match, ask the customer which one they mean.
7. If no record matches, say you could not find it and offer pharmacist assistance.

IMPORTANT SAFETY:
- Never prescribe a medicine or recommend a strength or dosage.
- Never decide which medicine a customer should take.
- If the customer is unsure about strength, ask them to check their
  prescription or speak with the pharmacist.
- Never automatically substitute one medicine for another.
- Refer medical questions, prescription uncertainty and clinical decisions
  to a qualified pharmacist.
- Do not claim a medicine is available unless the catalogue confirms it.
- Do not change stock or complete a sale.

CONVERSATION:
- Remember details the customer has already provided.
- Do not ask the same question again unnecessarily.
- Ask one clear question at a time.
"""


# --------------------------------------------------
# 6. Execute the Python function requested by the AI
# --------------------------------------------------

def execute_tool(tool_call):

    if tool_call.name == "search_medicine_catalog":

        arguments = json.loads(tool_call.arguments)

        return search_medicine_catalog(**arguments)

    return {"error": "Unknown function requested."}


# --------------------------------------------------
# 7. Main conversation engine
# --------------------------------------------------

def get_ai_response(conversation_history, customer_message):

    conversation_history.append({
        "role": "user",
        "content": customer_message
    })

    response = client.responses.create(
        model=MODEL,
        instructions=INSTRUCTIONS,
        tools=TOOLS,
        input=conversation_history
    )

    # Handle function calls until the AI has a final spoken reply
    while True:

        conversation_history.extend(response.output)

        tool_calls = [
            item for item in response.output
            if item.type == "function_call"
        ]

        if not tool_calls:
            break

        for tool_call in tool_calls:

            result = execute_tool(tool_call)

            conversation_history.append({
                "type": "function_call_output",
                "call_id": tool_call.call_id,
                "output": json.dumps(result, ensure_ascii=False)
            })

        response = client.responses.create(
            model=MODEL,
            instructions=INSTRUCTIONS,
            tools=TOOLS,
            input=conversation_history
        )

    return response.output_text


# --------------------------------------------------
# 8. Run a text-based conversation
# --------------------------------------------------

def main():

    history = []

    print("Pharmacy Assistant: Assalam-o-Alaikum! How can I help you?")
    print("(Type 'exit' to end the conversation.)\n")

    while True:

        customer_message = input("Customer: ").strip()

        if customer_message.lower() in ["exit", "quit"]:
            print("Assistant: Thank you! Allah Hafiz.")
            break

        if not customer_message:
            continue

        try:
            answer = get_ai_response(history, customer_message)
            print(f"\nAssistant: {answer}\n")

        except Exception as error:
            print("\nSomething went wrong:", error, "\n")


if __name__ == "__main__":
    main()
