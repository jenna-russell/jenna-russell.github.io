# Papers Feed Integration

This directory contains the papers feed integration for tracking research paper reading activity.

## Structure

- `frontend/` - Frontend HTML, CSS, and JavaScript files
- `scripts/` - Python scripts for processing paper data
- `extension/` - Browser extension source code
- `data/` - Will contain paper data (created automatically by workflows)

## Setup Instructions

### 1. Configure GitHub Repository Settings

- Ensure GitHub Actions has write permissions
- The workflows will automatically handle deployment

### 2. Install Browser Extension

1. Open Chrome/Edge and go to `chrome://extensions/` (or `edge://extensions/`)
2. Enable "Developer mode"
3. Click "Load unpacked"
4. Select the `papers-feed/extension` directory
5. The extension will be installed

### 3. Configure Extension

1. Click the extension icon in your browser
2. Click "Options" or right-click the extension icon and select "Options"
3. Create a GitHub Personal Access Token (PAT) with `repo` and `issues:write` permissions
4. Enter your repository name (e.g., `jenna-russell/jenna-russell.github.io`)
5. Save the configuration

### 4. Test the Setup

1. Visit an arXiv paper page (e.g., `https://arxiv.org/abs/2301.00001`)
2. The extension should automatically log the visit
3. Check your repository's Issues tab - a new issue should be created with labels
4. The GitHub Actions workflow will process the issue and update the feed

## How It Works

1. **Browser Extension**: Monitors visits to research paper sites (arXiv, OpenReview, etc.)
2. **GitHub Issues as Database**: Paper visits are logged as GitHub issues using the [gh-store](https://github.com/dmarx/gh-store) system
3. **Automated Processing**: GitHub Actions workflows:
   - Process new paper visits (`1_update_and_enrich.yml`)
   - Update the data snapshot
   - Deploy the frontend (`2_deploy-frontend.yml`)
4. **Interactive Feed**: The feed is available at `/papers-feed/` on your website

## Workflows

- `1_update_and_enrich.yml` - Processes paper visit issues and updates the data
- `2_deploy-frontend.yml` - Deploys the frontend to GitHub Pages

## Accessing the Feed

Once set up, the papers feed will be available at:
- Website: `https://jenna-russell.github.io/papers-feed/`
- Jekyll page: `/papers-feed/` (links to the feed)

## Troubleshooting

- **No issues created**: Check that the extension is configured with a valid PAT
- **Feed not updating**: Check GitHub Actions tab for workflow errors
- **Extension not working**: Ensure the extension is enabled and has proper permissions

## Credits

Based on the [papers-feed-template](https://github.com/dmarx/papers-feed-template) by [dmarx](https://github.com/dmarx).
