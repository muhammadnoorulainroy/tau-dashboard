#!/usr/bin/env python3
"""
Populate week_num, week_name, and pod_name for existing PRs using parse_week_pod_from_pr_files.
"""

import sys
from database import get_db, PullRequest
from github_service import GitHubService
from config import settings

def populate_weeks_from_github():
    """Use GitHubService to parse week info from PR files."""
    
    db = next(get_db())
    
    # Initialize GitHub service
    gh_service = GitHubService()
    
    # Get all PRs without week_num
    prs_without_week = db.query(PullRequest).filter(
        PullRequest.week_num.is_(None)
    ).all()
    
    print(f"Found {len(prs_without_week)} PRs without week_num")
    print(f"Fetching week info from GitHub using parse_week_pod_from_pr_files...")
    print(f"This will take a while due to GitHub API rate limits...\n")
    
    updated = 0
    errors = 0
    skipped = 0
    
    for i, db_pr in enumerate(prs_without_week, 1):
        if i % 20 == 0:
            print(f"  Progress: {i}/{len(prs_without_week)} PRs processed (updated: {updated}, errors: {errors}, no week: {skipped})")
        
        try:
            # Get PR from GitHub
            gh_pr = gh_service.repo.get_pull(db_pr.number)
            
            # Use the existing parse function
            week_pod_info = gh_service.parse_week_pod_from_pr_files(gh_pr)
            
            if week_pod_info:
                week_num, pod_name = week_pod_info
                
                # Update PR with week info
                db_pr.week_num = week_num
                db_pr.week_name = f'Week {week_num}'
                db_pr.pod_name = pod_name
                
                updated += 1
                
                if updated <= 5:  # Print first 5 as examples
                    print(f"    ✓ PR #{db_pr.number}: Week {week_num}, POD {pod_name}")
            else:
                skipped += 1
                if skipped <= 3:  # Print first 3 as examples
                    print(f"    - PR #{db_pr.number}: No week info in files")
            
            # Commit every 50 PRs to avoid losing progress
            if i % 50 == 0:
                db.commit()
                print(f"  ✅ Committed batch at {i} PRs\n")
                
        except Exception as e:
            errors += 1
            if errors <= 5:  # Only print first 5 errors
                print(f"  ⚠️  Error processing PR #{db_pr.number}: {e}")
            
            # If we hit rate limit, commit what we have and stop
            if '403' in str(e) or 'rate limit' in str(e).lower():
                print(f"\n⚠️  GitHub API rate limit reached!")
                print(f"   Updated so far: {updated} PRs")
                print(f"   Committing changes and exiting...")
                db.commit()
                break
    
    # Final commit
    db.commit()
    
    print(f"\n{'='*70}")
    print(f"✅ Population complete!")
    print(f"   Updated: {updated} PRs with week info")
    print(f"   No week info: {skipped} PRs")
    print(f"   Errors: {errors} PRs")
    print(f"{'='*70}")
    
    # Show distinct weeks now available
    weeks = db.query(PullRequest.week_num).filter(
        PullRequest.week_num.isnot(None)
    ).distinct().order_by(PullRequest.week_num).all()
    
    week_nums = [w[0] for w in weeks]
    print(f"\n📅 Available weeks in database: {week_nums}")
    print(f"   Total: {len(week_nums)} unique weeks")
    
    # Show count per week
    print(f"\n📊 PRs per week:")
    for week_num in sorted(week_nums):
        count = db.query(PullRequest).filter(PullRequest.week_num == week_num).count()
        print(f"   Week {week_num}: {count} PRs")
    
    db.close()

if __name__ == "__main__":
    try:
        populate_weeks_from_github()
    except KeyboardInterrupt:
        print("\n\n⚠️  Interrupted by user")
        sys.exit(1)
    except Exception as e:
        print(f"\n❌ Error: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)

