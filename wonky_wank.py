import csv
import logging
import os
import re
import time
from datetime import datetime
from seleniumbase import Driver
from selenium.webdriver.common.by import By
from selenium.webdriver.common.action_chains import ActionChains
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
import schedule

class UnifiedScraper:
    def __init__(self, url, driver):
        self.url = url
        self.driver = driver
        self.tokens = []
        self.processed_tokens = set()

    def fetch_tokens(self):
        self.driver.get(self.url)
        time.sleep(2)  # Allow page to load
        index = 1
        new_tokens = []
        while True:
            token_data = self.parse_token(index)
            if not token_data:
                break
            if token_data['href'] not in self.processed_tokens and self.is_new_token(token_data['age']):
                self.tokens.append(token_data)
                self.processed_tokens.add(token_data['href'])
                new_tokens.append(token_data)
            index += 1
        return new_tokens

    def parse_token(self, index):
        a_xpath = f'/html/body/div[1]/div/main/div/div[4]/a[{index}]'
        try:
            a_element = self.driver.find_element(By.XPATH, a_xpath)
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
        except Exception as e:
            print(f"Failed to parse token at index {index}: {e}")
            return None

    def is_new_token(self, age, max_minutes=30):
        time_parts = re.findall(r'(\d+)(mo|d|h|m)', age)
        total_minutes = sum(int(part) * {'m': 1, 'h': 60, 'd': 1440, 'mo': 43200}.get(unit, 0) for part, unit in time_parts)
        return total_minutes <= max_minutes

    def update_prices(self):
        self.driver.get(self.url)
        time.sleep(3)  # Allow page to load
        for token in self.tokens:
            try:
                token_data = self.parse_token_by_href(token['href'])
                if token_data:
                    token['price'] = token_data['price']
                    token['timestamp'] = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
            except Exception as e:
                print(f"Failed to update price for token {token['name']}: {e}")

    def parse_token_by_href(self, href):
        index = 1
        while True:
            a_xpath = f'/html/body/div[1]/div/main/div/div[4]/a[{index}]'
            try:
                a_element = self.driver.find_element(By.XPATH, a_xpath)
                if a_element.get_attribute('href').strip('/') == href:
                    token_data = {
                        'price': a_element.find_element(By.XPATH, f"{a_xpath}/div[2]").text
                    }
                    return token_data
            except Exception as e:
                print(f"Failed to parse token by href: {e}")
                return None
            index += 1

    def run_scraper(self):
        new_tokens = self.fetch_tokens()
        if new_tokens:
            self.save_to_csv()
        self.update_prices()

    def save_to_csv(self):
        today_date = datetime.now().strftime('%d-%m-%Y')
        filename = f"{today_date}_new_memes.csv"
        fieldnames = ['name', 'fullname', 'price', 'age', 'makers', 'volume', 'buys', 'sells', 'liquidity', 'FDV', 'href', 'timestamp']
        with open(filename, 'a', newline='', encoding='utf-8') as file:
            writer = csv.DictWriter(file, fieldnames=fieldnames)
            if not os.path.isfile(filename) or os.stat(filename).st_size == 0:
                writer.writeheader()
            for token in self.tokens:
                writer.writerow({field: token.get(field, '') for field in fieldnames})

    def close(self):
        self.driver.quit()

def main():
    logging.basicConfig(level=logging.DEBUG, format='%(asctime)s - %(levelname)s - %(message)s')
    driver = Driver(uc=True)
    driver.maximize_window()
    scraper = UnifiedScraper("https://dexscreener.com/?rankBy=pairAge&order=asc&chainIds=solana&minLiq=10000&maxFdv=200000000&min5MVol=35000", driver)
    scraper.run_scraper()  # Run immediately on start
    schedule.every(1).minutes.do(scraper.run_scraper)

    try:
        while True:
            schedule.run_pending()
            time.sleep(1)
    except KeyboardInterrupt:
        scraper.close()
        driver.quit()

if __name__ == "__main__":
    main()
