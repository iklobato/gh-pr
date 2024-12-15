import asyncio
import logging
from datetime import datetime
import os
from typing import List, Dict, Any
from rich.console import Console
from rich.progress import Progress
from rich.table import Table
import aiohttp
import inquirer
import argparse

logging.basicConfig(
    format='%(asctime)s - %(message)s',
    level=logging.INFO,
    datefmt='%H:%M:%S',
    handlers=[logging.StreamHandler()],
)

console = Console()


class GitHubPRClient:
    def __init__(self, token: str, repo_owner: str, repo_name: str):
        self.headers = {
            'Authorization': f'token {token}',
            'Accept': 'application/vnd.github.v3+json',
        }
        self.base_url = 'https://api.github.com'
        self.repo_owner = repo_owner
        self.repo_name = repo_name
        self.session = None

    async def __aenter__(self):
        self.session = aiohttp.ClientSession(headers=self.headers)
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb):
        if self.session:
            await self.session.close()

    async def _fetch(self, url: str) -> Dict[str, Any]:
        async with self.session.get(url) as response:
            response.raise_for_status()
            return await response.json()

    async def get_all_users(self) -> List[str]:
        url = f'{self.base_url}/repos/{self.repo_owner}/{self.repo_name}/pulls'
        data = await self._fetch(url)
        return list(set(pr['user']['login'] for pr in data))

    async def get_user_pull_requests(self, user: str = None):
        url = f'{self.base_url}/repos/{self.repo_owner}/{self.repo_name}/pulls'
        data = await self._fetch(url)
        if user:
            return [pr for pr in data if pr['user']['login'] == user]
        return data

    async def get_pr_details(self, pr_number: str) -> Dict[str, Any]:
        base_url = f'{self.base_url}/repos/{self.repo_owner}/{self.repo_name}/pulls/{pr_number}'
        endpoints = ['reviews', 'comments', 'commits', 'files']
        tasks = [self._fetch(f'{base_url}/{endpoint}') for endpoint in endpoints]
        results = await asyncio.gather(*tasks)
        return dict(zip(endpoints, results))


class InlinePRAnalyzer:
    def __init__(self, client: GitHubPRClient, args: argparse.Namespace):
        self.client = client
        self.args = args

    def process_pr(self, pr: Dict[str, Any], details: Dict[str, Any]) -> Dict[str, Any]:
        # reviews = details['reviews']
        comments = details['comments']
        commits = details['commits']
        files = details['files']

        # approvers = [review['user']['login'] for review in reviews if review['state'].lower() == 'approved']
        created_date = datetime.strptime(pr['created_at'], '%Y-%m-%dT%H:%M:%SZ')
        date_diff = (datetime.now() - created_date).days
        file_types = set(f['filename'].split('.')[-1] if '.' in f['filename'] else 'no_ext' for f in files)

        return {
            'PR #': pr['number'],
            'Title': pr['title'],
            'Days Open': date_diff,
            'Files Changed': len(files),
            'Commits': len(commits),
            'File Types': ', '.join(sorted(file_types)),
            'Comments': len(comments),
            # 'Status': ('DRAFT' if pr['draft'] else ('READY' if approvers else 'PENDING REVIEW')),
        }

    async def get_user_selection(self) -> str:
        if self.args.user:
            return self.args.user

        users = await self.client.get_all_users()
        questions = [inquirer.List('user', message="Select user", choices=users, carousel=True)]
        answers = inquirer.prompt(questions)
        return answers['user'] if answers else ''

    async def get_available_statuses(self) -> List[str]:
        prs = await self.client.get_user_pull_requests()
        statuses = {'ALL'}

        for pr in prs:
            if pr['draft']:
                statuses.add('DRAFT')
                continue

            details = await self.client.get_pr_details(pr['number'])
            reviews = details['reviews']

            approvers = [review['user']['login'] for review in reviews if review['state'].lower() == 'approved']
            if approvers:
                statuses.add('READY')
            else:
                statuses.add('PENDING REVIEW')

            for review in reviews:
                if review['state'].upper() not in ['APPROVED', 'COMMENTED']:
                    statuses.add(review['state'].upper())

        return sorted(list(statuses))

    async def get_status_selection(self) -> List[str]:
        if self.args.status:
            statuses = self.args.status.split(',')
            if 'ALL' in statuses:
                available_statuses = await self.get_available_statuses()
                return [status for status in available_statuses if status != 'ALL']
            return statuses

        available_statuses = await self.get_available_statuses()
        if not available_statuses:
            console.print("[yellow]No PR statuses found[/yellow]")
            return []

        questions = [
            inquirer.Checkbox(
                'statuses',
                message="Select PR statuses (ALL will select everything)",
                choices=available_statuses,
                default=['ALL'],
            )
        ]
        answers = inquirer.prompt(questions)
        if not answers:
            return []

        selected_statuses = answers['statuses']
        if 'ALL' in selected_statuses:
            return [status for status in available_statuses if status != 'ALL']
        return selected_statuses

    def get_sort_selection(self, fields: List[str]) -> str:
        if self.args.sort:
            return self.args.sort

        questions = [inquirer.List('sort', message="Sort by", choices=fields, default='Days Open')]
        answers = inquirer.prompt(questions)
        return answers['sort'] if answers else 'Days Open'

    def display_results(self, data: List[Dict[str, Any]]):
        if self.args.output == 'json':
            console.print_json(data=data)
            return

        table = Table(show_header=True, header_style="bold magenta")

        if not data:
            console.print("[red]No PRs found matching criteria[/red]")
            return

        for column in data[0].keys():
            table.add_column(column)

        for row in data:
            table.add_row(*[str(value) for value in row.values()])

        console.print(table)

    async def analyze(self):
        try:
            user = await self.get_user_selection()
            if not user:
                return

            # First progress for fetching PRs
            with Progress(disable=self.args.no_progress) as progress:
                fetch_task = progress.add_task("[cyan]Fetching PRs...", total=None)
                prs = await self.client.get_user_pull_requests(user)
                progress.update(fetch_task, completed=100)

            if not prs:
                console.print(f"[yellow]No PRs found for user {user}[/yellow]")
                return

            statuses = await self.get_status_selection()
            if not statuses:
                return

            # Second progress for processing PR details
            with Progress(disable=self.args.no_progress, transient=True) as progress:
                details_task = progress.add_task(
                    "[cyan]Processing PR details...", 
                    total=len(prs)
                )
                
                # Process PRs in smaller batches to avoid overwhelming the API
                batch_size = 3
                pr_details = []
                
                for i in range(0, len(prs), batch_size):
                    batch = prs[i:i + batch_size]
                    # Create tasks for the current batch
                    batch_tasks = [self.client.get_pr_details(pr['number']) for pr in batch]
                    # Wait for all tasks in the batch to complete
                    batch_results = await asyncio.gather(*batch_tasks)
                    pr_details.extend(batch_results)
                    # Update progress for the completed batch
                    progress.update(details_task, advance=len(batch))
                    # Small delay to avoid rate limiting
                    await asyncio.sleep(0.1)

            pr_data = [self.process_pr(pr, details) for pr, details in zip(prs, pr_details)]

            if pr_data:
                sort_by = self.get_sort_selection(list(pr_data[0].keys()))
                pr_data.sort(key=lambda x: x[sort_by], reverse=True)
                self.display_results(pr_data)
            else:
                console.print("[yellow]No PRs found matching selected statuses[/yellow]")

        except aiohttp.ClientError as e:
            console.print(f"[red]API Error: {e}[/red]")
            raise

def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description='GitHub PR Analysis Tool')

    parser.add_argument('--token', help='GitHub token (overrides GITHUB_TOKEN env var)')
    parser.add_argument('--repo-owner', help='Repository owner (overrides GITHUB_REPO_OWNER env var)')
    parser.add_argument('--repo-name', help='Repository name (overrides GITHUB_REPO_NAME env var)')

    parser.add_argument('--user', help='GitHub username to analyze (skips interactive selection)')
    parser.add_argument(
        '--status',
        help='Comma-separated list of PR statuses to include (DRAFT,READY,PENDING REVIEW)',
    )
    parser.add_argument('--sort', help='Field to sort by')

    parser.add_argument(
        '--output',
        choices=['table', 'json'],
        default='table',
        help='Output format (default: table)',
    )
    parser.add_argument('--no-progress', action='store_true', help='Disable progress bar')
    parser.add_argument(
        '--non-interactive',
        action='store_true',
        help='Run in non-interactive mode (requires --user)',
    )

    args = parser.parse_args()

    if args.non_interactive and not args.user:
        parser.error("--non-interactive requires --user")

    return args


async def main():
    args = parse_args()

    token = args.token or os.getenv('GITHUB_TOKEN')
    if not token:
        console.print("[red]Missing GitHub token. Provide via --token or GITHUB_TOKEN env var[/red]")
        return

    repo_owner = args.repo_owner or os.getenv('GITHUB_REPO_OWNER', 'WannaApp')
    repo_name = args.repo_name or os.getenv('GITHUB_REPO_NAME', 'wanna_backend_us')

    async with GitHubPRClient(token, repo_owner, repo_name) as client:
        analyzer = InlinePRAnalyzer(client, args)
        await analyzer.analyze()


if __name__ == "__main__":
    asyncio.run(main())

