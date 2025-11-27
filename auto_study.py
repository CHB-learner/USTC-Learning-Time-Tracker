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


def parse_learned_seconds_from_row(row_text: str) -> int:
    """
    从列表行文本中解析 '已学习：00:04:45 / 00:05:00' 里的已学习时间（秒）
    """
    # 支持：已学习: 00:04:45 / 00:05:00 或 已学习00:04:45/00:05:00
    m = re.search(r"已学习[：:\s]*([\d]{2}:[\d]{2}:[\d]{2})", row_text)
    if not m:
        return 0
    t = m.group(1)
    h, mi, s = map(int, t.split(":"))
    return h * 3600 + mi * 60 + s


def parse_required_seconds_from_row(row_text: str) -> int:
    """
    从行文本里解析 '/ 00:05:00' 或 '/ 00:04:00' 的总要求时间（秒）
    """
    m = re.search(r"/\s*([\d]{2}:[\d]{2}:[\d]{2}|[\d]{2}:[\d]{2})", row_text)
    if not m:
        return 0
    t = m.group(1)
    parts = list(map(int, t.split(":")))
    if len(parts) == 3:
        h, mi, s = parts
        return h * 3600 + mi * 60 + s
    else:
        mi, s = parts
        return mi * 60 + s


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

        # 从列表行里解析已学习时间 / 总要求时间（秒）
        learned = parse_learned_seconds_from_row(row_text)
        required = parse_required_seconds_from_row(row_text)
        print(f"已学习时间：{learned} 秒，行内总要求时间：{required} 秒")

        if required <= 0:
            # 行里都没写要求时间，那就用 300 秒兜底
            base_required = 300
            remaining = max(base_required - learned, 60)
            print("⚠ 行内未解析到总要求时间，按 300 秒兜底。")
        else:
            remaining = max(required - learned, 0)

        # 如果已经够时长了，直接跳过，不点“去学习”
        if remaining <= 0:
            print("✅ 已学习时间已达到或超过要求，跳过挂机。")
            # 直接处理下一门课（此时仍在列表页）
            print("===== 本门课程结束（已学够），留在列表页 =====\n")
            continue

        need_seconds = remaining + BUFFER_SECONDS
        print(f"剩余需学习时间：{remaining} 秒，实际挂机：{need_seconds} 秒。")

        # 进入学习详情页
        learn_btn.click()

        # 等学习详情页加载出来（中间文章 + 右侧进度）
        try:
            wait.until(
                EC.presence_of_element_located(
                    (By.XPATH, "//*[contains(text(),'已学习') or contains(text(),'学习时长') or contains(text(),'要求学习')]")
                )
            )
        except Exception:
            print("学习详情页等待超时，再等几秒。")
            time.sleep(5)

        # 挂机
        keep_active(need_seconds)

        # 挂机结束，回到课程列表页
        print("本门课程学习时间已到，返回课程列表……")
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
