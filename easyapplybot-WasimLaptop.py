from ast import While
from operator import truediv
import time
import random
import os
import csv
import platform
import logging
import urllib.parse
from selenium import webdriver
from selenium.webdriver.chrome.options import Options
from selenium.common.exceptions import TimeoutException
from selenium.webdriver.common.keys import Keys
from selenium.common.exceptions import NoSuchElementException
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.common.by import By
from selenium.webdriver.support import expected_conditions as EC
from bs4 import BeautifulSoup
import pandas as pd
import pyautogui

from urllib.request import urlopen
from webdriver_manager.chrome import ChromeDriverManager
import re
import yaml
from datetime import datetime, timedelta
from CompanyRating import GetCompanyRating
log = logging.getLogger(__name__)
driver = webdriver.Chrome(ChromeDriverManager().install())


def setupLogger():
    dt = datetime.strftime(datetime.now(), "%m_%d_%y %H_%M_%S ")

    if not os.path.isdir('./logs'):
        os.mkdir('./logs')

    # TODO need to check if there is a log dir available or not
    logging.basicConfig(filename=('./logs/' + str(dt) + 'applyJobs.log'), filemode='w',
                        format='%(asctime)s::%(name)s::%(levelname)s::%(message)s', datefmt='./logs/%d-%b-%y %H:%M:%S')
    log.setLevel(logging.DEBUG)
    c_handler = logging.StreamHandler()
    c_handler.setLevel(logging.DEBUG)
    c_format = logging.Formatter(
        '%(asctime)s - %(levelname)s - %(message)s', '%H:%M:%S')
    c_handler.setFormatter(c_format)
    log.addHandler(c_handler)


class EasyApplyBot:
    setupLogger()
    # MAX_SEARCH_TIME is 10 hours by default, feel free to modify it
    MAX_SEARCH_TIME = 10 * 60 * 60

    def __init__(self,
                 username,
                 password,
                 uploads={},
                 filename='output.csv',
                 blacklist=[],
                 blackListTitles=[],
                 companysize=[],
                 remote=False,
                 goodfitonly=False
                 ):
        with open("config.yaml", 'r') as stream:
            try:
                parameters = yaml.safe_load(stream)
            except yaml.YAMLError as exc:
                raise exc
        log.info("Welcome to Easy Apply Bot")
        dirpath = os.getcwd()
        log.info("current directory is : " + dirpath)

        self.uploads = uploads
        past_ids = self.get_appliedIDs(filename)
        self.appliedJobIDs = past_ids if past_ids != None else []
        self.filename = filename
        self.options = self.browser_options()
        self.browser = driver
        # Remove navigator.webdriver Flag using JavaScript
        self.browser.execute_script(
            "Object.defineProperty(navigator, 'webdriver', {get: () => undefined})")

        self.wait = WebDriverWait(self.browser, 30)
        self.blacklist = blacklist
        self.blackListTitles = blackListTitles
        self.companysize = companysize
        self.remote = remote
        self.goodfitonly = goodfitonly
        self.start_linkedin(username, password)

    def get_appliedIDs(self, filename):
        try:
            df = pd.read_csv(filename,
                             header=None,
                             names=['timestamp', 'jobID', 'job',
                                    'company', 'attempted', 'result'],
                             lineterminator='\n',
                             encoding='utf-8')

            df['timestamp'] = pd.to_datetime(
                df['timestamp'], format="%Y-%m-%d %H:%M:%S")
            df = df[df['timestamp'] > (datetime.now() - timedelta(days=2))]
            jobIDs = list(df.jobID)
            log.info(f"{len(jobIDs)} jobIDs found")
            return jobIDs
        except Exception as e:
            log.info(
                str(e) + "   jobIDs could not be loaded from CSV {}".format(filename))
            return None

    def browser_options(self):
        options = Options()
        options.add_argument("--start-maximized")
        options.add_argument("--ignore-certificate-errors")
        options.add_argument('--no-sandbox')
        options.add_argument("--disable-extensions")

        # Disable webdriver flags or you will be easily detectable
        options.add_argument("--disable-blink-features")
        options.add_argument("--disable-blink-features=AutomationControlled")
        options.add_argument("window-size=1280,800")
        # options.add_argument("user-agent=Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/74.0.3729.169 Safari/537.36")
        return options

    def start_linkedin(self, username, password):
        log.info("Logging in.....Please wait :)  ")
        self.browser.get(
            "https://www.linkedin.com/login?trk=guest_homepage-basic_nav-header-signin")
        try:
            user_field = self.browser.find_element(By.ID, "username")
            pw_field = self.browser.find_element(By.ID, "password")
            login_button = self.browser.find_element(By.CSS_SELECTOR,
                                                     ".btn__primary--large")
            user_field.send_keys(username)
            user_field.send_keys(Keys.TAB)
            time.sleep(2)
            pw_field.send_keys(password)
            time.sleep(2)
            login_button.click()
            time.sleep(3)
        except TimeoutException:
            log.info(
                "TimeoutException! Username/password field or login button not found")

    def fill_data(self):
        # self.browser.set_window_size(0, 0)
        # self.browser.set_window_position(2000, 2000)
        self.browser.maximize_window()

    def start_apply(self, positions, locations):
        start = time.time()
        self.fill_data()

        combos = []
        while len(combos) < len(positions) * len(locations):
            position = positions[random.randint(0, len(positions) - 1)]
            location = locations[random.randint(0, len(locations) - 1)]
            combo = (position, location)
            if combo not in combos:
                combos.append(combo)
                log.info(f"Applying to {position}: {location}")
                location = "&location=" + location
                self.applications_loop(position, location)
            if len(combos) > 500:
                break

    # self.finish_apply() --> this does seem to cause more harm than good, since it closes the browser which we usually don't want, other conditions will stop the loop and just break out

    def applications_loop(self, position, location):

        count_application = 0
        count_job = 0
        jobs_per_page = 0
        start_time = time.time()

        log.info("Looking for jobs.. Please wait..")

        self.browser.set_window_position(0, 0)
        self.browser.maximize_window()
        self.browser, _ = self.next_jobs_page(
            position, location, jobs_per_page)
        log.info("Looking for jobs.. Please wait..")

        while time.time() - start_time < self.MAX_SEARCH_TIME:
            try:
                log.info(
                    f"{(self.MAX_SEARCH_TIME - (time.time() - start_time)) // 60} minutes left in this search")

                # sleep to make sure everything loads, add random to make us look human.
                randoTime = random.uniform(3.5, 4.9)
                log.debug(f"Sleeping for {round(randoTime, 1)}")
                time.sleep(randoTime)
                self.load_page(sleep=1)

                # LinkedIn displays the search results in a scrollable <div> on the left side, we have to scroll to its bottom

                scrollresults = self.browser.find_element(By.CLASS_NAME,
                                                          "jobs-search-results-list"
                                                          )
                # Selenium only detects visible elements; if we scroll to the bottom too fast, only 8-9 results will be loaded into IDs list
                for i in range(300, 3000, 100):
                    self.browser.execute_script(
                        "arguments[0].scrollTo(0, {})".format(i), scrollresults)

                time.sleep(1)

                # get job links
                links = self.browser.find_elements(By.XPATH,
                                                   '//div[@data-job-id]'
                                                   )

                if len(links) == 0:
                    break

                # get job ID of each job link
                IDs = []
                for link in links:
                    children = link.find_elements(By.XPATH,
                                                  './/a[@data-control-id]'
                                                  )
                    for child in children:
                        if child.text not in self.blacklist:
                            temp = link.get_attribute("data-job-id")
                            jobID = temp.split(":")[-1]
                            IDs.append(int(jobID))
                IDs = set(IDs)

                # remove already applied jobs
                before = len(IDs)
                jobIDs = [x for x in IDs if x not in self.appliedJobIDs]
                after = len(jobIDs)

                # it assumed that 25 jobs are listed in the results window
                if len(jobIDs) == 0 and len(IDs) >= 23:
                    jobs_per_page = jobs_per_page + 25
                    count_job = 0
                    self.avoid_lock()
                    self.browser, jobs_per_page = self.next_jobs_page(position,
                                                                      location,
                                                                      jobs_per_page)
                log.info(self.companysize)
                # loop over IDs to apply
                for i, jobID in enumerate(jobIDs):
                    try:
                        count_job += 1
                        self.get_job_page(jobID)
                        textcompanysize = self.get_company_employee_size()
                        log.info("Company size "+str(textcompanysize))
                        res = False
                        goodfittext = False
                        for l in self.companysize:
                            if l in textcompanysize:
                                res = True
                        if "good fit" in textcompanysize or "You have a preferred" in textcompanysize:
                            log.info("Good Fit available")
                            goodfittext = True
                        else:
                            log.info("Not a Good Fit")
                        companyname = self.get_company_name()
                        log.info("Company Name"+str(companyname))
                        companyrating = GetCompanyRating(companyname)
                        log.info("Company Rating"+str(companyrating))
                        # if not res:
                        #     log.info('skipping as company size not matched')
                        #     continue
                        # get easy apply button
                        button = self.get_easy_apply_button()
                        # word filter to skip positions not wanted
                        log.info("Match result "+str(res))
                        if self.remote is True:
                            res = True
                        if self.goodfitonly is True and goodfittext is False:
                            res = False

                        if button is not False and res is True:
                            if any(word in self.browser.title for word in blackListTitles):
                                log.info(
                                    'skipping this application, a blacklisted keyword was found in the job position')
                                string_easy = "* Contains blacklisted keyword"
                                result = False
                            else:
                                string_easy = "* has Easy Apply Button"
                                log.info("Clicking the EASY apply button")
                                button.click()
                                time.sleep(3)
                                result = self.send_resume()
                                count_application += 1
                        else:
                            log.info("The button does not exist.")
                            string_easy = "* Doesn't have Easy Apply Button"
                            result = False

                        position_number = str(count_job + jobs_per_page)
                        log.info(
                            f"\nPosition {position_number}:\n {self.browser.title} \n {string_easy} \n")

                        self.write_to_file(
                            button, jobID, self.browser.title, result)
                        self.avoid_lock()
                        # sleep every 20 applications
                        if count_application != 0 and count_application % 20 == 0:
                            sleepTime = random.randint(500, 900)
                            waitedtime = 0
                            log.info(f"""********count_application: {count_application}************\n\n
                                        Time for a nap - see you in:{int(sleepTime / 60)} min
                                    ****************************************\n\n""")
                            # time.sleep(sleepTime)
                            while waitedtime < sleepTime:
                                timeinsec = random.randint(1, 60)
                                waitedtime = waitedtime+timeinsec
                                time.sleep(time)
                                self.avoid_lock()

                        # go to new page if all jobs are done
                        if count_job == len(jobIDs):
                            jobs_per_page = jobs_per_page + 25
                            count_job = 0
                            log.info("""****************************************\n\n
                            Going to next jobs page, YEAAAHHH!!
                            ****************************************\n\n""")
                            self.avoid_lock()
                            self.browser, jobs_per_page = self.next_jobs_page(position,
                                                                              location,
                                                                              jobs_per_page)
                    except Exception as ex:
                        print(ex)
            except Exception as e:
                print(e)
                self.browser, jobs_per_page = self.next_jobs_page(position,
                                                                  location,
                                                                  jobs_per_page)

    def write_to_file(self, button, jobID, browserTitle, result):
        def re_extract(text, pattern):
            target = re.search(pattern, text)
            if target:
                target = target.group(1)
            return target

        timestamp = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
        attempted = False if button == False else True
        job = re_extract(browserTitle.split(' | ')[0], r"\(?\d?\)?\s?(\w.*)")
        company = re_extract(browserTitle.split(' | ')[1], r"(\w.*)")

        toWrite = [timestamp, jobID, job, company, attempted, result]
        with open(self.filename, 'a', encoding="utf-8") as f:
            writer = csv.writer(f)
            writer.writerow(toWrite)

    def get_job_page(self, jobID):

        job = 'https://www.linkedin.com/jobs/view/' + str(jobID)
        self.browser.get(job)
        self.job_page = self.load_page(sleep=0.5)
        return self.job_page

    def get_company_employee_size(self):
        try:
            companytext = ""
            cards = self.browser.find_elements(By.CLASS_NAME,
                                               'jobs-unified-top-card__job-insight')
            for x in cards:
                companytext = companytext + ' ' + x.text
            return companytext
        except:
            return ''

    def get_company_name(self):
        try:
            companyname = ""
            companyname = self.browser.find_element(By.CLASS_NAME,
                                                    'ember-view t-black t-normal').text
            return companyname
        except:
            return ''

    def get_easy_apply_button(self):
        try:
            button = self.browser.find_elements(By.XPATH,
                                                '//div[contains(@class, "jobs-s-apply") and contains(@class, "jobs-s-apply--fadein") and contains(@class, "inline-flex") and contains(@class, "mr2")]/div/button/span[text()="Easy Apply"]'
                                                )

            EasyApplyButton = button[0]
        except:
            EasyApplyButton = False

        return EasyApplyButton

    def send_resume(self):
        def is_present(button_locator):
            return len(self.browser.find_elements(button_locator[0],
                                                  button_locator[1])) > 0

        try:
            time.sleep(random.uniform(1.5, 2.5))
            mobilenumber_locator=(By.XPATH,
                                                '(//input[contains(@class, "artdeco-text-input--input") and contains(@id, "phoneNumber-nationalNumber") and @type="text"])[1]'
                                                )
            next_locater = (By.CSS_SELECTOR,
                            "button[aria-label='Continue to next step']")
            resume_choose = (By.CSS_SELECTOR,
                             "button[aria-label='Choose Resume']")
            review_locater = (By.CSS_SELECTOR,
                              "button[aria-label='Review your application']")
            submit_locater = (By.CSS_SELECTOR,
                              "button[aria-label='Submit application']")
            submit_application_locator = (By.CSS_SELECTOR,
                                          "button[aria-label='Submit application']")
            error_locator = (By.XPATH,
                             '//div[contains(@id, "-error")]')
            upload_locator = (By.CSS_SELECTOR, "input[name='file']")
            follow_locator = (
                By.CSS_SELECTOR, "label[for='follow-company-checkbox']")

            submitted = False
            while True:
                if is_present(mobilenumber_locator):
                    # Set the value of the input field
                        
                                    # Choose Resume
                        inputext = self.browser.find_elements(By.XPATH,
                                                '(//input[contains(@class, "artdeco-text-input--input") and contains(@id, "phoneNumber-nationalNumber") and @type="text"])[1]'
                                                )
                        inputext[0].clear()
                        inputext[0].send_keys('9718742936')

                if is_present(resume_choose):
                    choosebutton = self.browser.find_element(By.CSS_SELECTOR,
                                                             "button[aria-label='Choose Resume']")
                    choosebutton.click()
                # Upload Cover Letter if possible
                # if is_present(upload_locator):
                #     try:
                #         input_buttons = self.browser.find_elements(upload_locator[0],
                #                                                    upload_locator[1])
                #         for input_button in input_buttons:
                #             parent = input_button.find_element(By.XPATH, "..")
                #             sibling = parent.find_element(
                #                 By.XPATH, "preceding-sibling::*")
                #             grandparent = sibling.find_element(By.XPATH, "..")
                #             for key in self.uploads.keys():
                #                 sibling_text = sibling.text
                #                 gparent_text = grandparent.text
                #                 if key.lower() in sibling_text.lower() or key in gparent_text.lower():
                #                     input_button.send_keys(self.uploads[key])
                #     except Exception as e:
                #         log.info(e)

                #     # input_button[0].send_keys(self.cover_letter_loctn)
                #     time.sleep(random.uniform(4.5, 6.5))

                # Click Next or submitt button if possible
                button = None
                buttons = [next_locater, review_locater, follow_locator,
                           submit_locater, submit_application_locator]
                for i, button_locator in enumerate(buttons):
                    if is_present(button_locator):
                        button = self.wait.until(
                            EC.element_to_be_clickable(button_locator))
                    self.additional_questions()
                    
                    if is_present(error_locator):
                        for element in self.browser.find_elements(error_locator[0],
                                                                  error_locator[1]):
                            text = element.text
                            if "enter a" in text:
                                button = None
                                break
                    if button:
                        button.click()
                        time.sleep(random.uniform(1.5, 2.5))
                        if i in (3, 4):
                            submitted = True
                        if i != 2:
                            break
                if button == None:
                    log.info("Could not complete submission")
                    break
                elif submitted:
                    log.info("Application Submitted")
                    break

            time.sleep(random.uniform(1.5, 2.5))

        except Exception as e:
            log.info(e)
            log.info("cannot apply to this job")
            raise (e)

        return submitted

    def additional_questions(self):
        # pdb.set_trace()
        frm_el = self.browser.find_elements(By.CLASS_NAME,
                                            'jobs-easy-apply-form-section__grouping')
        if len(frm_el) > 0:
            for el in frm_el:
                # Txt Field Check
                try:
                    question = el.find_element(By.CLASS_NAME,
                                               'artdeco-text-input--label')
                    question_text = el.find_element(By.CLASS_NAME,
                                                    'artdeco-text-input--input').text.lower()

                    txt_field_visible = False
                    txt_field = question_text
                    try:
                        txt_field = el.find_element(By.CLASS_NAME,
                                                    'artdeco-text-input--input')

                        txt_field_visible = True
                    except:
                        try:
                            txt_field = el.find_element(By.CLASS_NAME,
                                                        'fb-textarea')

                            txt_field_visible = True
                        except:
                            pass

                    # if txt_field_visible != True:
                    #     txt_field = question.find_element_by_class_name(
                    #         'multi-line-text__input')

                    # text_field_type = txt_field.get_attribute('name').lower()
                    # if 'numeric' in text_field_type:
                    #     text_field_type = 'numeric'
                    # elif 'text' in text_field_type:
                    #     text_field_type = 'text'

                    to_enter = '1'
                    txt_field_text = txt_field.get_attribute('value')
                    if txt_field_text == '':
                        txt_field.send_keys(to_enter)
                except Exception as e:
                    break
                # # Dropdown check
                # try:
                #     question = el.find_element(By.CLASS_NAME,
                #                                'fb-dash-form-element__label')
                #     question_text = el.find_element(By.CLASS_NAME,
                #                                     'fb-dash-form-element__label').text.lower()

                #     dropdown_field = el.find_element(By.Name,
                #                                      'select')

                #     select = Select(dropdown_field)

                #     options = [options.text for options in select.options]

                #     if 'english' in question_text:
                #         proficiency = "Yes"

                #         for language in self.languages:
                #             if language.lower() in question_text:
                #                 proficiency = self.languages[language]
                #                 break

                #         self.select_dropdown(dropdown_field, proficiency)
                #     elif 'country code' in question_text:
                #         self.select_dropdown(
                #             dropdown_field, self.personal_info['Phone Country Code'])
                #     elif 'north korea' in question_text:

                #         choice = ""

                #         for option in options:
                #             if 'no' in option.lower():
                #                 choice = option

                #         if choice == "":
                #             choice = options[len(options) - 1]

                #         self.select_dropdown(dropdown_field, choice)
                #     elif 'sponsor' in question_text:
                #         answer = self.get_answer('requireVisa')

                #         choice = ""

                #         for option in options:
                #             if answer == 'yes':
                #                 choice = option
                #             else:
                #                 if 'no' in option.lower():
                #                     choice = option

                #         if choice == "":
                #             choice = options[len(options) - 1]

                #         self.select_dropdown(dropdown_field, choice)
                #     elif 'authorized' in question_text or 'authorised' in question_text:
                #         answer = self.get_answer('legallyAuthorized')

                #         choice = ""

                #         for option in options:
                #             if answer == 'yes':
                #                 # find some common words
                #                 choice = option
                #             else:
                #                 if 'no' in option.lower():
                #                     choice = option

                #         if choice == "":
                #             choice = options[len(options) - 1]

                #         self.select_dropdown(dropdown_field, choice)
                #     elif 'citizenship' in question_text:
                #         answer = self.get_answer('legallyAuthorized')

                #         choice = ""

                #         for option in options:
                #             if answer == 'yes':
                #                 if 'no' in option.lower():
                #                     choice = option

                #         if choice == "":
                #             choice = options[len(options) - 1]

                #         self.select_dropdown(dropdown_field, choice)
                #     elif 'gender' in question_text or 'veteran' in question_text or 'race' in question_text or 'disability' in question_text or 'latino' in question_text:

                #         choice = ""

                #         for option in options:
                #             if 'prefer' in option.lower() or 'decline' in option.lower() or 'don\'t' in option.lower() or 'specified' in option.lower() or 'none' in option.lower():
                #                 choice = option

                #         if choice == "":
                #             choice = options[len(options) - 1]

                #         self.select_dropdown(dropdown_field, choice)
                #     else:
                #         choice = ""

                #         for option in options:
                #             if 'yes' in option.lower():
                #                 choice = option

                #         if choice == "":
                #             choice = options[len(options) - 1]

                #         self.select_dropdown(dropdown_field, choice)
                #     continue
                # except Exception as e:
                #     print(e)
                #     pass

    def load_page(self, sleep=1):
        scroll_page = 0
        while scroll_page < 4000:
            self.browser.execute_script(
                "window.scrollTo(0," + str(scroll_page) + " );")
            scroll_page += 200
            time.sleep(sleep)

        if sleep != 1:
            self.browser.execute_script("window.scrollTo(0,0);")
            time.sleep(sleep * 3)

        page = BeautifulSoup(self.browser.page_source, "lxml")
        return page

    def avoid_lock(self):
        x, _ = pyautogui.position()
        pyautogui.moveTo(x + 200, pyautogui.position().y, duration=1.0)
        pyautogui.moveTo(x, pyautogui.position().y, duration=0.5)
        pyautogui.keyDown('ctrl')
        pyautogui.press('esc')
        pyautogui.keyUp('ctrl')
        time.sleep(0.5)
        pyautogui.press('esc')

    def next_jobs_page(self, position, location, jobs_per_page):
        JObURL = "https://www.linkedin.com/jobs/search/?f_AL=true&keywords=" + str(urllib.parse.quote(position)) + \
            location + "&start=" + str(jobs_per_page)+"&refresh=true&sortBy=DD"
        if self.remote == True:
            JObURL = JObURL+"&f_WT=2"
        self.browser.get(JObURL)
        self.avoid_lock()
        log.info("Lock avoided.")
        self.load_page()
        return (self.browser, jobs_per_page)

    def finish_apply(self):
        self.browser.close()


if __name__ == '__main__':

    with open("config.yaml", 'r') as stream:
        try:
            parameters = yaml.safe_load(stream)
        except yaml.YAMLError as exc:
            raise exc

    assert len(parameters['positions']) > 0
    assert len(parameters['locations']) > 0
    assert parameters['username'] is not None
    assert parameters['password'] is not None

    if 'uploads' in parameters.keys() and type(parameters['uploads']) == list:
        raise Exception("uploads read from the config file appear to be in list format" +
                        " while should be dict. Try removing '-' from line containing" +
                        " filename & path")

    log.info({k: parameters[k] for k in parameters.keys()
             if k not in ['username', 'password']})

    output_filename = [f for f in parameters.get(
        'output_filename', ['output.csv']) if f != None]
    output_filename = output_filename[0] if len(
        output_filename) > 0 else 'output.csv'
    blacklist = parameters.get('blacklist', [])
    blackListTitles = parameters.get('blackListTitles', [])
    companysize = parameters.get('companysize', [])
    uploads = {} if parameters.get(
        'uploads', {}) == None else parameters.get('uploads', {})
    for key in uploads.keys():
        assert uploads[key] != None

    bot = EasyApplyBot(parameters['username'],
                       parameters['password'],
                       uploads=uploads,
                       filename=output_filename,
                       blacklist=blacklist,
                       blackListTitles=blackListTitles,
                       companysize=companysize,
                       remote=parameters['remote'],
                       goodfitonly=parameters['goodfitonly']
                       )

    locations = [l for l in parameters['locations'] if l != None]
    positions = [p for p in parameters['positions'] if p != None]
    bot.start_apply(positions, locations)
