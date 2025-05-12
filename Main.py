import requests
import pandas as pd
import matplotlib.pyplot as plt
import jieba
import jieba.analyse
import time
import random
import re
from bs4 import BeautifulSoup
from collections import Counter
import seaborn as sns
import numpy as np
import json
from fake_useragent import UserAgent  # 添加UA随机化
from urllib.parse import quote, urljoin
import logging
import warnings
from selenium import webdriver
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.common.exceptions import TimeoutException, NoSuchElementException
import os

# 配置日志
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
warnings.filterwarnings("ignore")

# 设置matplotlib中文字体（修改为更通用的字体名称）
plt.rcParams['font.sans-serif'] = ['Songti SC', 'SimHei', 'Arial Unicode MS']  # 增加多个备选字体
plt.rcParams['font.family'] = 'sans-serif'  # 新增：指定字体家族为无衬线
plt.rcParams['axes.unicode_minus'] = False  # 解决保存图像时负号'-'显示为方块的问题

# 添加对seaborn的字体设置（显式指定支持中文字体）
sns.set(font='Songti SC')  # 修改为与matplotlib一致的主字体


# 随机User-Agent生成
def get_random_ua():
    user_agents = [
        'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36',
        'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/92.0.4515.107 Safari/537.36',
        'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/15.0 Safari/605.1.15',
        'Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:90.0) Gecko/20100101 Firefox/90.0',
        'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.114 Safari/537.36'
    ]
    return random.choice(user_agents)

# 随机请求头生成
def get_random_headers():
    return {
        'User-Agent': get_random_ua(),
        'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8',
        'Accept-Language': 'zh-CN,zh;q=0.9,en;q=0.8',
        'Connection': 'keep-alive',
        'Upgrade-Insecure-Requests': '1',
        'Cache-Control': 'max-age=0',
        'Referer': 'https://www.google.com/',
        'Sec-Fetch-Dest': 'document',
        'Sec-Fetch-Mode': 'navigate',
        'Sec-Fetch-Site': 'cross-site',
        'Sec-Fetch-User': '?1',
        'Pragma': 'no-cache'
    }


# 初始化Selenium WebDriver
def init_webdriver():
    try:
        options = Options()
        options.add_argument('--headless')  # 无头模式
        options.add_argument('--disable-gpu')
        options.add_argument('--no-sandbox')
        options.add_argument('--disable-dev-shm-usage')
        options.add_argument(f'user-agent={get_random_ua()}')
        options.add_experimental_option("excludeSwitches", ["enable-automation"])
        options.add_experimental_option('useAutomationExtension', False)

        driver = webdriver.Chrome(options=options)
        # 设置隐藏webdriver特征
        driver.execute_cdp_cmd("Page.addScriptToEvaluateOnNewDocument", {
            "source": """ 
            Object.defineProperty(navigator, 'webdriver', { 
                get: () => undefined 
            }); 
            """
        })
        return driver
    except Exception as e:
        logging.error(f"初始化WebDriver失败: {e}")
        return None

    # 随机延时函数，使爬取行为更像人类


def random_sleep():
    sleep_time = random.uniform(0, 0.2)
    logging.info(f"随机等待 {sleep_time:.2f} 秒")
    time.sleep(sleep_time)


# 使用IP代理池（示例，实际使用需要有可用的代理IP）
def get_proxy():
    # 这里可以接入一个代理IP池服务
    # 简单起见，这里返回None，表示不使用代理
    return None

    # 如果有代理池，可以这样使用:
    # proxies = {
    #    'http': 'http://user:pass@host:port',
    #    'https': 'https://user:pass@host:port'
    # }
    # return proxies


# 爬取拉勾网实习岗位信息（使用Selenium绕过反爬）
def scrape_lagou(keyword, pages=5):
    all_jobs = []
    driver = init_webdriver()

    if driver is None:
        logging.error("WebDriver初始化失败，无法爬取拉勾网")
        return all_jobs

    try:
        # 智能等待策略
        wait = WebDriverWait(driver, 15)

        # 先访问拉勾网首页，获取必要的cookies
        driver.get("https://www.lagou.com/")
        wait.until(EC.presence_of_element_located((By.ID, "lg_header")))  # 等待首页关键元素
        random_sleep()

        # 进入搜索页面（使用编码后的URL）
        encoded_keyword = quote(keyword.encode('utf-8'))
        search_url = f"https://www.lagou.com/wn/jobs?kd={encoded_keyword}"
        driver.get(search_url)

        # 智能等待策略（增加容错机制）
        try:
            wait.until(EC.presence_of_element_located((By.CLASS_NAME, "item__10RTO")))
        except TimeoutException:
            if "验证" in driver.title:  # 检测验证页面
                logging.error("触发反爬验证机制，请手动处理验证码")
                return all_jobs

                # 新增：页面滚动加载
        last_height = driver.execute_script("return document.body.scrollHeight")
        for _ in range(3):  # 滚动3次确保加载
            driver.execute_script("window.scrollTo(0, document.body.scrollHeight);")
            time.sleep(2)
            new_height = driver.execute_script("return document.body.scrollHeight")
            if new_height == last_height:
                break
            last_height = new_height

            # 优化后的元素定位方式
        job_css_selector = "div.item__10RTO:not(.ad-box)"  # 排除广告职位

        # 等待页面加载完成
        WebDriverWait(driver, 10).until(
            EC.presence_of_element_located((By.CLASS_NAME, "item__10RTO"))
        )

        page_count = 0
        current_page = 1

        while current_page <= pages and page_count < pages:
            logging.info(f"正在爬取拉勾网第 {current_page} 页")

            # 确保页面元素完全加载
            WebDriverWait(driver, 10).until(
                EC.presence_of_element_located((By.CLASS_NAME, "item__10RTO"))
            )
            random_sleep()

            # 解析当前页面内容
            job_elements = driver.find_elements(By.CLASS_NAME, "item__10RTO")

            for element in job_elements:
                try:
                    job_title = element.find_element(By.CSS_SELECTOR, "div.p-top__1F7CL a").text.strip()
                    company = element.find_element(By.CSS_SELECTOR, "div.company-name__2-SjF a").text.strip()

                    # 提取薪资信息
                    try:
                        salary = element.find_element(By.CLASS_NAME, "money__3Lkgq").text.strip()
                    except NoSuchElementException:
                        salary = "未公布"

                        # 提取公司类型
                    try:
                        company_info = element.find_element(By.CLASS_NAME, "ir___QwEG").text.strip()
                        company_type = company_info.split('·')[0].strip() if '·' in company_info else "未知"
                    except NoSuchElementException:
                        company_type = "未知"

                        # 提取技能要求
                    try:
                        skill_tags = element.find_elements(By.CLASS_NAME, "il__18pLK")
                        skills = [tag.text.strip() for tag in skill_tags]
                        skills_text = ','.join(skills)
                    except NoSuchElementException:
                        skills_text = ""

                    job_info = {
                        '岗位名称': job_title,
                        '公司名称': company,
                        '公司类型': company_type,
                        '薪资范围': salary,
                        '技能要求': skills_text,
                        '数据来源': '拉勾网'
                    }

                    all_jobs.append(job_info)

                except Exception as e:
                    logging.error(f"解析岗位卡片出错: {e}")
                    continue

            page_count += 1
            current_page += 1

            # 检查是否有下一页
            try:
                next_btn = driver.find_element(By.CSS_SELECTOR, "button.lg-pagination-next")
                if "lg-pagination-disabled" in next_btn.get_attribute("class"):
                    logging.info("已到达最后一页")
                    break

                    # 点击下一页
                next_btn.click()
                # 等待页面刷新
                time.sleep(2)
            except Exception as e:
                logging.error(f"翻页失败: {e}")
                break

    except Exception as e:
        logging.error(f"爬取拉勾网时出错: {e}")
    finally:
        if driver:
            driver.quit()

    logging.info(f"成功从拉勾网爬取 {len(all_jobs)} 条实习岗位信息")
    return all_jobs


# 爬取实习僧实习岗位信息（使用Selenium绕过反爬）
def scrape_shixiseng(keyword, max_page=5):
    all_jobs = []

    # 字体反爬映射表（根据实际情况动态更新）
    FONT_MAPPING = {
        '\ue0a8': '0', '\ue0b9': '1', '\ue0d8': '2', '\ue0e4': '3', '\ue0f6': '4',
        '\ue1a2': '5', '\ue1b8': '6', '\ue1c7': '7', '\ue1d5': '8', '\ue1e9': '9',
        '\ue24a': '-', '\ue2f3': '/'
    }

    def decode_font(text):
        """解密字体反爬的数字"""
        return ''.join(FONT_MAPPING.get(char, char) for char in text)

    def get_job_list(page):
        """获取职位列表页中的详情页链接"""
        base_url = f'https://www.shixiseng.com/interns?keyword={quote(keyword)}&page={page}'
        headers = get_random_headers()
        try:
            response = requests.get(base_url, headers=headers, timeout=10)
            if response.status_code != 200:
                logging.error(f"第{page}页请求失败，状态码: {response.status_code}")
                return []
            soup = BeautifulSoup(response.text, 'html.parser')
            job_links = []
            for item in soup.select('.intern-wrap.intern-item'):
                link = item.select_one('.f-l.intern-detail__job a')
                if link and 'href' in link.attrs:
                    job_links.append(urljoin(base_url, link['href']))
            return job_links
        except Exception as e:
            logging.error(f"获取职位列表出错: {e}")
            return []

    def get_job_detail(detail_url):
        """访问详情页并提取岗位详细信息"""
        headers = get_random_headers()
        try:
            response = requests.get(detail_url, headers=headers, timeout=10)
            if response.status_code != 200:
                logging.error(f"详情页请求失败: {detail_url}, 状态码: {response.status_code}")
                return None

            soup = BeautifulSoup(response.text, 'html.parser')

            # 提取基本信息
            job_title_element = soup.select_one('.new_job_name')
            job_title = job_title_element.get_text(strip=True) if job_title_element else "未知岗位"

            company_name_element = soup.select_one('.com_intro .com-name')
            company_name = company_name_element.get_text(strip=True) if company_name_element else "未知公司"

            salary_element = soup.select_one('.job_money.cutom_font')
            salary = decode_font(salary_element.get_text(strip=True)) if salary_element else "未公布"

            job_type_element = soup.select_one('.job_position')
            job_type = job_type_element.get_text(strip=True) if job_type_element else "未知类型"

            job_benefits_elements = soup.select('.job_good_list span')
            job_benefits = [item.get_text(strip=True) for item in job_benefits_elements] if job_benefits_elements else []

            skills_text = ', '.join(job_benefits)

            # 公司类型
            company_type_element = soup.select_one('.com-type')
            company_type = company_type_element.get_text(strip=True) if company_type_element else "未知"

            return {
                '岗位名称': job_title,
                '公司名称': company_name,
                '公司类型': company_type,
                '薪资范围': salary,
                '技能要求': skills_text,
                '数据来源': '实习僧',
                '详情页URL': detail_url
            }

        except Exception as e:
            logging.error(f"解析详情页失败: {detail_url}, 错误: {e}")
            return None

    # 主流程：遍历每一页 -> 获取详情页链接 -> 解析详情页内容
    for page in range(1, max_page + 1):
        logging.info(f"正在爬取实习僧第 {page} 页")
        job_urls = get_job_list(page)

        for url in job_urls:
            job_info = get_job_detail(url)
            if job_info:
                all_jobs.append(job_info)
                logging.info(f"已爬取: {job_info['岗位名称']} - {job_info['公司名称']}")
            random_sleep()

    logging.info(f"成功从实习僧爬取 {len(all_jobs)} 条实习岗位信息")
    return all_jobs


# 备用方案：API接口爬取（部分网站可以通过接口获取数据）
def scrape_via_api(keyword, pages=5):
    """
    尝试通过API接口获取数据，部分网站会在前端请求数据时使用API
    这个函数是拉勾网和实习僧爬取失败的备用方案
    """
    all_jobs = []
    
    # 以拉勾网为例
    for page in range(1, pages + 1):
        try:
            # 拉勾网可能的API接口
            url = "https://www.lagou.com/jobs/v2/positionAjax.json"
            headers = get_random_headers()
            # 添加必要的请求头
            headers.update({
                'Content-Type': 'application/x-www-form-urlencoded; charset=UTF-8',
                'X-Requested-With': 'XMLHttpRequest',
                'Origin': 'https://www.lagou.com',
                'Referer': f'https://www.lagou.com/jobs/list_{keyword}'
            })
            
            form_data = {
                'first': 'true' if page == 1 else 'false',
                'pn': str(page),
                'kd': keyword,
                'sid': ''
            }
            
            response = requests.post(url, headers=headers, data=form_data, timeout=10)
            if response.status_code == 200:
                data = response.json()
                job_list = data.get('content', {}).get('positionResult', {}).get('result', [])
                for job in job_list:
                    job_info = {
                        '岗位名称': job.get('positionName', ''),
                        '公司名称': job.get('companyShortName', ''),
                        '公司类型': job.get('industryField', ''),
                        '薪资范围': job.get('salary', ''),
                        '技能要求': job.get('positionAdvantage', ''),
                        '数据来源': '拉勾网API'
                    }
                    all_jobs.append(job_info)
            else:
                logging.error(f"API请求失败，状态码: {response.status_code}")
                break
                
        except Exception as e:
            logging.error(f"通过API爬取拉勾网时出错: {e}")
            break
    
    logging.info(f"成功从拉勾网API爬取 {len(all_jobs)} 条实习岗位信息")
    return all_jobs

# 数据清洗与预处理
def preprocess_data(df):
    # 清洗岗位名称
    df['岗位名称'] = df['岗位名称'].str.replace(r'[^\w\s\u4e00-\u9fff]+', '', regex=True)

    # 从岗位名称中提取岗位类别
    def extract_job_category(title):
        if any(keyword in title for keyword in ['Python', 'Java', 'C++', '前端', '后端', '全栈', '开发']):
            return '技术开发'
        elif any(keyword in title for keyword in ['数据', '分析', '算法', 'AI', '人工智能', '机器学习']):
            return '数据/算法'
        elif any(keyword in title for keyword in ['产品', 'PM', '产品经理']):
            return '产品'
        elif any(keyword in title for keyword in ['设计', 'UI', 'UX', 'UI/UX']):
            return '设计'
        elif any(keyword in title for keyword in ['运营', '营销', '市场', '内容', '新媒体', '用户']):
            return '运营/市场'
        elif any(keyword in title for keyword in ['人力', 'HR', '招聘', '人事']):
            return '人力资源'
        elif any(keyword in title for keyword in ['财务', '会计', '金融']):
            return '财务/金融'
        else:
            return '其他'

    df['岗位类别'] = df['岗位名称'].apply(extract_job_category)

    # 处理薪资范围，统一格式并提取最低和最高薪资
    def process_salary(salary):
        if pd.isna(salary) or salary == '未公布':
            return {'min_salary': None, 'max_salary': None, 'unit': None}

        # 提取数字
        numbers = re.findall(r'\d+', salary)
        if len(numbers) >= 2:
            min_salary = int(numbers[0])
            max_salary = int(numbers[1])
        elif len(numbers) == 1:
            min_salary = max_salary = int(numbers[0])
        else:
            return {'min_salary': None, 'max_salary': None, 'unit': None}

        # 判断单位
        if '元/天' in salary or '元/日' in salary:
            unit = '元/天'
            # 转换为月薪（假设每月工作22天）
            min_salary = min_salary * 22
            max_salary = max_salary * 22
        else:
            unit = '元/月'

        return {'min_salary': min_salary, 'max_salary': max_salary, 'unit': unit}

    salary_info = df['薪资范围'].apply(process_salary)
    df['最低薪资'] = salary_info.apply(lambda x: x['min_salary'])
    df['最高薪资'] = salary_info.apply(lambda x: x['max_salary'])
    df['薪资单位'] = salary_info.apply(lambda x: x['unit'])

    # 计算平均薪资
    df['平均薪资'] = df.apply(
        lambda row: (row['最低薪资'] + row['最高薪资']) / 2 if pd.notna(row['最低薪资']) and pd.notna(
            row['最高薪资']) else None, axis=1)

    # 提取技能要求
    df['技能列表'] = df['技能要求'].str.split('[,，、 /]+')

    return df


# 数据分析
def analyze_data(df):
    # 1. 岗位分布分析
    job_category_counts = df['岗位类别'].value_counts()

    plt.figure(figsize=(12, 6))
    job_category_counts.plot(kind='bar', color='skyblue')
    plt.title('实习岗位类别分布')
    plt.xlabel('岗位类别')
    plt.ylabel('岗位数量')
    plt.xticks(rotation=45)
    plt.tight_layout()
    plt.savefig('岗位类别分布.png')
    plt.close()

    # 2. 公司类型分布
    company_type_counts = df['岗位类别'].value_counts().head(10)

    plt.figure(figsize=(12, 6))
    company_type_counts.plot(kind='bar', color='lightgreen')
    plt.title('企业类型分布（Top 10）')
    plt.xlabel('企业类型')
    plt.ylabel('数量')
    plt.xticks(rotation=45)
    plt.tight_layout()
    plt.savefig('企业类型分布.png')
    plt.close()

    # 3. 薪资分析
    # 按岗位类别的平均薪资
    salary_by_category = df.groupby('岗位类别')['平均薪资'].mean().sort_values(ascending=False)

    plt.figure(figsize=(12, 6))
    salary_by_category.plot(kind='bar', color='salmon')
    plt.title('各岗位类别平均薪资')
    plt.xlabel('岗位类别')
    plt.ylabel('平均薪资（元/天）')
    plt.xticks(rotation=45)
    plt.tight_layout()
    plt.savefig('各岗位类别平均薪资.png')
    plt.close()

    # 4. 技能要求分析
    # 提取所有技能
    all_skills = []
    for skills in df['技能要求']:
        if isinstance(skills, str):
            all_skills.extend([skill.strip() for skill in skills.split(',') if skill.strip()])

    # 计算各技能出现频次
    skill_counts = Counter(all_skills)

    # 创建技能频率表并保存（代替wordcloud，避免NumPy 2.0兼容性问题）
    top_skills_df = pd.DataFrame(skill_counts.most_common(50), columns=['技能', '频次'])
    top_skills_df.to_csv('技能频率表.csv', index=False, encoding='utf-8-sig')

    # 绘制技能频率条形图
    plt.figure(figsize=(14, 10))
    sns.barplot(x='频次', y='技能', data=top_skills_df.head(20), hue='技能', palette='viridis', legend=False)
    plt.title('热门技能TOP20')
    plt.xlabel('出现频次')
    plt.ylabel('技能')
    plt.tight_layout()
    plt.savefig('热门技能TOP20.png')
    plt.close()

    # 5. 各岗位类别对应的主要技能要求
    category_skills = {}
    for category in df['岗位类别'].unique():
        category_df = df[df['岗位类别'] == category]
        category_skills_list = []
        for skills in category_df['技能要求']:
            if isinstance(skills, str):
                category_skills_list.extend([skill.strip() for skill in skills.split(',') if skill.strip()])

        category_skills[category] = Counter(category_skills_list)

    # 为每个岗位类别绘制Top10技能
    for category, skills_counter in category_skills.items():
        if len(skills_counter) > 0:
            top_skills = pd.DataFrame(skills_counter.most_common(10), columns=['技能', '频次'])
            plt.figure(figsize=(12, 6))
            sns.barplot(x='频次', y='技能', data=top_skills, hue='技能', palette='viridis', legend=False)
            plt.title(f'{category}岗位Top10技能需求')
            plt.xlabel('出现频次')
            plt.ylabel('技能')
            plt.tight_layout()
            safe_category = category.replace("/", "_")
            plt.savefig(f'{safe_category}岗位技能需求.png')
            plt.close()

    # 6. 技能与薪资关系分析
    # 获取出现频次前20的技能
    top_skills = [skill for skill, count in skill_counts.most_common(20)]

    # 对于每个技能，计算包含该技能的岗位的平均薪资
    skill_salary = {}
    for skill in top_skills:
        # 找出包含该技能的所有岗位
        skill_jobs = df[df['技能要求'].apply(lambda x: isinstance(x, str) and skill in x)]
        if len(skill_jobs) > 0:
            avg_salary = skill_jobs['平均薪资'].mean()
            skill_salary[skill] = avg_salary

    # 排序并绘制
    skill_salary_df = pd.DataFrame({
        '技能': list(skill_salary.keys()),
        '平均薪资': list(skill_salary.values())
    }).sort_values('平均薪资', ascending=False)

    plt.figure(figsize=(14, 8))
    sns.barplot(x='平均薪资', y='技能', data=skill_salary_df, hue='技能', palette='coolwarm', legend=False)
    plt.title('各技能对应的平均薪资')
    plt.xlabel('平均薪资（元/天）')
    plt.ylabel('技能')
    plt.tight_layout()
    plt.savefig('技能薪资关系.png')
    plt.close()

    # 7. 薪资分布直方图
    print("绘制薪资")
    plt.figure(figsize=(12, 6))
    # 确保数据为NumPy数组并去除缺失值
    salary_data = np.array(df['平均薪资'].dropna().values)

    # 过滤掉异常值（如负值或极大值）
    salary_data = salary_data[(salary_data > 0) & (salary_data < 100000)]  # 假设薪资上限为100000元/月

    # 检查数据是否为空
    if len(salary_data) == 0:
        logging.warning("薪资数据为空，无法绘制直方图")
    else:
        logging.info(f"薪资数据形状: {salary_data.shape}, 数据类型: {salary_data.dtype}")
        sns.histplot(salary_data, bins=30, kde=True)
        plt.title('实习岗位薪资分布')
        plt.xlabel('平均薪资（元/月）')  # 修改单位说明
        plt.ylabel('岗位数量')
        plt.tight_layout()
        plt.savefig('薪资分布直方图.png')
        plt.close()

    return {
        'job_category_counts': job_category_counts,
        'company_type_counts': company_type_counts,
        'salary_by_category': salary_by_category,
        'skill_counts': skill_counts,
        'category_skills': category_skills,
        'skill_salary': skill_salary_df
    }


# 生成报告
def generate_report(analysis_results, df):
    # 岗位数量
    job_count = len(df)

    # 平均薪资
    avg_salary = df['平均薪资'].mean()

    # 最受欢迎的技能（出现频次最高的前10个）
    all_skills = []
    for skills in df['技能列表']:
        if isinstance(skills, list):
            all_skills.extend([skill.strip() for skill in skills if skill.strip()])

    top_skills = Counter(all_skills).most_common(10)

    # 薪资最高的岗位类别
    top_salary_category = analysis_results['salary_by_category'].index[0]

    # 薪资最高的技能
    if not analysis_results['skill_salary'].empty:
        top_salary_skill = analysis_results['skill_salary']['技能'].iloc[0]
        top_salary_skill_value = analysis_results['skill_salary']['平均薪资'].iloc[0]
    else:
        top_salary_skill = "无数据"
        top_salary_skill_value = 0

    # 生成报告
    report = f"""
# 实习岗位市场分析报告

## 基本情况

- 共分析了 {job_count} 个实习岗位
- 实习岗位平均薪资: {avg_salary:.2f} 元/月

## 岗位分布

最热门的岗位类型:
{analysis_results['job_category_counts'].head(5).to_string()}

## 薪资分析

薪资最高的岗位类别: {top_salary_category} ({analysis_results['salary_by_category'].iloc[0]:.2f} 元/月)

## 技能需求分析

### 最受欢迎的技能 (Top 10):
"""

    for skill, count in top_skills:
        report += f"- {skill}: {count}次\n"

    report += f"""
### 薪资最高的技能: {top_salary_skill} ({top_salary_skill_value:.2f} 元/月)

## 对大学生的建议

根据分析结果，我们向大学生提出以下建议:

1. **重点关注的技能领域**:
"""

    # 根据薪资和需求量提出建议
    high_value_skills = analysis_results['skill_salary'].head(5)['技能'].tolist()
    report += "   - 高薪技能: " + ", ".join(high_value_skills) + "\n"

    high_demand_skills = [skill for skill, _ in top_skills[:5]]
    report += "   - 高需求技能: " + ", ".join(high_demand_skills) + "\n\n"

    report += """2. **针对不同岗位方向的技能储备**:
"""

    # 对于每个主要岗位类别，提供技能储备建议
    for category, skills_counter in analysis_results['category_skills'].items():
        if len(skills_counter) > 0:
            top_cat_skills = [skill for skill, _ in skills_counter.most_common(5)]
            report += f"   - {category}方向: {', '.join(top_cat_skills)}\n"

    report += """
3. **实习市场洞察**:
   - 目前市场上技术开发类和数据/算法类岗位需求量大
   - 互联网和人工智能领域的公司提供了较多的实习机会
   - 提高核心技能的专业深度，同时培养通用软技能(如沟通能力、团队协作等)

4. **差距解读与提升路径**:
   - 学校教育与企业需求的差距主要体现在实践经验和前沿技术应用上
   - 建议通过参与开源项目、参加技术竞赛、自学热门框架等方式提升实践能力
   - 结合自身专业背景，选择1-2个热门技能进行深入学习和项目实践

## 总结

当前实习市场对大学生技能要求逐渐多元化和专业化，既需要专业技能的深度，也需要良好的软技能支持。大学生应当根据自身兴趣和市场需求，有针对性地提升核心竞争力，以更好地适应就业市场的需求.
"""

    return report


# 主函数
def main():
    # 爬取拉勾网实习岗位
    #lagou_jobs = scrape_lagou("实习", pages=3)
    Npg=int(input("请输入爬取网页数:"))
    # 爬取实习僧实习岗位
    shixiseng_jobs = scrape_shixiseng("实习", max_page=Npg)  # 将pages改为max_page

    # 如果Selenium爬取失败，尝试使用API接口
    #if not lagou_jobs:
    #    lagou_jobs = scrape_via_api("实习", pages=3)

    # 合并数据
    #all_jobs = lagou_jobs + shixiseng_jobs
    all_jobs = shixiseng_jobs

    # 转换为DataFrame
    df = pd.DataFrame(all_jobs)

    # 保存原始数据
    df.to_csv("实习岗位原始数据.csv", index=False, encoding='utf-8-sig')

    # 数据预处理
    processed_df = preprocess_data(df)

    # 保存处理后的数据
    processed_df.to_csv("实习岗位处理后数据.csv", index=False, encoding='utf-8-sig')

    # 数据分析
    analysis_results = analyze_data(processed_df)

    # 生成报告
    report = generate_report(analysis_results, processed_df)

    # 保存报告
    with open("实习岗位市场分析报告.md", "w", encoding='utf-8') as f:
        f.write(report)

    print("分析完成，已生成报告和可视化图表。")


if __name__ == "__main__":
    main()