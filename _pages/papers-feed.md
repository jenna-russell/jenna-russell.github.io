---
layout: page
title: Papers Feed
permalink: /papers-feed/
nav: true
nav_order: 5
---

# Research Papers Reading Feed

This page tracks the research papers I'm reading, automatically logged via a browser extension when I visit papers on arXiv, OpenReview, and other sources.

<div style="text-align: center; margin: 2rem 0;">
  <p style="margin-bottom: 1rem;">
    <a href="/papers-feed/index.html" class="btn btn-primary" style="padding: 1rem 2rem; font-size: 1.1rem;" target="_blank">
      View Interactive Papers Feed →
    </a>
  </p>
  <p style="font-size: 0.9em; color: #666;">
    The feed will show papers you've visited using the browser extension. Make sure you've visited some papers and the GitHub Actions workflows have processed them.
  </p>
</div>

## How it works

1. **Browser Extension**: A browser extension monitors my reading habits when I visit research paper sites
2. **Automatic Logging**: Interactions with papers get logged as GitHub issues (using [gh-store](https://github.com/dmarx/gh-store))
3. **Interactive Feed**: GitHub Actions workflows automatically update an interactive webpage showing my reading activity

## Supported Sources

- arXiv
- OpenReview
- Manual logging for any page via extension popup

## Setup

This feed is powered by the [papers-feed-template](https://github.com/dmarx/papers-feed-template) project.
