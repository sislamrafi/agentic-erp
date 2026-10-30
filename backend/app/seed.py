"""Seed demo data. Demo login: sislamrafi333@gmail.com / Admin@123"""
import random
from datetime import date, timedelta

from sqlalchemy import select

from .auth import hash_password
from .db import Base, SessionLocal, engine
from .models import Customer, Employee, Expense, Invoice, Order, Product, User

DEMO_EMAIL = "sislamrafi333@gmail.com"
DEMO_PASSWORD = "Admin@123"

COMPANIES = ["BlueHorizon Ltd.", "NexaCorp", "StarFreight Co.", "Movers Inc.", "Arvox Solutions", "Keystone Transport",
             "Kestrel Freight", "SwiftLogix", "GlobalTrade Inc.", "PathBlaze Inc.", "Northwind Traders", "Aurora Foods",
             "Cobalt Retail", "Verdant Farms", "Helix Medical", "Lumen Studios", "Orbit Electronics", "Pinecrest Hotels",
             "Quartz Builders", "Redwood Coffee", "Summit Outdoor", "Tidewater Marine", "Urban Nest", "Vista Optics",
             "Wavelength Media", "Zenith Pharma", "Atlas Hardware", "Beacon Dental", "Crescent Bakery", "Driftwood Design"]
CITIES = ["Austin", "Denver", "Seattle", "Chicago", "Boston", "Miami", "Dhaka", "London", "Toronto", "Berlin"]
FIRST = ["Ava", "Liam", "Noah", "Emma", "Olivia", "Mason", "Sofia", "Lucas", "Mia", "Ethan", "Zara", "Arif", "Nadia",
         "Omar", "Priya", "Chen", "Hana", "Leo", "Isla", "Ryan"]
LAST = ["Smith", "Rahman", "Garcia", "Lee", "Patel", "Khan", "Nguyen", "Brown", "Martin", "Silva", "Kim", "Hossain"]
PRODUCTS = [("Fleet GPS Tracker", "Hardware", 249), ("Pallet Jack", "Equipment", 420), ("Shipping Labels (1k)", "Supplies", 39),
            ("Stretch Wrap Roll", "Supplies", 24), ("Barcode Scanner", "Hardware", 189), ("Cold Chain Sensor", "Hardware", 129),
            ("Safety Vest", "Apparel", 15), ("Steel Toe Boots", "Apparel", 89), ("Route Optimizer License", "Software", 99),
            ("Warehouse Shelving", "Equipment", 560), ("Forklift Battery", "Equipment", 1450), ("Dash Camera", "Hardware", 159),
            ("Cardboard Boxes (50)", "Supplies", 45), ("Tire Pressure Kit", "Maintenance", 75), ("Engine Oil 5L", "Maintenance", 42),
            ("Hand Truck", "Equipment", 135), ("Packing Tape (36)", "Supplies", 52), ("Fleet Analytics Seat", "Software", 49),
            ("First Aid Kit", "Safety", 35), ("LED Work Light", "Equipment", 68), ("Thermal Printer", "Hardware", 299),
            ("Fuel Card Holder", "Accessories", 12), ("Cargo Straps (4)", "Supplies", 29), ("Driver Tablet", "Hardware", 349)]
EXPENSE_CATS = {"Salaries": (6000, 12000), "Rent": (2500, 3200), "Software": (200, 900), "Marketing": (300, 2500),
                "Fuel": (400, 2200), "Utilities": (150, 600), "Supplies": (80, 700), "Travel": (100, 1500),
                "Maintenance": (200, 1800)}
VENDORS = {"Salaries": ["Payroll"], "Rent": ["Prime Properties"], "Software": ["AWS", "Google Workspace", "Slack", "Notion"],
           "Marketing": ["Meta Ads", "Google Ads", "LinkedIn"], "Fuel": ["Shell", "BP", "Chevron"],
           "Utilities": ["City Power", "FiberNet"], "Supplies": ["Uline", "Staples"], "Travel": ["Delta", "Hilton", "Uber"],
           "Maintenance": ["AutoFix Garage", "Tire Pros"]}
DEPTS = {"Operations": ["Ops Manager", "Dispatcher"], "Sales": ["Account Executive", "Sales Lead"],
         "Finance": ["Accountant", "Controller"], "Engineering": ["Developer", "Data Analyst"],
         "Support": ["Support Specialist"], "HR": ["HR Generalist"], "Logistics": ["Driver", "Warehouse Associate"]}


def run(reset: bool = False):
    if reset:
        Base.metadata.drop_all(engine)
    Base.metadata.create_all(engine)
    db = SessionLocal()
    try:
        if db.scalar(select(User).where(User.email == DEMO_EMAIL)):
            return
        rnd = random.Random(42)
        today = date.today()
        db.add(User(email=DEMO_EMAIL, name="Islam Rafi", password_hash=hash_password(DEMO_PASSWORD),
                    company="NextERP Demo Co.", role="owner"))

        customers = []
        for i, name in enumerate(COMPANIES):
            slug = name.lower().split()[0].replace(".", "")
            c = Customer(name=name, email=f"accounts@{slug}.com", phone=f"+1 555 {rnd.randint(100,999)} {rnd.randint(1000,9999)}",
                         company=name, city=rnd.choice(CITIES), status=rnd.choices(["active", "lead", "inactive"], [7, 2, 1])[0])
            customers.append(c)
        db.add_all(customers)
        db.flush()

        for i, (name, cat, price) in enumerate(PRODUCTS):
            db.add(Product(sku=f"SKU-{1000 + i}", name=name, category=cat, price=price,
                           cost=round(price * rnd.uniform(0.45, 0.7), 2), stock=rnd.choice([0, 3, 6, 12, 25, 40, 80, 150]),
                           reorder_level=rnd.choice([5, 10, 20])))

        for i in range(140):
            issued = today - timedelta(days=rnd.randint(0, 360))
            due = issued + timedelta(days=30)
            if due < today:
                status = rnd.choices(["paid", "overdue"], [85, 15])[0]
            else:
                status = rnd.choices(["paid", "unpaid", "draft"], [30, 60, 10])[0]
            db.add(Invoice(number=f"INV-{1001 + i}", customer_id=rnd.choice(customers).id, issue_date=issued,
                           due_date=due, amount=round(rnd.uniform(800, 9500), -1), status=status))

        for i in range(90):
            d = today - timedelta(days=rnd.randint(0, 200))
            age = (today - d).days
            status = "delivered" if age > 30 else rnd.choice(["pending", "processing", "shipped", "delivered", "cancelled"])
            db.add(Order(number=f"SO-{1001 + i}", customer_id=rnd.choice(customers).id, order_date=d,
                         total=round(rnd.uniform(150, 6000), 2), status=status))

        for m in range(12):
            month_start = (today.replace(day=1) - timedelta(days=30 * m)).replace(day=1)
            for cat, (lo, hi) in EXPENSE_CATS.items():
                for _ in range(1 if cat in ("Salaries", "Rent") else rnd.randint(1, 3)):
                    d = month_start + timedelta(days=rnd.randint(0, 27))
                    if d > today:
                        d = today
                    db.add(Expense(date=d, category=cat, vendor=rnd.choice(VENDORS[cat]),
                                   amount=round(rnd.uniform(lo, hi), 2), description=f"{cat} - {d.strftime('%b %Y')}"))

        for i in range(18):
            dept = rnd.choice(list(DEPTS))
            fn, ln = rnd.choice(FIRST), rnd.choice(LAST)
            db.add(Employee(name=f"{fn} {ln}", email=f"{fn.lower()}.{ln.lower()}@nexterp.io", role=rnd.choice(DEPTS[dept]),
                            department=dept, salary=rnd.randrange(38000, 120000, 1000),
                            hire_date=today - timedelta(days=rnd.randint(60, 2000)),
                            status=rnd.choices(["active", "on_leave"], [9, 1])[0]))
        db.commit()
        print("Seeded demo data.")
    finally:
        db.close()


if __name__ == "__main__":
    import sys
    run(reset="--reset" in sys.argv)
