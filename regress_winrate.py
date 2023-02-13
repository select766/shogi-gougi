"""
評価値から勝率を回帰するシグモイドのパラメータを特定する
extract_score_from_cli_log.py の結果を入力とする
"""

import argparse
import pickle
import numpy as np
import torch
import torch.nn as nn
import torch.nn.functional as F
import torch.optim as optim

class Net(nn.Module):
    def __init__(self):
        super().__init__()
        self.fc = nn.Linear(1, 1)
        torch.nn.init.constant_(self.fc.weight, 1)
        torch.nn.init.constant_(self.fc.bias, 0)
        self.normalize = 1 / 1200

    def forward(self, x):
        x = x * self.normalize
        x = self.fc(x)
        x = torch.sigmoid(x)
        return x



def records_to_score_win_pair(records):
    scores = [[], []]
    wins = [[], []]
    winrates = [0.0, 0.0]
    games = [0, 0]
    for record in records:
        if record["winner"] is None:
            # 勝敗以外の結果（千日手など）の対局は除外
            continue
        for player in [1, 2]:
            win = 1 if record["winner"] == player else 0
            scores[player-1].extend(record[str(player)])
            wins[player-1].extend([win] * len(record[str(player)]))
            winrates[player-1] += win
            games[player-1] += 1
    for i in range(len(winrates)):
        winrates[i] /= games[i]
    return scores, wins, winrates

def do_regression(scores, wins, criterion, max_cp):
    scores = np.array(scores, dtype=np.float32)
    wins = np.array(wins, dtype=np.float32)
    mask = np.abs(scores) <= max_cp
    scores = scores[mask]
    wins = wins[mask]
    tensor_x = torch.Tensor(scores.reshape(-1, 1))
    tensor_y = torch.Tensor(wins.reshape(-1, 1))
    tensor_dataset = torch.utils.data.TensorDataset(tensor_x, tensor_y)
    dataloader = torch.utils.data.DataLoader(tensor_dataset, batch_size=1024)
    net = Net()
    optimizer = optim.SGD(net.parameters(), lr=0.1, momentum=0.9)

    for epoch in range(200):
        running_loss = 0.0
        batch_count = 0
        for i, data in enumerate(dataloader, 0):
            inputs, labels = data

            # zero the parameter gradients
            optimizer.zero_grad()

            # forward + backward + optimize
            outputs = net(inputs)
            loss = criterion(outputs, labels)
            loss.backward()
            optimizer.step()

            # print statistics
            running_loss += loss.item()
            batch_count += 1

        print(f'[{epoch + 1}] loss: {running_loss / batch_count:.3f}')
        print(net.fc.weight.item())

    print('Finished Training')
    weight = float(net.fc.weight.item() * net.normalize)
    bias = float(net.fc.bias.item())
    return {'weight': weight, 'bias': bias}

def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("src")
    parser.add_argument("dst")
    parser.add_argument("--loss", default="MSELoss", help="MSELoss or BCELoss")
    parser.add_argument("--max_cp", default=100000, type=int, help="Maximum abusolute score[cp]")
    args = parser.parse_args()

    criterion = {"MSELoss": nn.MSELoss, "BCELoss": nn.BCELoss}[args.loss]()

    with open(args.src, "rb") as f:
        records = pickle.load(f)
    
    scores, wins, winrates = records_to_score_win_pair(records)

    regressions = []
    for player_idx in range(2):
        regression_result = do_regression(scores[player_idx], wins[player_idx], criterion, args.max_cp)
        regressions.append(regression_result)
        print(f"player {player_idx+1}")
        print(f"winrate: {winrates[player_idx]}")
        print(f"regression: {regression_result['weight']} x + {regression_result['bias']}")

    with open(args.dst, "wb") as f:
        pickle.dump({'winrates': winrates, 'regression_coef': regressions}, f)

if __name__ == "__main__":
    main()
