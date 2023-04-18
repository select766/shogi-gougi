from typing import List, Optional


def get_book_move(moves: Optional[List[str]],
    sfen: str) -> Optional[str]:
    if sfen != "startpos":
        return None
    if moves is None or moves == []:
        return "2g2f"
    if moves in (["2g2f"], ["7g7f"]):
        return "8c8d"
    return None
