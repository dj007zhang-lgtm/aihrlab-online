import sys
sys.path.insert(0, "/Users/andyzhang/WorkBuddy/2026-06-03-17-17-18/site-migrated/scripts")
import git_atomic

files = [
    "articles/ai-era-employee-retention-2026.html",
    "assets/images/banners/ai-era-employee-retention-2026.webp",
    "assets/js/article-index.json",
    "articles/index.html",
    "sitemap.xml",
    "llms-full.txt",
]
msg = "feat: 发布《AI 改写岗位后，人凭什么留下》+ 四源同步 (#271)"
sha = git_atomic.atomic_commit(files, msg, dry_run=False, verbose=True)
print("NEW_COMMIT_SHA:", sha)
