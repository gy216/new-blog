#!/usr/bin/env python3
import os
import sys
import json
import urllib.request
import urllib.error
import html as html_mod
from datetime import datetime

# ========== 配置 ==========
OWNER = os.environ.get("OWNER", "")
REPO = os.environ.get("REPO", "")
TOKEN = os.environ.get("GH_TOKEN", "")
SITE_TITLE = os.environ.get("SITE_TITLE", "我的博客")
BASE_URL = os.environ.get("BASE_URL", "")

# ========== GitHub API ==========
def api_request(url):
    req = urllib.request.Request(url)
    if TOKEN:
        req.add_header("Authorization", f"token {TOKEN}")
    req.add_header("Accept", "application/vnd.github.v3+json")
    try:
        with urllib.request.urlopen(req, timeout=15) as resp:
            return json.loads(resp.read().decode())
    except urllib.error.HTTPError as e:
        print(f"API error: {e.code} {e.reason}")
        return []

# ========== Markdown 渲染（纯 Python，不依赖第三方） ==========
def markdown_to_html(md_text):
    """
    极简 Markdown 渲染器
    支持：标题、段落、加粗、斜体、代码块、行内代码、链接、图片、列表、引用
    """
    if not md_text:
        return ""

    lines = md_text.split("\n")
    html_lines = []
    in_code_block = False
    in_list = False
    in_quote = False

    i = 0
    while i < len(lines):
        line = lines[i]

        # 代码块
        if line.strip().startswith("```"):
            if not in_code_block:
                lang = line.strip()[3:].strip()
                html_lines.append(f'<pre><code class="language-{lang}">')
                in_code_block = True
            else:
                html_lines.append("</code></pre>")
                in_code_block = False
            i += 1
            continue

        if in_code_block:
            html_lines.append(html_mod.escape(line))
            i += 1
            continue

        # 空行
        if not line.strip():
            if in_list:
                html_lines.append("</ul>")
                in_list = False
            if in_quote:
                html_lines.append("</blockquote>")
                in_quote = False
            html_lines.append("")
            i += 1
            continue

        # 标题
        if line.startswith("# "):
            html_lines.append(f"<h1>{_inline(line[2:])}</h1>")
        elif line.startswith("## "):
            html_lines.append(f"<h2>{_inline(line[3:])}</h2>")
        elif line.startswith("### "):
            html_lines.append(f"<h3>{_inline(line[4:])}</h3>")
        elif line.startswith("#### "):
            html_lines.append(f"<h4>{_inline(line[5:])}</h4>")

        # 引用
        elif line.startswith("> "):
            if not in_quote:
                html_lines.append("<blockquote>")
                in_quote = True
            html_lines.append(f"<p>{_inline(line[2:])}</p>")

        # 无序列表
        elif line.startswith("- ") or line.startswith("* "):
            if not in_list:
                html_lines.append("<ul>")
                in_list = True
            html_lines.append(f"<li>{_inline(line[2:])}</li>")

        # 分割线
        elif line.strip() in ("---", "***", "___"):
            html_lines.append("<hr>")

        # 普通段落
        else:
            html_lines.append(f"<p>{_inline(line)}</p>")

        i += 1

    if in_list:
        html_lines.append("</ul>")
    if in_quote:
        html_lines.append("</blockquote>")

    return "\n".join(html_lines)


def _inline(text):
    """行内格式：加粗、斜体、行内代码、链接、图片"""
    import re
    # 行内代码
    text = re.sub(r'`([^`]+)`', r'<code>\1</code>', text)
    # 加粗
    text = re.sub(r'\*\*(.+?)\*\*', r'<strong>\1</strong>', text)
    # 斜体
    text = re.sub(r'\*(.+?)\*', r'<em>\1</em>', text)
    # 图片
    text = re.sub(r'!\[([^\]]*)\]\(([^)]+)\)', r'<img src="\2" alt="\1" loading="lazy">', text)
    # 链接
    text = re.sub(r'\[([^\]]+)\]\(([^)]+)\)', r'<a href="\2">\1</a>', text)
    return text


# ========== 拉 Issues ==========
def fetch_issues():
    url = f"https://api.github.com/repos/{OWNER}/{REPO}/issues?state=open&per_page=100&sort=created&direction=desc"
    issues = api_request(url)
    # 过滤 PR
    return [i for i in issues if "pull_request" not in i]


# ========== 生成首页 ==========
def build_index(issues):
    items = []
    for issue in issues:
        title = html_mod.escape(issue["title"])
        num = issue["number"]
        date = issue["created_at"][:10]
        labels = " ".join(
            f'<span class="tag">{html_mod.escape(l["name"])}</span>'
            for l in issue["labels"]
        )
        items.append(f"""
        <article class="post-preview">
          <h2><a href="posts/{num}.html">{title}</a></h2>
          <div class="meta">{date}</div>
          <div class="tags">{labels}</div>
        </article>
        """)

    return INDEX_TEMPLATE.replace("{{TITLE}}", SITE_TITLE) \
                         .replace("{{POSTS}}", "\n".join(items)) \
                         .replace("{{UPDATED}}", datetime.utcnow().strftime("%Y-%m-%d %H:%M UTC"))


# ========== 生成文章页 ==========
def build_post(issue):
    title = html_mod.escape(issue["title"])
    body_html = markdown_to_html(issue["body"] or "")
    date = issue["created_at"][:10]
    num = issue["number"]
    labels = " ".join(
        f'<span class="tag">{html_mod.escape(l["name"])}</span>'
        for l in issue["labels"]
    )

    return POST_TEMPLATE.replace("{{TITLE}}", title) \
                        .replace("{{BODY}}", body_html) \
                        .replace("{{DATE}}", date) \
                        .replace("{{NUMBER}}", str(num)) \
                        .replace("{{TAGS}}", labels) \
                        .replace("{{SITE_TITLE}}", SITE_TITLE)


# ========== 模板 ==========
INDEX_TEMPLATE = """<!DOCTYPE html>
<html lang="zh">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>{{TITLE}}</title>
<style>
* { margin: 0; padding: 0; box-sizing: border-box; }
body { font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", sans-serif; line-height: 1.7; color: #24292f; max-width: 720px; margin: 0 auto; padding: 20px; }
h1 { font-size: 1.8em; margin-bottom: 0.5em; }
.post-preview { padding: 1.5em 0; border-bottom: 1px solid #eaecef; }
.post-preview h2 { font-size: 1.3em; margin-bottom: 0.3em; }
.post-preview a { color: #0969da; text-decoration: none; }
.post-preview a:hover { text-decoration: underline; }
.meta { color: #656d76; font-size: 0.85em; margin-bottom: 0.5em; }
.tag { display: inline-block; background: #ddf4ff; color: #0969da; padding: 2px 8px; border-radius: 12px; font-size: 0.75em; margin-right: 4px; }
footer { margin-top: 2em; text-align: center; color: #656d76; font-size: 0.85em; }
</style>
</head>
<body>
<h1>{{TITLE}}</h1>
<p style="color:#656d76;margin-bottom:1.5em;">更新于 {{UPDATED}}</p>
{{POSTS}}
<footer>由 GitHub Issues 驱动 · <a href="https://github.com/OWNER/REPO">源仓库</a></footer>
</body>
</html>"""

POST_TEMPLATE = """<!DOCTYPE html>
<html lang="zh">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>{{TITLE}} - {{SITE_TITLE}}</title>
<style>
* { margin: 0; padding: 0; box-sizing: border-box; }
body { font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", sans-serif; line-height: 1.7; color: #24292f; max-width: 720px; margin: 0 auto; padding: 20px; }
h1 { font-size: 1.6em; margin-bottom: 0.3em; }
.meta { color: #656d76; font-size: 0.85em; margin-bottom: 1.5em; }
.back { display: inline-block; margin-bottom: 1.5em; color: #0969da; text-decoration: none; }
.back:hover { text-decoration: underline; }
article h2 { font-size: 1.3em; margin-top: 1.5em; margin-bottom: 0.5em; }
article h3 { font-size: 1.1em; margin-top: 1.2em; margin-bottom: 0.4em; }
article p { margin-bottom: 1em; }
article ul, article ol { margin-bottom: 1em; padding-left: 1.5em; }
article li { margin-bottom: 0.3em; }
article blockquote { border-left: 4px solid #d0d7de; padding-left: 1em; margin: 1em 0; color: #656d76; }
article code { background: #f6f8fa; padding: 2px 6px; border-radius: 4px; font-size: 0.9em; }
article pre { background: #f6f8fa; padding: 1em; border-radius: 6px; overflow-x: auto; margin-bottom: 1em; }
article pre code { background: none; padding: 0; }
article img { max-width: 100%; border-radius: 6px; margin: 1em 0; }
article a { color: #0969da; }
.tag { display: inline-block; background: #ddf4ff; color: #0969da; padding: 2px 8px; border-radius: 12px; font-size: 0.75em; margin-right: 4px; }
hr { border: none; border-top: 1px solid #eaecef; margin: 2em 0; }
</style>
</head>
<body>
<a class="back" href="../index.html">← 返回首页</a>
<h1>{{TITLE}}</h1>
<div class="meta">{{DATE}} · Issue #{{NUMBER}} · {{TAGS}}</div>
<article>
{{BODY}}
</article>
<hr>
<footer style="text-align:center;color:#656d76;font-size:0.85em;">
  <a href="https://github.com/OWNER/REPO/issues/{{NUMBER}}">在 GitHub 上讨论</a>
</footer>
</body>
</html>"""


# ========== 主流程 ==========
def main():
    print(f"Fetching issues from {OWNER}/{REPO}...")
    issues = fetch_issues()
    print(f"Found {len(issues)} posts")

    # 创建输出目录
    os.makedirs("output", exist_ok=True)
    os.makedirs("output/posts", exist_ok=True)

    # 生成首页
    index_html = build_index(issues)
    index_html = index_html.replace("OWNER/REPO", f"{OWNER}/{REPO}")
    with open("output/index.html", "w", encoding="utf-8") as f:
        f.write(index_html)
    print("✓ index.html")

    # 生成每篇文章
    for issue in issues:
        post_html = build_post(issue)
        post_html = post_html.replace("OWNER/REPO", f"{OWNER}/{REPO}")
        with open(f"output/posts/{issue['number']}.html", "w", encoding="utf-8") as f:
            f.write(post_html)
        print(f"✓ post #{issue['number']}: {issue['title'][:30]}")

    print("\nDone! All files in output/")
    print(f"Total: 1 index + {len(issues)} posts")


if __name__ == "__main__":
    if not OWNER or not REPO:
        print("ERROR: OWNER and REPO env vars required")
        sys.exit(1)
    main()
