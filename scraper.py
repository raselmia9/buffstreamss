import asyncio
from datetime import datetime, timezone
from zoneinfo import ZoneInfo
from bs4 import BeautifulSoup
import json
from playwright.async_api import async_playwright

URL = "https://www1.buffstreamss.sx/"
MAX_CONCURRENT_TABS = 5


async def scrape_final_stream_and_format(browser, match, semaphore):
  async with semaphore:
    page = await browser.new_page()

    await page.set_extra_http_headers({
        "User-Agent": (
            "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML,"
            " like Gecko) Chrome/120.0.0.0 Safari/537.36"
        )
    })

    page.on("popup", lambda popup: asyncio.create_task(popup.close()))

    c_link = match.get("channelPageLink")
    streaming_page_links = []
    stream_link_custom_list = []
    extracted_match_time = match.get("matchTime")

    if c_link:
      try:
        print(f"Visiting channel page: {c_link}")
        await page.goto(c_link, timeout=30000)
        await page.wait_for_timeout(2500)

        sub_html = await page.content()
        sub_soup = BeautifulSoup(sub_html, "html.parser")

        page_text = sub_soup.get_text()
        import re

        time_match = re.search(
            r"(\d{4}-\d{2}-\d{2}\s+\d{2}:\d{2}:\d{2})\s*(?:UTC|GMT)?",
            page_text,
            re.IGNORECASE,
        )
        if time_match:
          utc_time_str = time_match.group(1)
          try:
            dt_utc = datetime.strptime(utc_time_str, "%Y-%m-%d %H:%M:%S").replace(
                tzinfo=timezone.utc
            )
            dt_bd = dt_utc.astimezone(ZoneInfo("Asia/Dhaka"))
            extracted_match_time = dt_bd.strftime("%Y-%m-%d %H:%M:%S")
          except Exception as t_err:
            print(f"Time conversion error: {t_err}")

        watch_anchors = sub_soup.find_all("a", href=True)

        for a in watch_anchors:
          text = a.get_text(strip=True)
          if "Watch" in text or "watch" in text.lower():
            w_href = a["href"]

            if w_href.startswith("/"):
              s_page_link = "https://www1.buffstreamss.sx" + w_href
            elif w_href.startswith("http"):
              s_page_link = w_href
            else:
              continue

            channel_name = "Live Channel"
            row_container = a.find_parent(
                lambda tag: tag.name in ["div", "li", "tr", "section"]
                and len(tag.get_text(strip=True)) < 150
            )

            if row_container:
              full_text = row_container.get_text(separator="|", strip=True)
              parts = [p.strip() for p in full_text.split("|") if p.strip()]
              for p in parts:
                if (
                    p
                    and p.lower() != "watch"
                    and "watch" not in p.lower()
                    and len(p) < 40
                ):
                  channel_name = p
                  break

            formatted_page_entry = f"{channel_name},, {s_page_link}"
            if formatted_page_entry not in streaming_page_links:
              streaming_page_links.append(formatted_page_entry)

            detected_m3u8_link = None
            correct_referer_url = s_page_link

            try:
              found_links = []

              def handle_request(request):
                url = request.url
                if ".m3u8" in url or "playlist.m3u8" in url or "index.m3u8" in url:
                  if url not in found_links:
                    found_links.append(url)

              page.on("request", handle_request)

              await page.goto(
                  s_page_link, timeout=25000, wait_until="domcontentloaded"
              )
              await page.wait_for_timeout(4000)

              if found_links:
                detected_m3u8_link = found_links[0]
              else:
                content = await page.content()
                if ".m3u8" in content:
                  for line in content.split('"'):
                    if ".m3u8" in line:
                      detected_m3u8_link = line
                      break

            except Exception as ex:
              print(f"Error capturing m3u8 from {s_page_link}: {ex}")

            if detected_m3u8_link and ".m3u8" in detected_m3u8_link:
              final_stream_with_referer = (
                  f"{detected_m3u8_link}|Referer={correct_referer_url}"
              )
              formatted_stream_entry = (
                  f"{channel_name},, {final_stream_with_referer}"
              )
              if formatted_stream_entry not in stream_link_custom_list:
                stream_link_custom_list.append(formatted_stream_entry)

        if not streaming_page_links:
          streaming_page_links = [
              "Stream links will be activated before 1 hr of starting time."
          ]

        if not stream_link_custom_list:
          final_stream_output = (
              "Stream links will be activated before 1 hr of starting time."
          )
        elif len(stream_link_custom_list) == 1:
          final_stream_output = stream_link_custom_list[0]
        else:
          final_stream_output = ",)".join(stream_link_custom_list)

      except Exception as ex:
        print(f"Error processing match: {ex}")
        streaming_page_links = [
            "Stream links will be activated before 1 hr of starting time."
        ]
        final_stream_output = (
            "Stream links will be activated before 1 hr of starting time."
        )

    await page.close()

    match["matchTime"] = extracted_match_time
    match["Streaming page link"] = streaming_page_links
    match["streamLink"] = final_stream_output

    for old_key in ["streamPages", "streaming", "streams", "স্ট্রিম পেজ"]:
      if old_key in match:
        del match[old_key]

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

        # হোমপেজের নির্দিষ্ট ম্যাচ কার্ড বা কন্টেইনার
        card = link.find_parent(
            lambda tag: tag.name in ["div", "li", "tr"]
            and len(tag.find_all("img")) >= 2
        )
        if not card:
          card = link.find_parent(["div", "li", "tr", "article"])
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

        # হোমপেজের কার্ড থেকে সরাসরি আলাদা আলাদা লোগো তোলার পদ্ধতি
        card_imgs = card.find_all("img")
        valid_imgs = []
        for img in card_imgs:
          src = img.get("data-src") or img.get("src", "")
          if (
              src
              and not src.endswith(".svg")
              and "telegram" not in src.lower()
              and "discord" not in src.lower()
              and "icon" not in src.lower()
          ):
            if src.startswith("/"):
              src = "https://www1.buffstreamss.sx" + src
            elif not src.startswith("http"):
              src = "https://www1.buffstreamss.sx/" + src

            if src not in valid_imgs:
              valid_imgs.append(src)

        # হোমপেজের ওই নির্দিষ্ট কার্ডে টিমের নাম বা লোগো যেভাবে সাজানো থাকে সেই অনুযায়ী অ্যাসাইন করা
        team1Logo = ""
        team2Logo = ""

        if len(valid_imgs) >= 2:
          team1Logo = valid_imgs[0]
          team2Logo = valid_imgs[1]
        elif len(valid_imgs) == 1:
          team1Logo = valid_imgs[0]
          team2Logo = valid_imgs[0]

        # যদি হোমপেজের কার্ড থেকে ছবি না পাওয়া যায়, তবে টিম নামের ওপর ভিত্তি করে ডাইনামিক বা ডিফল্ট লোগো হ্যান্ডেল হবে
        if not team1Logo:
          team1Logo = (
              "https://v1.1cdnforall.online/storage/64/responsive-images/"
              f"{team1Title.replace(' ', '_')}___preview_thumbnail_120_120.webp"
          )
        if not team2Logo:
          team2Logo = (
              "https://v1.1cdnforall.online/storage/64/responsive-images/"
              f"{team2Title.replace(' ', '_')}___preview_thumbnail_120_120.webp"
          )

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

      print(
          f"Total matches found: {len(base_matches)}. Processing streams using"
          " multi-tabs..."
      )
      semaphore = asyncio.Semaphore(MAX_CONCURRENT_TABS)
      tasks = [
          scrape_final_stream_and_format(browser, match, semaphore)
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
        "eventTitle": "Live Stream | Streaming Event",
        "matchTime": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        "team1Logo": (
            "https://v1.1cdnforall.online/storage/64/responsive-images/Sunderland___preview_thumbnail_120_120.webp"
        ),
        "team2Logo": (
            "https://v1.1cdnforall.online/storage/111/responsive-images/Fulham___preview_thumbnail_120_120.webp"
        ),
        "team1Title": "Team 1",
        "team2Title": "Team 2",
        "channelPageLink": "https://www1.buffstreamss.sx/",
        "isHot": True,
        "Streaming page link": [
            "Stream links will be activated before 1 hr of starting time."
        ],
        "streamLink": (
            "Stream links will be activated before 1 hr of starting time."
        ),
    }]

  output_file = "matches.json"
  with open(output_file, "w", encoding="utf-8") as f:
    json.dump(data, f, indent=4, ensure_ascii=False)

  print(f"Successfully saved {len(data)} items to {output_file}.")
