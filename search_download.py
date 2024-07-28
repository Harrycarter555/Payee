import requests
from bs4 import BeautifulSoup
import urllib.parse
import os

# Function to search for file and download it
def search_and_download(file_name):
    search_engines = [
        {"name": "Google", "url": f"https://www.google.com/search?q={urllib.parse.quote(file_name)}"},
        {"name": "Bing", "url": f"https://www.bing.com/search?q={urllib.parse.quote(file_name)}"},
        # Add more search engines as needed
    ]

    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36"
    }

    download_url = None

    # Iterate through multiple search engines
    for engine in search_engines:
        try:
            # Sending request to search engine
            response = requests.get(engine["url"], headers=headers)
            response.raise_for_status()

            # Parsing search results
            soup = BeautifulSoup(response.content, "html.parser")
            search_results = soup.find_all("a")

            # Finding the first valid download URL
            for link in search_results:
                href = link.get("href")
                if href and href.startswith("http") and (".pdf" in href or ".doc" in href or ".xls" in href):
                    download_url = href
                    break

            if download_url:
                break  # Break if a valid download URL is found

        except requests.RequestException as e:
            print(f"Error occurred while searching on {engine['name']}: {e}")

    if download_url:
        try:
            # Downloading the file
            response = requests.get(download_url)
            file_extension = os.path.splitext(download_url)[1]
            file_path = os.path.join("downloads", f"{file_name}{file_extension}")  # Save in 'downloads' folder
            with open(file_path, "wb") as file:
                file.write(response.content)
            print(f"File '{file_name}' downloaded successfully to '{file_path}'")
        except requests.RequestException as e:
            print(f"Error occurred while downloading the file: {e}")
    else:
        print(f"File '{file_name}' not found or unable to download.")