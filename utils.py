"""工具函数"""

import json
import re
import time
from pathlib import Path
from typing import Optional

import requests


def save_json(data: dict, filepath: Path) -> None:
    """保存 JSON 文件"""
    filepath.parent.mkdir(parents=True, exist_ok=True)
    with open(filepath, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)


def load_json(filepath: Path) -> Optional[dict]:
    """加载 JSON 文件"""
    if not filepath.exists():
        return None
    with open(filepath, "r", encoding="utf-8") as f:
        return json.load(f)


def download_file(url: str, save_path: Path) -> Path:
    """下载文件到本地"""
    save_path.parent.mkdir(parents=True, exist_ok=True)
    resp = requests.get(url, timeout=(30, 300))
    resp.raise_for_status()
    with open(save_path, "wb") as f:
        f.write(resp.content)
    return save_path


def make_minimax_headers() -> dict:
    """构造 MiniMax API 请求头"""
    from config import MINIMAX_API_KEY, MINIMAX_GROUP_ID
    headers = {
        "Authorization": f"Bearer {MINIMAX_API_KEY}",
        "Content-Type": "application/json",
    }
    if MINIMAX_GROUP_ID:
        headers["MiniMax-Header-Group-Id"] = MINIMAX_GROUP_ID
    return headers


def retry_on_failure(func, max_retries=3, delay=2.0):
    """简单重试装饰器"""
    if max_retries <= 0:
        return func()
    last_error = None
    for attempt in range(max_retries):
        try:
            return func()
        except Exception as e:
            last_error = e
            if attempt == max_retries - 1:
                raise
            print(f"  重试 {attempt + 1}/{max_retries}: {e}")
            time.sleep(delay * (attempt + 1))


def format_timestamp(seconds: float) -> str:
    """将秒数转为 SRT 时间戳格式: HH:MM:SS,mmm"""
    h = int(seconds // 3600)
    m = int((seconds % 3600) // 60)
    s = int(seconds % 60)
    ms = int((seconds - int(seconds)) * 1000)
    return f"{h:02d}:{m:02d}:{s:02d},{ms:03d}"


# 尝试加载 opencc（可选依赖），用于繁简转换
_opencc = None
try:
    from opencc import OpenCC
    _opencc = OpenCC('t2s')
except ImportError:
    pass


def to_simplified(text: str) -> str:
    """将繁体中文转换为简体中文。
    优先使用 opencc（需 pip install opencc-python-reimplemented），
    不可用时回退到内置常用字映射。
    """
    if _opencc is not None:
        return _opencc.convert(text)

    _TS_MAP = str.maketrans({
        '個': '个', '們': '们', '來': '来', '對': '对', '會': '会',
        '時': '时', '這': '这', '為': '为', '國': '国', '學': '学',
        '發': '发', '開': '开', '關': '关', '說': '说', '後': '后',
        '過': '过', '體': '体', '現': '现', '機': '机', '實': '实',
        '電': '电', '動': '动', '樣': '样', '點': '点', '頭': '头',
        '經': '经', '氣': '气', '問': '问', '裡': '里', '應': '应',
        '當': '当', '還': '还', '沒': '没', '著': '着', '間': '间',
        '進': '进', '將': '将', '給': '给', '麼': '么', '讓': '让',
        '請': '请', '嗎': '吗', '見': '见', '門': '门', '長': '长',
        '書': '书', '萬': '万', '邊': '边', '處': '处', '義': '义',
        '業': '业', '樂': '乐', '傳': '传', '寫': '写', '許': '许',
        '從': '从', '級': '级', '結': '结', '極': '极', '無': '无',
        '熱': '热', '愛': '爱', '聲': '声', '變': '变', '場': '场',
        '帶': '带', '東': '东', '風': '风', '廣': '广', '號': '号',
        '歡': '欢', '畫': '画', '話': '话', '節': '节', '覺': '觉',
        '軍': '军', '連': '连', '買': '买', '賣': '卖', '難': '难',
        '腦': '脑', '錢': '钱', '強': '强', '輕': '轻', '確': '确',
        '認': '认', '識': '识', '數': '数', '樹': '树', '誰': '谁',
        '歲': '岁', '聽': '听', '網': '网', '係': '系', '線': '线',
        '選': '选', '魚': '鱼', '遠': '远', '運': '运', '戰': '战',
        '張': '张', '質': '质', '總': '总', '組': '组', '導': '导',
        '際': '际', '龍': '龙', '準': '准', '備': '备', '標': '标',
        '層': '层', '產': '产', '稱': '称', '創': '创', '達': '达',
        '單': '单', '黨': '党', '調': '调', '爾': '尔', '範': '范',
        '飛': '飞', '復': '复', '該': '该', '剛': '刚', '夠': '够',
        '規': '规', '紅': '红', '劃': '划', '黃': '黄', '積': '积',
        '計': '计', '濟': '济', '較': '较', '舊': '旧', '決': '决',
        '塊': '块', '況': '况', '離': '离', '歷': '历', '滿': '满',
        '麵': '面', '內': '内', '農': '农', '歐': '欧', '盤': '盘',
        '齊': '齐', '親': '亲', '區': '区', '卻': '却', '設': '设',
        '師': '师', '術': '术', '絲': '丝', '雖': '虽', '隨': '随',
        '臺': '台', '態': '态', '團': '团', '圍': '围', '衛': '卫',
        '務': '务', '誤': '误', '顯': '显', '縣': '县', '鄉': '乡',
        '響': '响', '壓': '压', '陽': '阳', '藥': '药', '異': '异',
        '銀': '银', '營': '营', '優': '优', '於': '于', '與': '与',
        '預': '预', '園': '园', '約': '约', '雜': '杂', '紙': '纸',
        '製': '制', '誌': '志', '眾': '众', '週': '周', '狀': '状',
        '資': '资', '護': '护', '證': '证', '報': '报', '華': '华',
        '藝': '艺', '蘭': '兰', '觀': '观', '講': '讲', '議': '议',
        '論': '论', '試': '试', '訓': '训', '記': '记', '訴': '诉',
        '語': '语', '課': '课', '讀': '读', '談': '谈', '謝': '谢',
        '貨': '货', '費': '费', '車': '车', '轉': '转', '辦': '办',
        '鐵': '铁', '錯': '错', '鋼': '钢', '鏡': '镜', '鐘': '钟',
        '醫': '医', '釋': '释', '雲': '云', '雙': '双', '靈': '灵',
        '顧': '顾', '養': '养', '鬥': '斗', '鳥': '鸟', '糾': '纠',
        '纏': '缠', '攝': '摄', '擴': '扩', '檢': '检', '測': '测',
        '驗': '验', '築': '筑', '構': '构', '煙': '烟', '奮': '奋',
        '礎': '础', '憶': '忆', '億': '亿', '儀': '仪', '嚴': '严',
        '蘇': '苏', '觸': '触', '臟': '脏', '艦': '舰', '蟲': '虫',
        '驚': '惊', '贊': '赞', '贏': '赢', '購': '购', '賴': '赖',
        '賽': '赛', '賬': '账', '陸': '陆', '階': '阶', '隻': '只',
        '霧': '雾', '靜': '静', '順': '顺', '鬆': '松', '鹽': '盐',
    })
    return text.translate(_TS_MAP)


def slugify(text: str, max_len: int = 50) -> str:
    """
    将文本转为路径安全的文件名 slug

    保留中文、字母、数字，其余非安全字符替换为连字符，
    连字符合并、去首尾，截断到 max_len。
    """
    # 替换非法文件名字符和标点为连字符
    safe = re.sub(r'[\\\\/*?:\"<>|\s,，。！？、；：""\'\'（）()【】\[\]《》<>「」『』]+', '-', text)
    # 合并连续连字符
    safe = re.sub(r'-+', '-', safe)
    # 去首尾连字符
    safe = safe.strip('-')
    # 截断
    if len(safe) > max_len:
        safe = safe[:max_len].rstrip('-')
    return safe or "video"
