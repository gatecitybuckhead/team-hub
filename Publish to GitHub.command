#!/bin/bash
# Double-click this to publish the GCB Team Hub to GitHub Pages.
# It commits every change in this folder and pushes it live.
cd "$(dirname "$0")" || exit 1

echo "Publishing GCB Team Hub…"
echo "Folder: $(pwd)"
echo

# clear any stale lock left by another tool
rm -f .git/index.lock 2>/dev/null

git add -A
git commit -m "Update Team Hub ($(date '+%Y-%m-%d %H:%M'))" || echo "(nothing new to commit)"
echo
echo "Pushing to GitHub…"
if git push origin main; then
  echo
  echo "✅ Done. Live in about a minute:"
  echo "   https://gatecitybuckhead.github.io/team-hub/"
else
  echo
  echo "⚠️  Push failed. If it asked for a username/password, your GitHub"
  echo "    login may need refreshing — tell Claude and it'll help."
fi

echo
read -n 1 -s -r -p "Press any key to close this window."
echo
