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

      base_matches = []

      # ১. প্রথম পেজ থেকে বেসিক ম্যাচ লিস্ট তৈরি করা
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

        card = link.find_parent("div", class_=["card", "item", "match-item"])
        if not card:
          card = link.parent if link.parent else link

        eventTitle = "Live Sports Event"
        curr = card
        for _ in range(6):
          if not curr:
            break
          prev_elem = curr.find_previous(
              ["h1", "h2", "h3", "h4", "div", "span"], class_=True
          )
          if prev_elem:
            t_text = prev_elem.get_text(strip=True)
            if (
                t_text
                and len(t_text) < 40
                and "Starts" not in t_text
                and "Live" not in t_text
                and "01:" not in t_text
            ):
              eventTitle = t_text
              break
          curr = curr.parent

        card_text = card.get_text(separator=" ", strip=True)

        slug = href.split("/game/")[-1]

        if "-vs-" in slug:
          parts = slug.split("-vs-")
          team1Title = parts[0].replace("-", " ").title()
          team2Title = parts[1].replace("-", " ").title()
        else:
          clean_slug = slug.lower()
          event_lower = eventTitle.lower().replace(" ", "-")

          if clean_slug.startswith(event_lower):
            clean_slug = clean_slug[len(event_lower) :].strip("-")

          slug_parts = [p for p in clean_slug.split("-") if p]

          if len(slug_parts) >= 2:
            team1Title = slug_parts[0].title()
            team2Title = slug_parts[-1].title()
          elif len(slug_parts) == 1:
            team1Title = slug_parts[0].title()
            team2Title = ""
          else:
            team1Title = slug.replace("-", " ").title()
            team2Title = ""

        imgs = card.find_all("img")
        team1Logo = ""
        team2Logo = ""

        if len(imgs) >= 2:
          team1Logo = imgs[0].get("src", "")
          team2Logo = imgs[1].get("src", "")
        elif len(imgs) == 1:
          team1Logo = imgs[0].get("src", "")
          team2Logo = imgs[0].get("src", "")
        else:
          team1Logo = "https://cricketvectors.akamaized.net/Teams/G2.png"
          team2Logo = "https://cricketvectors.akamaized.net/Teams/G5.png"

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

        base_matches.append({
            "eventTitle": eventTitle,
            "matchTime": matchTime,
            "team1Logo": team1Logo,
            "team2Logo": team2Logo,
            "team1Title": team1Title,
            "team2Title": team2Title,
            "streamLink": streamLink,
            "isHot": isHot,
        })

      # ২. দ্বিতীয় পেজে (স্ট্রিম লিংকে) প্রবেশ করে চ্যানেল ও ওয়াচ লিংকগুলো সংগ্রহ করা
      print(f"Total matches found: {len(base_matches)}. Scraping stream details...")

      for match in base_matches:
        s_link = match["streamLink"]
        channels_list = []

        try:
          print(f"Visiting stream page: {s_link}")
          await page.goto(s_link, timeout=30000)
          await page.wait_for_timeout(3000)

          sub_html = await page.content()
          sub_soup = BeautifulSoup(sub_html, "html.parser")

          # চ্যানেল কার্ড বা রো খুঁজে বের করা (যেখানে চ্যানেল নাম এবং ওয়াচ বাটন থাকে)
          # সাধারণত প্রতিটি চ্যানেলের জন্য একটি নির্দিষ্ট রো বা কার্ড থাকে
          channel_rows = sub_soup.find_all(
              "div", class_=["channel-row", "item", "card", "row"]
          )

          if not channel_rows:
            # যদি নির্দিষ্ট ক্লাস না পাওয়া যায়, তবে 'Watch' টেক্সটযুক্ত বাটন বা লিংকগুলোর প্যারেন্ট ধরে খোঁজা
            watch_tags = sub_soup.find_all(
                ["a", "button"], string=lambda t: t and "Watch" in t
            )
            for w in watch_tags:
              parent_box = w.find_parent(
                  "div", class_=["flex", "item", "card", "box", "row"]
              )
              if parent_box and parent_box not in channel_rows:
                channel_rows.append(parent_box)

          for row in channel_rows:
            row_text = row.get_text(separator=" ", strip=True)
            if "Watch" in row_text:
              # চ্যানেলের নাম বের করা (যেমন TNT Sports 2 HD)
              # সাধারণত ওয়াচ বাটনের পাশে বা ওপরে চ্যানেলের নাম লেখা থাকে
              channel_name = "Live Channel"
              
              # হেডিং বা টেক্সট এলিমেন্ট থেকে নাম খোঁজা
              text_elements = row.find_all(["span", "div", "p", "h4", "strong"])
              for el in text_elements:
                txt = el.get_text(strip=True)
                if txt and txt != "Watch" and len(txt) < 30:
                  channel_name = txt
                  break

              # ওয়াচ বাটন বা লিংকের ট্যাগ থেকে লিংক বের করা
              watch_btn = row.find("a", href=True)
              watch_link = ""
              if watch_btn:
                w_href = watch_btn["href"]
                if w_href.startswith("/"):
                  watch_link = "https://www1.buffstreamss.sx" + w_href
                elif w_href.startswith("http"):
                  watch_link = w_href

              if watch_link:
                channels_list.append({
                    "channelName": channel_name,
                    "watchLink": watch_link,
                })

          # যদি সাব-পেজ থেকে চ্যানেল বা ওয়াচ লিংক ডাইরেক্ট না পাওয়া যায়, তবে মূল স্ট্রিম লিংকটিই একটি চ্যানেল হিসেবে দিয়ে দেওয়া
          if not channels_list:
            channels_list.append(
                {"channelName": "Main Stream", "watchLink": s_link}
            )

        except Exception as ex:
          print(f"Error scraping stream page {s_link}: {ex}")
          channels_list.append(
              {"channelName": "Main Stream", "watchLink": s_link}
          )

        # মূল অবজেক্টে স্ট্রিম লিস্ট যুক্ত করে দেওয়া
        match["streams"] = channels_list
        match_list.append(match)

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
        "streams": [{
            "channelName": "Main Stream",
            "watchLink": "https://www1.buffstreamss.sx/",
        }],
    }]

  output_file = "matches.json"
  with open(output_file, "w", encoding="utf-8") as f:
    json.dump(data, f, indent=4, ensure_ascii=False)

  print(f"Successfully saved {len(data)} items to {output_file}.")
