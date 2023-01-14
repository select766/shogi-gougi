# shogi-gougi
将棋AIの合議実験

# 設定ファイル

将棋所からUSIエンジン登録用のバッチファイル例(Windows, Anaconda)

```
@echo off 
call C:\Users\xxx\Anaconda3\Scripts\activate.bat C:\Users\xxx\Anaconda3\envs\envname 
python usiproxy.py
```

エンジンオプションの `optionfile` で指定する設定ファイル

```
{
    "engine": "D:\\path\\to\\YaneuraOu_NNUE-tournament-clang++-avx2.exe"
}
```
