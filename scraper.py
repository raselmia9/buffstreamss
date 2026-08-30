import asyncio
import json
from datetime import datetime
from bs4 import BeautifulSoup
from playwright.async_api import async_playwright

URL = "https://www1.buffstreamss.sx/"

MAX_CONCURRENT_TABS = 5


async def scrape_final_stream_and_format(browser, match, semaphore):
  async "with" semaphore:
    page = await browser.new_page()

    await page.set_extra_http_headers({
        "User-Agent": (
            "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML,"
            " like Gecko) Chrome/120.0.0.0 Safari/537.36"
        )
    })

    page.on("popup", lambda popup: asyncio.create_task(popup.close()))

    # প্রথমে চ্যানেল পেজ থেকে ওয়াচ/স্ট্রিম পেজ লিংকগুলো সংগ্রহ করা
    c_link = match.get("channelPageLink")
    stream_pages_list = []
    final_solid_streaming_link = ""

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

            if not any(
                s["streamingPageLink"] == s_page_link for s in stream_pages_list
            ):
              stream_pages_list.append({
                  "channelName": channel_name,
                  "streamingPageLink": s_page_link,
              })

        if not stream_pages_list:
          stream_pages_list.append(
              {"channelName": "Main Stream", "streamingPageLink": c_link}
          )

        # এখন প্রথম ওয়াচ/স্ট্রিম পেজটিতে ঢুকে আসল সলিড ভিডিও লিংকটি বের করা (বিজ্ঞাপন ফিল্টার করে)
        target_page_link = stream_pages_list[0]["streamingPageLink"]
        print(f"Visiting streaming page to get solid link: {target_page_link}")

        await page.goto(
            target_page_link, timeout=30000, wait_until="domcontentloaded"
        )
        await page.wait_for_timeout(3000)

        stream_html = await page.content()
        stream_soup = BeautifulSoup(stream_html, "html.parser")

        # ফালতু অ্যাড লিংক বা chat.php বাদ দিয়ে আসল ভিডিও/আইফ্রেম সোর্স খোঁজা
        iframe = stream_soup.find("iframe", src=True)
        if iframe and iframe["src"]:
          src_val = iframe["src"]
          if "chat.php" not in src_val and "pxdrop" not in src_val:
            final_solid_streaming_link = src_val

        if not final_solid_streaming_link:
          video = stream_soup.find(["video", "source"], src=True)
          if video and video["src"]:
            final_solid_streaming_link = video["src"]

        # যদি কোনো কারণে ফালতু লিংক ছাড়া না পাওয়া যায়, তবে টার্গেট পেজ লিংকটিকেই সলিড লিংক হিসেবে রাখা
        if not final_solid_streaming_link:
          final_solid_streaming_link = target_page_link

      except Exception as ex:
        print(f"Error processing match: {ex}")
        final_solid_streaming_link = c_link
        if not stream_pages_list:
          stream_pages_list = [{
              "channelName": "Main Stream",
              "streamingPageLink": c_link,
          }]

    await page.close()

    # আপনার নির্দেশনা অনুযায়ী:
    # ১. 'streamPages' ট্যাগের ভেতরে থাকবে চ্যানেল লিস্ট ও স্ট্রিমিং পেজ লিংকগুলো
    match["streamPages"] = stream_pages_list
    if "streams" in match:
      del match["streams"]
    if "স্ট্রিম পেজ" in match:
      del match["স্ট্রিম পেজ"]

    # ২. মূল আইটেমের বাইরে আলাদা 'streaming' ট্যাগে সরাসরি সলিড লিংকটি বসে যাবে
    match["streaming"] = final_solid_streaming_link

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

      # মাল্টি-ট্যাব ব্যবহার করে একসাথে সব ম্যাচ প্রসেস করা
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
        "streamPages": [{
            "channelName": "Main Stream",
            "streamingPageLink": "https://www1.buffstreamss.sx/",
        }],
        "streaming": "https://www1.buffstreamss.sx/",
    }]

  output_file = "matches.json"
  with open(output_file, "w", encoding="utf-8") as f:
    json.dump(data, f, indent=4, ensure_ascii=False)

  print(f"Successfully saved {len(data)} items to {output_file}.")
