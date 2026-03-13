import os
import datetime
import feedparser
import html
import re
from typing import List, Dict
from googletrans import Translator

# 뉴스 소스 설정 (검증된 고품질 소스)
NEWS_SOURCES = {
    "AI & Machine Learning": [
        "https://openai.com/news/rss.xml",
        "https://huggingface.co/blog/feed.xml",
        "http://export.arxiv.org/rss/cs.AI"
    ],
    "Kubernetes & Cloud Native": [
        "https://kubernetes.io/feed.xml",
        "https://www.cncf.io/blog/feed/"
    ],
    "Open Source Ecosystem": [
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
        return "(번역 실패)"

def fetch_news(category: str, urls: List[str]) -> List[Dict]:
    news_items = []
    translator = Translator()
    
    # 24시간 이내의 기사만 수집하기 위한 기준 시간 설정
    now = datetime.datetime.now(datetime.timezone.utc)
    one_day_ago = now - datetime.timedelta(days=1)

    for url in urls:
        try:
            feed = feedparser.parse(url)
            source_name = feed.feed.get('title', url.split('/')[2])
            
            for entry in feed.entries:
                # 발행일 확인
                published_parsed = getattr(entry, "published_parsed", None)
                if published_parsed:
                    pub_date = datetime.datetime(*published_parsed[:6], tzinfo=datetime.timezone.utc)
                    if pub_date < one_day_ago:
                        continue # 24시간 이전 기사는 스킵
                
                # 상세 요약 확보 (더 길게)
                summary = clean_html(getattr(entry, "summary", getattr(entry, "description", "")))
                if not summary or len(summary) < 20:
                    summary = entry.title # 요약이 너무 짧으면 제목으로 대체
                
                if len(summary) > 600:
                    summary = summary[:597] + "..."
                
                # 한글 번역 수행
                summary_ko = translate_text(summary)
                
                news_items.append({
                    "title": entry.title,
                    "link": entry.link,
                    "published": getattr(entry, "published", "No Date"),
                    "source": source_name,
                    "summary_en": summary,
                    "summary_ko": summary_ko
                })
                
                if len(news_items) >= 15: # 카테고리당 최대 기사 수 제한
                    break
        except Exception as e:
            print(f"Error fetching from {url}: {e}")
            
    return news_items

def create_daily_readme(news_data: Dict[str, List[Dict]]):
    today = datetime.datetime.now().strftime("%Y-%m-%d")
    archive_dir = os.path.join("archive", today)
    os.makedirs(archive_dir, exist_ok=True)
    
    file_path = os.path.join(archive_dir, "README.md")
    
    content = f"# Technical Daily Report - {today}\n\n"
    content += "Selected technical updates from the last 24 hours across global industry sources.\n\n"
    
    for category, items in news_data.items():
        if not items:
            continue
        content += f"## {category}\n\n"
        for item in items:
            content += f"### {item['title']}\n"
            content += f"- **Source**: {item['source']} | **Date**: {item['published']}\n"
            content += f"- **Summary (EN)**: {item['summary_en']}\n"
            content += f"- **요약 (KO)**: {item['summary_ko']}\n"
            content += f"- **Link**: [View Original Article]({item['link']})\n\n"
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

Automated technical trend monitoring system covering AI, Infrastructure, and Hardware.

## Project Goal
This repository aggregates high-authority technical articles every morning at 09:00 KST, ensuring no gaps in industry monitoring:
- **AI & Machine Learning**: Breakthrough research and model releases.
- **Infrastructure**: Kubernetes, Cloud-native ecosystem, and Open Source.
- **Hardware**: GPU/CPU advancements and NVIDIA's strategic moves.
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
        print(f"Syncing {category} (Last 24h)...")
        all_news[category] = fetch_news(category, urls)
    
    today_date = create_daily_readme(all_news)
    update_main_readme(today_date)
