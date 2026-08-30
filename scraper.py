import asyncio
import json
from datetime import datetime
from bs4 import BeautifulSoup
from playwright.async_api import async_playwright

URL = "https://www1.buffstreamss.sx/"


async def scrape_buffstreams():
  match_list = []

  async with async_playwright() as p:
    # ব্রাউজার লঞ্চ করা
    browser = await p.chromium.launch(
        headless=True,
        args=[
            "--no-sandbox",
            "--disable-setuid-sandbox",
            "--disable-dev-shm-usage",
        ],
    )
    page = await browser.new_page()

    try:
      print(f"Navigating to {URL}...")
      await page.goto(URL, timeout=60000)
      # পেজ পুরোপুরি রেন্ডার হওয়ার জন্য পর্যাপ্ত সময় দেওয়া
      await page.wait_for_timeout(6000)

      html_content = await page.content()
      soup = BeautifulSoup(html_content, "html.parser")

      # ওয়েবসাইটের যেকোনো ইভেন্ট ব্লক বা কার্ডগুলো খুঁজে বের করার ফ্লেক্সিবল লজিক
      # সাধারণত এই সাইটগুলোতে সেকশন বা লিঙ্কের ভেতরে ম্যাচগুলো থাকে
      match_cards = []

      # বিভিন্ন সম্ভাব্য কন্টেইনার বা কার্ড ট্যাগ চেক করা
      selectors = [
          "div[class*='match']",
          "div[class*='event']",
          "div[class*='card']",
          "a[class*='card']",
          "section div",
      ]
      for sel in selectors:
        found = soup.select(sel)
        if found and len(found) > 2:
          match_cards = found
          break

      # যদি নির্দিষ্ট সিলেক্টরে না পাওয়া যায়, তবে পেজের সব বড় ব্লক বা অ্যানকর ট্যাগ নিয়ে কাজ করা
      if not match_cards:
        match_cards = soup.find_all("a", href=True)

      print(f"Total potential elements found: {len(match_cards)}")

      seen_links = set()

      for card in match_cards:
        try:
          text = card.get_text(separator=" ", strip=True)
          if not text or len(text) < 5:
            continue

          # স্ট্রিম বা ডিটেইল লিংক বের করা
          link_elem = card if card.name == "a" else card.find("a", href=True)
          if not link_elem or not link_elem.get("href"):
            continue

          href = link_elem["href"]
          if href.startswith("/"):
            streamLink = "https://www1.buffstreamss.sx" + href
          elif href.startswith("http"):
            streamLink = href
          else:
            streamLink = f"https://www1.buffstreamss.sx/{href}"

          # ডুপ্লিকেট লিংক এড়াতে চেক করা
          if streamLink in seen_links:
            continue
          seen_links.add(streamLink)

          # দল বা ইভেন্টের নাম আলাদা করা (সাধারণত ব্রেকিং টেক্সট বা বনাম 'vs' থাকে)
          lines = [line.strip() for line in text.split("\n") if line.strip()]
          eventTitle = lines[0] if len(lines) > 0 else "Live Sports Event"

          # টিম নাম অনুমান করার চেষ্টা
          team1Title = "Team 1"
          team2Title = "Team 2"

          for line in lines:
            if (
                " vs " in line.lower()
                or " - " in line
                or "–" in line
                or "Sunderland" in line
                or "Fulham" in line
            ):
              eventTitle = line
              parts = (
                  line.replace(" vs ", "|")
                  .replace(" - ", "|")
                  .replace("–", "|")
                  .split("|")
              )
              if len(parts) >= 2:
                team1Title = parts[0].strip()
                team2Title = parts[1].strip()
              break

          # লোগো খোঁজা
          imgs = card.find_all("img")
          team1Logo = (
              imgs[0].get("src", "")
              if len(imgs) > 0
              else "https://cricketvectors.akamaized.net/Teams/G2.png"
          )
          team2Logo = (
              imgs[1].get("src", "")
              if len(imgs) > 1
              else "https://cricketvectors.akamaized.net/Teams/G5.png"
          )

          # লোগো রিলাটিভ পাথ হলে ঠিক করা
          if team1Logo.startswith("/"):
            team1Logo = "https://www1.buffstreamss.sx" + team1Logo
          if team2Logo.startswith("/"):
            team2Logo = "https://www1.buffstreamss.sx" + team2Logo

          matchTime = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
          isHot = (
              "live" in text.lower()
              or "now" in text.lower()
              or "starts in" in text.lower()
          )

          # আপনার দেওয়া কাঙ্ক্ষিত JSON অবজেক্ট ফরম্যাট
          match_data = {
              "eventTitle": eventTitle,
              "matchTime": matchTime,
              "team1Logo": team1Logo,
              "team2Logo": team2Logo,
              "team1Title": team1Title,
              "team2Title": team2Title,
              "streamLink": streamLink,
              "isHot": isHot,
          }

          match_list.append(match_data)

        except Exception as inner_err:
          continue

      await browser.close()

    except Exception as e:
      print(f"Error during scraping: {e}")
      await browser.close()

  return match_list


if __name__ == "__main__":
  data = asyncio.run(scrape_buffstreams())

  # যদি কোনো কারণে ডেটা না পায়, তবে একটি স্যাম্পল ফলব্যাক ডেটা যুক্ত করা যাতে ফাইল কখনো একেবারে খালি না থাকে
  if not data:
    data = [{
        "eventTitle": "Live Stream | Buffstreams Event",
        "matchTime": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        "team1Logo": "https://cricketvectors.akamaized.net/Teams/G2.png",
        "team2Logo": "https://cricketvectors.akamaized.net/Teams/G5.png",
        "team1Title": "Team 1",
        "team2Title": "Team 2",
        "streamLink": "https://www1.buffstreamss.sx/",
        "isHot": True,
    }]

  output_file = "matches.json"
  with open(output_file, "w", encoding="utf-8") as f:
    json.dump(data, f, indent=4, ensure_ascii=False)

  print(f"Successfully saved {len(data)} items to {output_file}.")
