import math
from abc import ABC

import torch
import torch.nn as nn
import torch.nn.functional as F


class AttentionLayer(nn.Module, ABC):

    def __init__(self, h: int = 8, d_model: int = 512, drop_rate: float = 0.1):
        super(AttentionLayer, self).__init__()

        self.multi_attn = MultiHeadAttention(h, d_model, drop_rate)
        self.norm = nn.LayerNorm(d_model)
        self.dropout = nn.Dropout(p=drop_rate)


class SelfAttention(AttentionLayer):

    def forward(self, x, target_mask):
        out = self.multi_attn(x, x, x, target_mask)
        out = self.dropout(out)
        out = self.norm(x + out)
        return out


class SourceTargetAttention(AttentionLayer):

    def forward(self, mem, x, source_mask):
        out = self.multi_attn(x, mem, mem, source_mask)
        out = self.dropout(out)
        out = self.norm(x + out)
        return out


class MultiHeadAttention(nn.Module):

    def __init__(self, h: int = 8, d_model: int = 512, drop_rate: float = 0.1):
        super(MultiHeadAttention, self).__init__()
        # Warning d_model mod h is not zero
        # because cause that cannot make Multi-Head.
        # d_model mod h が0出なければエラー
        assert d_model % h == 0
        self.d_k = d_model // h
        self.h = h

        # Weight of doing linear transformation
        # 線形変換のための重み
        self.w_q = nn.Linear(d_model, d_model)
        self.w_k = nn.Linear(d_model, d_model)
        self.w_v = nn.Linear(d_model, d_model)

        self.linear = nn.Linear(d_model, d_model)

        # Just to be sure, hold the attention score.
        # 念のため注意のスコアを保存
        self.attn = None
        self.dropout = nn.Dropout(drop_rate)

    def forward(self,
                query: torch.FloatTensor, key: torch.FloatTensor,
                value: torch.FloatTensor, mask: torch.Tensor = None
                ) -> torch.FloatTensor:
        if mask is not None:
            mask = mask.unsqueeze(1)
        n_batches = query.size(0)

        # Simple Linear Transformation
        # 線形変換
        # B x h x d_model x d_k
        query = self.w_q(query).contiguous().view(n_batches, -1, self.h, self.d_k).transpose(1, 2)
        key = self.w_k(key).contiguous().view(n_batches, -1, self.h, self.d_k).transpose(1, 2)
        value = self.w_v(value).contiguous().view(n_batches, -1, self.h, self.d_k).transpose(1, 2)

        x, self.attn = self.attention(query, key, value, mask, self.dropout)
        x = x.transpose(1, 2).contiguous().view(n_batches, -1, self.h * self.d_k)
        return self.linear(x)

    def attention(self, query: torch.FloatTensor, key: torch.FloatTensor,
                  value: torch.FloatTensor, mask: torch.Tensor = None,
                  dropout: nn.Dropout = None) -> (torch.FloatTensor, torch.FloatTensor):
        d_k = query.size(-1)
        # (QK^T)/sqrt(d_k)
        scores = torch.matmul(query, key.transpose(-2, -1)) / math.sqrt(d_k)
        if mask is not None:
            scores = scores.masked_fill(mask == 0, -1e9)
        # softmax((QK^T)/sqrt(d_k))
        attn = F.softmax(scores, dim=-1)
        if dropout is not None:
            attn = dropout(attn)
        # calculate softmax((QK^T)/sqrt(d_k))V and return result and attention score
        return torch.matmul(attn, value), attn