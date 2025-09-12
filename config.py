import os
from dotenv import load_dotenv

load_dotenv()

class Config:
    INGRAM_CLIENT_ID = os.getenv("INGRAM_CLIENT_ID")
    INGRAM_CLIENT_SECRET = os.getenv("INGRAM_CLIENT_SECRET")
    INGRAM_CUSTOMER_NUMBER = os.getenv("INGRAM_CUSTOMER_NUMBER")
    INGRAM_SENDER_ID = os.getenv("INGRAM_SENDER_ID")
    INGRAM_COUNTRY_CODE = os.getenv("INGRAM_COUNTRY_CODE")
    INGRAM_LANGUAGE = os.getenv("INGRAM_LANGUAGE", "es-MX")
    UNSPLASH_ACCESS_KEY = os.getenv("UNSPLASH_ACCESS_KEY")
    
    CACHE_EXPIRY_HOURS = 24
    MAX_RECORDS_LIMIT = 10000