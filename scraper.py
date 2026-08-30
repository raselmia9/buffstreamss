import asyncio
import json
from datetime import datetime
from bs4 import BeautifulSoup
from playwright.async_api import async_playwright

URL = "https://www1.buffstreamss.sx/"

# কাজের গতি বাড়ানোর জন্য কনকারেন্ট ট্যাব সংখ্যা
MAX_CONCURRENT_TABS = 5


async def scrape_stream_channels(browser, match, semaphore):
  async with semaphore:
    page = await browser.new_page()
    c_link = match["channelPageLink"]
    streams_list = []

    try:
      print(f"Visiting channel page: {c_link}")
      await page.goto(c_link, timeout=30000)
      await page.wait_for_timeout(2500)

      sub_html = await page.content()
      sub_soup = BeautifulSoup(sub_html, "html.parser")

      # পেজের সব 'Watch' বাটন বা লিংক খুঁজে বের করা
      watch_anchors = sub_soup.find_all("a", href=True)

      for a in watch_anchors:
        text = a.get_text(strip=True)
        if "Watch" in text or "watch" in text.lower():
          w_href = a["href"]

          if w_href.startswith("/"):
            watch_page_link = "https://www1.buffstreamss.sx" + w_href
          elif w_href.startswith("http"):
            watch_page_link = w_href
          else:
            continue

          # চ্যানেলের নাম নিখুঁতভাবে তোলার জন্য উন্নত লজিক
          channel_name = "Live Channel"
          
          # ওয়াচ বাটনের নিকটবর্তী প্যারেন্ট কন্টেইনার বা রো খোঁজা
          row_container = a.find_parent(
              lambda tag: tag.name in ["div", "li", "tr", "section"]
              and len(tag.get_text(strip=True)) < 150
          )

          if row_container:
            # কন্টেইনারের ভেতরের টেক্সটগুলোকে আলাদা করা
            full_text = row_container.get_text(separator="|", strip=True)
            parts = [p.strip() for p in full_text.split("|") if p.strip()]
            
            for p in parts:
              # 'Watch' বা সংখ্যা বা খুব বড় টেক্সট বাদ দিয়ে চ্যানেলের নাম খুঁজে বের করা
              if (
                  p
                  and p.lower() != "watch"
                  and "watch" not in p.lower()
                  and len(p) < 40
              ):
                channel_name = p
                break
          
          # যদি কอนটেইনার থেকে না মিলে, তবে বাটনের আগের এলিমেন্ট চেক করা
          if channel_name == "Live Channel":
            prev_el = a.find_previous(["span", "div", "p", "strong", "h4"])
            if prev_el:
              p_val = prev_el.get_text(strip=True)
              if p_val and "watch" not in p_val.lower() and len(p_val) < 40:
                channel_name = p_val

          # ডুপ্লিকেট এড়িয়ে ওয়াচ পেজ লিংক এবং চ্যানেলের নাম যুক্ত করা
          if not any(
              s["watchPageLink"] == watch_page_link for s in streams_list
          ):
            streams_list.append({
                "channelName": channel_name,
                "watchPageLink": watch_page_link,
            })

      # যদি কোনো লিংক না পাওয়া যায়
      if not streams_list:
        streams_list.append(
            {"channelName": "Main Stream", "watchPageLink": c_link}
        )

      match["streams"] = streams_list

    except Exception as ex:
      print(f"Error scraping stream page {c_link}: {ex}")
      match["streams"] = [{"channelName": "Main Stream", "watchPageLink": c_link}]

    finally:
      await page.close()

    return match


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
      await page.wait_for_timeout(5000)

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
          channelPageLink = "https://www1.buffstreamss.sx" + href
        elif href.startswith("http"):
          channelPageLink = href
        else:
          continue

        if channelPageLink in seen_links:
          continue
        seen_links.add(channelPageLink)

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

        # URL স্লাগ থেকে টিম নাম নির্ধারণের লজিক
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
            "channelPageLink": channelPageLink,
            "isHot": isHot,
        })

      await page.close()

      # ২. মাল্টি-ট্যাব ব্যবহার করে খুব দ্রুত দ্বিতীয় পেজ থেকে চ্যানেল ও ওয়াচ পেজ লিংকগুলো আনা
      print(
          f"Total matches found: {len(base_matches)}. Scraping streams using"
          " multi-tabs..."
      )
      semaphore = asyncio.Semaphore(MAX_CONCURRENT_TABS)

      tasks = [
          scrape_stream_channels(browser, match, semaphore)
          for match in base_matches
      ]
      match_list = await asyncio.gather(*tasks)

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
        "channelPageLink": "https://www1.buffstreamss.sx/",
        "isHot": True,
        "streams": [{
            "channelName": "Main Stream",
            "watchPageLink": "https://www1.buffstreamss.sx/",
        }],
    }]

  output_file = "matches.json"
  with open(output_file, "w", encoding="utf-8") as f:
    json.dump(data, f, indent=4, ensure_ascii=False)

  print(f"Successfully saved {len(data)} items to {output_file}.")
