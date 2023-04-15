
from dataclasses import dataclass
import json
import math
from typing import List, Optional
from cshogi.usi.Engine import Engine

@dataclass
class ConsultationPV:
    move: str
    score: int
    multipv_rank: int # 1, 2, 3, ... (multipv無しの場合は1のみ)

@dataclass
class ConsultationInfo:
    move_count: int
    engine_pvs: List[List[ConsultationPV]] # List[ConsultationPV]ではmultipv_rankの昇順（bestmoveが先頭）

@dataclass
class ConsultationResult:
    bestmove: str
    winrate: float
    comment: Optional[dict]

def score_cp_to_winrate(score_cp: int, winrate_regression: dict) -> float:
    x = float(score_cp) * winrate_regression['weight'] + winrate_regression['bias']
    winrate = 1.0 / (1.0 + math.exp(-x))
    return winrate

def winrate_to_score_cp_standard(winrate: float) -> int:
    # 1/(1+exp(-x/600)) で勝率を求めたとして、逆変換
    try:
        score_cp = math.log(1.0 / winrate - 1.0) * -600.0
        return int(score_cp)
    except:
        return 0

def consult(config, info: ConsultationInfo) -> ConsultationResult:
    method = config["params"]["method"]
    if method == "max_union":
        score_dict = {}
        for engine_idx, pvs in enumerate(info.engine_pvs):
            for pv in pvs:
                score_cp = pv.score
                score_winrate = score_cp_to_winrate(score_cp, config['engines'][engine_idx]['winrate_regression'])
                score_dict[pv.move] = max(score_dict.get(pv.move, -1.0), score_winrate)
        score_tuples = list(score_dict.items())
        score_tuples.sort(key=lambda x: -x[1]) # スコア降順
        bestmove, winrate = score_tuples[0]
        return ConsultationResult(bestmove=bestmove, winrate=winrate, comment={"score_tuples": score_tuples})
    else:
        raise ValueError("Unknown consult method")

class Consultation:
    engines: List[Engine]

    def __init__(self, config, usi_send) -> None:
        self.usi_send = usi_send
        self.config = config
        self.engines = None

    def isready(self) -> None:
        if self.engines is None:
            self.engines = []
            for engine_config in self.config["engines"]:
                engine = Engine(cmd=engine_config["exe"])
                for setoption_line in engine_config.get("option", "").split("\n"):
                    elems = setoption_line.strip().split(" ", 5)
                    if len(elems) < 5:
                        continue
                    engine.setoption(name=elems[2], value=elems[4])
                engine.isready()
                self.engines.append(engine)

    def usinewgame(self) -> None:
        for engine in self.engines:
            engine.usinewgame()

    def go(self, moves, sfen) -> str:
        # 同時に動かすにはマルチスレッドがいる。今は逐次実行
        engine_outputs = []
        move_count = len(moves) + 1 # 現在何手目か
        no_consult = move_count > self.config["params"]["max_move_count"]
        for engine in self.engines:
            if no_consult:
                engine.setoption("MultiPV", "1")
            pvs = []
            engine.position(moves=moves, sfen=sfen)
            bestmove, pondermove = engine.go(ponder=False, btime=0, wtime=0, byoyomi=1000000, listener=lambda x: pvs.append(x))
            engine_outputs.append({"bestmove": bestmove, "pondermove": pondermove, "pvs": pvs})
            if no_consult:
                for pv in pvs:
                    if pv.startswith("info "):
                        self.usi_send(pv)
                return bestmove
        consult_info = self._extract_consultation_info(move_count, engine_outputs)
        self.usi_send(f"info string engine_outputs {json.dumps(engine_outputs)}")
        self.usi_send(f"info string engine0={engine_outputs[0]['bestmove']} engine1={engine_outputs[1]['bestmove']}")
        consult_result = consult(self.config, consult_info)
        self.usi_send(f"info string consult {json.dumps(consult_result.comment)}")
        self.usi_send(f"info depth 1 score cp {winrate_to_score_cp_standard(consult_result.winrate)} pv {consult_result.bestmove}")
        return consult_result.bestmove
    
    def _extract_consultation_info(self, move_count, engine_outputs) -> ConsultationInfo:
        engine_pvs = []
        for engine_output in engine_outputs:
            # pvsの例。最後のmultipvだけを取り出す。setoptionでmultipv=1のときは"multipv *"の要素はない。
            """
                "pvs": [ 
      "go btime 0 wtime 0 byoyomi 1000000", 
      "info depth 1 seldepth 1 score cp 361 multipv 1 nodes 435 nps 435000 time 1 pv 2g2f", 
      "info depth 1 seldepth 1 score cp 318 multipv 2 nodes 435 nps 435000 time 1 pv 4i5h", 
      "info depth 1 seldepth 1 score cp 315 multipv 3 nodes 435 nps 435000 time 1 pv 4g4f", 
      "info depth 2 seldepth 2 score cp 341 multipv 1 nodes 1281 nps 1281000 time 1 pv 3g3f 8c8d 2g2f", 
      "info depth 2 seldepth 2 score cp 332 multipv 2 nodes 1281 nps 1281000 time 1 pv 2g2f 8c8d", 
      "info depth 2 seldepth 2 score cp 296 multipv 3 nodes 1281 nps 1281000 time 1 pv 4i5h 8c8d 2g2f", 
      "info depth 3 seldepth 4 score cp 376 multipv 1 nodes 10011 nps 3337000 time 3 pv 8h7g 8c8d 2g2f", 
      "info depth 3 seldepth 4 score cp 296 multipv 2 nodes 10011 nps 3337000 time 3 pv 4g4f 8c8d 2g2f 4d4e", 
      "info depth 3 seldepth 4 score cp 287 multipv 3 nodes 10011 nps 3337000 time 3 pv 4i5h 4d4e 8h7g 3c7g+ 6h7g", 
      "bestmove 8h7g ponder 8c8d" 
    ] 
            """
            pvs = [] # type: List[ConsultationPV]
            for info_line in engine_output["pvs"][::-1]:
                elems = info_line.split(" ")
                if elems.pop(0) != "info":
                    continue

                pv_first_move = None
                multipv_rank = None
                score = None
                depth = None
                while len(elems) > 0:
                    key = elems.pop(0)
                    if key in ["seldepth", "time", "nodes", "currmove", "hashfull", "nps"]:
                        # 引数1個、読み飛ばす
                        elems.pop(0)
                    elif key == "depth":
                        depth = int(elems.pop(0))
                    elif key == "string":
                        # PVではない
                        break
                    elif key == "pv":
                        pv_first_move = elems.pop(0)
                        break
                    elif key == "multipv":
                        multipv_rank = int(elems.pop(0))
                    elif key == "score":
                        if elems.pop(0) == "cp":
                            # score cp 123
                            score = int(elems.pop(0))
                        else:
                            # score mate +3
                            mate_count = elems.pop(0)
                            if mate_count == "+":
                                score = 32000
                            elif mate_count == "-":
                                score = -32000
                            else:
                                score = int(mate_count)
                                if score > 0:
                                    score = 32000 - score
                                else:
                                    # 10手詰めのとき、mate_count=-10で、score=-31980にしたい
                                    score = -32000 - score
                if score is not None and pv_first_move is not None:
                    # multipv順位3,2,1の順に得られるが、pvsの中では1,2,3の順に並べたい
                    if (multipv_rank or 0) > 1 and depth < 5:
                        # 2番目以降の読み筋で、depthが極端に浅いものは除去(DLの場合、一切読んでいない指し手のPVも便宜上出てしまうため)
                        continue
                    pvs.insert(0, ConsultationPV(move=pv_first_move, score=score, multipv_rank=multipv_rank or 0))
                    if (multipv_rank is None) or (multipv_rank == 1):
                        # multipv無しの場合は読み筋1個だけ。multipvありの場合、1が来たら最新の読み筋は終わり。
                        break
            engine_pvs.append(pvs)
        
        cinfo = ConsultationInfo(engine_pvs=engine_pvs, move_count=move_count)
        return cinfo

    def gameover(self, result: Optional[str]) -> None:
        for engine in self.engines:
            engine.gameover(result)
