import string
import re
from collections import Counter

def normalize_answer(s):
    """
    标准化答案：去除标点、多余空格、大小写转换。
    """
    def remove_articles(text):
        return re.sub(r'\b(a|an|the)\b', ' ', text)

    def white_space_fix(text):
        return ' '.join(text.split())

    def remove_punc(text):
        # 去除英文标点
        exclude = set(string.punctuation)
        # 常见中文标点 (可按需扩充)
        cn_punc = set("，。！？【】（）《》“”、：；") 
        return ''.join(ch for ch in text if ch not in exclude and ch not in cn_punc)

    def lower(text):
        return text.lower()

    return white_space_fix(remove_punc(lower(str(s))))

def mixed_segmentation(text):
    """
    混合分词策略：
    如果包含中文字符，则按字切分（Character-level）；
    否则按空格切分（Word-level）。
    """
    if any("\u4e00" <= char <= "\u9fff" for char in text):
        # 中文：按字切分，去除空格
        return [c for c in text if c.strip()]
    else:
        # 英文：按空格切分
        return text.split()

def f1_score(prediction, ground_truth):
    # 1. 先标准化
    pred_text = normalize_answer(prediction)
    gold_text = normalize_answer(ground_truth)

    # 2. 混合分词 (关键修复)
    prediction_tokens = mixed_segmentation(pred_text)
    ground_truth_tokens = mixed_segmentation(gold_text)
    
    # 3. 计算 Overlap
    common = Counter(prediction_tokens) & Counter(ground_truth_tokens)
    num_same = sum(common.values())
    
    if num_same == 0:
        return 0
    
    precision = 1.0 * num_same / len(prediction_tokens)
    recall = 1.0 * num_same / len(ground_truth_tokens)
    f1 = (2 * precision * recall) / (precision + recall)
    return f1

def exact_match_score(prediction, ground_truth):
    return (normalize_answer(prediction) == normalize_answer(ground_truth))

def metric_max_over_ground_truths(metric_fn, prediction, ground_truths):
    scores_for_ground_truths = []
    for ground_truth in ground_truths:
        score = metric_fn(prediction, ground_truth)
        scores_for_ground_truths.append(score)
    return max(scores_for_ground_truths)

def evaluate_prediction(prediction, gold_answers):
    em = metric_max_over_ground_truths(exact_match_score, prediction, gold_answers)
    f1 = metric_max_over_ground_truths(f1_score, prediction, gold_answers)
    return em, f1


