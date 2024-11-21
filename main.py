import sys
import json
import asyncio
import time
import tempfile
import random
from fake_useragent import UserAgent
from loguru import logger
from seleniumwire import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.chrome.options import Options

logger.remove()
logger.add(sys.stdout, level="INFO", format="{time:YYYY-MM-DD HH:mm:ss} | {level} | {message}")

with open('config.json', 'r') as f:
    config = json.load(f)

MAX_ATTEMPTS = 5
DELAY = 10
ACCOUNTS_FILE = config['accounts_file']
PROXIES_FILE = config['proxies_file']
SESSION_INTERVAL = config['session_interval']
EXTENSION_PATH = './extensions/gradient_extension.crx'
CHROMEDRIVER_PATH = './chromedriver-linux64/chromedriver'

def load_data(filename):
    with open(filename, 'r') as f:
        return [line.strip() for line in f]

def setup_driver(proxy):
    chrome_options = Options()

    seleniumwire_options = {
        "proxy": {
            "http": proxy,
            "https": proxy,
        },
        'disable_encoding': True,
        'suppress_connection_errors': True,
        'verify_ssl': False,
        'connection_timeout': None,
        'connection_keep_alive': True,
        'no_proxy': '',
        'headers': {
            'User-Agent': UserAgent().random
        }
    }

    chrome_options.add_argument('--ignore-certificate-errors')
    chrome_options.add_argument('--ignore-ssl-errors')
    chrome_options.add_argument('--headless')
    chrome_options.add_argument('--no-sandbox')
    chrome_options.add_argument('--disable-gpu')
    chrome_options.add_argument('--disable-dev-shm-usage')
    chrome_options.add_argument(f'user-agent={UserAgent().random}')
    chrome_options.add_argument('--disable-blink-features=AutomationControlled')
    chrome_options.add_argument("--verbose")
    chrome_options.add_argument("--log-level=3")
    chrome_options.add_argument('--disable-software-rasterizer')
    chrome_options.add_argument('--disable-webgl')
    chrome_options.add_argument('--disable-webgl-extensions')
    chrome_options.add_argument('--disable-accelerated-2d-canvas')
    chrome_options.add_argument('--disable-accelerated-jpeg-decoding')
    chrome_options.add_argument('--disable-accelerated-video-decode')
    chrome_options.add_argument('--disable-gpu-sandbox')

    print(f"Loading extension from: {EXTENSION_PATH}")
    chrome_options.add_extension(EXTENSION_PATH)


    user_data_dir = tempfile.mkdtemp()

    driver = webdriver.Chrome(seleniumwire_options=seleniumwire_options, options=chrome_options)

    return driver
    
def close_popups(driver):
    try:
        close_button = WebDriverWait(driver, 5).until(
            EC.presence_of_element_located((By.XPATH,
                                            "//div[contains(@class, 'flex-row-center') and contains(@class, 'bg-[#fff]') and contains(@class, 'rounded-full')]"))
        )
        close_button.click()
        logger.info("Popup 1 was closed")
    except Exception:
        logger.info("Popup 1 not found or unable to close")

    try:
        got_it_button = WebDriverWait(driver, 5).until(
            EC.element_to_be_clickable(
                (By.XPATH, "//button[contains(@class, 'w-full') and contains(text(), 'I got it')]"))
        )
        got_it_button.click()
        logger.info("Popup 2 was closed")
    except Exception:
        logger.info("Popup 2 not found or unable to close")

def wait_for_page_load(driver):
    try:
        WebDriverWait(driver, 120).until(
            lambda d: d.execute_script('return document.readyState') == 'complete'
        )
        time.sleep(15)
        logger.info("Page fully loaded")
    except Exception as e:
        logger.error(f"Timeout waiting for page load: {str(e)}")
        raise

def login_to_extension(driver, username, password):
    try:
        driver.get('chrome-extension://caacbgbklghmpodbdafajbgdnegacfmo/popup.html')
        
        wait_for_page_load(driver)

        window_handles = driver.window_handles
        logger.info(f"Window handles: {window_handles}")

        while len(driver.window_handles) < 2:
            pass

        driver.switch_to.window(driver.window_handles[-1])
        wait_for_page_load(driver)
        logger.info("Switched to the second tab")
        
        driver.switch_to.window(window_handles[-1])
        email_input = WebDriverWait(driver, 15).until(
            EC.presence_of_element_located((By.XPATH, "/html/body/div[1]/div[2]/div/div/div/div[2]/div[1]/input"))
        )
        email_input.send_keys(username)
        logger.info("Entered username")

        password_input = WebDriverWait(driver, 15).until(
            EC.presence_of_element_located((By.XPATH, "/html/body/div[1]/div[2]/div/div/div/div[2]/div[2]/span/input"))
        )
        password_input.send_keys(password)
        logger.info("Entered password")

        login_button = driver.find_element(By.XPATH, "/html/body/div[1]/div[2]/div/div/div/div[4]/button[1]")
        login_button.click()
        logger.info("Logging button clicked")

        wait_for_page_load(driver)

        close_popups(driver)

        logger.info("Successfull login!")

        driver.switch_to.window(driver.window_handles[0])
        wait_for_page_load(driver)
        logger.info("Switched back to extension tab")

        if driver.current_url.startswith('chrome-extension://'):
            logger.info("Successfully returned to extension page")

            driver.refresh()
            wait_for_page_load(driver)
            logger.info("Extension page refreshed")

            time.sleep(random.randint(1, 5))

            close_popups(driver)

            time.sleep(random.randint(1, 5))

            return True
        else:
            logger.error("Failed to return to extension page")
            return False

    except Exception as e:
        logger.error(f"Error during login: {str(e)}")
        return False

async def run_session_maintenance(driver, interval, username, password, proxy):
    while True:
        try:
            await maintain_session(driver, username, password, proxy)
            await asyncio.sleep(interval)
        except Exception as e:
            logger.error(f"[{username}] Critical error in session maintenance: {str(e)}")
            break

async def farm_points(account, proxy):
    username, password = account.split(':')
    logger.info(f"[{username}] Start farming")
    driver = None
    login_attempts = 0
    maintenance_task = None

    while login_attempts < MAX_ATTEMPTS:
        try:
            if driver:
                driver.quit()

            driver = setup_driver(proxy)

            if login_to_extension(driver, username, password):
                logger.info(f"[{username}] Successfully logged in")

                if maintenance_task and not maintenance_task.done():
                    maintenance_task.cancel()
                maintenance_task = asyncio.create_task(
                    run_session_maintenance(driver, SESSION_INTERVAL, username, password, proxy)
                )

                while True:
                    await asyncio.sleep(60)
            else:
                raise Exception("Login failed")

        except Exception as e:
            login_attempts += 1
            logger.error(f"[{username}] Error occurred (Attempt {login_attempts}/{MAX_ATTEMPTS}): {str(e)}")

            if login_attempts < MAX_ATTEMPTS:
                logger.info(f"[{username}] Retrying login in {DELAY} seconds...")
                await asyncio.sleep(DELAY)
            else:
                logger.error(f"[{username}] Max login attempts reached. Giving up.")

        finally:
            if maintenance_task and not maintenance_task.done():
                maintenance_task.cancel()
            if driver:
                driver.quit()

    logger.error(f"[{username}] Failed to farm points after {MAX_ATTEMPTS} attempts.")

async def maintain_session(driver, username, password, proxy):
    attempts = 0

    while attempts < MAX_ATTEMPTS:
        try:
            logger.info(f"[{username}] Starting session maintenance")

            driver.switch_to.window(driver.window_handles[1])
            logger.info(f"[{username}] Switched to dashboard tab")

            driver.refresh()
            wait_for_page_load(driver)
            logger.info(f"[{username}] Dashboard refreshed")

            points_element = WebDriverWait(driver, 30).until(
                EC.presence_of_element_located(
                    (By.XPATH, "/html/body/div[1]/div[1]/div[2]/main/div/div/div[2]/div/div[1]/div[2]/div[1]")
                )
            )
            points = points_element.text
            logger.info(f"[{username}] Current points: {points}")

            driver.switch_to.window(driver.window_handles[0])
            driver.refresh()
            wait_for_page_load(driver)
            logger.info(f"[{username}] Extension tab refreshed")

            connection_status = WebDriverWait(driver, 30).until(
                EC.presence_of_element_located((By.XPATH, "//*/div/div[1]/div[2]/div[3]/div[2]/div/div[2]/div"))
            )
            
            connection = connection_status.text
            if(connection == "Good"):
                logger.info(f"[{username}] Connection status: {connection}")
            else:
                logger.info(f"Your connection status is {connection}. Terminating session.")
                driver.quit()
                driver = setup_driver(proxy)

                if not login_to_extension(driver, username, password):
                    logger.error(f"[{username}] Login failed after restarting driver.")
                    raise Exception("Login failed after driver restart")

                logger.info(f"[{username}] Successfully re-logged in after driver restart")

            attempts = 0
            await asyncio.sleep(SESSION_INTERVAL)

        except Exception as e:
            attempts += 1
            logger.error(f"[{username}] Error during session maintenance (Attempt {attempts}/{MAX_ATTEMPTS}): {str(e)}")

            if attempts >= MAX_ATTEMPTS:
                logger.error(f"[{username}] Max attempts reached. Restarting driver...")

                driver.quit()
                driver = setup_driver(proxy)

                if not login_to_extension(driver, username, password):
                    logger.error(f"[{username}] Login failed after restarting driver.")
                    raise Exception("Login failed after driver restart")

                logger.info(f"[{username}] Successfully re-logged in after driver restart")
                attempts = 0 

            await asyncio.sleep(DELAY)


async def main():
    accounts = load_data(ACCOUNTS_FILE)
    proxies = load_data(PROXIES_FILE)

    if len(accounts) == 0:
        logger.info("File accounts.txt can't be empty")
        return
    
    if len(proxies) == 0:
        logger.info("File proxy.txt can't be empty")
        return
    
    if len(accounts) > len(proxies):
        logger.info("You should have proxies <= than accounts.")
        return

    tasks = []
    for i in range(min(len(accounts), len(proxies))):
        tasks.append(farm_points(accounts[i], proxies[i]))

    await asyncio.gather(*tasks)

if __name__ == "__main__":
    asyncio.run(main())
