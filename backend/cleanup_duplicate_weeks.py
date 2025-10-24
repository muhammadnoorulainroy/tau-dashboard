#!/usr/bin/env python3
"""
Cleanup script to fix duplicate week entries.

Problem: Weeks were created with two different formats:
- "week_13" (from github_service.py)
- "Week 13" (from backfill_week_pod.py)

This script:
1. Identifies duplicate weeks
2. Migrates all PRs to use the correct format ("week_13")
3. Deletes the duplicate entries
"""

import logging
from database import SessionLocal, Week, PullRequest

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


def cleanup_duplicate_weeks():
    """Remove duplicate week entries and migrate PRs."""
    db = SessionLocal()
    
    try:
        logger.info("=" * 60)
        logger.info("Starting Week Cleanup")
        logger.info("=" * 60)
        
        # Find all weeks
        all_weeks = db.query(Week).order_by(Week.week_num).all()
        
        logger.info(f"Found {len(all_weeks)} weeks in database")
        
        # Group by week number
        weeks_by_num = {}
        for week in all_weeks:
            if week.week_num not in weeks_by_num:
                weeks_by_num[week.week_num] = []
            weeks_by_num[week.week_num].append(week)
        
        # Find duplicates
        duplicates_found = 0
        prs_migrated = 0
        weeks_deleted = 0
        
        for week_num, weeks in weeks_by_num.items():
            if len(weeks) > 1:
                duplicates_found += 1
                logger.info(f"\n📊 Week {week_num} has {len(weeks)} entries:")
                
                # Find the correct one (week_XX format)
                correct_week = None
                wrong_weeks = []
                
                for week in weeks:
                    logger.info(f"  - ID={week.id}, week_name='{week.week_name}'")
                    if week.week_name == f"week_{week_num}":
                        correct_week = week
                    else:
                        wrong_weeks.append(week)
                
                if not correct_week:
                    # None with correct format, use first one and rename it
                    correct_week = weeks[0]
                    logger.warning(f"  ⚠️  No 'week_{week_num}' format found, using ID={correct_week.id}")
                    correct_week.week_name = f"week_{week_num}"
                    correct_week.display_name = f"Week {week_num}"
                    db.flush()
                    wrong_weeks = weeks[1:]
                else:
                    logger.info(f"  ✅ Correct week: ID={correct_week.id} (week_name='{correct_week.week_name}')")
                
                # Migrate PRs from wrong weeks to correct week
                for wrong_week in wrong_weeks:
                    prs = db.query(PullRequest).filter_by(week_id=wrong_week.id).all()
                    if prs:
                        logger.info(f"  🔄 Migrating {len(prs)} PRs from ID={wrong_week.id} to ID={correct_week.id}")
                        for pr in prs:
                            pr.week_id = correct_week.id
                            prs_migrated += 1
                    
                    # Delete the duplicate
                    logger.info(f"  🗑️  Deleting duplicate week ID={wrong_week.id} (week_name='{wrong_week.week_name}')")
                    db.delete(wrong_week)
                    weeks_deleted += 1
        
        # Commit all changes
        db.commit()
        
        logger.info("\n" + "=" * 60)
        logger.info("Cleanup Summary")
        logger.info("=" * 60)
        logger.info(f"Duplicate week numbers found: {duplicates_found}")
        logger.info(f"PRs migrated: {prs_migrated}")
        logger.info(f"Duplicate weeks deleted: {weeks_deleted}")
        logger.info("=" * 60)
        logger.info("✅ Cleanup complete!")
        
    except Exception as e:
        logger.error(f"❌ Error during cleanup: {str(e)}")
        db.rollback()
        raise
    finally:
        db.close()


if __name__ == '__main__':
    cleanup_duplicate_weeks()

