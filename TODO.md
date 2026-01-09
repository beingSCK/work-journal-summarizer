# Future Improvements

Tracked ideas for future iterations. The tool is testable and feature-complete for core functionality.

## Email Formatting

**Problem**: Markdown doesn't render nicely in email clients - you see raw `#` headers and `**bold**` syntax.

**Potential solutions**:
- [ ] Convert markdown to HTML before sending (Pandoc, or Python's `markdown` library)
- [ ] Use a simple email template with inline CSS
- [ ] Consider plain text with smart formatting (indentation, dashes) instead of markdown

**Notes**: Pandoc is powerful but adds a system dependency. Python's `markdown` library is pure Python and might be sufficient for basic formatting.

## Summary Style Options

**Idea**: Offer different summary styles beyond the current bullet-point format.

- [ ] Add `--style narrative` flag for more prose-like summaries
- [ ] Add `--style brief` for ultra-condensed summaries
- [ ] Store style preference in config.yaml

**Far future**: A/B test which style leads to higher user satisfaction (track via reply sentiment?).

## Robustness

- [ ] Track processed message IDs to prevent duplicate processing on re-auth
- [ ] Add retry logic for transient API failures
- [ ] Better error messages when OAuth token is revoked

## Other Ideas

- [ ] Add `--since YYYY-MM-DD` flag for custom date ranges
- [ ] Support for multiple journal directories
- [ ] Weekly summaries option (in addition to bi-weekly)
- [ ] Slack/Discord notification option alongside email
