import os
import datetime
import feedparser
import html
import re
from typing import List, Dict
from googletrans import Translator

# 저명한 기술 소스 설정 (우선순위 기반 배치)
NEWS_SOURCES = {
    "Industry Trends (Hacker News)": [
        "https://news.ycombinator.com/rss" # 전 세계 엔지니어들의 인기 트렌드
    ],
    "AI & Machine Learning": [
        "https://nvidianews.nvidia.com/releases.xml", # NVIDIA 공식 보도자료
        "https://openai.com/news/rss.xml",
        "https://huggingface.co/blog/feed.xml",
        "https://deepmind.google/blog/rss.xml", # Google DeepMind
        "http://export.arxiv.org/rss/cs.AI"
    ],
    "Kubernetes & Cloud Native": [
        "https://kubernetes.io/feed.xml",
        "https://www.cncf.io/blog/feed/"
    ],
    "Hardware & Semiconductors": [
        "https://www.tomshardware.com/rss.xml",
        "https://wccftech.com/category/hardware/feed/"
    ],
    "Open Source Ecosystem": [
        "https://github.blog/category/open-source/feed/",
        "https://opensource.googleblog.com/feeds/posts/default"
    ],
    "Infrastructure & Cloud": [
        "https://aws.amazon.com/blogs/aws/feed/",
        "https://cloud.google.com/blog/rss"
    ],
    "Data Engineering & Iceberg": [
        "https://iceberg.apache.org/feed.xml",
        "https://www.tabular.io/blog/rss.xml"
    ]
}

def clean_html(text: str) -> str:
    """HTML 태그 제거 및 텍스트 정제"""
    if not text:
        return ""
    clean = re.compile('<.*?>')
    text = re.sub(clean, '', text)
    return html.unescape(text).strip()

def translate_text(text: str, dest: str = 'ko') -> str:
    """영문 요약을 한국어로 번역"""
    if not text:
        return ""
    try:
        translator = Translator()
        result = translator.translate(text, dest=dest)
        return result.text
    except Exception as e:
        print(f"Translation error: {e}")
        return "(번역 중 오류가 발생했습니다)"

def fetch_news(category: str, urls: List[str]) -> List[Dict]:
    news_items = []
    now = datetime.datetime.now(datetime.timezone.utc)
    one_day_ago = now - datetime.timedelta(days=1)

    for url in urls:
        try:
            feed = feedparser.parse(url)
            source_name = feed.feed.get('title', url.split('/')[2])
            
            # Hacker News 등의 소스는 최신 10개만, 나머지는 소스당 3개만
            limit = 10 if "ycombinator" in url else 3
            count = 0
            
            for entry in feed.entries:
                if count >= limit:
                    break
                
                # 발행일 확인
                published_parsed = getattr(entry, "published_parsed", None)
                if published_parsed:
                    pub_date = datetime.datetime(*published_parsed[:6], tzinfo=datetime.timezone.utc)
                    if pub_date < one_day_ago:
                        continue
                
                summary = clean_html(getattr(entry, "summary", getattr(entry, "description", "")))
                if not summary or len(summary) < 20:
                    summary = entry.title
                
                if len(summary) > 600:
                    summary = summary[:597] + "..."
                
                summary_ko = translate_text(summary)
                
                news_items.append({
                    "title": entry.title,
                    "link": entry.link,
                    "published": getattr(entry, "published", "No Date"),
                    "source": source_name,
                    "summary_en": summary,
                    "summary_ko": summary_ko
                })
                count += 1
                
        except Exception as e:
            print(f"Error fetching from {url}: {e}")
            
    return news_items

def create_daily_readme(news_data: Dict[str, List[Dict]]):
    today = datetime.datetime.now().strftime("%Y-%m-%d")
    archive_dir = os.path.join("archive", today)
    os.makedirs(archive_dir, exist_ok=True)
    
    file_path = os.path.join(archive_dir, "README.md")
    
    content = f"# Technical Daily Report - {today}\n\n"
    content += "A curated report of highly authoritative technical updates from the past 24 hours.\n\n"
    
    for category, items in news_data.items():
        if not items:
            continue
        content += f"## {category}\n\n"
        for item in items:
            content += f"### {item['title']}\n"
            content += f"- **Source**: {item['source']} | **Date**: {item['published']}\n"
            content += f"- **Summary (EN)**: {item['summary_en']}\n"
            content += f"- **요약 (KO)**: {item['summary_ko']}\n"
            content += f"- **Link**: [Original Content]({item['link']})\n\n"
        content += "---\n\n"
    
    with open(file_path, "w", encoding="utf-8") as f:
        f.write(content)
    
    return today

def update_main_readme(today: str):
    main_readme = "README.md"
    link_line = f"| {today} | [Technical Report](archive/{today}/README.md) |"
    
    archives = []
    if os.path.exists(main_readme):
        with open(main_readme, "r") as f:
            lines = f.readlines()
            for line in lines:
                if "| 20" in line and "archive/" in line:
                    archives.append(line.strip())
    
    if not any(today in a for a in archives):
        archives.insert(0, link_line)

    content = """# Tech-Daily-News

Technical Trend Monitoring and Bilingual Archive System focusing on high-authority sources.

## Project Overview
This system automatically aggregates and archives the latest trends in AI, cloud infrastructure, hardware, and the open-source ecosystem. Every morning at 09:00 KST, it extracts key updates, provides bilingual summaries, and ensures zero gaps in industry monitoring.

## Verified Sources
We monitor and aggregate data from the following authoritative organizations and media:
- **AI & ML**: NVIDIA Newsroom, OpenAI, DeepMind, Hugging Face, arXiv.
- **Infrastructure**: CNCF, Kubernetes, AWS Engineering, Google Cloud Blog.
- **Hardware**: Tom's Hardware, Wccftech (Semiconductor focus).
- **Open Source**: GitHub Blog, Google Open Source.
- **Trends**: Hacker News (Top engineering stories).

## Automation Mechanism
Operated autonomously by GitHub Actions. The system wakes up at 00:00 UTC, fetches the latest 24 hours of data, processes bilingual summaries, and archives them for future reference.

## Knowledge Base Archive
| Date | Technical Report | Status |
| :--- | :--- | :--- |
"""
    for arch in sorted(archives, reverse=True):
        content += arch + "\n"
    
    with open(main_readme, "w", encoding="utf-8") as f:
        f.write(content)

if __name__ == "__main__":
    all_news = {}
    for category, urls in NEWS_SOURCES.items():
        print(f"Syncing High-Authority {category}...")
        all_news[category] = fetch_news(category, urls)
    
    today_date = create_daily_readme(all_news)
    update_main_readme(today_date)
