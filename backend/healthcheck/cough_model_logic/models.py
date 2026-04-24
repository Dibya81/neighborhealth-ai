import torch
import torch.nn as nn
import torch.nn.functional as F
import math
from transformers import HubertModel, ASTModel

def vgg_make_layers(cfg, batch_norm=True, pool_type="max", dropout_after_pool=False, dropout_p=0.2):
    """
    Build the convolutional feature extractor with configurable pooling.
    Args:
        cfg: list, e.g. vgg_cfg["VGG16"].
        batch_norm: bool, whether to include BN.
        pool_type: str, one of {"max", "avg"}.
        dropout_after_pool: bool, whether to add dropout after each pooling layer.
        dropout_p: float, dropout probability.
    """
    layers = []
    in_channels = 1
    for v in cfg:
        if v == "M":
            if pool_type == "max":
                layers += [nn.MaxPool2d(kernel_size=2, stride=2)]
            elif pool_type == "avg":
                layers += [nn.AvgPool2d(kernel_size=2, stride=2)]
            else:
                raise ValueError(f"Invalid pool_type '{pool_type}', must be 'max' or 'avg'")
            if dropout_after_pool:
                layers += [nn.Dropout(dropout_p)]
        else:
            conv2d = nn.Conv2d(in_channels, v, kernel_size=3, padding=1)
            if batch_norm:
                layers += [conv2d, nn.BatchNorm2d(v), nn.ReLU(inplace=True)]
            else:
                layers += [conv2d, nn.ReLU(inplace=True)]
            in_channels = v
    return nn.Sequential(*layers)

class VGG(nn.Module):
    def __init__(
        self,
        vgg_name: str,
        hidden: int = 64,
        dropout: float = 0.4,
        pool_type: str = "max",
        end_pooling: str = "both",
        dropout_after_pool: bool = False,
        dropout_p: float = 0.3,
        weight_initialization: bool = True,
    ):
        """
        Args:
            vgg_name: one of ['VGG11', 'VGG13', 'VGG16', 'VGG19'].
            hidden: hidden layer dimension in classifier.
            dropout: dropout in classifier.
            pool_type: 'max' or 'avg' for pooling inside the CNN blocks.
            end_pooling: 'max', 'avg', or 'both' for global pooling at the end.
            dropout_after_pool: add dropout after each pooling layer.
            dropout_p: dropout prob after pooling.
        """
        super().__init__()
        assert end_pooling in {"max", "avg", "both"}, "end_pooling must be 'max', 'avg', or 'both'"
        self.end_pooling = end_pooling
        self.features = vgg_make_layers(
            vgg_cfg[vgg_name],
            batch_norm=True,
            pool_type=pool_type,
            dropout_after_pool=dropout_after_pool,
            dropout_p=dropout_p,
        )
        input_dim = 512 * 2 if end_pooling == "both" else 512
        self.classifier = nn.Sequential(
            nn.Dropout(dropout),
            nn.Linear(input_dim, hidden),
            nn.ReLU(),
            nn.Dropout(dropout),
            nn.Linear(hidden, hidden),
            nn.ReLU(),
            nn.Dropout(dropout),
            nn.Linear(hidden, 1),
        )
        if weight_initialization:
            self._initialize_weights()

    def forward(self, x):
        x.unsqueeze_(1)                             # (B, 1, n_feats, n_samples)
        x = self.features(x)                        # (B, 512, H, T)
        if self.end_pooling == "both":
            x1 = F.adaptive_max_pool2d(x, (1, 1))   # (B, 512, 1, 1)
            x2 = F.adaptive_avg_pool2d(x, (1, 1))   # (B, 512, 1, 1)
            x = torch.cat([x1, x2], dim=1)          # (B, 1024, 1, 1)
        elif self.end_pooling == "max":
            x = F.adaptive_max_pool2d(x, (1, 1))    # (B, 512, 1, 1)
        elif self.end_pooling == "avg":
            x = F.adaptive_avg_pool2d(x, (1, 1))    # (B, 512, 1, 1)
        x = x.view(x.size(0), -1)                   # (B, 1024 or 512)
        x = self.classifier(x)                      # (B, 1)
        return x.squeeze(-1)                        # (B)

    def _initialize_weights(self):
        for m in self.modules():
            if isinstance(m, nn.Conv2d):
                n = m.kernel_size[0] * m.kernel_size[1] * m.out_channels
                m.weight.data.normal_(0, math.sqrt(2. / n))
                if m.bias is not None:
                    m.bias.data.zero_()
            elif isinstance(m, nn.BatchNorm2d):
                m.weight.data.fill_(1)
                m.bias.data.zero_()
            elif isinstance(m, nn.Linear):
                m.weight.data.normal_(0, 0.01)
                m.bias.data.zero_()


vgg_cfg = {
    "VGG11": [64, "M", 128, "M", 256, 256, "M", 512, 512, "M", 512, 512, "M"],
    "VGG13": [64, 64, "M", 128, 128, "M", 256, 256, "M", 512, 512, "M", 512, 512, "M"],
    "VGG16": [64, 64, "M", 128, 128, "M", 256, 256, 256, "M", 512, 512, 512, "M", 512, 512, 512, "M"],
    "VGG19": [64, 64, "M", 128, 128, "M", 256, 256, 256, 256, "M", 512, 512, 512, 512, "M", 512, 512, 512, 512, "M"],
}

class HubertAudioClassifier(nn.Module):
    def __init__(
        self,
        adapter_hidden_size: int = 32,
        dropout: float = 0.2,
    ):
        super().__init__()
        self.hubert = HubertModel.from_pretrained("facebook/hubert-base-ls960")
        self.hidden_size = self.hubert.config.hidden_size
        self.adapter = nn.Sequential(                        # Adapter layer for fine-tuning
            nn.Linear(self.hidden_size, adapter_hidden_size),
            nn.GELU(approximate='tanh'),           
            nn.Dropout(dropout),
            nn.Linear(adapter_hidden_size, adapter_hidden_size),
            nn.GELU(approximate='tanh'),           
            nn.Dropout(dropout),        
            nn.Linear(adapter_hidden_size, self.hidden_size),
        )  
        self.layer_norm = nn.LayerNorm(self.hidden_size)
        self.classifier = nn.Sequential(
            nn.Linear(2*self.hidden_size, adapter_hidden_size),
            nn.GELU(approximate='tanh'),           
            nn.Dropout(dropout),            
            nn.Linear(adapter_hidden_size, 1),
        )
        
    def freeze_feature_encoder(self):
        self.hubert.feature_extractor._freeze_parameters()
    
    def forward(self, x):
        x = self.hubert(x).last_hidden_state  # (B, T, hidden_size)
        x = x + self.adapter(x)               # (B, T, hidden_szie) Residual connection
        x = self.layer_norm(x)                # (B, T, hidden_size) Layer norm
        x1, _ = x.max(dim=1)                  # (B, hidden_size)
        x2 = x.mean(dim=1)                    # (B, hidden_size)
        x = torch.cat((x1, x2), dim=1)        # (B, 2*hidden_size)
        out = self.classifier(x)              # (B, 1)
        return out.squeeze(-1)                # (B)
    
class ASTAudioClassifier(nn.Module):
    def __init__(
        self,
        adapter_hidden_size: int = 32,
        dropout: float = 0.2,
    ):
        super().__init__()
        self.ast = ASTModel.from_pretrained("MIT/ast-finetuned-audioset-10-10-0.4593")
        self.hidden_size = self.ast.config.hidden_size
        self.adapter = nn.Sequential(                        # Adapter layer for fine-tuning
            nn.Linear(self.hidden_size, adapter_hidden_size),
            nn.GELU(approximate='tanh'),           
            nn.Dropout(dropout),
            nn.Linear(adapter_hidden_size, adapter_hidden_size),
            nn.GELU(approximate='tanh'),           
            nn.Dropout(dropout),        
            nn.Linear(adapter_hidden_size, self.hidden_size),
        )  
        self.layer_norm = nn.LayerNorm(self.hidden_size)
        self.classifier = nn.Sequential(
            nn.Linear(self.hidden_size, adapter_hidden_size),
            nn.GELU(approximate='tanh'),           
            nn.Dropout(dropout),            
            nn.Linear(adapter_hidden_size, 1),
        )
    
    def forward(self, x):
        x = self.ast(x).pooler_output         # (B, hidden_size)
        x = x + self.adapter(x)               # (B, hidden_size) Residual connection
        x = self.layer_norm(x)                # (B, hidden_size) Layer norm
        out = self.classifier(x)              # (B, 1)
        return out.squeeze(-1)                # (B)
    
class HubertAudioClassifierWithAudioType(nn.Module):
    def __init__(
        self,
        adapter_hidden_size: int = 32,
        dropout: float = 0.2,
        audio_type_hidden_size: int = 16,
        num_audio_types: int = 2,         
    ):
        super().__init__()
        self.hubert = HubertModel.from_pretrained("facebook/hubert-base-ls960")
        self.hidden_size = self.hubert.config.hidden_size
        self.audio_type_fc = nn.Sequential(
            nn.Embedding(num_audio_types, audio_type_hidden_size),  # Embedding for each audio type
            nn.Linear(audio_type_hidden_size, audio_type_hidden_size),
            nn.GELU(approximate='tanh'),
        )
        self.adapter = nn.Sequential(                        # Adapter layer for fine-tuning
            nn.Linear(self.hidden_size + audio_type_hidden_size, adapter_hidden_size),
            nn.GELU(approximate='tanh'),
            nn.Dropout(dropout),
            nn.Linear(adapter_hidden_size, adapter_hidden_size),
            nn.GELU(approximate='tanh'),
            nn.Dropout(dropout),
            nn.Linear(adapter_hidden_size, self.hidden_size + audio_type_hidden_size),
        )  
        self.layer_norm = nn.LayerNorm(self.hidden_size + audio_type_hidden_size)
        self.classifier = nn.Sequential(
            nn.Linear(2 * (self.hidden_size + audio_type_hidden_size), adapter_hidden_size),
            nn.GELU(approximate='tanh'),
            nn.Dropout(dropout),
            nn.Linear(adapter_hidden_size, 1),
        )

    def freeze_feature_encoder(self):
        self.hubert.feature_extractor._freeze_parameters()

    def forward(self, x, audio_type):
        x = self.hubert(x).last_hidden_state  # (B, T, hidden_size)
        aud = self.audio_type_fc(audio_type)  # (B, audio_type_hidden_size)
        aud = aud.unsqueeze(1)                # (B, 1, audio_type_hidden_size)
        aud = aud.expand(-1, x.size(1), -1)   # (B, T, audio_type_hidden_size)
        x = torch.cat((x, aud), dim=2)        # (B, T, 2*hidden_size + audio_type_hidden_size)
        x = x + self.adapter(x)               # (B, T, hidden_size + audio_type_hidden_size) Residual connection
        x = self.layer_norm(x)                # (B, T, hidden_size + + audio_type_hidden_size)
        x1, _ = x.max(dim=1)                  # (B, hidden_size + audio_type_hidden_size)
        x2 = x.mean(dim=1)                    # (B, hidden_size + audio_type_hidden_size)
        x = torch.cat((x1, x2), dim=1)        # (B, 2*(hidden_size + audio_type_hidden_size))
        out = self.classifier(x)              # (B, 1)
        return out.squeeze(-1)                # (B)