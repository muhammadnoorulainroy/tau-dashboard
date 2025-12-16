"""
FIX TIME ENTRIES - Delete and re-sync from Jibble API
This is the SAFE approach - we don't guess which duplicate is correct,
we just get fresh data from the source.

Usage: python fix_time_entries.py
"""
import os
from pathlib import Path
from dotenv import load_dotenv
from datetime import datetime, timedelta

env_path = Path(__file__).parent / '.env'
if env_path.exists():
    load_dotenv(env_path)

from database_v2 import SessionLocal, JibbleTimeEntry, JibblePerson, JibbleEmailMapping
from jibble_service import JibbleService
from sqlalchemy import text, cast, Date

def fix():
    db = SessionLocal()
    jibble = JibbleService()
    
    # Current month range
    today = datetime.now()
    start_of_month = today.replace(day=1, hour=0, minute=0, second=0, microsecond=0)
    if today.month == 12:
        end_of_month = today.replace(year=today.year + 1, month=1, day=1) - timedelta(days=1)
    else:
        end_of_month = today.replace(month=today.month + 1, day=1) - timedelta(days=1)
    end_of_month = end_of_month.replace(hour=23, minute=59, second=59)
    
    print("=" * 80)
    print("FIX TIME ENTRIES - Delete and Re-sync from Jibble API")
    print("=" * 80)
    print(f"\nDate range: {start_of_month.date()} to {end_of_month.date()}")
    
    # 1. Show current state
    result = db.execute(text(f"""
        SELECT COUNT(*) FROM jibble_time_entries
        WHERE entry_date >= '{start_of_month.date()}' AND entry_date <= '{end_of_month.date()}'
    """))
    current_count = result.scalar()
    print(f"\nCurrent entries in DB for this period: {current_count}")
    
    # 2. Get allowed emails from mappings
    mappings = db.query(JibbleEmailMapping).all()
    allowed_jibble_emails = {m.jibble_email.lower() for m in mappings}
    print(f"Allowed Jibble emails from mappings: {len(allowed_jibble_emails)}")
    
    # 3. Get person_id -> email lookup
    people = db.query(JibblePerson).all()
    person_id_to_email = {}
    for p in people:
        email = p.personal_email or p.work_email
        if email and email.lower() in allowed_jibble_emails:
            person_id_to_email[p.jibble_id] = email.lower()
    
    print(f"Jibble people with allowed emails: {len(person_id_to_email)}")
    
    # 4. Delete ALL existing entries for these people in date range
    print(f"\n4. Deleting existing entries...")
    
    if person_id_to_email:
        person_ids = list(person_id_to_email.keys())
        delete_result = db.execute(text(f"""
            DELETE FROM jibble_time_entries
            WHERE person_id IN :person_ids
              AND entry_date >= :start_date
              AND entry_date <= :end_date
        """), {
            "person_ids": tuple(person_ids),
            "start_date": start_of_month,
            "end_date": end_of_month
        })
        deleted = delete_result.rowcount
        db.commit()
        print(f"   Deleted {deleted} entries")
    
    # 5. Fetch fresh data from Jibble API
    print(f"\n5. Fetching fresh data from Jibble API...")
    
    daily_hours = jibble.get_timesheets_summary(start_of_month, end_of_month)
    print(f"   Got data for {len(daily_hours)} people from Jibble")
    
    # 6. Insert fresh entries
    print(f"\n6. Inserting fresh entries...")
    
    inserted = 0
    for person_id, data in daily_hours.items():
        # Check if this person is in our allowed list
        person_email = person_id_to_email.get(person_id)
        if not person_email:
            continue
        
        for date_str, hours in data.items():
            if date_str.startswith("_"):  # Skip metadata keys
                continue
            if hours == 0:  # Skip zero hours
                continue
            
            try:
                # Parse date and create entry at midnight (naive datetime for consistency)
                entry_date = datetime.fromisoformat(date_str)
                
                new_entry = JibbleTimeEntry(
                    person_id=person_id,
                    entry_date=entry_date,
                    total_hours=hours,
                )
                db.add(new_entry)
                inserted += 1
                
            except Exception as e:
                print(f"   Error for {person_id}/{date_str}: {e}")
                continue
    
    db.commit()
    print(f"   Inserted {inserted} entries")
    
    # 7. Verify results
    print(f"\n7. Verification:")
    
    result = db.execute(text(f"""
        SELECT COUNT(*) FROM jibble_time_entries
        WHERE entry_date >= '{start_of_month.date()}' AND entry_date <= '{end_of_month.date()}'
    """))
    new_count = result.scalar()
    print(f"   New entry count: {new_count}")
    
    # Show top 10 users
    result = db.execute(text(f"""
        SELECT 
            m.turing_email,
            p.full_name,
            SUM(e.total_hours) as total,
            COUNT(*) as entries
        FROM jibble_email_mappings m
        JOIN jibble_people p ON LOWER(p.personal_email) = LOWER(m.jibble_email)
        JOIN jibble_time_entries e ON e.person_id = p.jibble_id
        WHERE e.entry_date >= '{start_of_month.date()}' AND e.entry_date <= '{end_of_month.date()}'
        GROUP BY m.turing_email, p.full_name
        ORDER BY total DESC
        LIMIT 10
    """))
    
    print(f"\n   Top 10 users by hours:")
    for row in result.fetchall():
        print(f"      {row[1]:<25} ({row[0]:<25}): {row[2]:.1f}h ({row[3]} entries)")
    
    db.close()
    print("\n" + "=" * 80)
    print("DONE! Refresh the Time Tracking page to see correct data.")
    print("=" * 80)

if __name__ == "__main__":
    fix()

