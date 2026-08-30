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

      match_list = []
      seen_links = set()

      # ওয়েবসাইটের সেকশনগুলো ধরে স্ক্র্যাপ করার লজিক
      # সাধারণত প্রতিটি সেকশনে একটি হেডিং থাকে এবং তার নিচে ম্যাচের কার্ডগুলো থাকে
      # আমরা পেজের সমস্ত ম্যাচ কার্ড বা লিগ সেকশন ট্র্যাক করব

      # প্রতিটি ম্যাচ কার্ডকে টার্গেট করা যার মধ্যে এক্সটার্নাল লিংক বা গেমের লিংক আছে
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

        # কার্ডের প্যারেন্ট বা কন্টেইনার খোঁজা
        card = link.find_parent(
            "div",
            class_=[
                "card",
                "item",
                "match-item",
                "bg-",
                "rounded",
                "flex",
                "grid",
            ],
        )
        if not card:
          card = link

        # বর্তমান কার্ডের উপরে বা সেকশনের মধ্যে লিগ/ইভেন্ট নাম খোঁজা
        eventTitle = "Live Sports Event"
        current = card
        for _ in range(5):  # ওপরের দিকে কয়েক ধাপ চেক করা
          if not current:
            break
          # আগের ভাইবোন বা হেডিং ট্যাগ খুঁজব যেখানে লিগের নাম থাকতে পারে
          prev_elem = current.find_previous(
              ["h1", "h2", "h3", "h4", "div", "span"],
              class_=True,
          )
          if prev_elem:
            text_val = prev_elem.get_text(strip=True)
            # যদি টেক্সটটি ছোট হয় এবং কোনো লিগ বা খেলার নাম হয়
            if (
                text_val
                and len(text_val) < 30
                and "Starts" not in text_val
                and "Live" not in text_val
            ):
              eventTitle = text_val
              break
          current = current.parent

        card_text = card.get_text(separator=" ", strip=True)

        # লোগো সংগ্রহ
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

        if team1Logo.startswith("/"):
          team1Logo = "https://www1.buffstreamss.sx" + team1Logo
        if team2Logo.startswith("/"):
          team2Logo = "https://www1.buffstreamss.sx" + team2Logo

        # URL থেকে টিম নাম বের করা (যেমন: /game/sunderland-vs-fulham)
        slug = href.split("/game/")[-1]
        parts = slug.split("-vs-")
        if len(parts) == 2:
          team1Title = parts[0].replace("-", " ").title()
          team2Title = parts[1].replace("-", " ").title()
        else:
          # টেক্সট থেকে আলাদা করার চেষ্টা
          team1Title = "Team 1"
          team2Title = "Team 2"

        # যদি ইভেন্ট টাইটেল ডিফল্ট থাকে, তবে স্লাগ বা ইউআরএল থেকে সুন্দর নাম দেওয়া
        if (
            eventTitle == "Live Sports Event"
            or len(eventTitle) < 3
            or "Starts" in eventTitle
        ):
          eventTitle = "Live Stream Match"

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
