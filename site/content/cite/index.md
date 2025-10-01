---
# title: "Cite Us"
---

<div class="container">
  <div class="page-header">
    <h1>How to Cite This Review</h1>
    <p class="page-subtitle">Help us track the impact of this living review by citing it in your work</p>
  </div>

  <!-- 📥 Download section moved on top -->
  <div class="section">
    <h2>Download Citation Files</h2>
    <p>Download citation files in various formats for easy import into your reference manager:</p>
    <div class="download-buttons">
      <a href="/downloads/ml-accel-review.bib" class="btn" download>📋 BibTeX (.bib)</a>
      <a href="/downloads/ml-accel-review.ris" class="btn" download>📄 RIS Format (.ris)</a>
      <a href="/downloads/ml-accel-review.enw" class="btn" download>📑 EndNote (.enw)</a>
    </div>
  </div>

  <!-- BibTeX entry -->
  <div class="section">
    <h2>BibTeX Entry</h2>
    <p>Use this BibTeX entry for LaTeX documents:</p>
    <div class="citation-box">
      <button class="copy-button" onclick="copyToClipboard('bibtex', this)">Copy</button>
      <pre class="citation-text" id="bibtex">
@misc{ml_accel_review_2025,
  title        = {The AI/ML for particle accelerators living review},
  author       = {{AI/ML for Particle Accelerators Collaboration}},
  year         = {2025},
  howpublished = {\url{https://ml-accel-review.org}},
  note         = {Accessed: 2025-09-30}
}</pre>
    </div>
  </div>

  <!-- Why Cite -->
  <div class="section">
    <h2>Why Cite This Review?</h2>
    <p>By citing this living review, you:</p>
    <ul style="color: var(--text-secondary); line-height: 1.8; margin-left: 20px; margin-top: 10px;">
      <li>Support the continued maintenance and development of this community resource</li>
      <li>Help track the impact and reach of AI/ML applications in accelerator science</li>
      <li>Enable funding agencies to recognize the value of open, collaborative reviews</li>
      <li>Give credit to the many contributors who maintain and update this resource</li>
    </ul>
  </div>
</div>

<script>
function copyToClipboard(elementId, button) {
  const text = document.getElementById(elementId).textContent;
  navigator.clipboard.writeText(text).then(() => {
    const originalText = button.textContent;
    button.textContent = '✓ Copied!';
    button.classList.add('copied');
    setTimeout(() => {
      button.textContent = originalText;
      button.classList.remove('copied');
    }, 2000);
  }).catch(err => {
    console.error('Failed to copy:', err);
    button.textContent = '✗ Failed';
    setTimeout(() => {
      button.textContent = 'Copy';
    }, 2000);
  });
}
</script>
