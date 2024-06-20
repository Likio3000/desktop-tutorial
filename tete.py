import json
import logging
import os
import time
from datetime import datetime
from seleniumbase import Driver
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.common.exceptions import NoSuchElementException, TimeoutException
import pyperclip
import schedule

class NewJunkScraper:
    BASE_URL = "https://dexscreener.com/"
    RANK_BY = "pairAge"
    ORDER = "asc"
    CHAIN_IDS = "solana"
    MIN_LIQ = 10000
    MAX_FDV = 200000000
    MAX_AGE = 1
    MIN_5M_VOL = 5000

    def __init__(self, driver):
        self.url = f"{self.BASE_URL}?rankBy={self.RANK_BY}&order={self.ORDER}&chainIds={self.CHAIN_IDS}&minLiq={self.MIN_LIQ}&maxFdv={self.MAX_FDV}&maxAge={self.MAX_AGE}&min5MVol={self.MIN_5M_VOL}"
        self.driver = driver
        self.new_tokens_file = "new_tokens.json"
        self.good_tokens_file = "good_tokens.json"
        self.bad_tokens_file = "bad_tokens.json"
        self.initialize_json_files()

    def initialize_json_files(self):
        for file in [self.new_tokens_file, self.good_tokens_file, self.bad_tokens_file]:
            if not os.path.exists(file):
                with open(file, 'w') as f:
                    json.dump([], f)

    def fetch_tokens(self):
        logging.debug(f"Fetching tokens from URL: {self.url}")
        self.driver.get(self.url)
        time.sleep(3)  # Allow page to load
        index = 1
        tokens = []
        while True:
            token_data = self.parse_token(index)
            if not token_data:
                break
            tokens.append(token_data)
            index += 1
        return tokens

    def parse_token(self, index):
        a_xpath = f'/html/body/div[1]/div/main/div/div[4]/a[{index}]'
        try:
            a_element = WebDriverWait(self.driver, 10).until(
                EC.presence_of_element_located((By.XPATH, a_xpath))
            )
            token_data = {
                'href': a_element.get_attribute('href').strip('/'),
                'age': a_element.find_element(By.XPATH, f"{a_xpath}/div[3]").text,
                'timestamp': datetime.now().strftime("%Y-%m-%d %H:%M:%S")
            }
            logging.debug(f"Parsed token at index {index}: {token_data}")
            return token_data
        except TimeoutException:
            logging.info(f"No more tokens found at index {index}. Ending parse.")
            return None
        except NoSuchElementException as e:
            logging.error(f"Failed to parse token at index {index}: {e}")
            return None

    def classify_and_save_tokens(self, tokens):
        good_tokens = self.load_tokens(self.good_tokens_file)
        bad_tokens = self.load_tokens(self.bad_tokens_file)
        known_tokens = {token['href'] for token in good_tokens + bad_tokens}

        new_tokens = [token for token in tokens if token['href'] not in known_tokens]

        for token in new_tokens:
            token['contract_address'] = self.get_contract_address(token['href'])

        logging.info(f"Found {len(new_tokens)} new tokens")
        self.save_tokens(new_tokens, self.new_tokens_file)
        return new_tokens

    def load_tokens(self, filepath):
        if os.path.exists(filepath):
            with open(filepath, 'r') as file:
                return json.load(file)
        return []

    def save_tokens(self, tokens, filepath):
        existing_tokens = self.load_tokens(filepath)
        existing_tokens.extend(tokens)
        with open(filepath, 'w') as file:
            json.dump(existing_tokens, file, indent=4)

    def get_contract_address(self, href):
        logging.info(f"Fetching contract address from {href}")
        self.driver.get(href)
        for attempt in range(3):  # Retry mechanism
            try:
                button_xpath = "(//button[@type='button'])[22]"
                button_element = WebDriverWait(self.driver, 10).until(
                    EC.element_to_be_clickable((By.XPATH, button_xpath))
                )
                button_element.click()
                time.sleep(1)
                contract_address = pyperclip.paste().strip()
                
                if self.validate_contract_address(contract_address):
                    logging.info(f"Extracted contract address: {contract_address}")
                    return contract_address
                else:
                    logging.warning(f"Invalid contract address fetched: {contract_address}. Retrying...")

            except (TimeoutException, NoSuchElementException) as e:
                logging.error(f"Failed to get contract address from {href} on attempt {attempt + 1}: {e}")
                
        return None

    def validate_contract_address(self, address):
        return address and address.isalnum() and address.lower() != address.upper()

    def run_scraper(self):
        logging.info("Starting new tokens scraper")
        tokens = self.fetch_tokens()
        self.classify_and_save_tokens(tokens)

    def schedule_scraper(self):
        schedule.every().minute.at(":10").do(self.run_scraper)
        while True:
            schedule.run_pending()
            time.sleep(1)

    def close(self):
        self.driver.quit()

def main():
    logging.basicConfig(level=logging.DEBUG, format='%(asctime)s - %(levelname)s - %(message)s')
    driver = Driver(uc=True)
    scraper = NewJunkScraper(driver)
    scraper.schedule_scraper()
    driver.quit()

if __name__ == "__main__":
    main()
