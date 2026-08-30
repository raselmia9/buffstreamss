import asyncio
import json
from datetime import datetime
from bs4 import BeautifulSoup
from playwright.async_api import async_playwright

# লক্ষ্য ওয়েবসাইট
URL = "https://www1.buffstreamss.sx/"


async def scrape_buffstreams():
  match_list = []

  # Playwright ব্যবহার করে ব্রাউজার সেশন শুরু করা
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
      # পেজ লোড হওয়া পর্যন্ত অপেক্ষা করা
      await page.goto(URL, timeout=60000)
      await page.wait_for_timeout(
          5000
      )  # ডায়নামিক কন্টেন্ট রেন্ডার হওয়ার জন্য ৫ সেকেন্ড ওয়েট

      # ফুল পেজের এইচটিএমএল সংগ্রহ করা
      html_content = await page.content()
      soup = BeautifulSoup(html_content, "html.parser")

      # ওয়েবসাইটের স্ট্রাকচার অনুযায়ী ম্যাচ কার্ডগুলো খুঁজে বের করা
      # (সাইটের লেআউট অনুযায়ী সিলেক্টর প্রয়োজনমতো অ্যাডজাস্ট করা যাবে)
      match_cards = soup.find_all("div", class_="card") or soup.find_all(
          "div", class_="event-item"
      )

      # যদি কার্ড সরাসরি ক্লাস দিয়ে না পাওয়া যায়, তবে সেকশন বা কন্টেইনার ধরে লুপ চালানো হবে
      if not match_cards:
        # ফলব্যাক হিসেবে পেজের মূল সেকশনগুলো টার্গেট করা
        match_cards = soup.find_all("section")

      for card in match_cards:
        try:
          # ১. ইভেন্ট বা লিগের নাম (eventTitle)
          category_elem = card.find(
              ["h2", "h3", "div"], class_=["category", "league-title", "title"]
          )
          eventTitle = (
              category_elem.get_text(strip=True)
              if category_elem
              else "Live Sports Event"
          )

          # ২. দলগুলোর নাম (Team Titles)
          team_elems = card.find_all(
              ["span", "div"], class_=["team", "name", "club"]
          )
          if len(team_elems) >= 2:
            team1Title = team_elems[0].get_text(strip=True)
            team2Title = team_elems[1].get_text(strip=True)
          else:
            team1Title = "Team 1"
            team2Title = "Team 2"

          # ৩. দলগুলোর লোগো (Team Logos)
          logo_elems = card.find_all("img")
          team1Logo = (
              logo_elems[0]["src"]
              if len(logo_elems) > 0 and "src" in logo_elems[0].attrs
              else ""
          )
          team2Logo = (
              logo_elems[1]["src"]
              if len(logo_elems) > 1 and "src" in logo_elems[1].attrs
              else ""
          )

          # ৪. ম্যাচের সময় (Match Time)
          time_elem = card.find(
              ["div", "span"], class_=["time", "starts", "status"]
          )
          time_text = (
              time_elem.get_text(strip=True)
              if time_elem
              else datetime.now().strftime("%Y-%m-%d %H:%M:%S")
          )
          # যদি কাউন্টডাউন বা টেক্সট থাকে, সেটিকে ফরম্যাট বা কারেন্ট টাইম দিয়ে সেট করা
          matchTime = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

          # ৫. স্ট্রিম লিংক বা এক্সটার্নাল পেজ লিংক (Stream Link)
          link_elem = card.find("a", href=True)
          streamLink = (
              link_elem["href"] if link_elem else URL
          )  # পরবর্তীতে এটি থেকে ভিডিও লিংক বের করা হবে

          # ৬. হট বা লাইভ স্ট্যাটাস (Is Hot)
          card_text = card.get_text().lower()
          isHot = "live" in card_text or "now" in card_text

          # আপনার দেওয়া JSON ফরম্যাট অনুযায়ী ডিকশনার তৈরি করা
          match_data = {
              "eventTitle": f"{eventTitle} | {team1Title} vs {team2Title}",
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
          print(f"Error parsing individual match card: {inner_err}")
          continue

      await browser.close()

    except Exception as e:
      print(f"An error occurred during scraping: {e}")
      await browser.close()

  return match_list


if __name__ == "__main__":
  # এসিনক্রোনাস ফাংশন রান করে ডেটা ফেচ করা
  data = asyncio.run(scrape_buffstreams())

  # আপনার কাঙ্ক্ষিত JSON ফরম্যাটে ফাইল সেভ করা
  output_file = "matches.json"
  with open(output_file, "w", encoding="utf-8") as f:
    json.dump(data, f, indent=4, ensure_ascii=False)

  print(
      f"Scraping completed successfully. Total matches found: {len(data)}. Saved"
      f" to {output_file}."
  )
