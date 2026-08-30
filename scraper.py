import json
from datetime import datetime
from bs4 import BeautifulSoup
import requests

# লক্ষ্য ওয়েবসাইট
URL = "https://www1.buffstreamss.sx/"


def scrape_buffstreams():
  headers = {
      "User-Agent": (
          "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML,"
          " like Gecko) Chrome/120.0.0.0 Safari/537.36"
      )
  }

  try:
    response = requests.get(URL, headers=headers)
    if response.status_code != 200:
      print(f"Failed to fetch website. Status code: {response.status_code}")
      return []

    soup = BeautifulSoup(response.text, "html.parser")
    match_list = []

    # ওয়েবসাইটের স্ট্রাকচার অনুযায়ী মেইন কন্টেইনার বা কার্ডগুলো খুঁজে বের করার লজিক
    # (নোট: সাইটের লাইভ DOM স্ট্রাকচার দেখে এখানে সিলেক্টর ফাইন টিউন করা হতে পারে)
    sections = soup.find_all("div", class_="card") or soup.find_all(
        "section"
    )  # উদাহরণস্বরূপ জেনেরিক ট্যাগ

    # যদি সাইটটি ক্লাউডফ্লেয়ার বা হেভি জাভাস্ক্রিপ্ট প্রোটেক্টেড হয়,
    # সেক্ষেত্রে পরবর্তীতে Selenium বা Playwright ব্যবহার করার অপশন রাখা যেতে পারে।

    print(
        "Successfully connected to the site. Parsing structure for extraction..."
    )

    # আপাতত ডেমো ডেটা বা বেসিক স্ট্রাকচার ফিলআপ করার লজিক এখানে যুক্ত হবে
    # একবার আপনি গিটহবে ফাইলটি তৈরি করলে আমরা লাইভ এলিমেন্টস অনুযায়ী ট্যাগ বসিয়ে দেবো।

    return match_list

  except Exception as e:
    print(f"An error occurred: {e}")
    return []


if __name__ == "__main__":
  data = scrape_buffstreams()

  # আপনার দেওয়া JSON ফরম্যাটে ফাইল সেভ করার কোড
  output_file = "matches.json"
  with open(output_file, "w", encoding="utf-8") as f:
    json.dump(data, f, indent=4, ensure_ascii=False)

  print(f"Data saved to {output_file} successfully.")
    
