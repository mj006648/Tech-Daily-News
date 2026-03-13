import os
import datetime
import feedparser
import html
import re
import requests
from typing import List, Dict
from googletrans import Translator
from bs4 import BeautifulSoup

# 저명한 기술 소스 설정
NEWS_SOURCES = {
    "Industry Trends (Hacker News)": [
        "https://news.ycombinator.com/rss"
    ],
    "AI & Machine Learning": [
        "https://nvidianews.nvidia.com/releases.xml",
        "https://openai.com/news/rss.xml",
        "https://huggingface.co/blog/feed.xml",
        "https://deepmind.google/blog/rss.xml",
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
    if not text:
        return ""
    clean = re.compile('<.*?>')
    text = re.sub(clean, '', text)
    return html.unescape(text).strip()

def get_article_content(url: str) -> str:
    """원문 링크에 접속하여 본문 요약본 추출"""
    try:
        headers = {'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36'}
        response = requests.get(url, headers=headers, timeout=10)
        if response.status_code != 200:
            return ""
        
        soup = BeautifulSoup(response.text, 'html.parser')
        
        # 불필요한 태그 제거
        for s in soup(['script', 'style', 'nav', 'header', 'footer', 'aside']):
            s.decompose()
            
        # p 태그 위주로 본문 수집
        paragraphs = soup.find_all('p')
        content = " ".join([p.get_text() for p in paragraphs[:5]]) # 상위 5개 문단만 수집
        
        content = clean_html(content)
        if len(content) > 800:
            content = content[:797] + "..."
        return content
    except Exception as e:
        print(f"Error scraping {url}: {e}")
        return ""

def translate_text(text: str, dest: str = 'ko') -> str:
    if not text or len(text) < 10:
        return ""
    try:
        translator = Translator()
        # 긴 텍스트 번역을 위해 문장 단위로 나누거나 적절히 처리
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
            
            limit = 5 if "ycombinator" in url else 3 # Hacker News는 상위 5개만
            count = 0
            
            for entry in feed.entries:
                if count >= limit:
                    break
                
                # 발행일 필터링
                published_parsed = getattr(entry, "published_parsed", None)
                if published_parsed:
                    pub_date = datetime.datetime(*published_parsed[:6], tzinfo=datetime.timezone.utc)
                    if pub_date < one_day_ago:
                        continue
                
                # 1단계: RSS 피드에서 요약 가져오기
                summary = clean_html(getattr(entry, "summary", getattr(entry, "description", "")))
                
                # 2단계: 요약이 부실한 경우(Hacker News 등) 원문 직접 크롤링
                if len(summary) < 100:
                    print(f"Summary too short for {entry.title}. Fetching original content...")
                    scraped_content = get_article_content(entry.link)
                    if scraped_content:
                        summary = scraped_content
                
                # 요약이 여전히 부실하면 제목이라도 활용
                if not summary or len(summary) < 20:
                    summary = entry.title
                
                # 최소 3줄 이상 확보를 위해 가공 (너무 짧으면 반복하지는 않음)
                summary_en = summary
                summary_ko = translate_text(summary_en)
                
                news_items.append({
                    "title": entry.title,
                    "link": entry.link,
                    "published": getattr(entry, "published", "No Date"),
                    "source": source_name,
                    "summary_en": summary_en,
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
    content += "Detailed bilingual report of high-authority technical updates from the past 24 hours.\n\n"
    
    for category, items in news_data.items():
        if not items:
            continue
        content += f"## {category}\n\n"
        for item in items:
            content += f"### {item['title']}\n"
            content += f"- **Source**: {item['source']} | **Date**: {item['published']}\n"
            content += f"- **Summary (EN)**:\n{item['summary_en']}\n"
            content += f"- **요약 (KO)**:\n{item['summary_ko']}\n"
            content += f"- **Read More**: [Original Content]({item['link']})\n\n"
            content += "---\n"
        content += "\n"
    
    with open(file_path, "w", encoding="utf-8") as f:
        f.write(content)
    
    return today

def update_main_readme(today: str):
    main_readme = "README.md"
    link_line = f"| {today} | [Detailed Report](archive/{today}/README.md) |"
    
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
This system automatically aggregates and archives the latest trends in AI, cloud infrastructure, hardware, and the open-source ecosystem. Every morning at 09:00 KST, it extracts key updates, provides detailed bilingual summaries, and ensures zero gaps in industry monitoring.

## Verified Sources
We monitor and aggregate data from the following authoritative organizations and media:
- **Industry Trends**: Hacker News (Top engineering stories).
- **AI & Machine Learning**: NVIDIA Newsroom, OpenAI, Google DeepMind, Hugging Face, arXiv.
- **Infrastructure & Cloud**: CNCF, Kubernetes, AWS Engineering, Google Cloud Blog.
- **Hardware**: Tom's Hardware, Wccftech.
- **Open Source**: GitHub Blog, Google Open Source.
- **Data Engineering**: Apache Iceberg, Tabular.

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
        print(f"Processing {category} with Deep Scraper...")
        all_news[category] = fetch_news(category, urls)
    
    today_date = create_daily_readme(all_news)
    update_main_readme(today_date)
