import os
import git
from datetime import datetime
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

# GitHub repository URL and user config from environment
GITHUB_REPO_URL = os.getenv('GITHUB_REPO_URL')
GIT_USER_NAME = os.getenv('GIT_USER_NAME')
GIT_USER_EMAIL = os.getenv('GIT_USER_EMAIL')
GIT_REMOTE_NAME = os.getenv('GIT_REMOTE_NAME', 'origin')

if not GITHUB_REPO_URL:
    raise ValueError("GITHUB_REPO_URL not found in environment variables")
if not GIT_USER_NAME or not GIT_USER_EMAIL:
    raise ValueError(
        "GIT_USER_NAME or GIT_USER_EMAIL not found in environment variables")

# Path to the repository (using current file's directory)
REPO_PATH = os.path.dirname(os.path.abspath(__file__))
LOG_FILE_PATH = os.path.join(REPO_PATH, "asset_registry_daily_log.txt")

BRANCH_NAME = "master"

def append_log_and_commit():
    """Appends daily asset registry log entry and commits changes to GitHub."""
    now = datetime.now()
    log_entry = f"{now.strftime('%Y-%m-%d %H:%M:%S')} - Asset Registry Daily Update: Fields and boundaries synchronized\n"

    # Create log file if it doesn't exist
    if not os.path.exists(LOG_FILE_PATH):
        with open(LOG_FILE_PATH, "w") as file:
            file.write("Asset Registry Daily Log\n")
            file.write("=======================\n\n")

    # Append to the log file
    with open(LOG_FILE_PATH, "a") as file:
        file.write(log_entry)

    try:
        # Commit and push changes
        repo = git.Repo(REPO_PATH)

        # Configure Git user for this repository
        repo.config_writer().set_value("user", "name", GIT_USER_NAME).release()
        repo.config_writer().set_value("user", "email", GIT_USER_EMAIL).release()

        repo.git.add(LOG_FILE_PATH)
        commit = repo.index.commit(
            f"Asset Registry: Daily log update {now.strftime('%Y-%m-%d')}")
        origin = repo.remote(name=GIT_REMOTE_NAME)

        # More verbose push with error handling
        try:
            origin.push(BRANCH_NAME)
            print(f"Successfully committed and pushed log: {log_entry.strip()}")
            print(f"Commit hash: {commit.hexsha}")
        except git.GitCommandError as git_error:
            print(f"Failed to push to GitHub: {git_error}")
            print("Check your GitHub token and repository permissions")
    except Exception as e:
        print(f"Error during Git operations: {str(e)}")

if __name__ == "__main__":
    append_log_and_commit()
