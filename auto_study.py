import time
import re

from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC

# ================== 自己改的部分 ==================
EXAM_URL = "https://sysaq.ustc.edu.cn/lab-study-front/examTask/10"
BUFFER_SECONDS = 8       # 比要求多挂几秒
SCROLL_INTERVAL = 30     # 每多少秒滚动一下防掉线
# =================================================

options = webdriver.ChromeOptions()
options.add_argument("--start-maximized")
# 想后台跑可以打开下一行
# options.add_argument("--headless=new")

driver = webdriver.Chrome(options=options)
wait = WebDriverWait(driver, 20)


def parse_time_to_seconds(text: str) -> int:
    """
    从给定文本中解析时间：优先匹配 hh:mm:ss，其次 mm:ss
    返回秒数，不匹配则返回 0
    """
    m = re.search(r"(\d{2}:\d{2}:\d{2})", text)
    if m:
        h, mi, s = map(int, m.group(1).split(":"))
        return h * 3600 + mi * 60 + s

    m = re.search(r"(\d{2}:\d{2})", text)
    if m:
        mi, s = map(int, m.group(1).split(":"))
        return mi * 60 + s

    return 0


def keep_active(total_seconds: int):
    """
    在当前页面停留 total_seconds 秒，并定期滚动一下
    """
    start = time.time()
    last_scroll = start

    while True:
        now = time.time()
        elapsed = now - start
        if elapsed >= total_seconds:
            break

        if now - last_scroll >= SCROLL_INTERVAL:
            try:
                driver.execute_script("window.scrollBy(0, 400);")
                time.sleep(1)
                driver.execute_script("window.scrollBy(0, -400);")
            except Exception:
                pass
            last_scroll = now

        time.sleep(1)


def wait_for_course_table():
    """
    等课程列表的 table 出现
    """
    wait.until(EC.presence_of_element_located((By.XPATH, "//table")))
    time.sleep(1)


def get_required_seconds_from_detail() -> int:
    """
    在学习详情页中，从“要求学习”区域提取时间（秒）
    只抓『要求学习』后面最近的时间，不去管上面的必学时长 00:31:00
    """
    # 找到“要求学习”四个字
    label = wait.until(
        EC.presence_of_element_located(
            (By.XPATH, "//*[contains(text(),'要求学习')]")
        )
    )

    # 找一个稍大的包含块（祖先），但只用文本里“要求学习”后面的时间
    try:
        block = label.find_element(By.XPATH, "ancestor::*[contains(., '要求学习')][1]")
        text = block.text.replace("\n", " ")
    except Exception:
        text = label.text.replace("\n", " ")

    # 重点：只匹配“要求学习”后面的时间（支持 mm:ss 或 hh:mm:ss）
    # 示例："... 已学习 00:21 要求学习 05:00"
    m = re.search(r"要求学习[^\d]*(\d{2}:\d{2}(?::\d{2})?)", text)
    if m:
        t = m.group(1)
        parts = list(map(int, t.split(":")))
        if len(parts) == 3:
            h, mi, s = parts
            return h * 3600 + mi * 60 + s
        elif len(parts) == 2:
            mi, s = parts
            return mi * 60 + s

    # 兜底：还是没找到，就用整个页面再扫一遍（一般用不到）
    full_text = driver.find_element(By.TAG_NAME, "body").text.replace("\n", " ")
    m2 = re.search(r"要求学习[^\d]*(\d{2}:\d{2}(?::\d{2})?)", full_text)
    if m2:
        t = m2.group(1)
        parts = list(map(int, t.split(":")))
        if len(parts) == 3:
            h, mi, s = parts
            return h * 3600 + mi * 60 + s
        elif len(parts) == 2:
            mi, s = parts
            return mi * 60 + s

    return 0


def auto_study_current_page():
    """
    自动学习当前页面上的所有“去学习”课程
    """
    wait_for_course_table()

    rows = driver.find_elements(By.XPATH, "//table//tbody/tr")
    row_count = len(rows)
    print(f"本页共发现 {row_count} 行（包含表头/空行）")

    for i in range(row_count):
        rows = driver.find_elements(By.XPATH, "//table//tbody/tr")
        if i >= len(rows):
            break
        row = rows[i]
        row_text = row.text.strip()

        # 在这一行中找到任何包含“去学习”文字的元素
        try:
            learn_btn = row.find_element(By.XPATH, ".//*[contains(text(),'去学习')]")
        except Exception:
            print(f"[跳过] 第 {i+1} 行：找不到『去学习』元素。内容为：{row_text}")
            continue

        print(f"\n===== 第 {i+1} 门课程开始学习 =====")
        print(f"行内容：{row_text}")

        # 点击“去学习”
        learn_btn.click()

        # 等学习详情页加载出来（中间那篇文章 + 右侧进度）
        try:
            wait.until(
                EC.presence_of_element_located(
                    (By.XPATH, "//*[contains(text(),'已学习') or contains(text(),'学习时长')]")
                )
            )
        except Exception:
            print("学习详情页等待超时，再等几秒。")
            time.sleep(5)

        # 从右侧“要求学习”区域获取总时间
        required = get_required_seconds_from_detail()
        if required <= 0:
            print("⚠ 没能解析到要求学习时间，默认挂 60 秒。")
            need_seconds = 60
        else:
            need_seconds = required + BUFFER_SECONDS

        print(f"解析到要求学习时间：{required} 秒，实际挂机：{need_seconds} 秒。")

        # 挂机
        keep_active(need_seconds)

        print("本门课程学习时间已到，返回课程列表……")

        # 不再点“返回”也不后退，直接重新打开任务页面
        driver.get(EXAM_URL)
        wait_for_course_table()

        print("===== 本门课程结束，返回列表 =====\n")



def main():
    driver.get(EXAM_URL)
    print("浏览器已打开，请你手动登录 / 选到对应任务页面。")
    input("登录完并看到课程列表后，按回车继续...")

    auto_study_current_page()

    print("当前页所有课程处理完毕，如有分页可以翻页再跑一次。")
    input("按回车关闭浏览器...")
    driver.quit()


if __name__ == "__main__":
    main()
