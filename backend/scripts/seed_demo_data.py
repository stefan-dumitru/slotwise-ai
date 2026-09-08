"""
Seeds a realistic demo dataset: 13 businesses (one per category) with owners,
staff, services, and working hours; 16 customers; ~65 appointments spanning
completed (with reviews), cancelled, and upcoming confirmed; 26 reviews.

Connects using the same Settings as the app (backend/app/config.py), so it
targets whatever MYSQL_* values are active when it's run — override them via
environment variables to target a different database (e.g. the Docker
Compose stack) without touching backend/.env:

    MYSQL_HOST=localhost MYSQL_PORT=3307 MYSQL_PASSWORD=slotwise_docker_dev \\
        .venv/Scripts/python.exe scripts/seed_demo_data.py

Safe to re-run: existing users/businesses (matched by email/name) are reused
rather than duplicated, though services/staff/hours/appointments/reviews are
only created once per business in practice since this is meant to run once
per fresh database.

All seeded accounts (owners and customers alike) share the password:
    password123
"""

import sys
import time as time_module
from datetime import date, datetime, time, timedelta
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from app.database import SessionLocal
from app import models
from app.auth_utils import hash_password
from app.geocoding import geocode_address

db = SessionLocal()

PASSWORD_HASH = hash_password("password123")

MON_FRI = [1, 2, 3, 4, 5]
SAT = [6]


def get_category(name):
    cat = db.query(models.Category).filter(models.Category.name == name).first()
    if not cat:
        raise RuntimeError(f"Category not found: {name} — run database/schema.sql and seed categories first")
    return cat


def create_user(full_name, email, role, phone=None):
    existing = db.query(models.User).filter(models.User.email == email).first()
    if existing:
        return existing
    user = models.User(full_name=full_name, email=email, password_hash=PASSWORD_HASH, role=role, phone=phone)
    db.add(user)
    db.flush()
    return user


def create_business(owner, name, category_name, description, address, phone):
    existing = db.query(models.Business).filter(models.Business.name == name).first()
    if existing:
        return existing, db.query(models.Staff).filter(
            models.Staff.business_id == existing.id, models.Staff.user_id == owner.id
        ).first()
    category = get_category(category_name)
    business = models.Business(
        owner_id=owner.id, category_id=category.id, name=name,
        description=description, address=address, phone=phone, status="active",
    )
    if address:
        coords = geocode_address(address)
        if coords:
            business.latitude, business.longitude = coords
        time_module.sleep(1)  # respect Nominatim's ~1 request/second usage policy
    db.add(business)
    db.flush()
    default_staff = models.Staff(business_id=business.id, user_id=owner.id, full_name=owner.full_name)
    db.add(default_staff)
    db.flush()
    return business, default_staff


def add_staff(business, full_name):
    staff = models.Staff(business_id=business.id, full_name=full_name)
    db.add(staff)
    db.flush()
    return staff


def add_service(business, name, description, duration, price):
    service = models.Service(
        business_id=business.id, name=name, description=description,
        duration_minutes=duration, price=price, is_active=True,
    )
    db.add(service)
    db.flush()
    return service


def add_hours(staff, days, start, end):
    for d in days:
        db.add(models.WorkingHours(staff_id=staff.id, day_of_week=d, start_time=start, end_time=end))


def nearest_weekday(d):
    while d.weekday() >= 5:
        d -= timedelta(days=1)
    return d


def make_appointment(customer, business, service, staff, day_offset, hour, minute=0, appt_status="confirmed", cancellation_reason=None):
    target_date = nearest_weekday(date.today() + timedelta(days=day_offset))
    start = datetime.combine(target_date, time(hour, minute))
    end = start + timedelta(minutes=service.duration_minutes)
    appt = models.Appointment(
        customer_id=customer.id, business_id=business.id, service_id=service.id, staff_id=staff.id,
        start_time=start, end_time=end, status=appt_status, cancellation_reason=cancellation_reason,
    )
    db.add(appt)
    db.flush()
    return appt


def make_review(appt, customer, rating, comment):
    existing = db.query(models.Review).filter(models.Review.appointment_id == appt.id).first()
    if existing:
        return existing
    review = models.Review(appointment_id=appt.id, customer_id=customer.id, business_id=appt.business_id, rating=rating, comment=comment)
    db.add(review)
    return review


REVIEW_COMMENTS = {
    5: [
        "Absolutely fantastic experience, highly recommend!",
        "Best in town — professional, friendly, and worth every penny.",
        "Couldn't be happier, already booked my next visit.",
        "Exceeded my expectations in every way.",
    ],
    4: [
        "Really good experience overall, just a short wait.",
        "Great service, will be back again.",
        "Very satisfied, small room for improvement on timing.",
    ],
    3: [
        "It was fine, nothing extraordinary.",
        "Decent service but a bit pricey for what you get.",
    ],
}


def review_for(rating):
    idx = (rating * 7) % len(REVIEW_COMMENTS[rating])
    return REVIEW_COMMENTS[rating][idx]


def ensure_categories():
    names = [
        "Salon", "Barbershop", "Spa & Massage", "Dental Care", "Medical Clinic",
        "Tutoring & Education", "Fitness & Personal Training", "Automotive Repair",
        "Home Cleaning", "Veterinary Care", "Beauty & Nails", "Photography",
        "Legal & Financial Consulting",
    ]
    for name in names:
        if not db.query(models.Category).filter(models.Category.name == name).first():
            db.add(models.Category(name=name))
    db.commit()


ensure_categories()

# ---------------------------------------------------------------------------
# Customers
# ---------------------------------------------------------------------------

customer_names = [
    "Olivia Bennett", "Ethan Park", "Maya Patel", "Liam Carter", "Ava Thompson",
    "Noah Rodriguez", "Isabella Chen", "Mason Brooks", "Chloe Dubois", "Lucas Ferreira",
    "Zoe Anderson", "Ryan Mitchell", "Amara Okafor", "Daniel Kim", "Hannah Fischer", "Jordan Lee",
]
customers = []
for full_name in customer_names:
    slug = full_name.lower().replace(" ", ".").replace("'", "")
    email = f"{slug}@mailhaven.com"
    phone = f"512-555-{1000 + len(customers):04d}"
    customers.append(create_user(full_name, email, "customer", phone))
db.commit()
print(f"Customers ready: {len(customers)}")


def next_customer(i):
    return customers[i % len(customers)]


# ---------------------------------------------------------------------------
# Businesses
# ---------------------------------------------------------------------------

businesses = []
ci = 0


def build_business(owner_name, owner_email, owner_phone, biz_name, category, description, address, biz_phone,
                    services_spec, extra_staff_names=None, sat_hours=False):
    owner = create_user(owner_name, owner_email, "business_owner", owner_phone)
    business, default_staff = create_business(owner, biz_name, category, description, address, biz_phone)

    staff_list = [default_staff]
    for name in (extra_staff_names or []):
        staff_list.append(add_staff(business, name))

    for staff in staff_list:
        add_hours(staff, MON_FRI, time(9, 0), time(17, 0))
        if sat_hours:
            add_hours(staff, SAT, time(10, 0), time(14, 0))

    services = [add_service(business, *spec) for spec in services_spec]
    db.commit()
    return {"owner": owner, "business": business, "staff": staff_list, "services": services}


businesses.append(build_business(
    "Sofia Marin", "sofia.marin@gildedchair.com", "512-555-2001",
    "The Gilded Chair", "Salon",
    "Upscale hair salon specializing in color, cuts, and styling for every occasion.",
    "412 Congress Ave, Austin, TX", "512-555-3001",
    [
        ("Women's Haircut & Style", "Wash, cut, and blow-dry.", 45, 65.00),
        ("Men's Haircut", "Precision cut with hot towel finish.", 30, 35.00),
        ("Balayage Color", "Full balayage with gloss and style.", 150, 220.00),
    ],
    extra_staff_names=["Renee Castillo"],
    sat_hours=True,
))

businesses.append(build_business(
    "Marcus Webb", "marcus.webb@fadeculture.com", "512-555-2002",
    "Fade Culture Barbershop", "Barbershop",
    "Classic and modern barbering — fades, tapers, beard grooming.",
    "2210 S Lamar Blvd, Austin, TX", "512-555-3002",
    [
        ("Classic Fade", "Skin fade with line-up.", 30, 28.00),
        ("Beard Trim", "Shape-up and line detail.", 15, 15.00),
        ("Hot Towel Shave", "Traditional straight-razor shave.", 30, 32.00),
    ],
    extra_staff_names=["DeShawn Miller"],
    sat_hours=True,
))

businesses.append(build_business(
    "Elena Voss", "elena.voss@serenityspa.com", "512-555-2003",
    "Serenity Spa & Massage", "Spa & Massage",
    "A calm retreat offering massage therapy and relaxation treatments.",
    "980 Barton Springs Rd, Austin, TX", "512-555-3003",
    [
        ("Swedish Massage", "Full-body relaxation massage.", 60, 90.00),
        ("Deep Tissue Massage", "Targeted muscle tension relief.", 60, 100.00),
        ("Hot Stone Therapy", "Heated stone massage treatment.", 75, 130.00),
    ],
    extra_staff_names=["Nadia Farouk"],
))

businesses.append(build_business(
    "Priya Nandan", "priya.nandan@brightsmiledental.com", "512-555-2004",
    "BrightSmile Dental Care", "Dental Care",
    "Family and cosmetic dentistry focused on comfortable, modern care.",
    "1500 W 6th St, Austin, TX", "512-555-3004",
    [
        ("Routine Cleaning", "Standard hygiene cleaning and check.", 45, 120.00),
        ("Teeth Whitening", "In-office professional whitening.", 60, 250.00),
        ("Dental Checkup", "Exam and X-rays.", 30, 80.00),
    ],
))

businesses.append(build_business(
    "James O'Connell", "james.oconnell@riversidemedical.com", "512-555-2005",
    "Riverside Family Medical Clinic", "Medical Clinic",
    "Primary care clinic offering checkups, vaccinations, and consultations.",
    "3300 Riverside Dr, Austin, TX", "512-555-3005",
    [
        ("General Checkup", "Routine physical examination.", 30, 150.00),
        ("Flu Shot", "Seasonal influenza vaccination.", 15, 40.00),
        ("Follow-up Consultation", "Review of ongoing treatment.", 20, 90.00),
    ],
    extra_staff_names=["Dr. Monica Reyes"],
))

businesses.append(build_business(
    "Angela Torres", "angela.torres@mathletestutoring.com", "512-555-2006",
    "Mathletes Tutoring Center", "Tutoring & Education",
    "One-on-one math tutoring from middle school through college prep.",
    "700 E 5th St, Austin, TX", "512-555-3006",
    [
        ("SAT Math Prep", "Exam strategy and practice.", 60, 55.00),
        ("Algebra Tutoring", "Core algebra concepts and homework help.", 45, 40.00),
        ("Calculus Tutoring", "AP/college calculus support.", 60, 60.00),
    ],
))

businesses.append(build_business(
    "Derek Simmons", "derek.simmons@ironcladfitness.com", "512-555-2007",
    "Ironclad Fitness Coaching", "Fitness & Personal Training",
    "Personal training and fitness assessments tailored to your goals.",
    "88 Rainey St, Austin, TX", "512-555-3007",
    [
        ("Personal Training Session", "1:1 strength & conditioning session.", 60, 75.00),
        ("Fitness Assessment", "Baseline fitness and goal-setting session.", 45, 50.00),
        ("HIIT Session", "High-intensity interval training, 1:1.", 30, 40.00),
    ],
    extra_staff_names=["Tasha Brown"],
))

businesses.append(build_business(
    "Tony Ricci", "tony.ricci@ricciauto.com", "512-555-2008",
    "Ricci Auto Repair", "Automotive Repair",
    "Family-owned auto shop for maintenance, diagnostics, and repairs.",
    "4501 S Congress Ave, Austin, TX", "512-555-3008",
    [
        ("Oil Change", "Standard oil and filter change.", 30, 45.00),
        ("Brake Inspection", "Full brake system inspection.", 45, 60.00),
        ("Full Diagnostic", "Computer diagnostic scan and report.", 60, 90.00),
    ],
    extra_staff_names=["Hector Delgado"],
    sat_hours=True,
))

businesses.append(build_business(
    "Lena Whitfield", "lena.whitfield@cleansweephome.com", "512-555-2009",
    "Clean Sweep Home Services", "Home Cleaning",
    "Reliable residential cleaning — standard, deep, and move-out cleans.",
    "1120 E 11th St, Austin, TX", "512-555-3009",
    [
        ("Standard House Cleaning", "Routine whole-home cleaning.", 120, 110.00),
        ("Deep Cleaning", "Detailed top-to-bottom clean.", 180, 180.00),
        ("Move-out Cleaning", "Full clean for move-out inspections.", 240, 250.00),
    ],
))

businesses.append(build_business(
    "Hannah Kim", "hannah.kim@pawsclaws.com", "512-555-2010",
    "Paws & Claws Veterinary Clinic", "Veterinary Care",
    "Compassionate veterinary care for cats, dogs, and small pets.",
    "6200 Burnet Rd, Austin, TX", "512-555-3010",
    [
        ("Wellness Exam", "Annual checkup for pets.", 30, 55.00),
        ("Vaccination", "Core vaccine administration.", 15, 35.00),
        ("Pet Dental Cleaning", "Professional dental cleaning under sedation.", 60, 150.00),
    ],
))

businesses.append(build_business(
    "Grace Nguyen", "grace.nguyen@polishednailbar.com", "512-555-2011",
    "Polished Nail Bar", "Beauty & Nails",
    "Manicures, pedicures, and nail art in a relaxing setting.",
    "2115 S Congress Ave, Austin, TX", "512-555-3011",
    [
        ("Classic Manicure", "Shape, cuticle care, and polish.", 30, 30.00),
        ("Gel Pedicure", "Soak, exfoliation, and gel polish.", 45, 45.00),
        ("Full Set Acrylics", "Acrylic extensions with polish.", 75, 65.00),
    ],
    extra_staff_names=["Mai Tran"],
    sat_hours=True,
))

businesses.append(build_business(
    "Owen Baxter", "owen.baxter@aperturemoments.com", "512-555-2012",
    "Aperture Moments Photography", "Photography",
    "Portrait, event, and family photography with a documentary style.",
    "901 E 6th St, Austin, TX", "512-555-3012",
    [
        ("Portrait Session", "Studio or outdoor portrait shoot.", 60, 150.00),
        ("Event Coverage", "On-location event photography.", 120, 350.00),
        ("Family Photoshoot", "Outdoor family session with edited gallery.", 90, 220.00),
    ],
))

businesses.append(build_business(
    "Richard Whitmore", "richard.whitmore@whitmorelegal.com", "512-555-2013",
    "Whitmore Legal Consulting", "Legal & Financial Consulting",
    "Consulting on contracts, small business law, and tax planning.",
    "301 Congress Ave, Austin, TX", "512-555-3013",
    [
        ("Initial Consultation", "Case review and advice session.", 45, 100.00),
        ("Contract Review", "Review and markup of a legal document.", 60, 180.00),
        ("Tax Planning Session", "Personal or small business tax strategy.", 60, 150.00),
    ],
))

db.commit()
print(f"Businesses ready: {len(businesses)}")

# ---------------------------------------------------------------------------
# Appointments + reviews
# ---------------------------------------------------------------------------

PAST_SLOTS = [(-32, 10), (-24, 14)]
CANCELLED_SLOT = (-10, 11)
FUTURE_SLOTS = [(4, 9), (9, 15)]

rating_cycle = [5, 4, 5, 3, 4, 5]

appt_count = 0
review_count = 0

for b in businesses:
    business = b["business"]
    services = b["services"]
    staff_list = b["staff"]

    for i, (offset, hour) in enumerate(PAST_SLOTS):
        customer = next_customer(ci); ci += 1
        service = services[i % len(services)]
        staff = staff_list[i % len(staff_list)]
        appt = make_appointment(customer, business, service, staff, offset, hour, appt_status="completed")
        appt_count += 1
        rating = rating_cycle[(ci + i) % len(rating_cycle)]
        make_review(appt, customer, rating, review_for(rating))
        review_count += 1

    offset, hour = CANCELLED_SLOT
    customer = next_customer(ci); ci += 1
    service = services[2 % len(services)]
    staff = staff_list[0]
    make_appointment(customer, business, service, staff, offset, hour, appt_status="cancelled",
                      cancellation_reason="Customer requested reschedule")
    appt_count += 1

    for i, (offset, hour) in enumerate(FUTURE_SLOTS):
        customer = next_customer(ci); ci += 1
        service = services[i % len(services)]
        staff = staff_list[i % len(staff_list)]
        make_appointment(customer, business, service, staff, offset, hour, appt_status="confirmed")
        appt_count += 1

db.commit()
print(f"Appointments created: {appt_count}, reviews created: {review_count}")

db.close()
print("\nSeed complete. All seeded accounts (owners + customers) use password: password123")
