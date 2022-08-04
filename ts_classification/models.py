import json
import numpy as np
import os
import pandas as pd
import torch
import torch.nn as nn


class MyCNN(nn.Module):
    def __init__(self, num_classes):
        """
        CNN architecture can be found in the presentation.
        """
        super().__init__()
        self.num_classes = num_classes  #number of classes
        
        super().__init__()
        self.net = nn.Sequential(
            nn.Conv2d(in_channels=15, out_channels=30, kernel_size=2, stride=2, padding=1),  # (b x 30 x 6 x 6)
            nn.ReLU(),
            nn.Conv2d(30, 64, 2, padding=0, stride=1),  # (b x 64 x 5 x 5)
            nn.ReLU(),
            nn.MaxPool2d(kernel_size=2, stride=1, padding=0),  # (b x 64 x 4 x 4)
        )
        # classifier is just a name for linear layers
        self.classifier = nn.Sequential(
            nn.Dropout(p=0.1, inplace=True),
            nn.Linear(in_features=(64 * 4 * 4), out_features=256),
            nn.ReLU(),
            nn.Linear(in_features=256, out_features=num_classes),
            nn.Sigmoid()
        )
        #self.init_bias()

    def init_bias(self):
        for layer in self.net:
            if isinstance(layer, nn.Conv2d):
                nn.init.normal_(layer.weight, mean=0, std=0.01)
                nn.init.constant_(layer.bias, 0)
        nn.init.constant_(self.net[0].bias, 1)
        nn.init.constant_(self.net[2].bias, 1)

    def forward(self, x):
        """
        Pass the input through the net.
        
        :param x: Input tensor.
        :return: Uutput tensor.
        """
        x = self.net(x)
        x = x.view(-1, 64 * 4 * 4)  # reduce the dimensions for linear layer input
        return self.classifier(x)
    
    
class MyLSTM(nn.Module):
    def __init__(self, num_classes, input_size, hidden_size, num_layers,
                 seq_length):
        super(LSTM1, self).__init__()
        self.num_classes = num_classes
        self.num_layers = num_layers
        self.input_size = input_size
        self.hidden_size = hidden_size
        self.seq_length = seq_length

        self.lstm = nn.LSTM(input_size=input_size,
                            hidden_size=hidden_size,
                            num_layers=num_layers,
                            batch_first=True)
        
        self.classifier = nn.Sequential(
            nn.Dropout(p=0.3, inplace=True),
            nn.Linear(in_features=(hidden_size), out_features=64),
            nn.ReLU(),
            nn.Linear(in_features=64, out_features=num_classes),
            nn.Sigmoid()
        )
        
    def forward(self, x):
        h_0 = Variable(
            torch.zeros(self.num_layers, x.size(0), self.hidden_size))
        c_0 = Variable(
            torch.zeros(self.num_layers, x.size(0), self.hidden_size))
        output, (hn, cn) = self.lstm(x, (h_0, c_0))
        hn = hn.view(-1, self.hidden_size)
        out = self.classifier(hn)
        return out