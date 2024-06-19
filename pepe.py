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

# Configuración de parámetros
CHAIN_ID = "solana"
MIN_LIQUIDITY = 10000
MAX_FDV = 200000000
MAX_AGE_HOURS = 1
MIN_5M_VOL = 3000

URL = f"https://dexscreener.com/?rankBy=pairAge&order=asc&chainIds={CHAIN_ID}&minLiq={MIN_LIQUIDITY}&maxFdv={MAX_FDV}&maxAge={MAX_AGE_HOURS}&min5MVol={MIN_5M_VOL}"

CSV_FOLDER = "csv_files"
MAX_RETRIES = 3  # Maximum number of retries for extracting contract address

class UnifiedScraper:
    def __init__(self, url, driver):
        self.url = url
        self.driver = driver
        self.tokens = []
        self.processed_tokens = set()
        if not os.path.exists(CSV_FOLDER):
            os.makedirs(CSV_FOLDER)

    def fetch_tokens(self):
        self.driver.get(self.url)
        self.driver.maximize_window()  # Ensure the window is maximized
        try:
            WebDriverWait(self.driver, 20).until(
                EC.presence_of_element_located((By.XPATH, '/html/body/div[1]/div/main/div/div[4]/a[1]'))
            )
        except Exception as e:
            logging.error(f"Error loading the page: {e}")
            return []

        index = 1
        new_tokens = []
        while True:
            token_data = self.parse_token(index)
            if not token_data:
                break
            if token_data['href'] not in self.processed_tokens:
                self.processed_tokens.add(token_data['href'])
                if self.is_recent_token(token_data['age'], max_minutes=30):
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
            logging.error(f"Failed to parse token at index {index}: {e}")
            return None

    def is_recent_token(self, age, max_minutes=30):
        time_parts = re.findall(r'(\d+)(s|m|h|d|mo)', age)
        total_minutes = sum(int(part) * {'s': 1/60, 'm': 1, 'h': 60, 'd': 1440, 'mo': 43200}.get(unit, 0) for part, unit in time_parts)
        return total_minutes <= max_minutes

    def fetch_contract_addresses(self, new_tokens):
        for token in new_tokens:
            self.process_token(token)

    def process_token(self, token):
        self.driver.execute_script(f"window.open('{token['href']}', '_blank');")
        new_window = self.driver.window_handles[-1]
        self.driver.switch_to.window(new_window)
        self.driver.maximize_window()  # Ensure the new window is maximized
        try:
            age_element = WebDriverWait(self.driver, 20).until(
                EC.presence_of_element_located((By.XPATH, "/html/body/div[1]/div/main/div/div/div[1]/div/div/div[4]/div/div[1]/div[1]/span[2]"))
            )
            age_text = age_element.text
            if self.is_recent_token(age_text):
                ca = self.extract_contract_address()
                if ca:
                    token['contract_address'] = ca
                    logging.info(f"Contract address fetched for token {token['name']} at {token['timestamp']}")
        except Exception as e:
            logging.error(f"Page load check failed: {e}")
        finally:
            self.driver.close()
            self.driver.switch_to.window(self.driver.window_handles[0])
        self.save_to_csv(token)

    def extract_contract_address(self):
        retries = 0
        while retries < MAX_RETRIES:
            try:
                address_xpath = "/html/body/div[1]/div/main/div/div/div[1]/div/div/div[4]/div/div[1]/div[9]/span"
                address_element = WebDriverWait(self.driver, 20).until(EC.presence_of_element_located((By.XPATH, address_xpath)))
                contract_address = address_element.get_attribute('title')
                return contract_address
            except Exception as e:
                logging.error(f"Could not extract contract address: {e}. Retry {retries + 1}/{MAX_RETRIES}")
                retries += 1
                time.sleep(2)
        return None

    def run_scraper(self):
        new_tokens = self.fetch_tokens()
        if new_tokens:
            self.fetch_contract_addresses(new_tokens)
        schedule.every(1).minutes.do(self.run_scraper_job)  # Schedule the job to run every minute

    def run_scraper_job(self):
        new_tokens = self.fetch_tokens()
        if new_tokens:
            self.fetch_contract_addresses(new_tokens)
        logging.info("Scraper job completed.")

    def save_to_csv(self, token):
        token_name = token['name'].replace(' ', '_')
        filename = os.path.join(CSV_FOLDER, f"{token_name}.csv")
        fieldnames = ['timestamp', 'price', 'volume', 'buys', 'sells', 'liquidity', 'FDV', 'contract_address', 'pair_link']
        file_exists = os.path.isfile(filename)
        with open(filename, 'a', newline='', encoding='utf-8') as file:
            writer = csv.DictWriter(file, fieldnames=fieldnames)
            if not file_exists:
                writer.writeheader()
            writer.writerow({
                'timestamp': token['timestamp'],
                'price': token['price'],
                'volume': token['volume'],
                'buys': token['buys'],
                'sells': token['sells'],
                'liquidity': token['liquidity'],
                'FDV': token['FDV'],
                'contract_address': token.get('contract_address', 'N/A'),
                'pair_link': token['href']
            })

    def close(self):
        self.driver.quit()

def main():
    logging.basicConfig(level=logging.DEBUG, format='%(asctime)s - %(levelname)s - %(message)s')
    driver = Driver(uc=True)
    driver.maximize_window()
    scraper = UnifiedScraper(URL, driver)
    scraper.run_scraper()  # Run immediately on start

    try:
        while True:
            schedule.run_pending()
            time.sleep(1)
    except KeyboardInterrupt:
        scraper.close()
        driver.quit()

if __name__ == "__main__":
    main()
