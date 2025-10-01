// netlify/functions/auth.js
const fetch = require("node-fetch");

exports.handler = async (event) => {
  const client_id = process.env.OAUTH_CLIENT_ID;
  const client_secret = process.env.OAUTH_CLIENT_SECRET;

  // Si pas de code fourni
  if (!event.queryStringParameters.code) {
    return {
      statusCode: 400,
      body: JSON.stringify({ error: "Missing code parameter" }),
    };
  }

  const code = event.queryStringParameters.code;

  // Échange le code contre un token GitHub
  const response = await fetch("https://github.com/login/oauth/access_token", {
    method: "POST",
    headers: { Accept: "application/json" },
    body: new URLSearchParams({
      client_id,
      client_secret,
      code,
    }),
  });

  const data = await response.json();

  return {
    statusCode: 200,
    body: JSON.stringify(data),
  };
};
