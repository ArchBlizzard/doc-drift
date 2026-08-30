# Deploying the web UI on Render

The repo ships a `Dockerfile` and a `render.yaml` blueprint. Steps:

1. Push this repo to GitHub.
2. On render.com: New > Blueprint > pick the repo. Render reads `render.yaml`
   and creates the `docdrift` web service (free plan, Docker).
3. In the service's Environment tab, set two secrets:
   - `CLAUDE_CODE_OAUTH_TOKEN`: run `claude setup-token` on your own machine
     and paste the token it prints. This is what lets the server call Claude
     using your subscription.
   - `DOCDRIFT_ACCESS_CODE`: any secret word. The site then shows an
     "Access code" field, and only people who know the word can start audits.
4. Deploy. Your app gets a public URL like `https://docdrift.onrender.com`.

## Will it work without an API key? (honest answer)

- **With nothing set:** the site loads and looks fine, but pressing
  "Run the audit" fails with an auth error, because the server has no way to
  call Claude. Your laptop works without any setup only because Claude Code
  is logged in there; a fresh server is not.
- **You do not need a paid API key.** `CLAUDE_CODE_OAUTH_TOKEN` (from
  `claude setup-token`) uses your existing Claude subscription. That is the
  same auth the whole project runs on.
- **Care with a public URL + your personal token:** every audit anyone runs
  spends YOUR subscription usage, and Anthropic's rules do not allow offering
  your claude.ai login to strangers as a service. So if you deploy, always
  set `DOCDRIFT_ACCESS_CODE` and share it only with people you trust (for
  example the hackathon judges), and rotate the token afterwards
  (`claude setup-token` again invalidates nothing by itself; revoke old
  tokens from your Claude account settings if needed).
- Free-plan notes: the service sleeps when idle (first visit after a while
  takes ~1 minute to wake), has 512MB RAM, and keeps no permanent disk, so
  past results disappear on restart. Fine for a demo, not for production.

## Kaggle fetch on a server

The "From Kaggle" tab needs Kaggle credentials on the server
(`KAGGLE_USERNAME` and `KAGGLE_KEY` env vars). Leave them unset to keep that
path disabled; uploads still work.
