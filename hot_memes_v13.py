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

    def is_new_token(self, age, max_hours=10):
        time_parts = re.findall(r'(\d+)(mo|d|h|m)', age)
        total_hours = sum(int(part) * {'m': 1/60, 'h': 1, 'd': 24, 'mo': 720}.get(unit, 0) for part, unit in time_parts)
        return total_hours <= max_hours
    
    
    def fetch_contract_addresses(self, new_tokens, max_hours=10):
        original_window = self.driver.current_window_handle
        for token in new_tokens:
            self.driver.execute_script(f"window.open('{token['href']}');")
            self.driver.switch_to.window(self.driver.window_handles[-1])
            # Ensure correct page has loaded
            try:
                age_element = WebDriverWait(self.driver, 10).until(
                    EC.presence_of_element_located((By.XPATH, "/html/body/div[1]/div/main/div/div/div[1]/div/div/div[4]/div/div[1]/div[1]/span[2]"))
                )
                age_text = age_element.text
                # Use updated is_new_token method to check if the token is within the desired age range
                if self.is_new_token(age_text, max_hours):
                    ca = self.extract_contract_address()
                    if ca:
                        token['contract_address'] = ca
                        print(f"Contract address fetched for token {token['name']} at {token['timestamp']}")
            except Exception as e:
                print(f"Page load check failed: {e}")
            finally:
                self.driver.close()
                self.driver.switch_to.window(original_window)


    def extract_contract_address(self):
        try:
            copy_button_xpath = "/html/body/div[1]/div/main/div/div/div[1]/div/div/div[4]/div/div[1]/div[9]/div/button"
            button = WebDriverWait(self.driver, 10).until(EC.element_to_be_clickable((By.XPATH, copy_button_xpath)))
            ActionChains(self.driver).click(button).perform()
            time.sleep(2)
            return pyperclip.paste()
        except Exception as e:
            print(f"Could not extract contract address: {e}")
            return None



    def run_scraper(self):
        new_tokens = self.fetch_tokens()
        if new_tokens:
           self.fetch_contract_addresses(new_tokens, max_hours=10)
           self.save_to_csv()

        

    def save_to_csv(self):
        today_date = datetime.now().strftime('%d-%m-%Y')
        filename = f"{today_date}_new_memes.csv"
        fieldnames = ['name', 'fullname', 'price', 'age', 'makers', 'volume', 'buys', 'sells', 'liquidity', 'FDV', 'href', 'timestamp', 'contract_address']
        # Open the file with UTF-8 encoding to support a wide range of characters
        with open(filename, 'a', newline='', encoding='utf-8') as file:
            writer = csv.DictWriter(file, fieldnames=fieldnames)
            # Check if the file is being created for the first time and write the header
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
    schedule.every(5).minutes.do(scraper.run_scraper)

    try:
        while True:
            schedule.run_pending()
            time.sleep(1)
    except KeyboardInterrupt:
        scraper.close()
        driver.quit()

if __name__ == "__main__":
    main()
