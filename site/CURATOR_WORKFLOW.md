# Curator Workflow for Paper Submissions

This document describes how curators review and process paper submissions.

## Overview

Submissions flow through this pipeline:

```
User Submits → GitHub Issue → Curator Reviews → Approved/Rejected → Update Database
```

## Submission Sources

Submissions can come from two sources:

1. **Manual Submissions** - Users fill out the form on the website, which creates a GitHub issue
2. **Automated Pipeline** - Your existing pipeline that fetches and classifies papers

## Processing Manual Submissions

### Step 1: Review GitHub Issues

1. Go to the repository's Issues tab
2. Filter by label: `submission`
3. Each issue contains:
   - Paper metadata in the issue body
   - JSON data at the bottom for easy copying

### Step 2: Create Pending Entry

For each submission you want to review:

1. Copy the JSON from the GitHub issue
2. Go to `/admin/` (Decap CMS)
3. Navigate to "Pending Submissions"
4. Click "New Pending Submissions"
5. Paste the JSON data or manually fill fields
6. Save as draft or publish

### Step 3: Review in Decap CMS

1. Open "Pending Submissions" collection
2. Each submission shows:
   - All paper metadata
   - Submitter information
   - Current status (pending/accepted/rejected)
   - Reviewer notes field

3. Review the paper:
   - Check if URL is accessible
   - Verify it's relevant to ML/AI for accelerators
   - Validate categories and keywords
   - Add any notes in "Reviewer Notes"

### Step 4: Make Decision

**To Accept:**
1. Change status to "accepted"
2. The paper data needs to be manually added to `data/livingreview.json`
3. Optionally move the submission file to `data/submissions/approved/`
4. Close the GitHub issue with a comment

**To Reject:**
1. Change status to "rejected"
2. Add rejection reason in "Reviewer Notes"
3. Optionally move to `data/submissions/rejected/`
4. Close the GitHub issue explaining why

## Merging Approved Submissions

### Manual Method

1. Open `data/livingreview.json` in the CMS or directly in GitHub
2. Add the paper to the `papers` array:

```json
{
  "id": "2025-unique-id",
  "title": "Paper Title",
  "authors": ["Author 1", "Author 2"],
  "abstract": "...",
  "year": 2025,
  "venue": "...",
  "url": "...",
  "doi": "...",
  "categories": [...],
  "keywords": [...],
  "source": "manual",
  "added_at": "2025-10-01T10:00:00Z",
  "featured": false
}
```

3. Update metadata:
   - Increment `total_papers`
   - Update `last_updated`

4. Regenerate statistics if needed
5. Commit changes

### Automated Method (Recommended)

Create a script to merge approved submissions:

```bash
# Example: merge-approved.sh
#!/bin/bash

# For each approved submission in pending/
for file in data/submissions/pending/*.json; do
  status=$(jq -r '.status' "$file")
  
  if [ "$status" = "accepted" ]; then
    # Add to livingreview.json
    jq '.papers += [input]' data/livingreview.json "$file" > temp.json
    mv temp.json data/livingreview.json
    
    # Move to approved folder
    mv "$file" data/submissions/approved/
    
    # Update count
    count=$(jq '.papers | length' data/livingreview.json)
    jq ".metadata.total_papers = $count" data/livingreview.json > temp.json
    mv temp.json data/livingreview.json
  fi
done

# Update last_updated timestamp
jq ".metadata.last_updated = \"$(date -u +%Y-%m-%dT%H:%M:%SZ)\"" \
   data/livingreview.json > temp.json
mv temp.json data/livingreview.json
```

## Automated Pipeline Integration

If you have an automated pipeline that fetches papers:

### Pipeline Output

Your pipeline should output papers in the same JSON format:

```json
{
  "title": "...",
  "authors": [...],
  "abstract": "...",
  "year": 2025,
  "venue": "...",
  "url": "...",
  "doi": "...",
  "categories": [...],
  "keywords": [...],
  "source": "arxiv",
  "added_at": "2025-10-01T08:00:00Z"
}
```

### Integration Options

**Option 1: Direct to Main Database**
- Pipeline writes directly to `data/livingreview.json`
- Skip manual review for auto-classified papers
- Good for high-confidence classifications

**Option 2: Through Pending Queue**
- Pipeline writes to `data/submissions/pending/`
- Curator reviews before merging
- Good for quality control

**Option 3: Hybrid**
- High-confidence papers (score > 0.9) → direct to database
- Lower confidence → pending queue for review

## Updating Statistics

After adding papers, update `data/statistics.json`:

```json
{
  "total_papers": 451,
  "last_updated": "2025-10-01",
  "next_update": "2025-11-01",
  "papers_by_year": {
    "2025": 99
  },
  "papers_by_category": {
    "Beam Dynamics & Optimization": 88
  },
  "top_venues": {
    "arXiv": 246
  },
  "top_keywords": {
    "neural networks": 146
  }
}
```

## Generating Downloads

After updating the database:

1. **BibTeX Generation**
   - Run script to convert JSON to BibTeX
   - Save to `static/downloads/livingreview.bib`

2. **PDF Generation**
   - Generate PDF from Hugo site or separate LaTeX
   - Save to `static/downloads/livingreview.pdf`

3. Commit and push changes

## Tips

- **Batch Processing**: Review multiple submissions at once
- **Categories**: Be consistent with category assignment
- **Keywords**: Normalize keywords (lowercase, singular)
- **DOIs**: Verify DOI format and accessibility
- **Duplicates**: Check if paper already exists before adding
- **Quality**: Ensure abstracts are complete and informative

## Common Issues

**Issue: Duplicate submission**
- Check if paper already in `livingreview.json`
- Search by DOI, title, or URL
- Reject with explanation if duplicate

**Issue: Irrelevant paper**
- Paper must apply ML/AI to accelerator physics
- Reject with specific reason

**Issue: Missing information**
- Contact submitter via email for clarification
- Add note in reviewer_notes field

**Issue: Broken links**
- Try alternative sources (DOI, Google Scholar)
- Contact submitter for updated link
- Reject if paper not accessible

## Automation Ideas

1. **Auto-validation**: Script to check URLs, DOI format
2. **Duplicate detection**: Compare title/DOI with existing papers
3. **Keyword normalization**: Auto-lowercase and standardize
4. **Email notifications**: Alert submitters of acceptance/rejection
5. **Metrics dashboard**: Track submission rates, approval rates

## Contact

For questions about the review process, open an issue or contact the maintainers.