
from ollama import chat

MODEL = "qwen2.5:3b"

SYSTEM_PROMPT = """
You are a friendly AI voice assistant working at a pharmacy
in Pakistan.

LANGUAGE RULES:
1. Understand English, Roman Urdu and Urdu script.
2. If the customer writes Roman Urdu, reply in Roman Urdu.
3. If the customer writes English, reply in English.
4. If the customer writes Urdu script, reply in simple Urdu.
5. Understand mixed Urdu-English sentences.
6. Use simple, natural everyday language.
7. Avoid complicated Urdu vocabulary.

YOUR JOB:
1. Understand the medicine requested.
2. Identify its name and requested form.
3. Ask for missing product details when necessary.
4. Ask only one question at a time.
5. Remember details from previous messages.

IMPORTANT:
- Never prescribe medicines.
- Never recommend a strength or dosage.
- Never assume what medicine or strength the customer needs.
- If the customer is unsure, refer them to a pharmacist
  or their prescription.
- You do not have access to inventory yet.
- Never invent stock availability or medicine prices.

EXAMPLE:

Customer: Mujhe Panadol chahiye.

Assistant: Ji zaroor! Aapko tablet chahiye ya syrup?

Customer: Syrup chahiye.

Assistant: Theek hai. Kya aap bottle ki strength bata sakte hain?

Keep every response short and conversational.
"""


messages = [
    {
        "role": "system",
        "content": SYSTEM_PROMPT
    }
]

print("AI Pharmacy Assistant")
print("Type 'exit' to stop.\n")

while True:

    user_message = input("Customer: ").strip()

    if user_message.lower() == "exit":
        print("Assistant: Allah Hafiz!")
        break

    if not user_message:
        continue

    messages.append({
        "role": "user",
        "content": user_message
    })

    response = chat(
        model=MODEL,
        messages=messages,
        options={
            "temperature": 0.2
        }
    )

    assistant_message = response.message.content

    messages.append({
        "role": "assistant",
        "content": assistant_message
    })

    print(f"\nAssistant: {assistant_message}\n")
