import csv
import logging
import os
import time
from datetime import datetime
from seleniumbase import Driver
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
import schedule
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
            logging.debug(f"Parsed token at index {index}: {token_data}")
            return token_data
        except TimeoutException:
            logging.info(f"No more tokens found at index {index}. Ending parse.")
            return None
        except NoSuchElementException as e:
            logging.error(f"Failed to parse token at index {index}: {e}")
            return None

    def save_to_csv(self, token):
        filename = os.path.join("new_memes", f"{token['name']}.csv")
        fieldnames = ['name', 'fullname', 'price', 'age', 'makers', 'volume', 'buys', 'sells', 'liquidity', 'FDV', 'href', 'timestamp']
        os.makedirs("new_memes", exist_ok=True)
        with open(filename, 'a', newline='', encoding='utf-8') as file:
            writer = csv.DictWriter(file, fieldnames=fieldnames)
            if os.stat(filename).st_size == 0:
                writer.writeheader()
            writer.writerow({field: token.get(field, '') for field in fieldnames})

    def run_scraper(self):
        logging.info("Starting scraper")
        self.schedule_token_updates()
        self.continuous_update()

    def schedule_token_updates(self):
        schedule.every().minute.at(":00").do(self.update_tokens)
        logging.info("Scheduled token updates every minute")

    def continuous_update(self):
        while True:
            schedule.run_pending()
            time.sleep(1)

    def update_tokens(self):
        logging.info("Updating tokens")
        tokens = self.fetch_tokens()
        for token in tokens:
            self.save_to_csv(token)
        logging.info(f"Updated {len(tokens)} tokens")

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
