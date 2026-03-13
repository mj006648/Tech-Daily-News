import os
import datetime
import feedparser
import html
import re
import requests
from typing import List, Dict
from googletrans import Translator
from bs4 import BeautifulSoup

# 저명한 기술 소스 설정 (NVIDIA 소스 보강)
NEWS_SOURCES = {
    "NVIDIA & AI Infrastructure": [
        "https://nvidianews.nvidia.com/releases.xml", # 공식 보도자료
        "https://blogs.nvidia.com/feed/",             # 공식 기술 블로그 (추가)
        "https://openai.com/news/rss.xml",
        "https://deepmind.google/blog/rss.xml"
    ],
    "Industry Trends (Hacker News)": [
        "https://news.ycombinator.com/rss"
    ],
    "AI & Machine Learning Research": [
        "https://huggingface.co/blog/feed.xml",
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
    "Open Source & Infrastructure": [
        "https://github.blog/category/open-source/feed/",
        "https://aws.amazon.com/blogs/aws/feed/",
        "https://cloud.google.com/blog/rss"
    ]
}

def clean_text(text: str) -> str:
    """텍스트 정제: 불필요한 공백, 태그, 노이즈 제거"""
    if not text: return ""
    text = html.unescape(text)
    text = re.sub(r'<[^>]+>', '', text) # 태그 제거
    text = re.sub(r'\s+', ' ', text)    # 연속 공백 제거
    return text.strip()

def get_smart_content(url: str) -> str:
    """본문만 스마트하게 추출 (광고/메뉴 제외)"""
    try:
        headers = {'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36'}
        response = requests.get(url, headers=headers, timeout=15)
        if response.status_code != 200: return ""
        
        soup = BeautifulSoup(response.text, 'html.parser')
        
        # 1. 불필요한 요소 제거
        for s in soup(['script', 'style', 'nav', 'header', 'footer', 'aside', 'iframe', 'button']):
            s.decompose()
            
        # 2. 본문으로 추정되는 태그 찾기 (article, main, div.content 등)
        content_tag = soup.find('article') or soup.find('main') or soup.find('div', class_=re.compile(r'content|article|post|body', re.I))
        
        if content_tag:
            paragraphs = content_tag.find_all('p')
        else:
            paragraphs = soup.find_all('p')
            
        # 3. 의미 있는 문장들만 조합 (글자 수 제한 및 품질 체크)
        cleaned_paragraphs = []
        for p in paragraphs:
            p_text = clean_text(p.get_text())
            if len(p_text) > 40: # 너무 짧은 문장은 메뉴일 확률 높음
                cleaned_paragraphs.append(p_text)
                
        full_content = " ".join(cleaned_paragraphs[:8]) # 상위 8개 문단 사용
        
        if len(full_content) > 1000:
            full_content = full_content[:997] + "..."
            
        return full_content
    except Exception as e:
        print(f"Scraping failed for {url}: {e}")
        return ""

def translate_text(text: str) -> str:
    if not text or len(text) < 20: return "(No content to translate)"
    try:
        translator = Translator()
        # 번역 전 텍스트가 너무 길면 잘라서 번역
        safe_text = text[:1500] 
        result = translator.translate(safe_text, dest='ko')
        return result.text
    except Exception as e:
        print(f"Translation error: {e}")
        return "(Translation failed)"

def fetch_news(category: str, urls: List[str]) -> List[Dict]:
    news_items = []
    now = datetime.datetime.now(datetime.timezone.utc)
    one_day_ago = now - datetime.timedelta(days=1)

    for url in urls:
        try:
            feed = feedparser.parse(url)
            source_name = feed.feed.get('title', url.split('/')[2])
            
            # Hacker News는 5개, 나머지는 3개
            limit = 5 if "news.ycombinator.com" in url else 3
            count = 0
            
            for entry in feed.entries:
                if count >= limit: break
                
                # 날짜 필터링 (최근 24시간)
                published_parsed = getattr(entry, "published_parsed", None)
                if published_parsed:
                    pub_date = datetime.datetime(*published_parsed[:6], tzinfo=datetime.timezone.utc)
                    if pub_date < one_day_ago: continue
                
                print(f"[{category}] Processing: {entry.title}")
                
                # 스마트 본문 추출
                summary_en = get_smart_content(entry.link)
                
                # 본문 추출 실패 시 RSS 요약이라도 활용
                if not summary_en or len(summary_en) < 100:
                    summary_en = clean_text(getattr(entry, "summary", getattr(entry, "description", entry.title)))
                
                # 최종 요약문이 3줄 이상 되도록 가공
                if len(summary_en.split('.')) < 3:
                    summary_en = (summary_en + " " + entry.title).strip()

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
            print(f"Error in {url}: {e}")
            
    return news_items

def create_daily_readme(news_data: Dict[str, List[Dict]]):
    today = datetime.datetime.now().strftime("%Y-%m-%d")
    archive_dir = os.path.join("archive", today)
    os.makedirs(archive_dir, exist_ok=True)
    
    file_path = os.path.join(archive_dir, "README.md")
    
    content = f"# Technical Daily Report - {today}\n\n"
    content += "Detailed technical insights curated from high-authority global sources within the last 24 hours.\n\n"
    
    for category, items in news_data.items():
        if not items: continue
        content += f"## {category}\n\n"
        for item in items:
            content += f"### {item['title']}\n"
            content += f"- **Source**: {item['source']} | **Date**: {item['published']}\n"
            content += f"- **Summary (English)**:\n{item['summary_en']}\n"
            content += f"- **Summary (Korean)**:\n{item['summary_ko']}\n"
            content += f"- **Full Article**: [Read More]({item['link']})\n\n"
            content += "---\n"
        content += "\n"
    
    with open(file_path, "w", encoding="utf-8") as f:
        f.write(content)
    
    return today

def update_main_readme(today: str):
    main_readme = "README.md"
    link_line = f"| {today} | [Full Report](archive/{today}/README.md) |"
    
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
- **NVIDIA & AI Infrastructure**: NVIDIA Newsroom, NVIDIA Blog, OpenAI, Google DeepMind.
- **Industry Trends**: Hacker News (Top engineering stories).
- **AI Research**: Hugging Face, arXiv.
- **Cloud & Kubernetes**: CNCF, Kubernetes, AWS Engineering, Google Cloud Blog.
- **Hardware**: Tom's Hardware, Wccftech.

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
        print(f"Scraping {category}...")
        all_news[category] = fetch_news(category, urls)
    
    today_date = create_daily_readme(all_news)
    update_main_readme(today_date)
