import sqlite3
from pathlib import Path
import re
import pandas as pd

DB_PATH = Path("shop_database.db")
DATA_DIR = Path("OneDrive - University of Plymouth/Data Science/COMP5000/Coursework")
FILE_CSV = DATA_DIR / "file.csv"
CUSTOMER_CSV = DATA_DIR / "customer.csv"
CREDITCARD_CSV = DATA_DIR / "creditCard.csv"


SCHEMA_SQL = """
PRAGMA foreign_keys = ON;

-- 1) Customer
CREATE TABLE IF NOT EXISTS Customer (
    CustomerID      INTEGER PRIMARY KEY,
    Name            TEXT,
    Gender          TEXT,
    Location        TEXT,
    Tenure_Months   INTEGER,
    Street          TEXT,
    City            TEXT,
    Postcode        TEXT
);

-- 2) Product
CREATE TABLE IF NOT EXISTS Product (
    Product_SKU          TEXT PRIMARY KEY,
    Product_Description  TEXT,
    Product_Category     TEXT
);

-- 3) Transactions
CREATE TABLE IF NOT EXISTS Transactions (
    Transaction_ID     INTEGER PRIMARY KEY,
    CustomerID         INTEGER NOT NULL,
    Transaction_Date   TEXT,   -- store dates as ISO text: YYYY-MM-DD or YYYY-MM-DD HH:MM:SS
    Coupon_Code        TEXT,
    Coupon_Status      TEXT,
    Delivery_Charges   REAL,
    Month              TEXT,

    FOREIGN KEY (CustomerID) REFERENCES Customer(CustomerID)
        ON UPDATE CASCADE
        ON DELETE RESTRICT
);

-- 4) Credit_Card (ONE card per customer)
CREATE TABLE IF NOT EXISTS Credit_Card (
    CustomerID           INTEGER PRIMARY KEY,
    CreditCard_number    TEXT NOT NULL,
    CreditCard_provider  TEXT,

    FOREIGN KEY (CustomerID) REFERENCES Customer(CustomerID)
        ON UPDATE CASCADE
        ON DELETE CASCADE
);

-- 5) Transaction_Item (junction table / line items)
-- Composite PK: (Transaction_ID, Product_SKU)
CREATE TABLE IF NOT EXISTS Transaction_Item (
    Transaction_ID   INTEGER NOT NULL,
    Product_SKU      TEXT NOT NULL,
    Quantity         INTEGER,
    Avg_Price        REAL,
    Discount_pct     REAL,
    GST              REAL,

    PRIMARY KEY (Transaction_ID, Product_SKU),

    FOREIGN KEY (Transaction_ID) REFERENCES Transactions(Transaction_ID)
        ON UPDATE CASCADE
        ON DELETE CASCADE,

    FOREIGN KEY (Product_SKU) REFERENCES Product(Product_SKU)
        ON UPDATE CASCADE
        ON DELETE RESTRICT
);
"""

def create_database(db_path: Path) -> None:
    """Create the SQLite database file and all tables defined in SCHEMA_SQL"""
    conn = sqlite3.connect(db_path)
    try:
        # Ensure FK constraints are enforced for this connection
        conn.execute("PRAGMA foreign_keys = ON;")

        #Create all tables
        conn.executescript(SCHEMA_SQL)
        conn.commit()

        print(f"Database created/updated successfully: {db_path.resolve()}")
    finally:
        conn.close()



#Cleaning helpers

def clean_name(name: object) -> str | None:
    """Remove non-letter characters and normalise whitespace"""
    if pd.isna(name):
        return None
    s = str(name).strip()
    # Keep letters and spaces only
    s = re.sub(r"[^A-Za-z\s]", "", s)
    s = " ".join(s.split())
    return s if s else None


def normalise_provider(provider: object) -> str | None:
    """Standardise provider values into consistent categories"""
    if pd.isna(provider):
        return None
    p = str(provider).strip().upper()

    #Remove obvious noise characters
    p = re.sub(r"[^A-Z\s]", " ", p)
    p = " ".join(p.split())

    if "VISA" in p:
        return "VISA"
    if "MAST" in p:
        return "MASTERCARD"
    if "AMER" in p or "AMEX" in p:
        return "AMERICAN EXPRESS"
    if "DISC" in p:
        return "DISCOVER"
    if "JCB" in p:
        return "JCB"
    if "MAEST" in p:
        return "MAESTRO"
    if "DINE" in p or "CLUB" in p or "CARTE" in p or "BLANCHE" in p:
        return "DINERS CLUB/CARTE BLANCHE"
    if p in {"NA", "N A", ""}:
        return None
    return p


def clean_card_number(x: object) -> str | None:
    """Ensure card numbers are stored as TEXT and not corrupted by scientific notation. Removes trailing .0 and whitespace."""
    if pd.isna(x):
        return None
    
    s= str(x).strip()

    #convert common placeholders to None
    if s.upper() in {"NA", "N/A", ""}:
        return None
    
    #If the value looks like a float string with .0 at end, drop it
    s = re.sub(r"\.0$", "", s)

    #remove spaces
    s = s.replace(" ", "")

    #If it is in scientific notation, pandas often gives strings like '6.30422E+11'
    #Keep as is but remove trailing decimals.
    if re.search(r"[eE][+-]?\d+", s):
        #Can try to expand without losing precision by using Decimal via pandas
        try:
            from decimal import Decimal, InvalidOperation
            s = format(Decimal(s), "f").rstrip("0").rstrip(".")
        except Exception:
            #If expansion fails, keep original string
            pass
    
    #After cleanup, ensure its digits only if possible
    digits = re.sub(r"\D", "", s)
    if digits:
        return digits
    return None


def to_int_series(series: pd.Series) -> pd.Series:
    return pd.to_numeric(series, errors="coerce").astype("Int64")

def to_float_series(series: pd.Series) -> pd.Series:
    return pd.to_numeric(series, errors="coerce").astype(float)

def to_iso_date(series: pd.Series) -> pd.Series:
    """Parse dates and store as ISO 8601 text"""
    dt = pd.to_datetime(series, errors="coerce", dayfirst=False)
    #Store as ISO string; keep NaT as None
    return dt.dt.strftime("%Y-%m-%d %H:%M:%S").where(~dt.isna(), None)




#Load and Clean

def load_and_clean_file_csv(path: Path) -> pd.DataFrame:
    df = pd.read_csv(path)

    #drop rows where key identifiers are missing
    key_cols = ["CustomerID", "Transaction_ID", "Product_SKU"]
    for col in key_cols:
        if col not in df.columns:
            raise ValueError(f"file.csv missing expected column: {col}")
        
    before = len(df)
    df = df.dropna(subset=key_cols)
    after = len(df)
    print(f"[file.csv] Dropped {before - after} rows with missing identifiers (CustomerID/Transaction_ID/Product_SKU).")


    #Coerce types
    df["CustomerID"] = to_int_series(df["CustomerID"])
    df["Transaction_ID"] = to_int_series(df["Transaction_ID"])
    df["Quantity"] = to_int_series(df["Quantity"]) if "Quantity" in df.columns else pd.Series(dtype="Int64")

    for col in ["Avg_Price", "Delivery_Charges", "GST", "Discount_pct", "Offline_Spend", "Online_Spend"]:
        if col in df.columns:
            df[col] = to_float_series(df[col])

    #Dates
    if "Transaction_Date" in df.columns:
        df["Transaction_Date"] = to_iso_date(df["Transaction_Date"])
    
    #Drop date column
    if "Date" in df.columns:
        df = df.drop(columns=["Date"])

    #remove rows where IDs became null after coercion
    df = df.dropna(subset=["CustomerID", "Transaction_ID", "Product_SKU"])

    #Normalise Product_SKU to string
    df["Product_SKU"] = df["Product_SKU"].astype(str).str.strip()

    #Basic string cleanup
    for c in ["Product_Description", "Product_Category", "Coupon_Status", "Coupon_Code", "Month", "Location", "Gender"]:
        if c in df.columns:
            df[c] = df[c].astype(str).str.strip().replace({"nan": None, "NA": None, "N/A": None})

    return df


def load_and_clean_customer_csv(path: Path) -> pd.DataFrame:
    c = pd.read_csv(path)
    if "CustomerID" not in c.columns:
        raise ValueError("customer.csv missing CustomerID")

    c["CustomerID"] = to_int_series(c["CustomerID"])
    c["Name"] = c.get("Name", pd.Series([None] * len(c))).apply(clean_name)


    #String cleaning for address fields
    for col in ["Street", "City", "Postcode"]:
        if col in c.columns:
            c[col] = c[col].astype(str).str.strip().replace({"nan": None, "NA": None, "N/A": None})
    
    #Drop rows with no customerID
    c = c.dropna(subset=["CustomerID"])

    return c


def load_and_clean_creditcard_csv(path: Path) -> pd.DataFrame:
    cc = pd.read_csv(path)

    #Drop index column
    if "X" in cc.columns:
        cc = cc.drop(columns=["X"])

    #Clean name
    if "Name" not in cc.columns:
        raise ValueError("creditCard.csv missing Name")
    cc["Name_clean"] = cc["Name"].apply(clean_name)

    #Clean card numbers
    if "CreditCard_number" not in cc.columns:
        raise ValueError("creditCard.csv missing CreditCard_number")
    cc["CreditCard_number"] = cc["CreditCard_number"].apply(clean_card_number)

    #Normalise providers
    if "CreditCard_provider" in cc.columns:
        cc["CreditCard_provider"] = cc["CreditCard_provider"].apply(normalise_provider)
    else:
        cc["CreditCard_provider"] = None

    #Drop rows without a usable card number
    before = len(cc)
    cc = cc.dropna(subset=["CreditCard_number"])
    after = len(cc)
    print(f"[creditCard.csv] Dropped {before - after} rows with missing/invalid CreditCard_number.")

    return cc



#Build customer master

def build_customer_master(customers: pd.DataFrame, file_df: pd.DataFrame) -> pd.DataFrame:
    """Merge name/address from customer.csv with gender/location/tenure from file.csv"""
    
    # Get one row per CustomerID from file.csv for demographic fields
    demo_cols = ["CustomerID", "Gender", "Location", "Tenure_Months"]
    demo = file_df[demo_cols].copy()

    #Coerce types
    demo["CustomerID"] = to_int_series(demo["CustomerID"])
    demo["Tenure_Months"] = to_int_series(demo["Tenure_Months"]) if "Tenure_Months" in demo.columns else pd.Series(dtype="Int64")

    #Reduce to one row per customer (prefer first occurrence)
    demo = demo.sort_values("CustomerID").drop_duplicates(subset=["CustomerID"], keep="first")

    #Merge with customers. Keep all customers known from both sources
    master = pd.merge(customers, demo, on="CustomerID", how="outer")

    #Ensure consistent columns exist
    for col in ["Name", "Street", "City", "Postcode", "Gender", "Location", "Tenure_Months"]:
        if col not in master.columns:
            master[col] = None

    return master



#Map credit cards to customerID (by name)

def map_cards_to_customer_ids(cc: pd.DataFrame, customer_master: pd.DataFrame) -> pd.DataFrame:
    """creditCard.csv lacks CUstomerID, so match on cleaned name."""
    cust_names = customer_master[["CustomerID", "Name"]].copy()
    cust_names["Name_clean"] = cust_names["Name"].apply(clean_name)

    #Drop customers with no name as they cannot be matched
    cust_names = cust_names.dropna(subset=["Name_clean"])

    #Merge cards with customers using cleaned name
    merged = pd.merge(
        cc,
        cust_names[["CustomerID", "Name_clean"]],
        on="Name_clean",
        how="inner"
    )

    #One card per customer, keep the first card per CustomerID
    #Prefer rows that have a provider, then keep first
    merged["provider_present"] = merged["CreditCard_provider"].notna().astype(int)
    merged = merged.sort_values(["CustomerID", "provider_present"], ascending=[True, False])
    merged = merged.drop_duplicates(subset=["CustomerID"], keep="first")

    #Keep only columns needed for database
    out = merged[["CustomerID", "CreditCard_number", "CreditCard_provider"]].copy()
    return out



#Database insert helpers

def insert_many(conn: sqlite3.Connection, sql: str, rows: list[tuple]) -> None:
    cur = conn.cursor()
    cur.executemany(sql, rows)


def populate_database(
    db_path: Path,
    customer_master: pd.DataFrame,
    file_df: pd.DataFrame,
    cards_mapped: pd.DataFrame
) -> None:
    conn = sqlite3.connect(db_path)
    try:
        conn.execute("PRAGMA foreign_keys = ON;")

        
        #Insert customer
        
        cust = customer_master.copy()
        cust = cust.dropna(subset=["CustomerID"])
        cust_rows = [
            (
                int(row.CustomerID),
                row.Name if pd.notna(row.Name) else None,
                row.Gender if pd.notna(row.Gender) else None,
                row.Location if pd.notna(row.Location) else None,
                int(row.Tenure_Months) if pd.notna(row.Tenure_Months) else None,
                row.Street if pd.notna(row.Street) else None,
                row.City if pd.notna(row.City) else None,
                row.Postcode if pd.notna(row.Postcode) else None,
            )
            for row in cust.itertuples(index=False)
        ]

        insert_many(
            conn,
            """
            INSERT OR REPLACE INTO Customer
            (CustomerID, Name, Gender, Location, Tenure_Months, Street, City, Postcode)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?);
            """,
            cust_rows
        )
        print(f"[DB] Inserted/updated Customer: {len(cust_rows)} rows")

    
        #Insert product

        prod_cols = ["Product_SKU", "Product_Description", "Product_Category"]
        products = file_df[prod_cols].copy()
        products["Product_SKU"] = products["Product_SKU"].astype(str).str.strip()
        products = products.dropna(subset=["Product_SKU"]).drop_duplicates(subset=["Product_SKU"], keep="first")

        prod_rows = [
            (
                row.Product_SKU,
                row.Product_Description if pd.notna(row.Product_Description) else None,
                row.Product_Category if pd.notna(row.Product_Category) else None,
            )
            for row in products.itertuples(index=False)
        ]

        insert_many(
            conn,
            """
            INSERT OR REPLACE INTO Product
            (Product_SKU, Product_Description, Product_Category)
            VALUES (?, ?, ?);
            """,
            prod_rows
        )
        print(f"[DB] Inserted/updated Product: {len(prod_rows)} rows")

        
        #Insert Transactions

        tx_cols = ["Transaction_ID", "CustomerID", "Transaction_Date", "Coupon_Code", "Coupon_Status", "Delivery_Charges", "Month"]
        tx = file_df[tx_cols].copy()
        tx = tx.dropna(subset=["Transaction_ID", "CustomerID"]).drop_duplicates(subset=["Transaction_ID"], keep="first")

        tx_rows = [
            (
                int(row.Transaction_ID),
                int(row.CustomerID),
                row.Transaction_Date if pd.notna(row.Transaction_Date) else None,
                row.Coupon_Code if pd.notna(row.Coupon_Code) else None,
                row.Coupon_Status if pd.notna(row.Coupon_Status) else None,
                float(row.Delivery_Charges) if pd.notna(row.Delivery_Charges) else None,
                row.Month if pd.notna(row.Month) else None,
            )
            for row in tx.itertuples(index=False)
        ]

        insert_many(
            conn,
            """
            INSERT OR REPLACE INTO Transactions
            (Transaction_ID, CustomerID, Transaction_Date, Coupon_Code, Coupon_Status, Delivery_Charges, Month)
            VALUES (?, ?, ?, ?, ?, ?, ?);
            """,
            tx_rows
        )
        print(f"[DB] Inserted/updated Transactions: {len(tx_rows)} rows")

        
        #Insert Transaction_Item

        item_cols = ["Transaction_ID", "Product_SKU", "Quantity", "Avg_Price", "Discount_pct", "GST"]
        items = file_df[item_cols].copy()
        items["Product_SKU"] = items["Product_SKU"].astype(str).str.strip()
        items = items.dropna(subset=["Transaction_ID", "Product_SKU"])
        items = items.drop_duplicates(subset=["Transaction_ID", "Product_SKU"], keep="first")

        item_rows = [
            (
                int(row.Transaction_ID),
                row.Product_SKU,
                int(row.Quantity) if pd.notna(row.Quantity) else None,
                float(row.Avg_Price) if pd.notna(row.Avg_Price) else None,
                float(row.Discount_pct) if pd.notna(row.Discount_pct) else None,
                float(row.GST) if pd.notna(row.GST) else None,
            )
            for row in items.itertuples(index=False)
        ]

        insert_many(
            conn,
            """
            INSERT OR REPLACE INTO Transaction_Item
            (Transaction_ID, Product_SKU, Quantity, Avg_Price, Discount_pct, GST)
            VALUES (?, ?, ?, ?, ?, ?);
            """,
            item_rows
        )
        print(f"[DB] Inserted/updated Transaction_Item: {len(item_rows)} rows")

    
        #Insert Credit_Card (1 per customer)

        if cards_mapped is not None and len(cards_mapped) > 0:
            card_rows = [
                (
                    int(row.CustomerID),
                    row.CreditCard_number,
                    row.CreditCard_provider if pd.notna(row.CreditCard_provider) else None,
                )
                for row in cards_mapped.itertuples(index=False)
            ]

            insert_many(
                conn,
                """
                INSERT OR REPLACE INTO Credit_Card
                (CustomerID, CreditCard_number, CreditCard_provider)
                VALUES (?, ?, ?);
                """,
                card_rows
            )
            print(f"[DB] Inserted/updated Credit_Card: {len(card_rows)} rows")
        else:
            print("[DB] No credit cards mapped to CustomerIDs (Credit_Card not populated).")

        conn.commit()
        print("[DB] Commit complete.")

    finally:
        conn.close()



#Main

def main() -> None:
    # Sanity check file existence
    for p in [FILE_CSV, CUSTOMER_CSV, CREDITCARD_CSV]:
        if not p.exists():
            raise FileNotFoundError(f"Missing required file: {p.resolve()}")

    # Create database + schema
    conn = sqlite3.connect(DB_PATH)
    try:
        conn.execute("PRAGMA foreign_keys = ON;")
        conn.executescript(SCHEMA_SQL)
        conn.commit()
        print(f"[OK] Database schema created at: {DB_PATH.resolve()}")
    finally:
        conn.close()

    #Load and clean
    file_df = load_and_clean_file_csv(FILE_CSV)
    customers = load_and_clean_customer_csv(CUSTOMER_CSV)
    cc = load_and_clean_creditcard_csv(CREDITCARD_CSV)

    #Build customer master
    customer_master = build_customer_master(customers, file_df)

    #Map credit cards to CustomerID using cleaned name
    cards_mapped = map_cards_to_customer_ids(cc, customer_master)
    print(f"[creditCard.csv] Mapped cards to CustomerIDs: {len(cards_mapped)} rows")

    #Populate database
    populate_database(DB_PATH, customer_master, file_df, cards_mapped)

    #Verification
    conn = sqlite3.connect(DB_PATH)
    try:
        conn.execute("PRAGMA foreign_keys = ON;")
        cur = conn.cursor()
        cur.execute("SELECT name FROM sqlite_master WHERE type='table' ORDER BY name;")
        print("[DB] Tables:", cur.fetchall())

        for table in ["Customer", "Product", "Transactions", "Transaction_Item", "Credit_Card"]:
            cur.execute(f"SELECT COUNT(*) FROM {table};")
            print(f"[DB] {table} row count:", cur.fetchone()[0])
    finally:
        conn.close()


if __name__ == "__main__":
    main()