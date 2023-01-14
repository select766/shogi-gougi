"""
USIエンジンとしてふるまい、ただ別のUSIエンジンを呼び出して指し手を中継する
ponderは考えない(思考中にメッセージが来ることに対応しない)
"""

import argparse
import json
import cshogi
from cshogi.usi.Engine import Engine

def usi_send(msg: str):
    print(msg, flush=True)

def usi_loop(commandline_args):
    engine = None
    config = {}
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
                with open(option_value) as f:
                    config = json.load(f)
        elif command == "isready":
            if engine is None:
                engine = Engine(config["engine"])
            engine.isready()
            usi_send("readyok")
        elif command == "usinewgame":
            engine.usinewgame()
        elif command == "position":
            # position startpos
            # position startpos moves 7g7f 3c3d ...
            engine.position(moves=args[2:], sfen="startpos")
        elif command == "go":
            if args[0] == "ponder":
                # ponder未対応
                continue
            go_args = {}
            args_queue = args.copy()
            while len(args_queue) > 0:
                top = args_queue.pop(0)
                if top in ["btime", "wtime", "byoyomi", "binc", "winc"]:
                    # 制限時間
                    go_args[top] = int(args_queue.pop(0))
            bestmove, ponder_move = engine.go(**go_args)
            usi_send(f"bestmove {bestmove}")
        elif command == "gameover":
            engine.gameover(result=args[0])
        else:
            usi_send(f"info string unknown command {command}")

def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--name", default="usiproxy")
    parser.add_argument("--author", default="shogiaiauthor")
    args = parser.parse_args()
    usi_loop(args)

if __name__ == "__main__":
    main()
