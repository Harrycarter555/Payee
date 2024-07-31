import requests
import os

# Define your URL shortener API endpoint and key here
URL_SHORTENER_API = 'https://api.urlshortener.com/shorten'
URL_SHORTENER_API_KEY = os.getenv('URL_SHORTENER_API_KEY')

def shorten_url(long_url: str) -> str:
    try:
        response = requests.post(
            URL_SHORTENER_API,
            json={'longUrl': long_url},
            headers={'Authorization': f'Bearer {URL_SHORTENER_API_KEY}'}
        )
        if response.status_code == 200:
            return response.json().get('shortUrl', long_url)
        else:
            return long_url
    except Exception as e:
        return long_url
