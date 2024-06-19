import csv
import logging
import os
import re
import time
from datetime import datetime
from seleniumbase import Driver
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
import schedule
import threading
from selenium.common.exceptions import NoSuchElementException, TimeoutException

class UnifiedScraper:
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
        self.tokens = []
        self.processed_tokens = set()
        self.new_tokens = []

    def fetch_tokens(self):
        self.driver.get(self.url)
        time.sleep(3)  # Allow page to load
        index = 1
        while True:
            token_data = self.parse_token(index)
            if not token_data:
                break
            if token_data['href'] not in self.processed_tokens:
                self.tokens.append(token_data)
                self.processed_tokens.add(token_data['href'])
                if self.is_new_token(token_data['age']):
                    self.new_tokens.append(token_data)
            index += 1
        return self.new_tokens

    def parse_token(self, index):
        a_xpath = f'/html/body/div[1]/div/main/div/div[4]/a[{index}]'
        try:
            a_element = WebDriverWait(self.driver, 10).until(
                EC.presence_of_element_located((By.XPATH, a_xpath))
            )
            token_data = {
                'href': a_element.get_attribute('href').strip('/'),
                'timestamp': datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
                'name': a_element.find_element(By.XPATH, f"{a_xpath}/div[1]/span[2]").text,
                'fullname': a_element.find_element(By.XPATH, f"{a_xpath}/div[1]/span[5]").text,
                'price': a_element.find_element(By.XPATH, f"{a_xpath}/div[2]").text,
                'age': a_element.find_element(By.XPATH, f"{a_xpath}/div[3]").text,
                'makers': a_element.find_element(By.XPATH, f"{a_xpath}/div[7]").text,
                'volume': a_element.find_element(By.XPATH, f"{a_xpath}/div[6]").text,
                'buys': a_element.find_element(By.XPATH, f"{a_xpath}/div[4]").text,
                'sells': a_element.find_element(By.XPATH, f"{a_xpath}/div[5]").text,
                'liquidity': a_element.find_element(By.XPATH, f"{a_xpath}/div[12]").text,
                'FDV': a_element.find_element(By.XPATH, f"{a_xpath}/div[13]").text
            }
            return token_data
        except (NoSuchElementException, TimeoutException) as e:
            logging.error(f"Failed to parse token at index {index}: {e}")
            return None

    def is_new_token(self, age, max_minutes=30):
        time_parts = re.findall(r'(\d+)(mo|d|h|m|s)', age)
        total_minutes = sum(int(part) * {'s': 1/60, 'm': 1, 'h': 60, 'd': 1440, 'mo': 43200}.get(unit, 0) for part, unit in time_parts)
        return total_minutes <= max_minutes

    def fetch_contract_addresses(self, new_tokens):
        original_window = self.driver.current_window_handle
        for token in new_tokens:
            self.driver.execute_script(f"window.open('{token['href']}');")
            self.driver.switch_to.window(self.driver.window_handles[-1])
            self.driver.maximize_window()  # Ensure the new window is maximized
            try:
                age_element = WebDriverWait(self.driver, 20).until(
                    EC.presence_of_element_located((By.XPATH, "/html/body/div[1]/div/main/div/div/div[1]/div/div/div[4]/div/div[1]/div[1]/span[2]"))
                )
                age_text = age_element.text
                if self.is_new_token(age_text, max_minutes=5):
                    ca = self.extract_contract_address()
                    if ca:
                        token['contract_address'] = ca
                    print(f"Contract address fetched for token {token['name']} at {token['timestamp']}")
            except Exception as e:
                logging.error(f"Page load check failed: {e}")
            finally:
                self.driver.close()
                self.driver.switch_to.window(original_window)
            self.save_to_csv(token)

    def extract_contract_address(self):
        try:
            contract_address_xpath = "/html/body/div[1]/div/main/div/div/div[1]/div/div/div[3]/div/div[1]/div[9]/div/a"
            contract_address_element = WebDriverWait(self.driver, 10).until(
                EC.presence_of_element_located((By.XPATH, contract_address_xpath))
            )
            return contract_address_element.get_attribute('href')
        except Exception as e:
            logging.error(f"Could not extract contract address: {e}")
            return None

    def run_scraper(self):
        new_tokens = self.fetch_tokens()
        if new_tokens:
            threading.Thread(target=self.fetch_contract_addresses, args=(new_tokens,)).start()
        self.schedule_token_updates()
        self.continuous_update()

    def schedule_token_updates(self):
        for token in self.new_tokens:
            schedule.every(1).minute.do(self.update_token_data, token)

    def continuous_update(self):
        while True:
            schedule.run_pending()
            time.sleep(1)

    def update_token_data(self, token):
        self.driver.get(token['href'])
        try:
            token_data = self.parse_token_data(token['href'])
            if token_data:
                token.update(token_data)
                self.save_to_csv(token)
        except Exception as e:
            logging.error(f"Failed to update token data: {e}")

    def parse_token_data(self, href):
        try:
            self.driver.get(href)
            token_data = {
                'price': self.driver.find_element(By.XPATH, "//div[2]").text,
                'volume': self.driver.find_element(By.XPATH, "//div[6]").text,
                'buys': self.driver.find_element(By.XPATH, "//div[4]").text,
                'sells': self.driver.find_element(By.XPATH, "//div[5]").text,
                'liquidity': self.driver.find_element(By.XPATH, "//div[12]").text,
                'FDV': self.driver.find_element(By.XPATH, "//div[13]").text,
                'makers': self.driver.find_element(By.XPATH, "//div[7]").text,
                'age': self.driver.find_element(By.XPATH, "//div[3]").text,
                'href': href
            }
            return token_data
        except Exception as e:
            logging.error(f"Failed to parse token data from {href}: {e}")
            return None

    def save_to_csv(self, token):
        filename = os.path.join("new_memes", f"{token['name']}.csv")
        fieldnames = ['name', 'fullname', 'price', 'age', 'makers', 'volume', 'buys', 'sells', 'liquidity', 'FDV', 'href', 'timestamp', 'contract_address']
        os.makedirs("new_memes", exist_ok=True)
        with open(filename, 'a', newline='', encoding='utf-8') as file:
            writer = csv.DictWriter(file, fieldnames=fieldnames)
            if not os.path.isfile(filename) or os.stat(filename).st_size == 0:
                writer.writeheader()
            writer.writerow({field: token.get(field, '') for field in fieldnames})

    def close(self):
        self.driver.quit()

def main():
    logging.basicConfig(level=logging.DEBUG, format='%(asctime)s - %(levelname)s - %(message)s')
    driver = Driver(uc=True)
    driver.maximize_window()
    scraper = UnifiedScraper(driver)
    scraper.run_scraper()  # Run immediately on start

    try:
        while True:
            time.sleep(1)
    except KeyboardInterrupt:
        scraper.close()
        driver.quit()

if __name__ == "__main__":
    main()
