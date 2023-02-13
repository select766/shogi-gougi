"""
cshogi.cliで出力された対局ログをパースし、各対局の評価値推移、勝敗を出力する
"""

import re
import argparse
import pickle

def load_records(path, encoding):
    records = []
    re_score = re.compile("([12]):info .*score (cp|mate) ([0-9+-]+) .*")
    with open(path, "r", encoding=encoding) as f:
        for line in f:
            line = line.rstrip()
            if line[1:] == ":usinewgame":
                # 先手について
                # "1:usinewgame"->"2:usinewgame"の順=1が先手
                # "2:usinewgame"->"1:usinewgame"の順=2が先手
                # 後に呼ばれた側で初期化された以下の変数が使われるのでこの式になる
                match_info = {"1": [], "2": [], "winner": None, "sente": 3-int(line[0])}
                last_bestmove_player = None
                last_info = None
            elif line.startswith("まで"):
                # https://github.com/TadaoYamaoka/cshogi/blob/master/cshogi/cli.py
                # の勝ち/持将棋/千日手/入玉宣言
                # ほかにもあるが反則など特殊ケース
                
                if "の勝ち" in line:
                    if "先手" in line:
                        winner = match_info["sente"]
                    else:
                        winner = 3 - match_info["sente"]
                elif ("持将棋" in line) or ("千日手" in line):
                    winner = None
                elif "入玉宣言" in line:
                    winner = last_bestmove_player # 最後に着手したプレイヤーが勝ち
                else:
                    winner = None
                    
                match_info["winner"] = winner
                records.append(match_info)
                match_info = None
            elif match := re_score.match(line):
                last_info = match.groups() # ('2', 'cp', '104')
            elif line[1:].startswith(":bestmove"):
                if last_info[1] == 'cp': # mateはスルー
                    match_info[last_info[0]].append(int(last_info[2]))
                last_bestmove_player = int(line[0])
            elif line[1:].startswith(":go"):
                last_info = None
    return records

def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("src")
    parser.add_argument("dst")
    parser.add_argument("--encoding", default="cp932") # 日本語Windowsでは"cp932"
    args = parser.parse_args()

    records = load_records(args.src, args.encoding)
    with open(args.dst, "wb") as f:
        pickle.dump(records, f)

if __name__ == "__main__":
    main()
