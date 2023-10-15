# -*- coding: utf-8 -*-

import re
import unicodedata
from io import StringIO
import json
import os

from pdfminer.converter import TextConverter
from pdfminer.layout import LAParams
from pdfminer.pdfdocument import PDFDocument
from pdfminer.pdfinterp import PDFResourceManager, PDFPageInterpreter
from pdfminer.pdfpage import PDFPage
from pdfminer.pdfparser import PDFParser


class Question:
    
    def __init__(self, title):
        self.title = self.format_title(title)
        self.text = ""
        self.iroha_items = []
        self.options = []

    def format_title(self, item):
        k = ("category", "num")
        v = re.match(r"【(.*)】([0-9０-９]+)", item).groups()
        v = (v[0], int(unicodedata.normalize("NFKC", v[1])))
        item = dict(zip(k,v))
        return item

    def add_text(self, text):
        self.text += text
    
    def add_iroha_items(self, item):
        k = ("id","text")
        v = re.match(r"\(([ｱ-ﾝ])\) (.*)", item).groups()
        item = dict(zip(k,v))
        self.iroha_items.append(item)

    def add_abc_items(self, item):
        k = ("id","text")
        v = re.match(r"^([A-ZＡ-Ｚ]) (.*)", item).groups()
        item = dict(zip(k,v))
        self.iroha_items.append(item)


    def add_options(self, item):
        k = ("id","text")
        v = re.match(r"([0-9０-９]) +(.*?) ?$|\(([0-9])\) +(.*?) ?$", item).groups()
        v = (v[0] or v[2], v[1] or v[3])
        v = (int(unicodedata.normalize("NFKC", v[0])), v[1])
        item = dict(zip(k,v))
        self.options.append(item)

    def dictionalize(self):
        result = {
            "title":self.title,
            "text":self.text,
            "iroha_items":self.iroha_items,
            "options":self.options
        }
        if len(self.iroha_items) == 0:
            del result["iroha_items"]

        return result


class Answer:

    def __init__(self, matchings):
        self.matchings = matchings    
        self.title = self.clean_title(self.findall("title")[0])
        self.pairs = self.merge_numbers()
        self.headers = self.merge_headers()

    
    def findall(self, label):
        return [m for m in self.matchings if m[0] == label]

    @staticmethod
    def format_col(item):
        return re.findall(r"(\d+,?\d*)\n?", item)
        
    @staticmethod
    def merge_cols(cols):
        return list(zip(*cols))
    
    @staticmethod
    def clean_title(title):
        return title[1].replace("\u3000","").replace(" ","")
    
    @staticmethod
    def format_title(item):
        return item
    
    def merge_numbers(self):
        pairs = []
        answers = self.findall("answer")
        nums = self.findall("num")
        if len(answers) != len(nums):
            raise ValueError("解答列と番号列の数が合いません")
        
        for i in range(len(nums)):
            num_col = self.format_col(nums[i][1])
            ans_col = self.format_col(answers[i][1])
            if len(num_col) != len(ans_col):
                raise ValueError("解答行と番号行の数が合いません", ans_col, num_col)
            p = self.merge_cols([num_col, ans_col])
            pairs += p
        
        return pairs
    

    
    def merge_headers(self):
        headers = self.findall("header")
        # return [h[1].replace(" ","") for h in headers]
        return [h[1].replace(" ","") for h in headers]
    
    def assign_category(self):
        src = self.pairs.copy()
        headers = self.headers.copy()
        data = []
        # print(src)
        while len(src):
            item = src.pop(0)
            if item[0] == "1":
                block = {"category":headers.pop(0)}
                # print(block)
                items = []

            n = int(item[0])
            a_ = re.match(r"(\d+),?(\d*)", item[1]).groups()
            if a_[1] == "":
                ans = int(a_[0])
            else:
                ans = (int(a_[0]), int(a_[1]))
            # items.append({"num":int(item[0]), "answer":int(item[1])})
            items.append({"num":n, "answer":ans})
            
            if len(src) == 0:
                block["answers"] = items
                data.append(block)
            elif src[0][0] == "1":
                block["answers"] = items
                data.append(block)
                # print(block)

        return data
    
    def dictionalize(self):
        data = self.assign_category()
        return {
            "title":self.title,
            "data":data
        }


def textize(path, line_margin=1.5, boxes_flow=0.5, detect_vertical=False, char_margin=2.0, all_texts=False):
    output_string = StringIO()
    with open(path, 'rb') as in_file:
        parser = PDFParser(in_file)
        doc = PDFDocument(parser)
        rsrcmgr = PDFResourceManager()
        device = TextConverter(rsrcmgr, output_string, laparams=LAParams(line_margin=line_margin, boxes_flow=boxes_flow, detect_vertical=detect_vertical, char_margin=char_margin, all_texts= all_texts))
        interpreter = PDFPageInterpreter(rsrcmgr, device)
        for page in PDFPage.create_pages(doc):
            interpreter.process_page(page)

    return output_string.getvalue()

def split_paragraphs(text):
    return re.split(r"\n\n|\n ", text)

def match_pattern_single(string, patterns=None):
    if patterns:
        for k,p in patterns.items():
            m = re.match(p, string.strip())
            if m:
                result = k
                break
            else:
                result = False
    else:
        result = True

    if string.find("\x0c") > 0 and type(result) == str:
        # print("!")
        result += "_FF"

    return result


def match_patterns(paragraphs, patterns):
    matchings = [(match_pattern_single(p, patterns),p.strip()) for p in paragraphs]
    matchings = [p for p in matchings if p[0]]

    return matchings


def bond_page_break(matchings):
    src = matchings.copy()
    tar = []
    i = 0
    last_m = ("","")
    while len(src):
        m = src.pop(0)
        if m[0] != "item_num" and m[0] == f"{last_m[0]}_FF" and m[0] != "item_abc":
            tar[-1] = last_m[0], last_m[1] + "\n" + m[1]
        elif m[0] != "item_num" and m[0] == last_m[0] and i>0 and m[0] != "item_abc":
            tar[-1] = last_m[0], last_m[1] + "\n" + m[1]
        elif m[0] == "text" and last_m[0] == "item_iroha":
            tar[-1] = last_m[0], last_m[1] + "\n" + m[1]
        else:
            tar.append((m[0].replace("_FF",""), m[1]))
            i += 1

        last_m = tar[-1]

    return tar


def divide_iroha(matchings):
    src = matchings.copy()
    tar = []

    while len(src):
        m = src.pop(0)
        if m[0] == "item_iroha":
            pattern = r"\([ｱ-ﾝ]\)[\s\S]*?(?=\([ｱ-ﾝ]\))"
            items = re.findall(pattern,m[1], re.MULTILINE)
            tar += list(zip([m[0]]*len(items),items))
            last_item = m[1][m[1].find(items[-1])+len(items[-1]):]
            tar.append((m[0], last_item))
        else:
            tar.append(m)

    return tar


def divide_num(matchings):
    src = matchings.copy()
    tar = []
    while len(src):
        m = src.pop(0)
        if m[0] in ["item_num", "item_n_iroha"]:
            pattern = r"([０-９] +.+\n?){2,}|(\([0-9]\) +.+\n?){2,}"
            items = re.match(pattern,m[1], re.MULTILINE)
            if items:
                items = re.findall(r"[０-９] +[\s\S]*?(?=[０-９] )|\([0-9]\) +[\s\S]*?(?=\([0-9]\) )", m[1], re.MULTILINE)
                tar += list(zip([m[0]]*len(items),items))
                last_item = m[1][m[1].find(items[-1])+len(items[-1]):]
                tar.append((m[0],last_item))
            else:
                tar.append(m)
        else:
            tar.append(m)

    return tar

def divide_header_text(matchings, dummy_text="問題"):
    src = matchings.copy()
    tar = []
    while len(src):
        m = src.pop(0)
        if m[0] == "header_text":
            pattern = r"〔 ?([0-9０-９]+) ?〕 ?([\s\S]*)"
            num, text = re.match(pattern, m[1], re.MULTILINE).groups()
            tar.append(("header", f"【{dummy_text}】{num}"))
            tar.append(("text", text))
        else:
            tar.append(m)
    return tar

def remove_page_break(matchings):
    src = matchings.copy()
    tar = []
    while len(src):
        m = src.pop(0)
        tar.append((m[0],m[1].replace("\n","")))
    return tar


def construct(matchings):
    result = {}
    question = None
    for label, string in matchings:
        if label == "title":
            result["title"] = string
            result["questions"] = []
        elif label == "header":
            if question:
                result["questions"].append(question.dictionalize())
                question = None
            question = Question(string)
        elif label == "text":
            question.add_text(string)
        elif label == "item_iroha":
            question.add_iroha_items(string)
        elif label == "item_abc":
            question.add_abc_items(string)
        elif label in ["item_n_iroha", "item_num"]:

            try:
                question.add_options(string)
            except AttributeError as e:
                print(label, string)
                print(question.dictionalize())
                raise e

    result["questions"].append(question.dictionalize())
    return result

def check_label(matchings, label="header"):
    for m in matchings:
        if m[0] == label:
            print(m)

def check_empty_text(matchings):
    for m in matchings:
        if m[0] == "text":
            assert len(m[1]) > 0


def jsonize_question(src, tar=None):
    patterns = {
        "title":r".*?年度弁理士試験",
        "header":r"【.*】",
        "item_iroha":r"\([ｱ-ﾝ]\)",
        "item_n_iroha":r"[０-９] +([０-９]つ|なし)|\(1\) +([０-９]つ|なし)",
        "item_num":r"[０-９]",
        "text":r".+"
    }
    text = textize(src)
    paragraphs = split_paragraphs(text)
    matchings = match_patterns(paragraphs, patterns)
    matchings = bond_page_break(matchings)
    matchings = divide_iroha(matchings)
    matchings = divide_num(matchings)
    matchings = remove_page_break(matchings)
    check_empty_text(matchings)
    if tar:
        with open(tar, "w") as f:
            json.dump(construct(matchings), f)

    return construct(matchings)

def jsonize_answer(src, tar=None):
    patterns = {
        "title":r".*?年度弁理士試験",
        "answer":r"問題番号.*",
        "num":r"(\d\n)+",
        "header":r".+"
    }
    text = textize(src, boxes_flow=-1, detect_vertical=True)
    paragraphs = split_paragraphs(text)
    matchings = match_patterns(paragraphs, patterns)
    if tar:
        with open(tar, "w") as f:
            json.dump(Answer(matchings).dictionalize(), f)
    
    return Answer(matchings).dictionalize()


def sort_years(years):
    divided = []
    for year in years:
        name, num = re.match(r"(R|H)(\d+)", year).groups()
        divided.append((name, int(num)))
    divided = sorted(divided)
    result = [name+str(num) for name, num in divided][::-1]
    return result


def find_available_dirs(root):
    dir_available = []
    for d in sort_years(os.listdir(root)):
        dirpath = os.path.join(root, d)
        files =  os.listdir(dirpath)
        available = "question.json" in files and "answer.json" in files
        if available:
            dir_available.append(dirpath)
    
    return dir_available
