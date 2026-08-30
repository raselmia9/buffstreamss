import asyncio
import json
from datetime import datetime
from bs4 import BeautifulSoup
from playwright.async_api import async_playwright

URL = "https://www1.buffstreamss.sx/"


async def scrape_buffstreams():
  match_list = []

  async with async_playwright() as p:
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
      await page.wait_for_timeout(6000)

      html_content = await page.content()
      soup = BeautifulSoup(html_content, "html.parser")

      seen_links = set()
      links = soup.find_all("a", href=True)

      for link in links:
        href = link["href"]
        if "/game/" not in href:
          continue

        if href.startswith("/"):
          streamLink = "https://www1.buffstreamss.sx" + href
        elif href.startswith("http"):
          streamLink = href
        else:
          continue

        if streamLink in seen_links:
          continue
        seen_links.add(streamLink)

        # কার্ড বা কন্টেইনার এলিমেন্ট খুঁজে বের করা
        card = link.find_parent("div", class_=["card", "item", "match-item"])
        if not card:
          card = link

        # ১. সঠিক লিগ বা ইভেন্টের নাম খোঁজা (কার্ডের ওপরের সেকশন হেডিং থেকে)
        eventTitle = "Live Sports Event"
        curr = card
        for _ in range(5):
          if not curr:
            break
          # ওপরের দিকে হেডিং বা সেকশন লেবেল খোঁজা
          prev_elem = curr.find_previous(
              ["h1", "h2", "h3", "h4", "div", "span"], class_=True
          )
          if prev_elem:
            t_text = prev_elem.get_text(strip=True)
            if (
                t_text
                and len(t_text) < 35
                and "Starts" not in t_text
                and "Live" not in t_text
                and "1" not in t_text
            ):
              eventTitle = t_text
              break
          curr = curr.parent

        card_text = card.get_text(separator=" ", strip=True)

        # ২. URL থেকে টিম ১ ও টিম ২ এর নাম আলাদা করা
        slug = href.split("/game/")[-1]
        parts = slug.split("-vs-")
        if len(parts) == 2:
          team1Title = parts[0].replace("-", " ").title()
          team2Title = parts[1].replace("-", " ").title()
        else:
          team1Title = "Team 1"
          team2Title = "Team 2"

        # ৩. কার্ডের ভেতর থেকে সুনির্দিষ্টভাবে দুটি আলাদা লোগো সংগ্রহ করা
        imgs = card.find_all("img")
        team1Logo = ""
        team2Logo = ""

        # যদি কার্ডের ভেতর একাধিক ছবি থাকে, তবে প্রথম দুটি ছবি টিমগুলোর লোগো হিসেবে নেব
        valid_img_sources = []
        for img in imgs:
          src = img.get("src", "")
          if src and src not in valid_img_sources:
            # যদি লিগের আইকন বা বাইরের লোগো না হয়
            if "leagues" not in src and "icon" not in src:
              valid_img_sources.append(src)

        if len(valid_img_sources) >= 2:
          team1Logo = valid_img_sources[0]
          team2Logo = valid_img_sources[1]
        elif len(imgs) >= 2:
          team1Logo = imgs[0].get("src", "")
          team2Logo = imgs[1].get("src", "")
        elif len(imgs) == 1:
          team1Logo = imgs[0].get("src", "")
          team2Logo = imgs[0].get("src", "")
        else:
          team1Logo = "https://cricketvectors.akamaized.net/Teams/G2.png"
          team2Logo = "https://cricketvectors.akamaized.net/Teams/G5.png"

        # রিলাটিভ পাথ ফিক্স করা
        if team1Logo.startswith("/"):
          team1Logo = "https://www1.buffstreamss.sx" + team1Logo
        if team2Logo.startswith("/"):
          team2Logo = "https://www1.buffstreamss.sx" + team2Logo

        matchTime = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        isHot = (
            "live" in card_text.lower()
            or "now" in card_text.lower()
            or "starts in" in card_text.lower()
        )

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

      await browser.close()

    except Exception as e:
      print(f"Error during scraping: {e}")
      await browser.close()

  return match_list


if __name__ == "__main__":
  data = asyncio.run(scrape_buffstreams())

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
