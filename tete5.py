import json
import logging
import os
import time
from datetime import datetime
from seleniumbase import Driver
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.common.exceptions import NoSuchElementException, TimeoutException, ElementClickInterceptedException
import pyperclip

class InitialTokenScraper:
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
        self.driver.set_window_size(1919, 1040)  # Configure window size

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
            a_element = WebDriverWait(self.driver, 5).until(
                EC.presence_of_element_located((By.XPATH, a_xpath))
            )
            token_data = {
                'href': a_element.get_attribute('href').strip('/'),
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
            token['locked_liquidity'] = self.check_locked_liquidity(token['href'])
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
        
        # Scrolling down to load elements
        try:
            target_element_selector = "#root > div > main > div > div > div.custom-7w9b0e > div > div > div.custom-13zeudb > div > div:nth-child(1) > div.chakra-stack.custom-on4tvx > div:nth-child(3)"
            target_element = WebDriverWait(self.driver, 5).until(
                EC.presence_of_element_located((By.CSS_SELECTOR, target_element_selector))
            )
            logging.info(f"Located target element using selector: {target_element_selector}")

            # Move the mouse to the element by clicking on it (clicking ensures the focus is set to the element)
            self.driver.execute_script("arguments[0].scrollIntoView(true);", target_element)
            logging.info("Moved to and scrolled the target element into view.")
            time.sleep(1)  # Pause to simulate human-like interaction

            # Scroll down a few times with human-like delays
            for i in range(5):  # Adjust the range for more or fewer scrolls
                self.driver.execute_script("window.scrollBy(0, window.innerHeight / 5);")
                logging.info(f"Scrolled down {i + 1} time(s)")
                time.sleep(1)  # Adjust the sleep time for human-like delays
        except (TimeoutException, NoSuchElementException) as e:
            logging.error(f"Error during scrolling: {e}")

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

            except (TimeoutException, NoSuchElementException, ElementClickInterceptedException) as e:
                logging.error(f"Failed to get contract address from {href} on attempt {attempt + 1}: {e}")
                
        return None

    def check_locked_liquidity(self, href):
        logging.info(f"Checking locked liquidity for {href}")
        self.driver.get(href)
        try:
            liquidity_css_selector = ".custom-f1j64i > .chakra-icon"
            WebDriverWait(self.driver, 10).until(
                EC.presence_of_element_located((By.CSS_SELECTOR, liquidity_css_selector))
            )
            logging.info(f"Locked liquidity present for {href}")
            return True
        except TimeoutException:
            logging.info(f"No locked liquidity found for {href}")
            return False
        except NoSuchElementException as e:
            logging.error(f"Failed to check locked liquidity for {href}: {e}")
            return False

    def validate_contract_address(self, address):
        return address and address.isalnum() and address.lower() != address.upper()

    def run_initialization(self):
        logging.info("Starting initial tokens scraper")
        tokens = self.fetch_tokens()
        self.classify_and_save_tokens(tokens)

    def close(self):
        self.driver.quit()

def main():
    logging.basicConfig(level=logging.DEBUG, format='%(asctime)s - %(levelname)s - %(message)s')

    driver = Driver(uc=True)
    driver.set_window_size(1919, 1040)  # Configure window size
    scraper = InitialTokenScraper(driver)
    scraper.run_initialization()
    scraper.close()

if __name__ == "__main__":
    main()
