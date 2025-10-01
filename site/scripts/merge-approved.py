#!/usr/bin/env python3
"""
Merge approved submissions from pending/ into the main livingreview.json database.
"""

import json
import os
from datetime import datetime
from pathlib import Path
import shutil

# Paths
PENDING_DIR = Path("data/submissions/pending")
APPROVED_DIR = Path("data/submissions/approved")
REJECTED_DIR = Path("data/submissions/rejected")
LIVINGREVIEW_FILE = Path("data/livingreview.json")
STATS_FILE = Path("data/statistics.json")

def load_json(filepath):
    """Load JSON file."""
    with open(filepath, 'r', encoding='utf-8') as f:
        return json.load(f)

def save_json(filepath, data):
    """Save JSON file with pretty formatting."""
    with open(filepath, 'w', encoding='utf-8') as f:
        json.dump(data, f, indent=2, ensure_ascii=False)

def generate_paper_id(paper):
    """Generate a unique ID for a paper."""
    # Use year + sanitized title
    title_slug = paper['title'][:30].lower()
    title_slug = ''.join(c if c.isalnum() else '-' for c in title_slug)
    title_slug = title_slug.strip('-')
    return f"{paper['year']}-{title_slug}"

def process_submissions():
    """Process all pending submissions."""
    
    # Load main database
    print(f"Loading {LIVINGREVIEW_FILE}...")
    livingreview = load_json(LIVINGREVIEW_FILE)
    
    # Get existing paper IDs to avoid duplicates
    existing_ids = {paper.get('id', '') for paper in livingreview['papers']}
    existing_dois = {paper.get('doi', '').lower() for paper in livingreview['papers'] if paper.get('doi')}
    
    # Create output directories if they don't exist
    APPROVED_DIR.mkdir(parents=True, exist_ok=True)
    REJECTED_DIR.mkdir(parents=True, exist_ok=True)
    
    # Track statistics
    approved_count = 0
    rejected_count = 0
    skipped_count = 0
    
    # Process each pending submission
    for filepath in PENDING_DIR.glob("*.json"):
        print(f"\nProcessing {filepath.name}...")
        submission = load_json(filepath)
        
        status = submission.get('status', 'pending')
        
        if status == 'accepted':
            # Check for duplicates
            paper_doi = submission.get('doi', '').lower()
            if paper_doi and paper_doi in existing_dois:
                print(f"  ⚠️  Skipping: Duplicate DOI ({paper_doi})")
                skipped_count += 1
                continue
            
            # Generate paper entry
            paper_id = generate_paper_id(submission)
            
            # Ensure unique ID
            original_id = paper_id
            counter = 1
            while paper_id in existing_ids:
                paper_id = f"{original_id}-{counter}"
                counter += 1
            
            paper = {
                "id": paper_id,
                "title": submission['title'],
                "authors": submission['authors'],
                "abstract": submission['abstract'],
                "year": submission['year'],
                "venue": submission['venue'],
                "url": submission['url'],
                "doi": submission.get('doi'),
                "categories": submission.get('categories', []),
                "keywords": submission.get('keywords', []),
                "source": submission.get('source', 'manual'),
                "added_at": datetime.utcnow().isoformat() + 'Z',
                "featured": False
            }
            
            # Add to main database
            livingreview['papers'].append(paper)
            existing_ids.add(paper_id)
            if paper_doi:
                existing_dois.add(paper_doi)
            
            # Move to approved archive
            archive_path = APPROVED_DIR / filepath.name
            shutil.move(str(filepath), str(archive_path))
            
            print(f"  ✓ Approved and added: {paper['title'][:50]}...")
            approved_count += 1
            
        elif status == 'rejected':
            # Move to rejected archive
            archive_path = REJECTED_DIR / filepath.name
            shutil.move(str(filepath), str(archive_path))
            
            print(f"  ✗ Rejected: {submission['title'][:50]}...")
            rejected_count += 1
            
        else:
            print(f"  → Still pending (status: {status})")
    
    # Update metadata
    livingreview['metadata']['total_papers'] = len(livingreview['papers'])
    livingreview['metadata']['last_updated'] = datetime.utcnow().isoformat() + 'Z'
    
    # Save updated database
    save_json(LIVINGREVIEW_FILE, livingreview)
    print(f"\n✓ Updated {LIVINGREVIEW_FILE}")
    
    # Update statistics
    if approved_count > 0:
        update_statistics(livingreview)
    
    # Summary
    print(f"\n{'='*60}")
    print(f"Summary:")
    print(f"  Approved: {approved_count}")
    print(f"  Rejected: {rejected_count}")
    print(f"  Skipped (duplicates): {skipped_count}")
    print(f"  Total papers in database: {len(livingreview['papers'])}")
    print(f"{'='*60}\n")

def update_statistics(livingreview):
    """Update statistics.json based on current papers."""
    print("\nUpdating statistics...")
    
    papers = livingreview['papers']
    
    # Count by year
    papers_by_year = {}
    for paper in papers:
        year = str(paper['year'])
        papers_by_year[year] = papers_by_year.get(year, 0) + 1
    
    # Count by category
    papers_by_category = {}
    for paper in papers:
        for category in paper.get('categories', []):
            papers_by_category[category] = papers_by_category.get(category, 0) + 1
    
    # Count by venue
    top_venues = {}
    for paper in papers:
        venue = paper['venue']
        top_venues[venue] = top_venues.get(venue, 0) + 1
    
    # Count keywords
    top_keywords = {}
    for paper in papers:
        for keyword in paper.get('keywords', []):
            keyword_lower = keyword.lower()
            top_keywords[keyword_lower] = top_keywords.get(keyword_lower, 0) + 1
    
    # Sort and limit
    top_venues = dict(sorted(top_venues.items(), key=lambda x: x[1], reverse=True)[:10])
    top_keywords = dict(sorted(top_keywords.items(), key=lambda x: x[1], reverse=True)[:20])
    
    # Update statistics file
    stats = {
        "total_papers": len(papers),
        "last_updated": datetime.utcnow().date().isoformat(),
        "next_update": "", # You can calculate this
        "total_categories": len(papers_by_category),
        "papers_by_year": dict(sorted(papers_by_year.items())),
        "papers_by_category": dict(sorted(papers_by_category.items(), key=lambda x: x[1], reverse=True)),
        "top_venues": top_venues,
        "top_keywords": top_keywords
    }
    
    save_json(STATS_FILE, stats)
    print(f"✓ Updated {STATS_FILE}")

if __name__ == "__main__":
    print("=" * 60)
    print("Merging Approved Submissions")
    print("=" * 60)
    
    # Check if files exist
    if not LIVINGREVIEW_FILE.exists():
        print(f"Error: {LIVINGREVIEW_FILE} not found!")
        exit(1)
    
    if not PENDING_DIR.exists():
        print(f"Warning: {PENDING_DIR} not found. Creating...")
        PENDING_DIR.mkdir(parents=True, exist_ok=True)
    
    # Process submissions
    process_submissions()
    
    print("Done! Remember to commit and push the changes:")
    print("  git add data/")
    print("  git commit -m 'Update: Merged approved submissions'")
    print("  git push")