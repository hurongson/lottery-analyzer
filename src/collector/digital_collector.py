"""
数字型彩票采集器（福彩3D、排列三、排列五、七星彩）
数据源：中国福彩官网 / 中国体彩官网
"""
import requests
import time
from datetime import datetime

HEADERS = {
    'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36',
    'Referer': 'https://www.lottery.gov.cn/'
}

# 体彩 gameNo 映射
SPORTTERY_GAME_NO = {
    'pl3': '35',       # 排列三
    'pl5': '350133',   # 排列五
}


def collect_fc3d_data(db=None, full_refresh=False, max_pages=100):
    """采集福彩3D历史数据"""
    all_draws = []
    page_no = 1
    page_size = 100

    while page_no <= max_pages:
        url = (
            f'https://www.cwl.gov.cn/cwl_admin/front/cwlkj/search/kjxx/findDrawNotice'
            f'?name=3d&issueCount=&issueStart=&issueEnd=&dayStart=&dayEnd='
            f'&pageNo={page_no}&pageSize={page_size}&systemType=PC'
        )
        try:
            resp = requests.get(url, headers={
                'User-Agent': 'Mozilla/5.0',
                'Referer': 'https://www.cwl.gov.cn/'
            }, timeout=15)
            data = resp.json()
            result = data.get('result', [])
            if not result:
                break

            for item in result:
                draw = _parse_fc3d_item(item)
                if draw:
                    all_draws.append(draw)

            total = data.get('total', 0)
            if page_no * page_size >= total:
                break
            page_no += 1
            time.sleep(0.3)
        except Exception as e:
            print(f'福彩3D采集第{page_no}页失败: {e}')
            break

    # 去重并按期号排序
    seen = set()
    unique_draws = []
    for d in sorted(all_draws, key=lambda x: x['issue_number']):
        if d['issue_number'] not in seen:
            seen.add(d['issue_number'])
            unique_draws.append(d)

    if db:
        from src.storage.database import Database
        count = db.insert_draws('fc3d', unique_draws)
        print(f'福彩3D入库: {count} 条')
        return count

    return unique_draws


def collect_sporttery_data(lottery_type, db=None, full_refresh=False, max_pages=100):
    """采集体彩数字型彩票数据（排列三、排列五、七星彩）"""
    game_no = SPORTTERY_GAME_NO.get(lottery_type)
    if not game_no:
        raise ValueError(f'不支持的体彩类型: {lottery_type}')

    all_draws = []
    page_no = 1
    page_size = 100

    while page_no <= max_pages:
        url = (
            f'https://webapi.sporttery.cn/gateway/lottery/getHistoryPageListV1.qry'
            f'?gameNo={game_no}&provinceId=0&pageSize={page_size}&isVerify=1&pageNo={page_no}'
        )
        try:
            resp = requests.get(url, headers=HEADERS, timeout=15)
            data = resp.json()
            value = data.get('value', {})
            result_list = value.get('list', [])
            if not result_list:
                break

            for item in result_list:
                draw = _parse_sporttery_item(lottery_type, item)
                if draw:
                    all_draws.append(draw)

            pages = value.get('pages', 0)
            if page_no >= pages:
                break
            page_no += 1
            time.sleep(0.3)
        except Exception as e:
            print(f'{lottery_type}采集第{page_no}页失败: {e}')
            break

    # 去重并按期号排序
    seen = set()
    unique_draws = []
    for d in sorted(all_draws, key=lambda x: x['issue_number']):
        if d['issue_number'] not in seen:
            seen.add(d['issue_number'])
            unique_draws.append(d)

    if db:
        count = db.insert_draws(lottery_type, unique_draws)
        print(f'{lottery_type}入库: {count} 条')
        return count

    return unique_draws


def _parse_fc3d_item(item):
    """解析福彩3D单条数据"""
    try:
        issue = item.get('code', '')
        red_str = item.get('red', '')
        red_balls = [int(x) for x in red_str.split(',') if x.strip()]
        date_str = item.get('date', '').split('(')[0]

        if len(red_balls) != 3:
            return None

        return {
            'issue_number': issue,
            'draw_date': date_str,
            'red_balls': red_balls,
            'blue_balls': [],
            'raw': item
        }
    except Exception:
        return None


def _parse_sporttery_item(lottery_type, item):
    """解析体彩单条数据"""
    try:
        issue = item.get('lotteryDrawNum', '')
        result_str = item.get('lotteryDrawResult', '')
        date_str = item.get('lotteryDrawTime', '')

        # 号码用空格分隔
        balls = [int(x) for x in result_str.split() if x.strip().isdigit()]

        if lottery_type == 'pl3' and len(balls) >= 3:
            red_balls = balls[:3]
            blue_balls = []
        elif lottery_type == 'pl5' and len(balls) >= 5:
            red_balls = balls[:5]
            blue_balls = []
        elif lottery_type == 'qxc' and len(balls) >= 7:
            red_balls = balls[:6]
            blue_balls = [balls[6]]
        else:
            return None

        return {
            'issue_number': issue,
            'draw_date': date_str,
            'red_balls': red_balls,
            'blue_balls': blue_balls,
            'raw': item
        }
    except Exception:
        return None


def collect_digital_data(lottery_type, db=None, full_refresh=False):
    """统一入口：采集数字型彩票数据"""
    if lottery_type == 'fc3d':
        return collect_fc3d_data(db=db, full_refresh=full_refresh)
    elif lottery_type in SPORTTERY_GAME_NO:
        return collect_sporttery_data(lottery_type, db=db, full_refresh=full_refresh)
    else:
        raise ValueError(f'不支持的彩种: {lottery_type}')
