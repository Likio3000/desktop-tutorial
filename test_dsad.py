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

class DexScreenerTest:
    BASE_URL = "https://dexscreener.com/solana/ani2uhlux4nfi8xrp7n6uhus2gguqvhjharry2sspndu"

    def __init__(self, driver):
        self.driver = driver
        self.driver.set_window_size(1919, 1040)  # Configurar el tamaño de la ventana

    def open_page_and_click(self):
        self.driver.get(self.BASE_URL)
        self.driver.maximize_window()  # Maximize the window at the beginning
        self.driver.execute_script("window.scrollTo(0,0)")
        self.driver.switch_to.frame(0)
        try:
            element = WebDriverWait(self.driver, 10).until(
                EC.presence_of_element_located((By.CSS_SELECTOR, ".chart-gui-wrapper > canvas:nth-child(2)"))
            )
            element.click()
        except (NoSuchElementException, TimeoutException, ElementClickInterceptedException) as e:
            logging.error(f"Error occurred: {e}")

    def close(self):
        self.driver.quit()

def main():
    logging.basicConfig(level=logging.DEBUG, format='%(asctime)s - %(levelname)s - %(message)s')

    driver = Driver(uc=True)
    test = DexScreenerTest(driver)
    try:
        test.open_page_and_click()
        print("Test completed. Browser will remain open for inspection.")
        time.sleep(19)  # Keep the browser open for 19 seconds before closing
    finally:
        test.close()

if __name__ == "__main__":
    main()
