import tkinter as tk
from tkinter import filedialog, messagebox, scrolledtext
import multiprocessing
import os
import glob
import random
import time

# ====== الوظيفة التي تنفذ النشر لكل حساب ======
def run_poster(BASE_FOLDER, port, log_queue):
    import pyperclip
    from selenium import webdriver
    from selenium.webdriver.chrome.service import Service
    from selenium.webdriver.chrome.options import Options
    from selenium.webdriver.common.by import By
    from selenium.webdriver.common.action_chains import ActionChains
    from selenium.webdriver.common.keys import Keys
    from selenium.webdriver.support.ui import WebDriverWait
    from selenium.webdriver.support import expected_conditions as EC
    from webdriver_manager.chrome import ChromeDriverManager

    def log(msg):
        log_queue.put(f"[{os.path.basename(BASE_FOLDER)}] {msg}")

    PROFILE_PATH_FILE = os.path.join(BASE_FOLDER, "profile.txt")
    LINKS_PATH = os.path.join(BASE_FOLDER, "links.txt")
    MEDIA_FOLDER = os.path.join(BASE_FOLDER, "images")
    SUPPORTED_EXTENSIONS = ("*.jpg", "*.jpeg", "*.png", "*.gif", "*.mp4", "*.mov", "*.avi", "*.mkv")
    FAILED_GROUPS_FILE = os.path.join(BASE_FOLDER, "failed_groups.txt")  # NEW

    def send_text_to_box(driver, element, message):
        try:
            element.click()
            time.sleep(0.3)
            element.send_keys(message)
            time.sleep(1)
            value = element.text or element.get_attribute("innerText") or ""
            if message.strip()[:5] not in value:
                raise Exception("Text not typed, trying clipboard method")
            return True
        except Exception as e:
            log(f"send_keys failed, trying clipboard: {e}")

        try:
            pyperclip.copy(message)
            element.click()
            time.sleep(0.3)
            ActionChains(driver).key_down(Keys.COMMAND).send_keys('v').key_up(Keys.COMMAND).perform()
            time.sleep(1)
            value = element.text or element.get_attribute("innerText") or ""
            if message.strip()[:5] not in value:
                log("❌ Clipboard paste did not work either.")
                return False
            return True
        except Exception as e:
            log(f"Clipboard paste failed: {e}")
            return False

    if not os.path.isfile(PROFILE_PATH_FILE):
        log(f"❌ ملف profile.txt غير موجود")
        return
    with open(PROFILE_PATH_FILE, "r") as pf:
        TEMP_PROFILE = pf.read().strip()
    if not TEMP_PROFILE or not os.path.isdir(TEMP_PROFILE):
        log(f"❌ المسار الموجود في profile.txt غير صحيح أو غير موجود:\n{TEMP_PROFILE}")
        return

    if not os.path.isfile(LINKS_PATH):
        log(f"❌ ملف links.txt غير موجود")
        return
    with open(LINKS_PATH, "r", encoding="utf-8") as f:
        GROUP_URLS = [line.strip() for line in f if line.strip()]
    # إزالة التكرار مع الحفاظ على الترتيب
    seen = set()
    GROUP_URLS = [url for url in GROUP_URLS if url.startswith("http") and not (url in seen or seen.add(url))]
    if not GROUP_URLS:
        log("❌ لا توجد لينكات جروبات صالحة")
        return
    random.shuffle(GROUP_URLS)

    text_files = sorted(glob.glob(os.path.join(BASE_FOLDER, "text*.txt")))
    if not text_files:
        log("❌ لا يوجد أي ملف نصي text*.txt في الفولدر!")
        return
    else:
        log(f"✅ تم العثور على {len(text_files)} ملف نصي.")

    if not os.path.isdir(MEDIA_FOLDER):
        log("❌ فولدر الصور والفيديوهات images/ غير موجود")
        return
    media_files = []
    for ext in SUPPORTED_EXTENSIONS:
        media_files.extend(glob.glob(os.path.join(MEDIA_FOLDER, ext)))
    media_files = [os.path.abspath(f) for f in media_files]
    if not media_files:
        log("❌ لا توجد صور أو فيديوهات")
        return
    else:
        log(f"📸 Files to upload ({len(media_files)}):")
        for m in media_files:
            log("   - " + m)

    chrome_options = Options()
    chrome_options.add_argument(f"user-data-dir={TEMP_PROFILE}")
    chrome_options.add_argument('--disable-blink-features=AutomationControlled')
    chrome_options.add_argument('start-maximized')
    chrome_options.add_argument('--disable-notifications')
    chrome_options.add_argument(f'--remote-debugging-port={port}')
    service = Service(ChromeDriverManager().install())
    driver = webdriver.Chrome(service=service, options=chrome_options)
    log("✅ Browser launched. Navigating to Facebook.")
    driver.get("https://www.facebook.com")
    time.sleep(5)
    log("✅ Current URL:" + driver.current_url)

    for group_url in GROUP_URLS:
        if not group_url.startswith("http"):
            log(f"❌ تخطيت لينك غير صالح أو سطر فاضي: {group_url}")
            continue

        text_file = random.choice(text_files)
        with open(text_file, "r", encoding="utf-8") as f:
            POST_MESSAGE = f.read().strip()
        log(f"📤 Posting to {group_url} with message from {os.path.basename(text_file)}")

        media_files_shuffled = random.sample(media_files, len(media_files))

        driver.get(group_url)
        log(f"➡️ Navigated to {group_url}")
        time.sleep(10)

        try:
            # Step 1: Open post dialog
            try:
                time.sleep(5)
                post_box = WebDriverWait(driver, 20).until(
                    EC.element_to_be_clickable((By.XPATH, '//span[contains(text(),"Write something...") or contains(text(),"اكتب شيئًا...")]/ancestor::div[@role="button"]'))
                )
                driver.execute_script("arguments[0].scrollIntoView({block: 'center'});", post_box)
                time.sleep(1)
                try:
                    post_box.click()
                except Exception as e:
                    log(f"❌ Normal click failed: {e}, trying JS click...")
                    driver.execute_script("arguments[0].click();", post_box)
                log("✅ Clicked on 'Create Post' button.")
                time.sleep(4)
            except Exception as e:
                log(f"❌ Could not open post dialog: {e}")
                with open(FAILED_GROUPS_FILE, "a", encoding="utf-8") as ff:  # NEW
                    ff.write(group_url + "\n")  # NEW
                continue

            # Step 2: Upload images (always click photo icon if exists)
            modal = None
            modals = driver.find_elements(By.XPATH, '//div[@aria-modal="true"]')
            modal = modals[0] if modals else driver

            photo_icon_btn = None
            for xp in [
                './/div[@aria-label and (contains(@aria-label, "Photo/video") or contains(@aria-label, "صورة/فيديو"))]',
                './/span[contains(text(), "Photo/video") or contains(text(), "صورة/فيديو")]/ancestor::div[@role="button"]',
                './/i[contains(@class,"image")]/ancestor::div[@role="button"]'
            ]:
                try:
                    btn = modal.find_element(By.XPATH, xp)
                    if btn.is_displayed():
                        photo_icon_btn = btn
                        break
                except:
                    continue

            if photo_icon_btn:
                driver.execute_script("arguments[0].scrollIntoView({block: 'center'});", photo_icon_btn)
                time.sleep(1)
                try:
                    photo_icon_btn.click()
                except:
                    driver.execute_script("arguments[0].click();", photo_icon_btn)
                log("✅ Clicked on photo icon in post dialog")
                time.sleep(2)

            found_input = False
            file_inputs = modal.find_elements(By.XPATH, './/input[@type="file"]')
            for i, file_input in enumerate(file_inputs):
                multiple = file_input.get_attribute("multiple")
                if multiple:
                    try:
                        driver.execute_script("arguments[0].scrollIntoView();", file_input)
                        file_input.send_keys('\n'.join(media_files_shuffled))
                        log(f"✅ Uploaded {len(media_files_shuffled)} files using file input #{i+1}")
                        found_input = True
                        break
                    except Exception as e:
                        log(f"❌ Could not upload files using input #{i+1}: {e}")
            if not found_input:
                log("❌ لم يتم العثور على input مناسب لرفع الملفات.")
                with open(FAILED_GROUPS_FILE, "a", encoding="utf-8") as ff:
                    ff.write(group_url + "\n")
                continue

            # Step 3: انتظر تحديث مربع الكتابة الجديد بعد الصور
            main_box = None
            for _ in range(50):
                textboxes = modal.find_elements(By.XPATH, './/div[@role="textbox" and @contenteditable="true"]')
                for idx, tb in enumerate(textboxes):
                    aria_label = (tb.get_attribute("aria-label") or "").lower()
                    html = tb.get_attribute("outerHTML") or ""
                    if tb.is_displayed() and not any(x in aria_label for x in ["comment", "رد باسم", "comment as", "answer as", "أجب باسم", "أجب بإسم", "answer"]):
                        main_box = tb
                        break
                if main_box:
                    break
                time.sleep(1)
            if not main_box:
                log("❌ No visible post textbox found (not a comment). Skipping this group.")
                with open(FAILED_GROUPS_FILE, "a", encoding="utf-8") as ff:
                    ff.write(group_url + "\n")
                continue

            try:
                driver.execute_script("arguments[0].scrollIntoView();", main_box)
                time.sleep(1)
                main_box.click()
                time.sleep(1)
                success = send_text_to_box(driver, main_box, POST_MESSAGE)
                if success:
                    log("✅ Message typed (emojis supported).")
                else:
                    log("❌ Could not type message even with clipboard.")
            except Exception as e:
                log(f"❌ Could not type message in post box: {e}")
                with open(FAILED_GROUPS_FILE, "a", encoding="utf-8") as ff:
                    ff.write(group_url + "\n")
                continue

            try:
                post_button = WebDriverWait(driver, 15).until(
                    EC.element_to_be_clickable((By.XPATH, '//div[@aria-label="Post"]'))
                )
                driver.execute_script("arguments[0].scrollIntoView();", post_button)
                time.sleep(1)
                post_button.click()
                log("✅ Post submitted")
            except Exception as e:
                log(f"❌ Could not click 'Post': {e}")
                with open(FAILED_GROUPS_FILE, "a", encoding="utf-8") as ff:
                    ff.write(group_url + "\n")

            time.sleep(5)

        except Exception as e:
            log(f"❌ Failed to post in {group_url}: {e}")
            with open(FAILED_GROUPS_FILE, "a", encoding="utf-8") as ff:
                ff.write(group_url + "\n")

        wait_time = random.randint(180, 420)
        log(f"⏳ Waiting {wait_time} seconds before next post...")
        time.sleep(wait_time)

    time.sleep(5)
    driver.quit()
    log("✅ Script finished and browser closed.")

# ====== GUI ======
def gui_main():
    root = tk.Tk()
    root.title("Facebook Group Poster")
    root.geometry("850x600")

    folders = []

    folder_frame = tk.Frame(root)
    folder_frame.pack(pady=8)
    tk.Label(folder_frame, text="الحسابات:").pack(side=tk.LEFT)
    folder_listbox = tk.Listbox(folder_frame, width=60, height=3)
    folder_listbox.pack(side=tk.LEFT)
    def add_folder():
        folder = filedialog.askdirectory()
        if folder and folder not in folders:
            folders.append(folder)
            folder_listbox.insert(tk.END, folder)
    tk.Button(folder_frame, text="إضافة حساب", command=add_folder).pack(side=tk.LEFT, padx=6)
    def remove_folder():
        sel = folder_listbox.curselection()
        if sel:
            idx = sel[0]
            folders.pop(idx)
            folder_listbox.delete(idx)
    tk.Button(folder_frame, text="حذف", command=remove_folder, fg="red").pack(side=tk.LEFT)

    # زر بدء النشر & LOGS
    start_btn = tk.Button(root, text="ابدأ النشر", fg="white", bg="green")
    start_btn.pack(pady=10)

    log_box = scrolledtext.ScrolledText(root, width=100, height=25, state="disabled", font=("Courier", 10))
    log_box.pack(padx=10, pady=10)

    def start_poster_processes():
        start_btn.config(state="disabled")
        log_box.config(state="normal")
        log_box.delete(1.0, tk.END)
        log_box.config(state="disabled")
        manager = multiprocessing.Manager()
        log_queue = manager.Queue()
        jobs = []
        for idx, folder in enumerate(folders):
            port = 9222 + idx
            p = multiprocessing.Process(target=run_poster, args=(folder, port, log_queue))
            p.start()
            jobs.append(p)
            time.sleep(random.randint(2, 5))
        # عرض اللوجات باستمرار
        def poll_logs():
            while not log_queue.empty():
                msg = log_queue.get()
                log_box.config(state="normal")
                log_box.insert(tk.END, msg + "\n")
                log_box.see(tk.END)
                log_box.config(state="disabled")
            if any(p.is_alive() for p in jobs):
                root.after(1200, poll_logs)
            else:
                start_btn.config(state="normal")
        poll_logs()
    start_btn.config(command=start_poster_processes)

    root.mainloop()

if __name__ == "__main__":
    gui_main()
