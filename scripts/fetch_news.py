import os
import datetime
import feedparser
import html
from typing import List, Dict

# 저명한 기술 소스 위주로 재설정
NEWS_SOURCES = {
    "AI": [
        "https://openai.com/news/rss.xml",
        "https://huggingface.co/blog/feed.xml",
        "http://export.arxiv.org/rss/cs.AI"
    ],
    "Kubernetes": [
        "https://kubernetes.io/feed.xml",
        "https://www.cncf.io/blog/feed/"
    ],
    "Open Source": [
        "https://github.blog/category/open-source/feed/",
        "https://opensource.googleblog.com/feeds/posts/default"
    ],
    "Infrastructure & Cloud": [
        "https://aws.amazon.com/blogs/aws/feed/",
        "https://cloud.google.com/blog/rss"
    ],
    "Hardware (NVIDIA/GPU/CPU/SSD)": [
        "https://www.tomshardware.com/rss.xml",
        "https://wccftech.com/category/hardware/feed/"
    ],
    "Data Lakehouse & Iceberg": [
        "https://iceberg.apache.org/feed.xml",
        "https://www.tabular.io/blog/rss.xml"
    ]
}

def clean_html(text: str) -> str:
    """HTML 태그 제거 및 텍스트 정제"""
    if not text:
        return ""
    # 간단한 태그 제거 및 엔티티 변환
    import re
    clean = re.compile('<.*?>')
    text = re.sub(clean, '', text)
    return html.unescape(text).strip()

def fetch_news(category: str, urls: List[str]) -> List[Dict]:
    news_items = []
    for url in urls:
        try:
            feed = feedparser.parse(url)
            source_name = feed.feed.get('title', url.split('/')[2])
            for entry in feed.entries[:3]:  # 소스당 가장 중요한 3개 기사만 선별
                # 요약문 정리 (최대 200자)
                summary = clean_html(getattr(entry, "summary", getattr(entry, "description", "")))
                if len(summary) > 200:
                    summary = summary[:197] + "..."
                
                news_items.append({
                    "title": entry.title,
                    "link": entry.link,
                    "published": getattr(entry, "published", "No Date"),
                    "source": source_name,
                    "summary": summary
                })
        except Exception as e:
            print(f"Error fetching from {url}: {e}")
    return news_items

def create_daily_readme(news_data: Dict[str, List[Dict]]):
    today = datetime.datetime.now().strftime("%Y-%m-%d")
    archive_dir = os.path.join("archive", today)
    os.makedirs(archive_dir, exist_ok=True)
    
    file_path = os.path.join(archive_dir, "README.md")
    
    content = f"# Technical Daily Report - {today}\n\n"
    content += "Selected technical news and updates from verified industry sources.\n\n"
    
    for category, items in news_data.items():
        if not items:
            continue
        content += f"## {category}\n\n"
        for item in items:
            content += f"### {item['title']}\n"
            content += f"- **Source**: {item['source']}\n"
            content += f"- **Date**: {item['published']}\n"
            content += f"- **Summary**: {item['summary']}\n"
            content += f"- **Read more**: [Direct Link]({item['link']})\n\n"
        content += "---\n\n"
    
    with open(file_path, "w", encoding="utf-8") as f:
        f.write(content)
    
    return today

def update_main_readme(today: str):
    main_readme = "README.md"
    link_line = f"| {today} | [Technical Report](archive/{today}/README.md) |\n"
    
    # 메인 README를 다시 작성하기 위해 현재 목록만 추출
    archives = []
    if os.path.exists(main_readme):
        with open(main_readme, "r") as f:
            lines = f.readlines()
            for line in lines:
                if "| 20" in line and "archive/" in line:
                    archives.append(line.strip())
    
    if not any(today in a for a in archives):
        archives.insert(0, link_line.strip()) # 최신순 정렬

    # 세련된 메인 README 구조 작성
    content = """# Tech-Daily-News

Technical Trend Monitoring System for AI, Infrastructure, and Hardware.

## Project Goal
This repository automatically aggregates high-authority technical articles every morning at 09:00 KST. The objective is to monitor industry shifts in:
- **AI & Machine Learning**: Latest research and model releases.
- **Infrastructure**: Kubernetes, Cloud-native ecosystem, and Open Source movements.
- **Hardware**: GPU/CPU advancements, Memory/SSD technology, and NVIDIA's ecosystem.
- **Data Engineering**: Lakehouse architectures and Apache Iceberg developments.

## Knowledge Base Archive
| Date | Link |
| :--- | :--- |
"""
    for arch in sorted(archives, reverse=True):
        content += arch + "\n"
    
    with open(main_readme, "w", encoding="utf-8") as f:
        f.write(content)

if __name__ == "__main__":
    all_news = {}
    for category, urls in NEWS_SOURCES.items():
        print(f"Analyzing {category}...")
        all_news[category] = fetch_news(category, urls)
    
    today_date = create_daily_readme(all_news)
    update_main_readme(today_date)
