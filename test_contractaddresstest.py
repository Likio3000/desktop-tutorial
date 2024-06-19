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
from selenium.webdriver.common.action_chains import ActionChains

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

class TestContractAddressTest:
    def setup_method(self, method):
        self.driver = Driver(browser="chrome")
        self.vars = {}
    
    def teardown_method(self, method):
        self.driver.quit()
    
    def wait_for_window(self, timeout=2):
        time.sleep(timeout)
        wh_now = self.driver.window_handles
        wh_then = self.vars["window_handles"]
        if len(wh_now) > len(wh_then):
            return list(set(wh_now) - set(wh_then))[0]
    
    def test_contract_address_test(self):
        self.driver.get("https://dexscreener.com/solana/8mtwqhqpeu9xqpmndhpo59z6nkvo32ptz7qwggo8ewrz")
        self.driver.set_window_size(1919, 1040)
        self.driver.execute_script("window.scrollTo(0, 0)")
        self.vars["window_handles"] = self.driver.window_handles
        self.driver.find_element(By.CSS_SELECTOR, ".chakra-stack:nth-child(9) .chakra-link").click()
        self.vars["win6911"] = self.wait_for_window(2)
        self.driver.switch_to.window(self.vars["win6911"])
        try:
            element = WebDriverWait(self.driver, 10).until(
                EC.presence_of_element_located((By.CSS_SELECTOR, "a:nth-child(1) > .cursor-pointer"))
            )
            actions = ActionChains(self.driver)
            actions.move_to_element(element).perform()
        except (NoSuchElementException, TimeoutException):
            logging.error("Element not found or timeout exceeded")

def main():
    logging.basicConfig(level=logging.DEBUG, format='%(asctime)s - %(levelname)s - %(message)s')
    driver = Driver(uc=True)
    driver.maximize_window()
    
    # Run the contract scraper
    scraper = ContractScraper(driver)
    scraper.run_scraper()

    # Run the test
    test = TestContractAddressTest()
    test.setup_method(None)
    try:
        test.test_contract_address_test()
    finally:
        test.teardown_method(None)

    try:
        while True:
            time.sleep(1)
    except KeyboardInterrupt:
        scraper.close()
        driver.quit()

if __name__ == "__main__":
    main()
