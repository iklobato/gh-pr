# GitHub PR Analysis Tool

A powerful command-line tool for analyzing GitHub Pull Requests with interactive features, status filtering, and detailed metrics tracking. The tool provides insights into PR statistics, review status, and historical changes over time.

## Features

- Interactive user and status selection
- PR metrics visualization including:
  - Days open
  - Number of files changed
  - Commit count
  - File types affected
  - Comment count
- Historical tracking of PR changes
- Multiple output formats (table/JSON)
- Progress tracking
- Support for both interactive and non-interactive modes
- Rich terminal output with color-coded changes

## Installation

1. Clone the repository
2. Install dependencies:
```bash
pip install aiohttp inquirer rich
```

## Configuration

The tool can be configured using either command-line arguments or environment variables:

### Environment Variables
- `GITHUB_TOKEN`: Your GitHub personal access token
- `GITHUB_REPO_OWNER`: Repository owner (default: 'iklobato')
- `GITHUB_REPO_NAME`: Repository name (default: 'LightApi')

### Command Line Arguments
```bash
python gh-pr.py [OPTIONS]

Options:
  --token TEXT          GitHub token (overrides GITHUB_TOKEN env var)
  --repo-owner TEXT     Repository owner
  --repo-name TEXT      Repository name
  --user TEXT          GitHub username to analyze
  --status TEXT        Comma-separated list of PR statuses (DRAFT,READY,PENDING REVIEW)
  --sort TEXT          Field to sort results by
  --output TEXT        Output format: table|json (default: table)
  --no-progress        Disable progress bar
  --non-interactive    Run in non-interactive mode (requires --user)
```

## Usage Examples

### Interactive Mode
```bash
# Basic usage with interactive prompts
python gh-pr.py

# Specify a user but select status interactively
python gh-pr.py --user johndoe
```

### Non-interactive Mode
```bash
# Analyze specific user's PRs with defined status
python gh-pr.py --user johndoe --status READY,PENDING_REVIEW --non-interactive

# Output results as JSON
python gh-pr.py --user johndoe --output json --non-interactive
```

## Features in Detail

### Status Tracking
The tool tracks various PR statuses:
- DRAFT: Pull requests in draft mode
- READY: Approved and ready to merge
- PENDING REVIEW: Awaiting review
- Custom status based on review states

### Historical Analysis
- Tracks changes in PR metrics over time
- Shows increases/decreases in various metrics
- Stores historical data in `.pr_history.json`

### Rich Output
- Color-coded changes (increases in green, decreases in red)
- Progress bars for long-running operations
- Formatted tables for easy reading

## Development

### Project Structure
```
gh-pr/
├── GitHubPRClient        # Handles GitHub API interactions
├── HistoryManager        # Manages historical PR data
├── InlinePRAnalyzer     # Core analysis functionality
└── main                 # CLI entry point and argument parsing
```

### Key Components

1. `GitHubPRClient`: Manages GitHub API interactions
   - Fetches PR data
   - Retrieves user information
   - Gets PR details including reviews, comments, and commits

2. `HistoryManager`: Handles historical data
   - Saves PR analysis results
   - Loads previous results for comparison
   - Manages the `.pr_history.json` file

3. `InlinePRAnalyzer`: Core analysis functionality
   - Processes PR data
   - Calculates metrics
   - Generates comparisons with historical data

## Contributing

1. Fork the repository
2. Create a feature branch
3. Submit a pull request

## License

This project is open source and available under the MIT License.