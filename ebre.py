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

class ContractScraper:
    def __init__(self, driver, folder="new_memes"):
        self.driver = driver
        self.folder = folder

    def scrape_contract_addresses(self):
        for filename in os.listdir(self.folder):
            if filename.endswith(".csv"):
                self.scrape_contract_from_file(os.path.join(self.folder, filename))

    def scrape_contract_from_file(self, filepath):
        logging.info(f"Scraping contract addresses from {filepath}")
        tokens = self.read_csv(filepath)
        for token in tokens:
            contract_address = self.get_contract_address(token['href'])
            if contract_address:
                token['contract_address'] = contract_address
                self.update_csv(filepath, token)

    def read_csv(self, filepath):
        tokens = []
        with open(filepath, newline='', encoding='utf-8') as file:
            reader = csv.DictReader(file)
            for row in reader:
                tokens.append(row)
        return tokens

    def update_csv(self, filepath, token):
        temp_filepath = filepath + ".tmp"
        fieldnames = ['name', 'fullname', 'price', 'age', 'makers', 'volume', 'buys', 'sells', 'liquidity', 'FDV', 'href', 'timestamp', 'contract_address']
        with open(filepath, 'r', newline='', encoding='utf-8') as file, open(temp_filepath, 'w', newline='', encoding='utf-8') as temp_file:
            reader = csv.DictReader(file)
            writer = csv.DictWriter(temp_file, fieldnames=fieldnames)
            writer.writeheader()
            for row in reader:
                if row['href'] == token['href']:
                    row['contract_address'] = token.get('contract_address', row.get('contract_address', ''))
                writer.writerow(row)
        os.replace(temp_filepath, filepath)

    def get_contract_address(self, href):
        logging.info(f"Fetching contract address from {href}")
        self.driver.get(href)
        try:
            # Presionar el botón para abrir una nueva pestaña
            button_xpath = "/html/body/div[1]/div/main/div/div/div[1]/div/div/div[3]/div/div[1]/div[9]/div/a"
            button_element = WebDriverWait(self.driver, 10).until(
                EC.element_to_be_clickable((By.XPATH, button_xpath))
            )
            button_element.click()
            
            # Cambiar a la nueva pestaña
            self.driver.switch_to.window(self.driver.window_handles[-1])
            contract_address_url = self.driver.current_url
            logging.info(f"Found contract address URL: {contract_address_url}")

            # Extraer la dirección del contrato desde la URL
            contract_address = contract_address_url.split("token/")[1]
            logging.info(f"Extracted contract address: {contract_address}")

            # Cerrar la pestaña y volver a la original
            self.driver.close()
            self.driver.switch_to.window(self.driver.window_handles[0])
            
            return contract_address
        except (TimeoutException, NoSuchElementException) as e:
            logging.error(f"Failed to get contract address from {href}: {e}")
            return None

    def run_scraper(self):
        self.scrape_contract_addresses()

    def close(self):
        self.driver.quit()

def main():
    logging.basicConfig(level=logging.DEBUG, format='%(asctime)s - %(levelname)s - %(message)s')
    driver = Driver(uc=True)
    driver.maximize_window()
    scraper = ContractScraper(driver)
    scraper.run_scraper()

    try:
        while True:
            time.sleep(1)
    except KeyboardInterrupt:
        scraper.close()
        driver.quit()

if __name__ == "__main__":
    main()
