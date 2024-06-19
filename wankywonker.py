import csv
import logging
import os
import pyperclip
import re
import time
from datetime import datetime
from seleniumbase import Driver
from selenium.webdriver.common.by import By
from selenium.webdriver.common.action_chains import ActionChains
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

class UnifiedScraper:
    def __init__(self, url, driver):
        self.url = url
        self.driver = driver
        self.tokens = []
        self.processed_tokens = set()

    def fetch_tokens(self):
        self.driver.get(self.url)
        time.sleep(3)  # Allow page to load
        index = 1
        new_tokens = []
        while True:
            token_data = self.parse_token(index)
            if not token_data:
                break
            if token_data['href'] not in self.processed_tokens:
                self.tokens.append(token_data)
                self.processed_tokens.add(token_data['href'])
                if self.is_new_token(token_data['age']):
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

    def is_new_token(self, age, max_minutes=5):
        time_parts = re.findall(r'(\d+)(s|m|h|d|mo)', age)
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
                    liquidity_locked = self.extract_liquidity_locked()
                    if ca:
                        token['contract_address'] = ca
                    if liquidity_locked:
                        token['liquidity_locked'] = liquidity_locked
                    print(f"Contract address fetched for token {token['name']} at {token['timestamp']}")
            except Exception as e:
                print(f"Page load check failed: {e}")
            finally:
                self.driver.close()
                self.driver.switch_to.window(original_window)
            self.save_to_csv(token)

    def extract_contract_address(self):
        try:
            copy_button_xpath = "/html/body/div[1]/div/main/div/div/div[1]/div/div/div[4]/div/div[1]/div[9]/div/button"
            button = WebDriverWait(self.driver, 20).until(EC.element_to_be_clickable((By.XPATH, copy_button_xpath)))
            ActionChains(self.driver).click(button).perform()
            time.sleep(2)
            return pyperclip.paste()
        except Exception as e:
            print(f"Could not extract contract address: {e}")
            return None

    def extract_liquidity_locked(self):
        try:
            icon_xpath = "/html/body/div[1]/div/main/div/div/div[1]/div/div/div[3]/div/div[1]/div[2]/div[1]/span[2]/div/div/div[2]/section/div/div/div/span"
            WebDriverWait(self.driver, 20).until(EC.element_to_be_clickable((By.XPATH, icon_xpath))).click()
            time.sleep(2)
            liquidity_locked_xpath = "/html/body/div[1]/div/main/div/div/div[1]/div/div/div[3]/div/div[1]/div[2]/div[1]/span[2]/div/div/div[2]/section/div/div/div/span"
            liquidity_locked_element = WebDriverWait(self.driver, 20).until(EC.presence_of_element_located((By.XPATH, liquidity_locked_xpath)))
            return liquidity_locked_element.text
        except Exception as e:
            print(f"Could not extract liquidity locked: {e}")
            return None

    def run_scraper(self):
        while True:
            new_tokens = self.fetch_tokens()
            if new_tokens:
                self.fetch_contract_addresses(new_tokens)
            time.sleep(60)  # Adjust the interval to scrape tokens (e.g., every minute)

    def save_to_csv(self, token):
        token_name = token['name'].replace(' ', '_')
        filename = f"{token_name}.csv"
        fieldnames = ['timestamp', 'price', 'volume', 'buys', 'sells', 'liquidity', 'FDV', 'contract_address', 'liquidity_locked']
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
                'liquidity_locked': token.get('liquidity_locked', 'N/A')
            })

    def close(self):
        self.driver.quit()

def main():
    logging.basicConfig(level=logging.DEBUG, format='%(asctime)s - %(levelname)s - %(message)s')
    driver = Driver(uc=True)
    driver.maximize_window()
    scraper = UnifiedScraper(URL, driver)
    scraper.run_scraper()  # Run immediately on start
    schedule.every(1).minutes.do(scraper.run_scraper)  # Check every minute

    try:
        while True:
            schedule.run_pending()
            time.sleep(1)
    except KeyboardInterrupt:
        scraper.close()
        driver.quit()

if __name__ == "__main__":
    main()
