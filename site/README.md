# The AI/ML for Particle Accelerators Living Review

A comprehensive, community-maintained living review of machine learning and artificial intelligence applications in particle accelerator science.

## 🚀 Quick Start

### Prerequisites
- [Hugo Extended](https://gohugo.io/installation/) (v0.120.0 or later)
- Git
- A GitHub account
- (Optional) Node.js for local Decap CMS development

### Local Development

1. **Clone the repository:**
   ```bash
   git clone https://github.com/yourusername/ml-accel-review.git
   cd ml-accel-review
   ```

2. **Run Hugo locally:**
   ```bash
   hugo server -D
   ```
   Visit `http://localhost:1313`

3. **Test Decap CMS locally (optional):**
   ```bash
   npx decap-server
   ```
   Then in another terminal:
   ```bash
   hugo server -D
   ```
   Visit `http://localhost:1313/admin`

## 📊 Data Structure

### Main Database
The living review is built from `data/livingreview.json`:

```json
{
  "metadata": {
    "last_updated": "2025-09-30T10:00:00Z",
    "next_update": "2025-10-31T10:00:00Z",
    "total_papers": 450,
    "version": "1.0"
  },
  "papers": [
    {
      "id": "unique-id",
      "title": "Paper Title",
      "authors": ["Author1", "Author2"],
      "abstract": "...",
      "year": 2025,
      "venue": "...",
      "url": "...",
      "doi": "...",
      "categories": [...],
      "keywords": [...],
      "source": "arxiv",
      "added_at": "2025-01-15T10:00:00Z",
      "featured": false
    }
  ]
}
```

### Downloadable Files
- `static/downloads/livingreview.bib` - BibTeX export
- `static/downloads/livingreview.pdf` - PDF version

### Submission Pipeline

```
┌─────────────────┐
│ User Submission │ → GitHub Issue
└─────────────────┘
         ↓
┌─────────────────┐
│  Curator Review │ → Decap CMS
└─────────────────┘
         ↓
    ┌────┴────┐
    ↓         ↓
[Approved] [Rejected]
    ↓
data/livingreview.json
```

Submissions are stored in:
- `data/submissions/pending/*.json` - Awaiting review
- `data/submissions/approved/*.json` - Accepted (archived)
- `data/submissions/rejected/*.json` - Rejected (archived)

## 📝 Content Management

### Automated Pipeline Integration

If you have an automated pipeline that fetches and classifies papers:

1. **Pipeline outputs to:**
   - Direct: `data/livingreview.json`
   - Review queue: `data/submissions/pending/*.json`

2. **JSON format:**
   ```json
   {
     "title": "...",
     "authors": ["..."],
     "abstract": "...",
     "year": 2025,
     "venue": "...",
     "url": "...",
     "doi": "...",
     "categories": [...],
     "keywords": [...],
     "source": "arxiv",
     "added_at": "2025-01-15T08:00:00Z"
   }
   ```

3. **Trigger site rebuild:**
   ```bash
   git add data/livingreview.json
   git commit -m "Update database"
   git push
   ```

### Manual Submissions (via Website)

1. Users fill form at `/submit/`
2. Creates GitHub issue with paper data
3. Curator reviews in Decap CMS
4. Approved papers added to `livingreview.json`

See [CURATOR_WORKFLOW.md](CURATOR_WORKFLOW.md) for detailed review process.

### Using Decap CMS

1. Navigate to `https://yourusername.github.io/ml-accel-review/admin/`
2. Log in with Netlify Identity
3. Access collections:
   - **Pending Submissions** - Review new papers
   - **Living Review Database** - Edit main database
   - **Approved/Rejected** - View archives
   - **Statistics** - Update counts and metrics

## 🔧 Configuration

### GitHub Repository Setup

1. **Create a new GitHub repository** named `ml-accel-review`

2. **Enable GitHub Pages:**
   - Go to Settings → Pages
   - Source: GitHub Actions
   - Save

3. **Set up Netlify Identity (for Decap CMS authentication):**
   - Sign up at [Netlify](https://www.netlify.com/)
   - Create a new site (can be the same repo)
   - Enable Identity service
   - Settings → Identity → Enable Git Gateway
   - Invite yourself as a user

4. **Update `config.toml`:**
   ```toml
   baseURL = "https://yourusername.github.io/ml-accel-review/"
   
   [params]
     github = "https://github.com/yourusername/ml-accel-review"
   ```

5. **Push to GitHub:**
   ```bash
   git add .
   git commit -m "Initial commit"
   git branch -M main
   git remote add origin https://github.com/yourusername/ml-accel-review.git
   git push -u origin main
   ```

## 📁 Project Structure

```
ml-accel-review/
├── config.toml              # Site configuration
├── data/
│   ├── livingreview.json   # Main paper database
│   ├── statistics.json     # Aggregated statistics
│   └── submissions/
│       ├── pending/        # Awaiting review
│       ├── approved/       # Accepted (archive)
│       └── rejected/       # Rejected (archive)
├── content/
│   ├── _index.md           # Homepage
│   ├── cite.md             # Citation page
│   └── docs.md             # Documentation
├── layouts/
│   ├── _default/           # Default templates
│   ├── papers/
│   │   └── list.html       # Living review page
│   ├── submit/
│   │   └── single.html     # Submission form
│   └── partials/           # Reusable components
├── static/
│   ├── admin/              # Decap CMS
│   ├── css/                # Styles
│   └── downloads/          # Generated files
│       ├── livingreview.bib
│       └── livingreview.pdf
└── .github/
    └── workflows/          # CI/CD
```

## 🔄 Updating the Review

### Option 1: Automated Pipeline

Your pipeline can directly update `livingreview.json`:

```bash
# Your pipeline script
python fetch_papers.py --output data/livingreview.json

# Commit and push
git add data/livingreview.json data/statistics.json
git commit -m "Update: Added X new papers"
git push
```

### Option 2: Manual via CMS

1. Go to `/admin/`
2. Open "Living Review Database"
3. Click "Main Paper Database"
4. Edit the papers array
5. Save and publish

### Option 3: Hybrid Workflow

1. Pipeline writes to `pending/`
2. Curator reviews in CMS
3. Approved papers merged to main database
4. See [CURATOR_WORKFLOW.md](CURATOR_WORKFLOW.md)

## 🎨 Customization

### Styling
- Edit `static/css/style.css` for custom styles
- Modify theme colors in CSS variables
- Supports dark/light mode toggle

### Categories
- Modify in `static/admin/config.yml`
- Update paper category taxonomy

### Statistics
- Auto-generated from `livingreview.json`
- Manual updates in `data/statistics.json`

## 🚢 Deployment

### Automatic Deployment
- Push to `main` branch triggers GitHub Actions
- Site builds and deploys to GitHub Pages
- Usually takes 2-3 minutes

### What Gets Deployed
1. Hugo builds static site from `data/livingreview.json`
2. Statistics charts rendered
3. Downloads available at `/downloads/`
4. CMS accessible at `/admin/`

## 📊 Generating Exports

### BibTeX Export

```bash
# Generate from JSON
python scripts/generate_bibtex.py \
  --input data/livingreview.json \
  --output static/downloads/livingreview.bib
```

### PDF Export

```bash
# Option 1: From Hugo site
hugo --minify
wkhtmltopdf public/papers/index.html static/downloads/livingreview.pdf

# Option 2: From LaTeX
python scripts/generate_latex.py --input data/livingreview.json
pdflatex livingreview.tex
mv livingreview.pdf static/downloads/
```

## 🤝 Contributing

### Submit a Paper
1. Use the web form at `/submit/`
2. Or create a GitHub issue with paper data
3. Or submit PR with JSON file in `pending/`

### For Curators
See [CURATOR_WORKFLOW.md](CURATOR_WORKFLOW.md) for:
- Reviewing submissions
- Approving/rejecting papers
- Merging to main database
- Updating statistics

## 📄 License

[Specify your license]

## 🔗 Links

- **Live Site:** https://yourusername.github.io/ml-accel-review/
- **Review Page:** https://yourusername.github.io/ml-accel-review/papers/
- **Admin Panel:** https://yourusername.github.io/ml-accel-review/admin/
- **GitHub:** https://github.com/yourusername/ml-accel-review

## 💡 Tips

- **Automated Updates**: Set up cron job to run your pipeline weekly
- **Backup**: `livingreview.json` is version-controlled
- **Search**: Client-side search included in review page
- **Duplicates**: Check before adding papers
- **Statistics**: Regenerate after major updates

## 🆘 Troubleshooting

**Papers not showing?**
- Check `data/livingreview.json` format
- Verify JSON is valid
- Check Hugo build logs

**CMS not loading?**
- Verify Netlify Identity is enabled
- Check Git Gateway configuration
- Look for errors in browser console

**GitHub Pages not deploying?**
- Check Actions tab for errors
- Verify Pages is enabled
- Ensure `baseURL` is correct

**Submission form not working?**
- Check GitHub repo URL in config
- Verify form redirects to issues
- Test with a dummy submission

---

For questions or help, open an issue or contact the maintainers.