
import sqlite3
from pathlib import Path

# Database is stored in the project folder
DB_PATH = Path(__file__).with_name("pharmacy.db")


# =========================================
# 1. DATABASE CONNECTION
# =========================================

def get_connection():
    connection = sqlite3.connect(DB_PATH)
    connection.row_factory = sqlite3.Row
    return connection


# =========================================
# 2. CREATE DATABASE
# =========================================

def create_database():

    with get_connection() as connection:

        connection.execute("""
            CREATE TABLE IF NOT EXISTS medicines (

                id INTEGER PRIMARY KEY AUTOINCREMENT,

                brand_name TEXT NOT NULL,
                generic_name TEXT NOT NULL,

                strength TEXT NOT NULL,
                dosage_form TEXT NOT NULL,
                pack_size TEXT NOT NULL,

                price_pkr REAL NOT NULL,
                stock_quantity INTEGER NOT NULL DEFAULT 0,

                shelf_location TEXT,

                sku TEXT UNIQUE NOT NULL,

                stock_unit TEXT NOT NULL DEFAULT 'packs'
            )
        """)

        # Migration for databases created with the older schema
        columns = {
            row["name"]
            for row in connection.execute(
                "PRAGMA table_info(medicines)"
            ).fetchall()
        }

        if "stock_unit" not in columns:
            connection.execute("""
                ALTER TABLE medicines
                ADD COLUMN stock_unit TEXT NOT NULL DEFAULT 'packs'
            """)

        # Syrup stock is counted in individual bottles
        connection.execute("""
            UPDATE medicines
            SET stock_unit = 'bottles'
            WHERE sku = 'PAN-120-SYR'
        """)

    print("Medicine database is ready!")


# =========================================
# 3. INSERT SAMPLE MEDICINES
# =========================================

def add_sample_medicines():

    sample_medicines = [

        (
            "Panadol",
            "Paracetamol",
            "500 mg",
            "Tablet",
            "10 tablets",
            30,
            120,
            "Shelf A1",
            "PAN-500-TAB",
            "packs"
        ),

        (
            "Panadol Extra",
            "Paracetamol + Caffeine",
            "500 mg + 65 mg",
            "Tablet",
            "10 tablets",
            45,
            80,
            "Shelf A1",
            "PAN-EXTRA-TAB",
            "packs"
        ),

        (
            "Panadol",
            "Paracetamol",
            "120 mg/5 ml",
            "Syrup",
            "60 ml bottle",
            180,
            25,
            "Shelf B2",
            "PAN-120-SYR",
            "bottles"
        ),

        (
            "Brufen",
            "Ibuprofen",
            "200 mg",
            "Tablet",
            "10 tablets",
            55,
            45,
            "Shelf A3",
            "BRU-200-TAB",
            "packs"
        ),

        (
            "Augmentin",
            "Amoxicillin + Clavulanic Acid",
            "625 mg",
            "Tablet",
            "6 tablets",
            450,
            0,
            "Shelf C1",
            "AUG-625-TAB",
            "packs"
        )
    ]

    with get_connection() as connection:

        connection.executemany("""
            INSERT OR IGNORE INTO medicines (
                brand_name,
                generic_name,
                strength,
                dosage_form,
                pack_size,
                price_pkr,
                stock_quantity,
                shelf_location,
                sku,
                stock_unit
            )
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, sample_medicines)

    print("Sample medicines inserted!")


# =========================================
# 4. SEARCH MEDICINES
# =========================================

def search_medicine(
    search_term,
    strength=None,
    dosage_form=None
):

    if not isinstance(search_term, str) or not search_term.strip():
        return []

    query = """
        SELECT *
        FROM medicines
        WHERE (
            brand_name LIKE ?
            OR generic_name LIKE ?
        )
    """

    search_pattern = f"%{search_term.strip()}%"

    parameters = [
        search_pattern,
        search_pattern
    ]

    # Optional strength filter
    if strength and strength.strip():

        query += " AND strength LIKE ?"
        parameters.append(f"%{strength.strip()}%")

    # Optional dosage form filter
    if dosage_form and dosage_form.strip():

        query += " AND LOWER(dosage_form) = LOWER(?)"
        parameters.append(dosage_form.strip())

    query += " ORDER BY brand_name, strength"

    with get_connection() as connection:

        results = connection.execute(
            query,
            parameters
        ).fetchall()

    # Convert database rows into dictionaries
    medicines = []

    for row in results:

        medicine = dict(row)

        # Explicit availability field for the AI assistant
        medicine["is_available"] = (
            medicine["stock_quantity"] > 0
        )

        # Explicit price label
        medicine["price_per_unit_pkr"] = medicine["price_pkr"]

        medicines.append(medicine)

    return medicines


# =========================================
# 5. DISPLAY SEARCH RESULTS
# =========================================

def display_results(results):

    if not results:
        print("\nNo matching medicine found.")
        return

    for medicine in results:

        print("\n------------------------------")

        print("Brand:", medicine["brand_name"])
        print("Generic:", medicine["generic_name"])
        print("Strength:", medicine["strength"])
        print("Form:", medicine["dosage_form"])
        print("Pack size:", medicine["pack_size"])

        print(
            f"Price per {medicine['stock_unit'][:-1] if medicine['stock_unit'] == 'bottles' else 'pack'}:",
            f"PKR {medicine['price_pkr']:.2f}"
        )

        print(
            f"Stock ({medicine['stock_unit']}):",
            medicine["stock_quantity"]
        )

        if medicine["is_available"]:
            print("Availability: IN STOCK")
        else:
            print("Availability: OUT OF STOCK")

        print("Location:", medicine["shelf_location"])

    print("------------------------------")


# =========================================
# 6. MAIN PROGRAM
# =========================================

if __name__ == "__main__":

    create_database()

    add_sample_medicines()

    print("\nMedicine Catalogue Search")

    while True:

        medicine_name = input(
            "\nEnter medicine name (or exit): "
        ).strip()

        if medicine_name.lower() == "exit":
            print("Goodbye!")
            break

        if not medicine_name:
            print("Please enter a medicine name.")
            continue

        strength = input(
            "Enter strength (press Enter to skip): "
        ).strip()

        dosage_form = input(
            "Enter form (press Enter to skip): "
        ).strip()

        results = search_medicine(
            search_term=medicine_name,
            strength=strength or None,
            dosage_form=dosage_form or None
        )

        display_results(results)