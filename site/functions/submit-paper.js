// functions/submit-paper.js
import fetch from "node-fetch";

export async function handler(event, context) {
  if (event.httpMethod !== "POST") {
    return { statusCode: 405, body: "Method Not Allowed" };
  }

  try {
    const data = JSON.parse(event.body);

    // Prepare filename
    const date = new Date().toISOString().split("T")[0];
    const slug = data.title.toLowerCase().replace(/[^a-z0-9]+/g, "-");
    const path = `data/submissions/pending/${date}-${slug}.json`;

    // Encode JSON for GitHub API
    const content = Buffer.from(JSON.stringify(data, null, 2)).toString("base64");

    // GitHub API call
    const response = await fetch(
      `https://api.github.com/repos/${process.env.GITHUB_REPO}/contents/${path}`,
      {
        method: "PUT",
        headers: {
          "Authorization": `token ${process.env.GITHUB_TOKEN}`,
          "Content-Type": "application/json",
          "Accept": "application/vnd.github.v3+json"
        },
        body: JSON.stringify({
          message: `Add pending submission: ${data.title}`,
          content: content,
          branch: process.env.GITHUB_BRANCH || "main"
        })
      }
    );

    if (!response.ok) {
      const err = await response.text();
      return { statusCode: response.status, body: err };
    }

    return {
      statusCode: 200,
      body: JSON.stringify({ success: true, message: "Submission stored as pending." })
    };
  } catch (err) {
    return { statusCode: 500, body: err.message };
  }
}
