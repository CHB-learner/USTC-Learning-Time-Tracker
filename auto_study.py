import time
import re

from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC

# ================== 自己改的部分 ==================
# 直接填“学习详情”页面，比如你现在的 39 那个
DETAIL_URL = "https://sysaq.ustc.edu.cn/lab-study-front/examTask/10/4/1/39"

BUFFER_SECONDS = 8       # 在要求时间基础上多挂几秒
SCROLL_INTERVAL = 30     # 每多少秒滚动一下防掉线
# ==================================================

options = webdriver.ChromeOptions()
options.add_argument("--start-maximized")
# 想后台静默跑可以开这一行（有时候 headless 容易被识别，就看你自己）
# options.add_argument("--headless=new")

driver = webdriver.Chrome(options=options)
wait = WebDriverWait(driver, 20)


def parse_mmss_to_seconds(text: str) -> int:
    """
    从文本中解析 mm:ss（也兼容 m:ss），返回秒数；失败返回 0
    例如 "00:06" -> 6, "01:00" -> 60
    """
    m = re.search(r"(\d{1,2}):(\d{2})", text)
    if not m:
        return 0
    mm = int(m.group(1))
    ss = int(m.group(2))
    return mm * 60 + ss


def keep_active(total_seconds: int):
    """
    在当前页面停留 total_seconds 秒，并定期滚动一下页面防掉线
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
                # 主页面上下滚一下
                driver.execute_script("window.scrollBy(0, 400);")
                time.sleep(1)
                driver.execute_script("window.scrollBy(0, -400);")
            except Exception:
                pass
            last_scroll = now

        time.sleep(1)


def wait_for_left_list():
    """
    等左侧课程列表的 li.panelItem 出现
    """
    wait.until(
        EC.presence_of_all_elements_located(
            (By.CSS_SELECTOR, "div.ivu-scroll-content ul li.panelItem")
        )
    )
    time.sleep(1)


def get_learned_and_required_from_side():
    """
    从右侧小面板获取『已学习 xx:xx』和『要求学习 xx:xx』，返回 (learned_sec, required_sec)
    """
    root = wait.until(
        EC.presence_of_element_located(
            (By.XPATH, "//*[contains(text(),'已学')]/ancestor::*[contains(.,'要求学习')][1]")
        )
    )
    text = root.text.replace("\n", " ")

    # 右侧通常是：已学 00:06 要求学习 01:00
    m_learned = re.search(r"已学[^\d]*(\d{1,2}:\d{2})", text)
    m_required = re.search(r"要求学习[^\d]*(\d{1,2}:\d{2})", text)

    learned = parse_mmss_to_seconds(m_learned.group(1)) if m_learned else 0
    required = parse_mmss_to_seconds(m_required.group(1)) if m_required else 0

    return learned, required


def auto_study_on_detail_page():
    """
    在单个“学习详情”页面内：
    左侧 li.panelItem 一个个点，右侧根据『已学 / 要求学习』决定挂机多久。
    """
    wait_for_left_list()

    items = driver.find_elements(By.CSS_SELECTOR, "div.ivu-scroll-content ul li.panelItem")
    item_count = len(items)
    print(f"左侧共发现 {item_count} 条课程")

    for i in range(item_count):
        # 每次循环都重新抓一次，避免 DOM 更新导致 stale element
        items = driver.find_elements(By.CSS_SELECTOR, "div.ivu-scroll-content ul li.panelItem")
        if i >= len(items):
            break

        li = items[i]
        title = li.text.strip()
        if not title:
            print(f"[跳过] 第 {i+1} 条：文本为空")
            continue

        print(f"\n===== 第 {i+1} 门课程 =====")
        print("标题：", title)

        # 滚动该 li 到可视区域再点击
        try:
            driver.execute_script("arguments[0].scrollIntoView({block: 'center'});", li)
            time.sleep(0.5)
            li.click()
        except Exception as e:
            print(f"[跳过] 第 {i+1} 条：点击失败 -> {e}")
            continue

        # 给一点时间让右侧内容刷新
        time.sleep(1.5)

        try:
            learned, required = get_learned_and_required_from_side()
        except Exception as e:
            print(f"⚠ 第 {i+1} 条：右侧时间面板解析失败 -> {e}，默认挂 60 秒。")
            keep_active(60 + BUFFER_SECONDS)
            continue

        print(f"已学：{learned} 秒，要求学习：{required} 秒")

        if required <= 0:
            # 要求学习没解析出来，就按 60 秒兜底
            remaining = max(60 - learned, 20)
            print(f"⚠ 未解析到要求学习时间，兜底挂机 {remaining + BUFFER_SECONDS} 秒。")
        else:
            remaining = max(required - learned, 0)

        if remaining <= 0:
            print("✅ 已达到或超过要求学习时间，跳过挂机。")
            continue

        need_seconds = remaining + BUFFER_SECONDS
        print(f"剩余需学习时间：{remaining} 秒，实际挂机：{need_seconds} 秒。")

        keep_active(need_seconds)
        print("本门课程挂机完成。")


def main():
    driver.get(DETAIL_URL)
    print("浏览器已打开，请你手动登录，并打开某个任务的『学习详情』页面。")
    input("当你已经在类似 https://.../examTask/10/4/1/39 这样的页面上时，按回车继续...")

    auto_study_on_detail_page()

    print("当前页面左侧课程已全部处理完毕。")
    input("按回车关闭浏览器...")
    driver.quit()


if __name__ == "__main__":
    main()
