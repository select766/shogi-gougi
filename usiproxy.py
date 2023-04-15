"""
USIエンジンとしてふるまい、ただ別のUSIエンジンを呼び出して指し手を中継する
ponderは考えない(思考中にメッセージが来ることに対応しない)
"""

import argparse
import yaml
import cshogi
from consultation import Consultation

def usi_send(msg: str):
    print(msg, flush=True)

def usi_loop(commandline_args):
    consultation = None
    config = {}
    last_position = None
    while True:
        try:
            msg_recv = input()
        except EOFError:
            break
        params = msg_recv.split(" ")
        command = params[0]
        args = params[1:]
        if command == "quit":
            break
        elif command == "usi":
            usi_send(f"id name {commandline_args.name}")
            usi_send(f"id author {commandline_args.author}")
            usi_send("option name optionfile type filename default <empty>")
            usi_send("usiok")
        elif command == "setoption":
            # setoption name USI_Ponder value true
            option_name = args[1]
            option_value = " ".join(args[3:])
            if option_name == "optionfile":
                if consultation is None: # 2回目以降の対局では起動済みエンジンをそのまま使う
                    with open(option_value) as f:
                        config = yaml.safe_load(f)
                        consultation = Consultation(config, usi_send)
        elif command == "isready":
            consultation.isready()
            usi_send("readyok")
        elif command == "usinewgame":
            consultation.usinewgame()
        elif command == "position":
            # position startpos
            # position startpos moves 7g7f 3c3d ...
            last_position = {"moves": args[2:], "sfen": "startpos"}
        elif command == "go":
            if len(args) > 0 and args[0] == "ponder":
                # ponder未対応
                continue
            # 今は制限時間は考えてなくて、ノード数制限で探索を終える
            # go_args = {}
            # args_queue = args.copy()
            # while len(args_queue) > 0:
            #     top = args_queue.pop(0)
            #     if top in ["btime", "wtime", "byoyomi", "binc", "winc"]:
            #         # 制限時間
            #         go_args[top] = int(args_queue.pop(0))
            bestmove = consultation.go(moves=last_position["moves"], sfen=last_position["sfen"])
            usi_send(f"bestmove {bestmove}")
        elif command == "gameover":
            # cshogi.cliでの対局では勝敗が来ない
            consultation.gameover(result=args[0] if len(args) > 0 else None)
        else:
            usi_send(f"info string unknown command {command}")

def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--name", default="usiproxy")
    parser.add_argument("--author", default="shogiaiauthor")
    args = parser.parse_args()
    try:
        usi_loop(args)
    except Exception as ex:
        ex_str = repr(ex).replace('\n', '\\n')
        usi_send(f"info string Error {ex_str}")
        raise

if __name__ == "__main__":
    main()
