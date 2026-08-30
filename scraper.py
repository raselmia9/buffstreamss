import asyncio
import json
from datetime import datetime
from bs4 import BeautifulSoup
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

    if c_link:
      try:
        print(f"Visiting channel page: {c_link}")
        await page.goto(c_link, timeout=30000)
        await page.wait_for_timeout(2500)

        sub_html = await page.content()
        sub_soup = BeautifulSoup(sub_html, "html.parser")

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

            # ১. Streaming page link ফরম্যাট: Channel Name,, Streaming Page URL
            formatted_page_entry = f"{channel_name},, {s_page_link}"
            if formatted_page_entry not in streaming_page_links:
              streaming_page_links.append(formatted_page_entry)

            # ২. streamLink এর জন্য সঠিক m3u8 এবং সঠিক Referer ইউআরএল ক্যাপচার করা
            detected_m3u8_link = s_page_link
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
              await page.wait_for_timeout(5000)

              if found_links:
                detected_m3u8_link = found_links[0]
              else:
                # আইফ্রেম বা ভিডিও সোর্স থেকে সঠিক পেজ লিংক বের করা
                iframe_element = await page.query_selector("iframe")
                if iframe_element:
                  src_val = await iframe_element.get_attribute("src")
                  if (
                      src_val
                      and "chat.php" not in src_val
                      and "pxdrop" not in src_val
                  ):
                    if src_val.startswith("//"):
                      correct_referer_url = "https:" + src_val
                    elif src_val.startswith("/"):
                      correct_referer_url = (
                          "https://www1.buffstreamss.sx" + src_val
                      )
                    else:
                      correct_referer_url = src_val
                    detected_m3u8_link = correct_referer_url

            except Exception as ex:
              print(f"Error capturing m3u8 from {s_page_link}: {ex}")

            # সঠিক m3u8 লিংকের সাথে সঠিক সঠিক Referer ইউআরএল যুক্ত করা
            final_stream_with_referer = (
                f"{detected_m3u8_link}|Referer={correct_referer_url}"
            )

            # streamLink ফরম্যাট: Channel Name,, m3u8_link|Referer=Correct_Url
            formatted_stream_entry = (
                f"{channel_name},, {final_stream_with_referer}"
            )
            if formatted_stream_entry not in stream_link_custom_list:
              stream_link_custom_list.append(formatted_stream_entry)

        if not streaming_page_links:
          streaming_page_links.append(f"Main Stream,, {c_link}")
          stream_link_custom_list.append(f"Main Stream,, {c_link}|Referer={c_link}")

      except Exception as ex:
        print(f"Error processing match: {ex}")
        streaming_page_links = [f"Main Stream,, {c_link}"]
        stream_link_custom_list = [f"Main Stream,, {c_link}|Referer={c_link}"]

    await page.close()

    # ফাইনাল আউটপุต ট্যাগগুলো এসাইন করা
    match["Streaming page link"] = streaming_page_links
    match["streamLink"] = stream_link_custom_list

    # পুরোনো অপ্রয়োজনীয় ট্যাগগুলো মুছে ফেলা
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
        team1Logo = imgs[0].get("src", "") if len(imgs) >= 1 else ""
        team2Logo = imgs[1].get("src", "") if len(imgs) >= 2 else team1Logo

        if not team1Logo:
          team1Logo = "https://cricketvectors.akamaized.net/Teams/G2.png"
        if not team2Logo:
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
        "team1Logo": "https://cricketvectors.akamaized.net/Teams/G2.png",
        "team2Logo": "https://cricketvectors.akamaized.net/Teams/G5.png",
        "team1Title": "Team 1",
        "team2Title": "Team 2",
        "channelPageLink": "https://www1.buffstreamss.sx/",
        "isHot": True,
        "Streaming page link": [
            "Main Stream,, https://www1.buffstreamss.sx/"
        ],
        "streamLink": [
            "Main Stream,, https://www1.buffstreamss.sx/|Referer=https://www1.buffstreamss.sx/"
        ],
    }]

  output_file = "matches.json"
  with open(output_file, "w", encoding="utf-8") as f:
    json.dump(data, f, indent=4, ensure_ascii=False)

  print(f"Successfully saved {len(data)} items to {output_file}.")
