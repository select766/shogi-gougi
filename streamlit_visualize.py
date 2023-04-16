# streamlit run streamlit_visualize.py -- xxx.log
# 合議結果をリアルタイム可視化するツール

import argparse
import time
import json
from cshogi import Board
from cshogi.KIF import move_to_kif
import streamlit as st
import pandas as pd

class ReadLine:
    """
    EOFに達しても読み取りを再試行する機構
    ログファイルを読み取る目的
    """
    def __init__(self, f) -> None:
        self.f = f
        self.buffer = ""
    
    def readline(self) -> str:
        nl = self.buffer.find("\n")
        if nl >= 0:
            ret = self.buffer[:nl]
            self.buffer = self.buffer[nl+1:]
            return ret
        while True:
            data = self.f.read()
            self.buffer += data
            nl = self.buffer.find("\n")
            if nl >= 0:
                ret = self.buffer[:nl]
                self.buffer = self.buffer[nl+1:]
                return ret
            time.sleep(1)

CONSULT_RESULT_PREFIX = "info string consult "
BESTMOVE_PREFIX = "bestmove "
CONTEXT_INIT = {"consult_count": 0, "nnue_best_chosen_count": 0}

def score_dict_to_tuples(score_dict):
    # {"4a3b": 0.398, "8c8d": 0.433}
    # => [("8c8d", 0.433), ("4a3b", 0.398)] (スコア降順)
    score_tuples = list(score_dict.items())
    score_tuples.sort(key=lambda x: -x[1])  # スコア降順
    return score_tuples

def score_tuples_to_dataframe(score_tuples, board):
    return pd.DataFrame({
        "move": [move_to_kif(board.move_from_usi(t[0])) for t in score_tuples],
        "winrate": [f"{int(t[1] * 100)}%" for t in score_tuples],
    })

def parse_consult_result(line, phs, context):
    json_str = line[len(CONSULT_RESULT_PREFIX):]
    consult_obj = json.loads(json_str)

    board = Board()
    pos_str = consult_obj["sfen"]
    if consult_obj["moves"] not in (None, []):
        pos_str += " moves " + " ".join(consult_obj["moves"])
    board.set_position(pos_str)

    phs["result"].write(score_tuples_to_dataframe(consult_obj["score_tuples"], board))
    nnue_st = score_dict_to_tuples(consult_obj["engine_score_dicts"][0])
    phs["nnue"].write(score_tuples_to_dataframe(nnue_st, board))
    deep_st = score_dict_to_tuples(consult_obj["engine_score_dicts"][1])
    phs["deep"].write(score_tuples_to_dataframe(deep_st, board))

    # 最善手採択率更新
    context["consult_count"] += 1
    try:
        if consult_obj["score_tuples"][0][0] == nnue_st[0][0]:
            # NNUEの最善手と、合議結果の最上位（選ばれた手）が一致
            context["nnue_best_chosen_count"] += 1
    except:
        # 合議が行われなかった時(PVが出なかった場合)
        pass
    phs["nnue_best_ratio"].write(f'{int(context["nnue_best_chosen_count"] / context["consult_count"] * 100)}%')


def process(f):
    phs = {}
    st.write("合議結果")
    phs["result"] = st.empty()
    st.write("NNUEの出力")
    phs["nnue"] = st.empty()
    st.write("DLの出力")
    phs["deep"] = st.empty()
    st.write("NNUE最善手採択率")
    phs["nnue_best_ratio"] = st.empty()
    rl = ReadLine(f)
    context = CONTEXT_INIT.copy()
    while True:
        line = rl.readline()
        try:
            if line == "readyok":
                # 新しい対局
                context = CONTEXT_INIT.copy()
            if line.startswith(CONSULT_RESULT_PREFIX):
                parse_consult_result(line, phs, context)
            if line.startswith(BESTMOVE_PREFIX):
                pass
        except Exception as ex:
            st.write("Error processing " + line + repr(ex))

def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("log")
    args = parser.parse_args()
    with open(args.log, "r") as f:
        process(f)

main()
