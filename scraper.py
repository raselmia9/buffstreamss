from bs4 import BeautifulSoup
import json
import requests


def scrape_buffstreams():
  url = "https://www1.buffstreamss.sx/"  # আপনার টার্গেটেড ওয়েবসাইট লিংক
  headers = {
      "User-Agent": (
          "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
          "AppleWebKit/537.36 (KHTML, like Gecko) "
          "Chrome/120.0.0.0 Safari/537.36"
      )
  }

  try:
    response = requests.get(url, headers=headers)
    response.raise_for_status()
  except requests.exceptions.RequestException as e:
    print(f"Error fetching the website: {e}")
    return []

  soup = BeautifulSoup(response.text, "html.parser")
  matches_data = []

  # এখানে আপনার ওয়েবসাইটের কাঠামোগত ম্যাচ কার্ডের ক্লাস বা ট্যাগ দিতে হবে
  # যেমন সাধারণত প্রতিটি ম্যাচের জন্য আলাদা কন্টেইনার বা কার্ড থাকে:
  match_cards = soup.find_all(
      "div", class_="match-card"
  )  # আপনার সাইট অনুযায়ী ক্লাস নেম পরিবর্তন করে নিতে পারেন

  # যদি নির্দিষ্ট ক্লাস না পাওয়া যায়, তবে আপনার আগের লজিক অনুযায়ী কার্ড সিলেক্ট করুন
  if not match_cards:
    # ব্যাকআপ বা আপনার আগের স্ক্রিপ্টের সিলেক্টর এখানে কাজ করবে
    match_cards = soup.select(
        ".game-item, .card, tr"
    )  # উদাহরণের জন্য রাখা হয়েছে

  for card in match_cards:
    try:
      # ইভেন্ট টাইটেল বা লিগের নাম
      event_title_elem = card.find(
          class_="event-title"
      )  # আপনার সাইটের ক্লাস অনুযায়ী বদলাবেন
      eventTitle = (
          event_title_elem.get_text(strip=True)
          if event_title_elem
          else "English Premier League"
      )

      # ম্যাচ টাইম
      time_elem = card.find(class_="match-time")
      matchTime = time_elem.get_text(strip=True) if time_elem else ""

      # টিম ১ ও টিম ২ এর নাম
      team1_elem = card.find(class_="team-1-title")
      team2_elem = card.find(class_="team-2-title")

      team1Title = team1_elem.get_text(strip=True) if team1_elem else "Team 1"
      team2Title = team2_elem.get_text(strip=True) if team2_elem else "Team 2"

      # চ্যানেল পেজ লিংক
      link_elem = card.find("a", href=True)
      channelPageLink = ""
      if link_elem:
        href = link_elem["href"]
        if href.startswith("http"):
          channelPageLink = href
        else:
          channelPageLink = "https://www1.buffstreamss.sx" + href

      # সুনির্দিষ্টভাবে এই কার্ডের ভেতরের সব img ট্যাগ বের করা (লোগোর জন্য)
      card_imgs = card.find_all("img")
      valid_imgs = []
      for img in card_imgs:
        src = img.get("src", "")
        # আইকন, টেলিগ্রাম বা ডিসকর্ড লোগো বাদ দিয়ে শুধু টিমের লোগো ফিল্টার করা
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

      # প্রতিটি ম্যাচের কার্ডে সাধারণত দুটি লোগো থাকে (টিম ১ এবং টিম ২)
      team1Logo = ""
      team2Logo = ""

      if len(valid_imgs) >= 2:
        team1Logo = valid_imgs[0]
        team2Logo = valid_imgs[1]
      elif len(valid_imgs) == 1:
        team1Logo = valid_imgs[0]
        team2Logo = valid_imgs[0]

      # যদি কোনো লোগো না পাওয়া যায় তবে ফলব্যাক লোগো বসবে
      if not team1Logo:
        team1Logo = "https://v1.1cdnforall.online/storage/64/responsive-images/Sunderland___preview_thumbnail_120_120.webp"
      if not team2Logo:
        team2Logo = "https://v1.1cdnforall.online/storage/111/responsive-images/Fulham___preview_thumbnail_120_120.webp"

      # স্ট্রিম লিংক বা অন্যান্য ডাটা এক্সট্রাক্ট করার লজিক (আপনার রিকোয়ারমেন্ট অনুযায়ী)
      streaming_page_links = []
      stream_links = []

      # ম্যাচ ডাটা ডিকশনারিতে যুক্ত করা
      match_item = {
          "eventTitle": eventTitle,
          "matchTime": matchTime,
          "team1Logo": team1Logo,
          "team2Logo": team2Logo,
          "team1Title": team1Title,
          "team2Title": team2Title,
          "channelPageLink": channelPageLink,
          "isHot": True,
          "Streaming page link": streaming_page_links,
          "streamLink": stream_links,
      }

      matches_data.append(match_item)

    except Exception as e:
      print(f"Error parsing a card: {e}")
      continue

  return matches_data


if __name__ == "__main__":
  data = scrape_buffstreams()
  # ফলাফল সুন্দরভাবে JSON ফরম্যাটে প্রিন্ট বা ফাইলে সেভ করার জন্য
  print(json.dumps(data, indent=4, ensure_ascii=False))
