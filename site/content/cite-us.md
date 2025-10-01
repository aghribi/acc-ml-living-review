---
title: "Cite Us"
date: 2025-01-01
draft: false
layout: "single"
---

<div class="container">
 <div class="page-header">
<h1>How to Cite This Review</h1>
<p class="page-subtitle">Help us track the impact of this living review by citing it in your work</p>
</div>
<div class="section">
<h2>Standard Citation</h2>
<span class="citation-format">APA Format</span>
<div class="citation-box">
<button class="copy-button" onclick="copyToClipboard('citation-apa', this)">Copy</button>
<pre class="citation-text" id="citation-apa">AI/ML for Particle Accelerators Collaboration. (2025). The AI/ML for particle accelerators living review. Retrieved from https://ml-accel-review.org</pre>
</div>
<span class="citation-format">IEEE Format</span>
<div class="citation-box">
<button class="copy-button" onclick="copyToClipboard('citation-ieee', this)">Copy</button>
<pre class="citation-text" id="citation-ieee">AI/ML for Particle Accelerators Collaboration, "The AI/ML for particle accelerators living review," 2025. [Online]. Available: https://ml-accel-review.org</pre>
</div>
</div>

<script>
function copyToClipboard(elementId, button) {
    const text = document.getElementById(elementId).textContent;
    navigator.clipboard.writeText(text).then(() => {
        button.textContent = 'Copied!';
        setTimeout(() => button.textContent = 'Copy', 2000);
    });
}
</script>