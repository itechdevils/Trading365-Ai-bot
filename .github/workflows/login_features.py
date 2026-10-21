"""Opt-in single-account browser sign-in; credentials never written to app data."""
from pathlib import Path

def sign_in(profile_path, username, password):
    from selenium import webdriver
    from selenium.webdriver.chrome.options import Options
    from selenium.webdriver.common.by import By
    from selenium.webdriver.support.ui import WebDriverWait
    from selenium.webdriver.support import expected_conditions as EC
    if not username or not password:
        raise ValueError('Username and password are required')
    options=Options()
    options.add_argument('--user-data-dir='+str(Path(profile_path).resolve()))
    options.add_argument('--no-first-run')
    driver=webdriver.Chrome(options=options)
    driver.get('https://www.facebook.com/login/')
    wait=WebDriverWait(driver,25)
    wait.until(EC.presence_of_element_located((By.ID,'email'))).send_keys(username)
    driver.find_element(By.ID,'pass').send_keys(password)
    driver.find_element(By.NAME,'login').click()
    # Leave browser open for user to complete any 2FA, CAPTCHA or checkpoints.
    return driver
